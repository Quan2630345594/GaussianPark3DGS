"""Local HTTP API + static frontend. No Node.js, CDN or web framework required."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs
import uuid
import numpy as np
from .scene import Scene, demo_scene
from .mapping import build_grid
from .planner import plan as hybrid_plan
from .astar import plan as astar_plan
from .control import simulate
from .feedforward import reconstruct_video

ROOT=Path(__file__).resolve().parents[1]


class Service:
    def __init__(self, root=ROOT):
        self.root=Path(root); self.jobs={}; self.lock=threading.Lock()
        self.pool=ThreadPoolExecutor(max_workers=1); self.capacity=threading.BoundedSemaphore(4)

    def scenes(self):
        return [dict(id='demo',name='合成停车场 · 无需数据',source='procedural')]+[
            dict(id=p.parent.name,name=p.parent.name,source='file')
            for p in sorted((self.root/'outputs').glob('*/scene.npz')) if p.parent.name!='demo']

    def scene(self, scene_id):
        if scene_id=='demo': return demo_scene()
        allowed={s['id'] for s in self.scenes()}
        if scene_id not in allowed: raise ValueError('Unknown scene id')
        return Scene.load(self.root/'outputs'/scene_id/'scene.npz')

    def submit(self, body):
        scene_id=body.get('scene','demo'); scene=self.scene(scene_id)
        def pose(key):
            a=np.asarray(body.get(key,scene.metadata[key]),dtype=float)
            if a.shape!=(3,) or not np.isfinite(a).all(): raise ValueError(f'{key} must contain 3 finite values')
            return a.tolist()
        start,goal=pose('start'),pose('goal'); uncertainty=float(body.get('uncertainty',.12))
        if not np.isfinite(uncertainty) or not 0<=uncertainty<=.6: raise ValueError('uncertainty must be 0..0.6 m')
        if not self.capacity.acquire(blocking=False): raise OverflowError('Queue full; wait for current jobs')
        jid=uuid.uuid4().hex
        with self.lock:
            # Retain only recent completed responses in RAM; saved files remain.
            done=[k for k,v in self.jobs.items() if v['status'] in ('done','failed')]
            for k in done[:-15]: self.jobs.pop(k)
            self.jobs[jid]=dict(id=jid,status='queued')
        def run():
            try:
                self.update(jid,status='running')
                grid=build_grid(scene,uncertainty=uncertainty)
                planner_name=str(body.get('planner', 'hybrid')).lower()
                if planner_name == 'astar':
                    result=astar_plan(start,goal,grid,allow_unknown=bool(body.get('allow_unknown', False)))
                elif planner_name == 'hybrid':
                    result=hybrid_plan(start,goal,grid)
                else:
                    raise ValueError('planner must be hybrid or astar')
                sim=simulate(result,grid)
                payload=dict(plan=result,simulation=sim,grid=grid.public(),scene=scene_id,uncertainty=uncertainty)
                folder=self.root/'outputs'/'runs'; folder.mkdir(parents=True,exist_ok=True)
                (folder/f'{jid}.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
                self.update(jid,status='done',result=payload)
            except Exception as exc: self.update(jid,status='failed',error=str(exc))
            finally: self.capacity.release()
        self.pool.submit(run)
        return dict(id=jid,status='queued')

    def submit_reconstruction(self, video_bytes, filename, fields):
        """Queue a video reconstruction without exposing a shell endpoint."""
        if not video_bytes or len(video_bytes) > 1024 * 1024 * 1024:
            raise ValueError('Video must be between 1 byte and 1 GiB')
        suffix = Path(filename or 'video.mp4').suffix.lower()
        if suffix not in {'.mp4', '.mov', '.avi', '.mkv', '.webm'}:
            raise ValueError('Supported video extensions: mp4, mov, avi, mkv, webm')
        backend = str(fields.get('backend', 'dggt')).lower()
        if backend not in {'dggt', 'splatt3r', 'external'}:
            raise ValueError('backend must be dggt, splatt3r or external')
        try:
            config = json.loads(fields.get('config', '{}') or '{}')
        except json.JSONDecodeError as exc:
            raise ValueError(f'config must be JSON: {exc.msg}') from exc
        if not isinstance(config, dict):
            raise ValueError('config must be a JSON object')
        if not self.capacity.acquire(blocking=False):
            raise OverflowError('Queue full; wait for current jobs')
        jid = uuid.uuid4().hex
        output = self.root / 'outputs' / jid
        output.mkdir(parents=True, exist_ok=True)
        video_path = output / f'input{suffix}'
        video_path.write_bytes(video_bytes)
        with self.lock:
            self.jobs[jid] = dict(id=jid, status='queued', kind='reconstruction', backend=backend)

        def run():
            try:
                self.update(jid, status='running')
                scene, report = reconstruct_video(
                    video_path, output, backend=backend,
                    repo=fields.get('repo') or None, checkpoint=fields.get('checkpoint') or None,
                    command=fields.get('command') or None, config=config,
                    stride=int(fields.get('stride', 3)), max_frames=int(fields.get('max_frames', 96)),
                    max_width=int(fields.get('max_width', 960)),
                    sequence_length=int(fields.get('sequence_length', 8)))
                self.update(jid, status='done', result=dict(scene=jid, report=report,
                                                             count=len(scene.means)))
            except Exception as exc:
                self.update(jid, status='failed', error=str(exc))
            finally:
                self.capacity.release()
        self.pool.submit(run)
        return dict(id=jid, status='queued', kind='reconstruction')

    def update(self,jid,**values):
        with self.lock: self.jobs[jid]={**self.jobs[jid],**values}

    def job(self,jid):
        with self.lock:
            if jid not in self.jobs: raise ValueError('Job not found or expired')
            return dict(self.jobs[jid])


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def send(self,data,status=200,kind='application/json; charset=utf-8'):
            raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if not isinstance(data,bytes) else data
            self.send_response(status); self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
            try: self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError): pass

        def do_GET(self):
            u=urlparse(self.path); q=parse_qs(u.query)
            try:
                if u.path=='/api/health': self.send(dict(status='ok',version='0.1.0')); return
                if u.path=='/api/scenes': self.send(service.scenes()); return
                if u.path=='/api/scene':
                    s=service.scene(q.get('id',['demo'])[0]); self.send(s.public()); return
                if u.path=='/api/grid':
                    s=service.scene(q.get('id',['demo'])[0]); self.send(build_grid(s).public()); return
                if u.path.startswith('/api/jobs/'):
                    self.send(service.job(u.path.rsplit('/',1)[-1])); return
                allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
                if u.path not in allowed: self.send(dict(error='Not found'),404); return
                p=service.root/'frontend'/allowed[u.path]
                kind={'html':'text/html','js':'text/javascript','css':'text/css'}[p.suffix[1:]]
                self.send(p.read_bytes(),kind=kind+'; charset=utf-8')
            except (ValueError,FileNotFoundError) as exc: self.send(dict(error=str(exc)),404)
            except Exception as exc: self.send(dict(error=str(exc)),500)

        def do_POST(self):
            if self.path not in {'/api/jobs', '/api/reconstruct'}:
                self.send(dict(error='Not found'),404); return
            # Same-origin UI only; no permissive CORS or remote command endpoints.
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                self.send(dict(error='Origin rejected'),403); return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if self.path == '/api/jobs':
                    if size<=0 or size>8192: raise ValueError('JSON body size must be 1..8192 bytes')
                    body=json.loads(self.rfile.read(size))
                    if not isinstance(body,dict): raise ValueError('JSON object required')
                    self.send(service.submit(body),202)
                    return
                if size<=0 or size>1024 * 1024 * 1024:
                    raise ValueError('Multipart video body must be 1 byte..1 GiB')
                content_type=self.headers.get('Content-Type','')
                if 'multipart/form-data' not in content_type or 'boundary=' not in content_type:
                    raise ValueError('Use multipart/form-data with a video field')
                boundary=content_type.split('boundary=',1)[1].strip().strip('"')
                fields, video, filename = {}, None, None
                for part in self.rfile.read(size).split(('--'+boundary).encode()):
                    if b'\r\n\r\n' not in part: continue
                    head, payload=part.split(b'\r\n\r\n',1)
                    if payload.endswith(b'\r\n'):
                        payload=payload[:-2]
                    disposition=next((x for x in head.decode('latin1').split('\r\n') if x.lower().startswith('content-disposition:')), '')
                    import re
                    name=re.search(r'name="([^"]+)"', disposition)
                    file_match=re.search(r'filename="([^"]*)"', disposition)
                    if not name: continue
                    if file_match:
                        filename=file_match.group(1); video=payload
                    else:
                        fields[name.group(1)]=payload.decode('utf-8', errors='strict')
                if video is None: raise ValueError('Missing multipart video field')
                self.send(service.submit_reconstruction(video,filename,fields),202)
            except OverflowError as exc: self.send(dict(error=str(exc)),429)
            except (ValueError,TypeError,KeyError) as exc: self.send(dict(error=str(exc)),400)
            except Exception as exc: self.send(dict(error=str(exc)),500)
    return Handler


def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8080)
    args=p.parse_args(); service=Service(); server=ThreadingHTTPServer((args.host,args.port),handler_for(service))
    print(f'Gaussian Park: http://{args.host}:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); service.pool.shutdown(wait=True)


if __name__=='__main__': main()
