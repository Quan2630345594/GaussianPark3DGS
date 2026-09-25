import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from parking_gs.scene import Scene, demo_scene
from parking_gs.mapping import Grid, build_grid
from parking_gs.planner import Vehicle, advance, collision, plan, wrap
from parking_gs.control import simulate
from parking_gs.dataset import import_colmap, Dataset
from parking_gs.astar import plan as astar_plan
from parking_gs.feedforward import _load_npz


class CoreTests(unittest.TestCase):
    def empty(self): return Grid(np.zeros((100,100)),np.ones((100,100),bool),[-10,-10,10,10],.2)

    def test_roundtrip(self):
        s=demo_scene()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scene.npz'; s.save(p); loaded=Scene.load(p)
            np.testing.assert_allclose(s.covariance(),loaded.covariance())
            self.assertEqual(loaded.metadata['units'],'meters')

    def test_unknown_and_boundary_rejected(self):
        g=self.empty(); v=Vehicle()
        self.assertFalse(collision((0,0,0),g,v))
        self.assertTrue(collision((8,0,0),g,v))
        g.known[:]=False
        self.assertTrue(collision((0,0,0),g,v))
        with self.assertRaises(ValueError): plan((0,0,0),(2,0,0),g)

    def test_thin_obstacle_inside_footprint(self):
        g=self.empty(); g.risk[50,58]=1
        self.assertTrue(collision((0,0,0),g,Vehicle()))

    def test_reverse_bicycle(self):
        v=Vehicle(); p=(1.,2.,.3)
        q=advance(advance(p,1.5,.4,v),-1.5,.4,v)
        np.testing.assert_allclose(q,p,atol=1e-10)

    def test_covariance_rotation_and_ground(self):
        s=Scene(np.array([[0,0,1.]]),np.array([[1.,.05,.05]]),
                np.array([[math.cos(math.pi/4),0,0,math.sin(math.pi/4)]]),np.ones((1,3)),np.ones(1),
                dict(units='meters',up_axis='z',bounds=[-4,-4,4,4],known_free_polygon=[[-4,-4],[4,-4],[4,4],[-4,4]])).validate()
        g=build_grid(s,.2,0)
        self.assertGreater(g.risk[26,20],g.risk[20,26])
        s.means[0,2]=-1
        self.assertEqual(build_grid(s).risk.max(),0)

    def test_reverse_plan_and_closed_loop(self):
        g=self.empty(); r=plan((1,0,0),(-3,0,0),g,timeout=5)
        self.assertTrue(any(p['direction']==-1 for p in r['path']))
        sim=simulate(r,g)
        self.assertEqual(sim['status'],'parked')
        self.assertLess(sim['metrics']['position_error_m'],.2)
        for p in sim['trace']: self.assertFalse(collision((p['x'],p['y'],p['yaw']),g,Vehicle()))

    def test_traditional_astar_on_occupancy_grid(self):
        g=self.empty(); g.risk[45:55,45:55]=1
        r=astar_plan((-8,-8,0),(6,6,0),g,timeout=5)
        self.assertEqual(r['planner'],'astar')
        self.assertGreater(r['expanded'],0)
        self.assertGreater(len(r['path']),2)
        self.assertTrue(all(p['direction']==1 for p in r['path']))
        r2=astar_plan((-8,0,0),(6,0,0),self.empty(),timeout=5,simplify=False)
        self.assertEqual(simulate(r2,self.empty())['status'],'parked')

    def test_feedforward_npz_contract(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'prediction.npz'; n=20
            np.savez(p,points=np.zeros((n,3)),scales=np.ones((n,3))*.1,
                     rotation=np.tile([1,0,0,0],(n,1)),rgbs=np.ones((n,3))*.4,opacity=np.ones(n))
            s=_load_npz(p,dict(units='meters',up_axis='z',bounds=[-2,-2,2,2],known_free_polygon=[]))
            self.assertEqual(len(s.means),n); self.assertEqual(s.metadata['units'],'meters')

    def test_demo_pipeline(self):
        s=demo_scene(); g=build_grid(s); r=plan(s.metadata['start'],s.metadata['goal'],g,timeout=40)
        self.assertLess(r['position_error'],.35)
        for p in r['path']: self.assertFalse(collision((p['x'],p['y'],p['yaw']),g,Vehicle()))
        sim=simulate(r,g); self.assertEqual(sim['status'],'parked')
        self.assertGreaterEqual(sim['metrics']['gear_switches'],1)
        for p in sim['trace']: self.assertFalse(collision((p['x'],p['y'],p['yaw']),g,Vehicle()))

    def test_colmap_metric_transform(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); model=root/'model'; model.mkdir(); images=root/'images'; images.mkdir()
            (model/'cameras.txt').write_text('1 PINHOLE 8 6 4 4 4 3\n')
            records=[]
            for i in range(3):
                Image.new('RGB',(8,6),(100,120,130)).save(images/f'{i}.png')
                records.append(f'{i+1} 1 0 0 0 {i} 0 0 1 {i}.png\n\n')
            (model/'images.txt').write_text(''.join(records))
            (model/'points3D.txt').write_text('\n'.join(f'{i} {i} 0 2 100 120 130 0' for i in range(10)))
            cfg=dict(colmap_to_metric_scale=2,world_rotation=np.eye(3).tolist(),world_translation=[1,2,3],bounds=[-5,-5,5,5])
            c=root/'config.json'; c.write_text(json.dumps(cfg))
            import_colmap(model,images,root/'processed',c)
            ds=Dataset(root/'processed')
            np.testing.assert_allclose(ds.points[0],[1,2,7])
            _,k,vm,_=ds.read(1)
            np.testing.assert_allclose(np.linalg.inv(vm)[:3,3],[-1,2,3])
            self.assertEqual(k[0,0],4)


if __name__=='__main__': unittest.main()
