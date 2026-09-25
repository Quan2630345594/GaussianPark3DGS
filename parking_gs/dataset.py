"""COLMAP PINHOLE text adapter and validated camera/image dataset."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .scene import rotation


def safe_path(root, relative):
    root=Path(root).resolve(); p=(root/relative).resolve()
    if not p.is_relative_to(root): raise ValueError('Path escapes dataset directory')
    return p


def import_colmap(model, images, output, config):
    model,images,output=Path(model),Path(images).resolve(),Path(output)
    cfg=json.loads(Path(config).read_text(encoding='utf-8'))
    scale=float(cfg['colmap_to_metric_scale']); r=np.asarray(cfg['world_rotation'],float)
    t=np.asarray(cfg['world_translation'],float)
    if scale<=0 or r.shape!=(3,3) or not np.allclose(r.T@r,np.eye(3),atol=1e-5) or not np.isclose(np.linalg.det(r),1):
        raise ValueError('Expected positive metric scale and a proper world rotation')
    if t.shape!=(3,) or not np.isfinite(t).all(): raise ValueError('Invalid translation')
    cameras={}
    for line in (model/'cameras.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        a=line.split(); cid=int(a[0]); kind=a[1]; w,h=map(int,a[2:4]); p=list(map(float,a[4:]))
        if kind=='PINHOLE': fx,fy,cx,cy=p
        elif kind=='SIMPLE_PINHOLE': fx,cx,cy=p; fy=fx
        else: raise ValueError(f'{kind}: run COLMAP image_undistorter first')
        cameras[cid]=(w,h,[[fx,0,cx],[0,fy,cy],[0,0,1]])
    lines=(model/'images.txt').read_text().splitlines(); frames=[]; i=0
    while i<len(lines):
        line=lines[i]; i+=1
        if not line.strip() or line.startswith('#'): continue
        a=line.split(maxsplit=9)
        if len(a)!=10: raise ValueError('Malformed COLMAP image record')
        q=np.array(list(map(float,a[1:5]))); tr=np.array(list(map(float,a[5:8])))
        rcw=rotation(q); center=-rcw.T@tr
        c2w=np.eye(4); c2w[:3,:3]=r@rcw.T; c2w[:3,3]=scale*r@center+t
        w,h,k=cameras[int(a[8])]
        image_path=safe_path(images,a[9])
        if not image_path.is_file(): raise FileNotFoundError(image_path)
        # Paths relative to project make the complete desktop folder portable.
        import os
        frames.append(dict(image=os.path.relpath(image_path,output.resolve()),width=w,height=h,K=k,c2w=c2w.tolist()))
        i+=1  # observations line, which may be empty
    points=[]; colors=[]
    for line in (model/'points3D.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        a=line.split(); points.append(scale*r@np.array(list(map(float,a[1:4])))+t)
        colors.append(np.array(list(map(float,a[4:7])))/255)
    if len(frames)<3 or len(points)<10: raise ValueError('Need at least 3 registered frames and 10 points')
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'points.npz',points=np.array(points),colors=np.array(colors))
    metadata={k:v for k,v in cfg.items() if k not in ['colmap_to_metric_scale','world_rotation','world_translation']}
    metadata.update(units='meters',up_axis='z',source='trained_colmap')
    (output/'dataset.json').write_text(json.dumps(dict(frames=frames,points='points.npz',metadata=metadata),indent=2),encoding='utf-8')


class Dataset:
    def __init__(self,path,max_width=960):
        self.root=Path(path).resolve(); self.data=json.loads((self.root/'dataset.json').read_text(encoding='utf-8'))
        self.frames=self.data['frames']; self.max_width=max_width
        if len(self.frames)<3: raise ValueError('At least 3 frames required for train/validation split')
        with np.load(self.root/self.data['points'],allow_pickle=False) as f:
            self.points=f['points'].astype(np.float32); self.colors=f['colors'].astype(np.float32)
        if self.points.ndim!=2 or self.points.shape[1]!=3 or self.colors.shape!=self.points.shape or not np.isfinite(self.points).all():
            raise ValueError('Invalid seed points')
        self.val_ids=list(range(0,len(self.frames),8))
        self.train_ids=[i for i in range(len(self.frames)) if i not in self.val_ids]

    def read(self,i):
        f=self.frames[i]; image=Image.open(self.root/f['image']).convert('RGB')
        w,h=image.size
        if (w,h)!=(f['width'],f['height']): raise ValueError('Image dimensions disagree with calibration')
        ratio=min(1.,self.max_width/w); nw,nh=round(w*ratio),round(h*ratio)
        image=image.resize((nw,nh),Image.Resampling.LANCZOS)
        k=np.array(f['K'],dtype=np.float32); k[0]*=nw/w; k[1]*=nh/h
        c=np.array(f['c2w'],dtype=np.float32)
        if c.shape!=(4,4) or not np.isfinite(c).all() or not np.allclose(c[3],[0,0,0,1]) or not np.allclose(c[:3,:3].T@c[:3,:3],np.eye(3),atol=1e-4):
            raise ValueError('c2w must be a rigid OpenCV camera-to-world matrix')
        depth=None
        if f.get('depth'):
            depth=np.load(self.root/f['depth'],allow_pickle=False)
            if depth.shape!=(h,w): raise ValueError('Depth shape mismatch')
            depth=np.array(Image.fromarray(depth.astype(np.float32)).resize((nw,nh),Image.Resampling.NEAREST))
        return np.array(image,dtype=np.float32)/255,k,np.linalg.inv(c),depth
