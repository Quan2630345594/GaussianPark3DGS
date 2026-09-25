"""Portable metric Gaussian scene format; no pickle or executable checkpoints."""
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np


def rotation(q):
    q = np.asarray(q, dtype=float)
    q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-12)
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                     2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                     2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], -1).reshape(q.shape[:-1]+(3,3))


@dataclass
class Scene:
    means: np.ndarray
    scales: np.ndarray
    quats: np.ndarray
    colors: np.ndarray
    opacities: np.ndarray
    metadata: dict

    def validate(self):
        n = len(self.means)
        for key, shape in [('means',(n,3)),('scales',(n,3)),('quats',(n,4)),
                           ('colors',(n,3)),('opacities',(n,))]:
            a = np.asarray(getattr(self, key), dtype=np.float64)
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError(f'Invalid {key}: expected finite {shape}')
            setattr(self, key, a)
        if n == 0 or np.any(self.scales <= 0):
            raise ValueError('Scene must contain Gaussians with positive scales')
        if np.any(np.linalg.norm(self.quats, axis=1) < 1e-8):
            raise ValueError('Zero quaternion')
        if np.any((self.colors < 0) | (self.colors > 1)) or np.any((self.opacities < 0) | (self.opacities > 1)):
            raise ValueError('Colors and opacity must be in [0,1]')
        if self.metadata.get('units') != 'meters' or self.metadata.get('up_axis') != 'z':
            raise ValueError('Parking requires metric coordinates with Z up')
        return self

    def covariance(self):
        r = rotation(self.quats)
        return (r * self.scales[:, None, :]**2) @ r.transpose(0,2,1)

    def save(self, path):
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, means=self.means, scales=self.scales,
                            quats=self.quats, colors=self.colors, opacities=self.opacities,
                            metadata=np.array(json.dumps(self.metadata, ensure_ascii=False)))

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as f:
            return cls(**{k: f[k] for k in ['means','scales','quats','colors','opacities']},
                       metadata=json.loads(str(f['metadata']))).validate()

    def public(self, limit=12000):
        ids = np.linspace(0, len(self.means)-1, min(limit,len(self.means)), dtype=int)
        return dict(means=self.means[ids].round(4).tolist(),
                    covariance=self.covariance()[ids].round(6).tolist(),
                    colors=self.colors[ids].round(3).tolist(),
                    opacities=self.opacities[ids].round(3).tolist(),
                    metadata=self.metadata, count=len(self.means), displayed=len(ids))


def demo_scene():
    """Procedural geometry, explicitly not a learned reconstruction."""
    rng = np.random.default_rng(7)
    means, scales, colors = [], [], []
    for x in np.arange(-12, 12, .5):
        for y in np.arange(-8, 8, .5):
            means.append([x,y,-.08]); scales.append([.3,.3,.035]); colors.append([.17,.22,.25])
    for cx, cy, sx, sy, color in [(-5,-4,1.85,4.4,[.28,.52,.68]),
                                  (2,-4,1.85,4.4,[.8,.46,.24]),
                                  (6,-4,1.85,4.4,[.48,.52,.6]),
                                  (4,5,4.4,1.85,[.32,.55,.45])]:
        for _ in range(650):
            p = rng.uniform([cx-sx/2,cy-sy/2,.18],[cx+sx/2,cy+sy/2,1.5])
            means.append(p); scales.append([.16,.16,.16]); colors.append(color)
    n = len(means)
    return Scene(np.array(means),np.array(scales),np.tile([1.,0,0,0],(n,1)),
                 np.array(colors),np.full(n,.85),dict(units='meters', up_axis='z',
                 source='procedural_demo_not_trained', bounds=[-12,-8,12,8],
                 start=[-8,1,0], goal=[-1.5,-5.3,1.57079632679],
                 known_free_polygon=[[-12,-8],[12,-8],[12,8],[-12,8]],
                 slots=[dict(id='P01',x=-1.5,y=-4,yaw=1.57079632679,width=3.4,length=5.4)])).validate()
