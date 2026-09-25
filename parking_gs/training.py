"""Actual differentiable 3DGS training, optional metric depth, adaptive splitting."""
import json
from pathlib import Path
import numpy as np
from .dataset import Dataset
from .scene import Scene


def train(data, output, steps=3000, max_points=40000, max_width=960, seed=42, depth_weight=.1):
    import torch
    from gsplat import rasterization
    if not torch.cuda.is_available(): raise RuntimeError('3DGS training requires CUDA; demo/planning do not')
    if steps<1 or max_points<10: raise ValueError('Invalid training budget')
    torch.manual_seed(seed); rng=np.random.default_rng(seed); ds=Dataset(data,max_width)
    out=Path(output); out.mkdir(parents=True,exist_ok=True)
    ids=rng.choice(len(ds.points),min(max_points,len(ds.points)),replace=False)
    def tensor(a): return torch.as_tensor(a,dtype=torch.float32,device='cuda')
    n=len(ids)
    params=torch.nn.ParameterDict(dict(means=torch.nn.Parameter(tensor(ds.points[ids])),
        log_scales=torch.nn.Parameter(torch.full((n,3),-2.7,device='cuda')),
        quats=torch.nn.Parameter(tensor(np.tile([1,0,0,0],(n,1)))),
        color_logits=torch.nn.Parameter(torch.logit(tensor(ds.colors[ids]).clamp(.001,.999))),
        opacity_logits=torch.nn.Parameter(torch.full((n,),-1.,device='cuda'))))
    def optimizer():
        return torch.optim.Adam([{'params':[p],'lr':.0005 if k=='means' else .005} for k,p in params.items()])
    opt=optimizer(); log=[]
    def render(frame):
        im,k,vm,depth=frame; h,w=im.shape[:2]
        pred,alpha,_=rasterization(means=params['means'],quats=params['quats'],
            scales=params['log_scales'].exp(),opacities=params['opacity_logits'].sigmoid(),
            colors=params['color_logits'].sigmoid(),viewmats=tensor(vm)[None],Ks=tensor(k)[None],
            width=w,height=h,packed=False,render_mode='RGB+ED')
        return pred[0],alpha[0],tensor(im),depth
    for step in range(steps):
        frame=ds.read(int(rng.choice(ds.train_ids))); pred,alpha,target,depth=render(frame)
        photo=(pred[...,:3]-target).abs().mean(); loss=photo
        if depth is not None:
            dep=tensor(depth); valid=torch.isfinite(dep)&(dep>0)&(alpha[...,0]>.1)
            if valid.any(): loss=loss+depth_weight*(pred[...,3][valid]-dep[valid]).abs().mean()
        loss=loss+.001*params['log_scales'].exp().mean()
        opt.zero_grad(); loss.backward()
        grad=params['means'].grad.detach().norm(dim=1)
        opt.step()
        with torch.no_grad():
            params['log_scales'].clamp_(-6.,.7)
            params['quats'].copy_(torch.nn.functional.normalize(params['quats'],dim=-1))
            if step>0 and (step+1)%300==0 and step<steps*.75:
                opacity=params['opacity_logits'].sigmoid(); keep=opacity>.02
                if keep.sum()<10: keep[opacity.topk(min(10,len(opacity))).indices]=True
                room=max_points-int(keep.sum())
                candidates=torch.where(keep & (grad>grad.median()) & (params['log_scales'].exp().max(1).values>.025))[0]
                split=candidates[torch.argsort(grad[candidates],descending=True)[:max(0,room)]]
                values={k:torch.cat([p[keep],p[split]],0) for k,p in params.items()}
                if len(split):
                    values['means'][-len(split):]+=torch.randn_like(values['means'][-len(split):])*params['log_scales'][split].exp()*.4
                    values['log_scales'][-len(split):]-=.35
                params=torch.nn.ParameterDict({k:torch.nn.Parameter(a) for k,a in values.items()})
                opt=optimizer()  # explicit reset after topology change
        if step%50==0 or step==steps-1:
            entry=dict(step=step+1,l1=float(photo.detach()),loss=float(loss.detach()),gaussians=len(params['means']))
            log.append(entry); print(json.dumps(entry),flush=True)
        if (step+1)%500==0 or step==steps-1:
            Scene(params['means'].detach().cpu().numpy(),params['log_scales'].exp().detach().cpu().numpy(),
                  params['quats'].detach().cpu().numpy(),params['color_logits'].sigmoid().detach().cpu().numpy(),
                  params['opacity_logits'].sigmoid().detach().cpu().numpy(),ds.data['metadata']).save(out/'scene.npz')
            (out/'training.json').write_text(json.dumps(dict(seed=seed,steps=step+1,log=log),indent=2),encoding='utf-8')
    from PIL import Image
    metrics=[]
    with torch.no_grad():
        for i in ds.val_ids:
            pred,_,target,_=render(ds.read(i)); mse=(pred[...,:3]-target).square().mean().clamp_min(1e-10)
            metrics.append(dict(frame=i,psnr=float(-10*torch.log10(mse))))
            Image.fromarray((pred[...,:3].clamp(0,1).cpu().numpy()*255).astype('uint8')).save(out/f'validation_{i:05d}.png')
    report=dict(frames=metrics,mean_psnr=float(np.mean([m['psnr'] for m in metrics])),train_frames=ds.train_ids,val_frames=ds.val_ids)
    (out/'reconstruction_metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
