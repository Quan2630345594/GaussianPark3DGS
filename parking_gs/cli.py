"""CLI commands; every relative path is relative to the current project directory."""
import argparse
import json
from pathlib import Path
from .scene import Scene, demo_scene
from .mapping import build_grid
from .planner import plan
from .control import simulate


def main():
    p=argparse.ArgumentParser(description='3DGS parking pipeline')
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('demo'); d.add_argument('--output',default='outputs/demo')
    c=sub.add_parser('prepare'); c.add_argument('--model',required=True); c.add_argument('--images',required=True)
    c.add_argument('--config',default='configs/site.json'); c.add_argument('--output',default='data/processed/site')
    t=sub.add_parser('train'); t.add_argument('--data',default='data/processed/site'); t.add_argument('--output',default='outputs/site')
    t.add_argument('--steps',type=int,default=3000); t.add_argument('--max-points',type=int,default=40000); t.add_argument('--max-width',type=int,default=960)
    v=sub.add_parser('reconstruct-video', help='Decode a video and run a feed-forward 3DGS backend')
    v.add_argument('--video',required=True); v.add_argument('--backend',choices=['dggt','splatt3r','external'],default='dggt')
    v.add_argument('--repo'); v.add_argument('--checkpoint'); v.add_argument('--command')
    v.add_argument('--output',default='outputs/video_reconstruction'); v.add_argument('--config',default='configs/site.json')
    v.add_argument('--stride',type=int,default=3); v.add_argument('--max-frames',type=int,default=96); v.add_argument('--max-width',type=int,default=960); v.add_argument('--sequence-length',type=int,default=8)
    e=sub.add_parser('evaluate'); e.add_argument('--scene',default='outputs/demo/scene.npz'); e.add_argument('--output',default='outputs/evaluation.json')
    e.add_argument('--ablation',action='store_true')
    a=p.parse_args()
    if a.command=='demo':
        out=Path(a.output); demo_scene().save(out/'scene.npz'); print(f'Wrote {out / "scene.npz"} (procedural, not trained)')
    elif a.command=='prepare':
        from .dataset import import_colmap
        import_colmap(a.model,a.images,a.output,a.config)
    elif a.command=='train':
        from .training import train
        train(a.data,a.output,a.steps,a.max_points,a.max_width)
    elif a.command=='reconstruct-video':
        from .feedforward import reconstruct_video
        cfg=json.loads(Path(a.config).read_text(encoding='utf-8')) if a.config else {}
        _, report=reconstruct_video(a.video,a.output,a.backend,a.repo,a.checkpoint,a.command,cfg,a.stride,a.max_frames,a.max_width,a.sequence_length)
        print(json.dumps(report,ensure_ascii=False,indent=2))
    else:
        scene=Scene.load(a.scene); reports=[]
        for mode in (['covariance','centers'] if a.ablation else ['covariance']):
            grid=build_grid(scene,use_covariance=mode=='covariance')
            try:
                result=plan(scene.metadata['start'],scene.metadata['goal'],grid)
                sim=simulate(result,grid)
                # Always evaluate executed trajectory on the full covariance map.
                from .planner import collision, Vehicle
                reference=build_grid(scene)
                reference_collision=any(collision((p['x'],p['y'],p['yaw']),reference,Vehicle()) for p in sim['trace'])
                reports.append(dict(mode=mode,status=sim['status'],metrics=sim['metrics'],
                                    reference_collision=reference_collision,plan=result,simulation=sim))
            except (ValueError,RuntimeError) as exc: reports.append(dict(mode=mode,status='failed',error=str(exc)))
        out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(reports,indent=2),encoding='utf-8'); print(json.dumps([{k:v for k,v in r.items() if k not in ['plan','simulation']} for r in reports],indent=2))


if __name__=='__main__': main()
