import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from parking_gs.server import Service,handler_for


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.service=Service(Path(cls.tmp.name))
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(cls.service))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.service.pool.shutdown(); cls.tmp.cleanup()

    def test_scene_api(self):
        with urlopen(self.base+'/api/scene?id=demo') as r:
            data=json.load(r); self.assertGreater(data['count'],1000); self.assertEqual(data['metadata']['units'],'meters')

    def test_unknown_scene_and_path(self):
        for path in ['/api/scene?id=../../secret','/../requirements.txt']:
            with self.assertRaises(HTTPError) as cm: urlopen(self.base+path)
            self.assertEqual(cm.exception.code,404)

    def test_invalid_pose(self):
        req=Request(self.base+'/api/jobs',data=json.dumps(dict(start=[float('nan'),0,0])).encode(),headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as cm: urlopen(req)
        self.assertEqual(cm.exception.code,400)

    def test_cross_origin_rejected(self):
        req=Request(self.base+'/api/jobs',data=b'{}',headers={'Origin':'http://untrusted.example'})
        with self.assertRaises(HTTPError) as cm: urlopen(req)
        self.assertEqual(cm.exception.code,403)

    def test_job_lifecycle(self):
        req=Request(self.base+'/api/jobs',data=json.dumps(dict(scene='demo',start=[-8,1,0],goal=[-6,1,0])).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:
            self.assertEqual(r.status,202); jid=json.load(r)['id']
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with urlopen(self.base+'/api/jobs/'+jid) as r: job=json.load(r)
            if job['status'] in ('done','failed'): break
            time.sleep(.05)
        self.assertEqual(job['status'],'done',job)
        self.assertEqual(job['result']['simulation']['status'],'parked')
        self.assertTrue((Path(self.tmp.name)/'outputs'/'runs'/f'{jid}.json').is_file())


if __name__=='__main__': unittest.main()
