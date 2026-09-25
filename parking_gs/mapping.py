"""Gaussian covariance-aware BEV risk with explicit unknown-space policy."""
from dataclasses import dataclass
import numpy as np


@dataclass
class Grid:
    risk: np.ndarray
    known: np.ndarray
    bounds: list
    resolution: float
    threshold: float = .35

    def indices(self, xy):
        return np.floor((np.asarray(xy)-self.bounds[:2])/self.resolution).astype(int)

    def blocked(self, xy):
        ij = self.indices(xy)
        valid = (ij[...,0]>=0)&(ij[...,1]>=0)&(ij[...,0]<self.risk.shape[1])&(ij[...,1]<self.risk.shape[0])
        out = np.ones(valid.shape, dtype=bool)
        p = ij[valid]
        out[valid] = (~self.known[p[:,1],p[:,0]]) | (self.risk[p[:,1],p[:,0]] >= self.threshold)
        return out

    def public(self):
        return dict(risk=self.risk.round(3).tolist(),known=self.known.astype(int).tolist(),
                    bounds=self.bounds,resolution=self.resolution,threshold=self.threshold)


def in_polygon(x, y, vertices):
    inside = np.zeros_like(x, dtype=bool)
    for a,b in zip(vertices, vertices[1:]+vertices[:1]):
        if abs(b[1]-a[1]) < 1e-12:
            continue
        inside ^= ((a[1]>y)!=(b[1]>y)) & (x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
    return inside


def build_grid(scene, resolution=.25, uncertainty=.12, use_covariance=True):
    bounds = list(scene.metadata['bounds'])
    if resolution < .1 or uncertainty < 0:
        raise ValueError('resolution >= 0.1 and uncertainty >= 0 required')
    w,h = np.ceil((np.array(bounds[2:])-bounds[:2])/resolution).astype(int)
    if w <= 0 or h <= 0 or w*h > 1_000_000:
        raise ValueError('Invalid or excessively large map bounds')
    yy,xx = np.mgrid[:h,:w]
    x,y = bounds[0]+(xx+.5)*resolution, bounds[1]+(yy+.5)*resolution
    polygon = scene.metadata.get('known_free_polygon', [])
    known = in_polygon(x,y,polygon) if len(polygon)>=3 else np.zeros((h,w),bool)
    risk = np.zeros((h,w))
    cov = scene.covariance()
    for i,mu in enumerate(scene.means):
        # Test Gaussian vertical support against the vehicle collision band.
        sz = np.sqrt(cov[i,2,2])
        if mu[2]+2*sz < .15 or mu[2]-2*sz > 2.0 or scene.opacities[i]<.05:
            continue
        c = cov[i,:2,:2] if use_covariance else np.eye(2)*.03**2
        c = c + np.eye(2)*(uncertainty**2 + (resolution*.5)**2)
        radius = 3*np.sqrt(np.linalg.eigvalsh(c).max())
        lo = np.maximum(np.floor((mu[:2]-radius-bounds[:2])/resolution).astype(int),0)
        hi = np.minimum(np.ceil((mu[:2]+radius-bounds[:2])/resolution).astype(int)+1,[w,h])
        if np.any(hi<=lo): continue
        sl = np.s_[lo[1]:hi[1],lo[0]:hi[0]]
        d = np.stack([x[sl]-mu[0], y[sl]-mu[1]],-1)
        mahal = np.einsum('...i,ij,...j->...',d,np.linalg.inv(c),d)
        evidence = scene.opacities[i]*np.exp(-.5*mahal)
        # Max avoids turning dense correlated splats into fictitious certainty.
        risk[sl] = np.maximum(risk[sl],evidence)
    return Grid(risk,known,bounds,resolution)
