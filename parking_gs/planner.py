"""Hybrid A* with exact bicycle arcs and raster-conservative footprint tests."""
from dataclasses import dataclass, asdict
import heapq
import itertools
import math
import time
import numpy as np


def wrap(a): return (a+math.pi)%(2*math.pi)-math.pi


@dataclass
class Vehicle:
    wheelbase: float = 2.65
    width: float = 1.8
    front: float = 3.55  # rear axle to front bumper
    rear: float = .9
    max_steer: float = .6
    margin: float = .12


def advance(pose, distance, steer, vehicle):
    x,y,yaw = pose
    k = math.tan(steer)/vehicle.wheelbase
    if abs(k)<1e-10: return (x+distance*math.cos(yaw),y+distance*math.sin(yaw),yaw)
    end = yaw+distance*k
    return (x+(math.sin(end)-math.sin(yaw))/k,y+(-math.cos(end)+math.cos(yaw))/k,wrap(end))


def collision(pose, grid, vehicle):
    x,y,a = pose
    # Include any occupied cell whose square overlaps the oriented rectangle.
    # Projection onto vehicle axes is conservative (possible false positives).
    c,s = math.cos(a),math.sin(a)
    corners=np.array([[-vehicle.rear-vehicle.margin,-vehicle.width/2-vehicle.margin],
                      [-vehicle.rear-vehicle.margin,vehicle.width/2+vehicle.margin],
                      [vehicle.front+vehicle.margin,-vehicle.width/2-vehicle.margin],
                      [vehicle.front+vehicle.margin,vehicle.width/2+vehicle.margin]])@np.array([[c,s],[-s,c]])+[x,y]
    if np.any(corners<grid.bounds[:2]) or np.any(corners>=grid.bounds[2:]): return True
    lo=grid.indices(corners.min(0)); hi=grid.indices(corners.max(0))+1
    blocked=(~grid.known[lo[1]:hi[1],lo[0]:hi[0]]) | (grid.risk[lo[1]:hi[1],lo[0]:hi[0]]>=grid.threshold)
    yy,xx=np.nonzero(blocked)
    if not len(xx): return False
    pts=np.stack([grid.bounds[0]+(xx+lo[0]+.5)*grid.resolution,grid.bounds[1]+(yy+lo[1]+.5)*grid.resolution],1)
    d = pts-[x,y]
    lx,ly = d[:,0]*c+d[:,1]*s, -d[:,0]*s+d[:,1]*c
    pad = vehicle.margin+grid.resolution*.5*(abs(c)+abs(s))
    mask = (lx>=-vehicle.rear-pad)&(lx<=vehicle.front+pad)&(abs(ly)<=vehicle.width/2+pad)
    return bool(mask.any())


def connect(start, goal, grid, vehicle):
    """Four CSC Dubins families in both driving directions; collision checked."""
    radius=vehicle.wheelbase/math.tan(vehicle.max_steer)
    mod=lambda x:x%(2*math.pi)
    candidates=[]
    for direction in (1,-1):
        offset=math.pi if direction<0 else 0
        dx,dy=(goal[0]-start[0])/radius,(goal[1]-start[1])/radius
        d=math.hypot(dx,dy); theta=math.atan2(dy,dx)
        a,b=mod(start[2]+offset-theta),mod(goal[2]+offset-theta)
        sa,sb,ca,cb=math.sin(a),math.sin(b),math.cos(a),math.cos(b)
        for family in ('LSL','RSR','LSR','RSL'):
            if family=='LSL':
                p2=2+d*d-2*math.cos(a-b)+2*d*(sa-sb)
                tmp=math.atan2(cb-ca,d+sa-sb); t=mod(-a+tmp); q=mod(b-tmp)
            elif family=='RSR':
                p2=2+d*d-2*math.cos(a-b)+2*d*(sb-sa)
                tmp=math.atan2(ca-cb,d-sa+sb); t=mod(a-tmp); q=mod(-b+tmp)
            elif family=='LSR':
                p2=-2+d*d+2*math.cos(a-b)+2*d*(sa+sb)
                if p2<0: continue
                tmp=math.atan2(-ca-cb,d+sa+sb)-math.atan2(-2,math.sqrt(p2))
                t=mod(-a+tmp); q=mod(-b+tmp)
            else:
                p2=d*d-2+2*math.cos(a-b)-2*d*(sa+sb)
                if p2<0: continue
                tmp=math.atan2(ca+cb,d-sa-sb)-math.atan2(2,math.sqrt(p2))
                t=mod(a-tmp); q=mod(b-tmp)
            if p2<0: continue
            lens=[t,math.sqrt(p2),q]
            candidates.append((sum(lens)*radius,direction,family,lens))
    for length,direction,family,lens in sorted(candidates):
        if length>25: continue
        p=start; segment=[]; valid=True
        for mode,angle in zip(family,lens):
            dist=angle*radius; count=max(1,math.ceil(dist/.1))
            steer=(0 if mode=='S' else (1 if mode=='L' else -1)*direction*vehicle.max_steer)
            for _ in range(count):
                p=advance(p,direction*dist/count,steer,vehicle)
                if collision(p,grid,vehicle): valid=False; break
                segment.append(dict(x=p[0],y=p[1],yaw=p[2],direction=direction,steer=steer))
            if not valid: break
        if valid and math.hypot(p[0]-goal[0],p[1]-goal[1])<1e-5 and abs(wrap(p[2]-goal[2]))<1e-5:
            return segment
    return None


def plan(start, goal, grid, vehicle=None, max_expansions=35000, timeout=25):
    v = vehicle or Vehicle()
    start,goal = tuple(start),tuple(goal)
    if len(start)!=3 or len(goal)!=3 or not np.isfinite([start,goal]).all():
        raise ValueError('Poses must be three finite numbers')
    if collision(start,grid,v): raise ValueError('Start vehicle footprint is blocked or unknown')
    if collision(goal,grid,v): raise ValueError('Goal vehicle footprint is blocked or unknown')
    begin = time.perf_counter()
    def key(p,d,si):
        return (round(p[0]/.35),round(p[1]/.35),round(wrap(p[2])/(math.pi/36))%72,d,si)
    def heuristic(p):
        return math.hypot(p[0]-goal[0],p[1]-goal[1])+1.5*abs(wrap(p[2]-goal[2]))
    counter=itertools.count(); root=(start,1,2,None,[],0.)
    nodes=[root]; heap=[(heuristic(start),next(counter),0)]; best={key(start,1,2):0.}
    expanded=0; step=.7; substeps=7; steers=np.linspace(-v.max_steer,v.max_steer,5)
    while heap and expanded<max_expansions and time.perf_counter()-begin<timeout:
        _,_,idx=heapq.heappop(heap)
        pose,direction,si,parent,segment,cost=nodes[idx]
        if cost > best.get(key(pose,direction,si),float('inf'))+1e-9: continue
        expanded+=1
        tail=connect(pose,goal,grid,v) if expanded%15==1 else None
        if tail is not None or (math.hypot(pose[0]-goal[0],pose[1]-goal[1])<.35 and abs(wrap(pose[2]-goal[2]))<.10):
            chunks=[]; cur=idx
            while nodes[cur][3] is not None:
                chunks.append(nodes[cur][4]); cur=nodes[cur][3]
            path=[dict(x=start[0],y=start[1],yaw=start[2],direction=1,steer=0.)]
            for chunk in reversed(chunks): path.extend(chunk)
            if tail:
                path.extend(tail); pose=goal
            return dict(path=path,expanded=expanded,seconds=time.perf_counter()-begin,
                        vehicle=asdict(v),goal=list(goal),position_error=math.hypot(pose[0]-goal[0],pose[1]-goal[1]),
                        yaw_error=abs(wrap(pose[2]-goal[2])))
        for nd in (1,-1):
            for ns,steer in enumerate(steers):
                p=pose; seg=[]
                for _ in range(substeps):
                    p=advance(p,nd*step/substeps,float(steer),v)
                    if collision(p,grid,v): break
                    seg.append(dict(x=p[0],y=p[1],yaw=p[2],direction=nd,steer=float(steer)))
                if len(seg)!=substeps: continue
                ij=grid.indices(np.array([p[:2]]))[0]
                nc=cost+step*(1 if nd==1 else 1.3)+(.9 if nd!=direction else 0)+.12*abs(ns-si)+.5*grid.risk[ij[1],ij[0]]
                nk=key(p,nd,ns)
                if nc>=best.get(nk,float('inf')): continue
                best[nk]=nc; nodes.append((p,nd,ns,idx,seg,nc))
                heapq.heappush(heap,(nc+1.5*heuristic(p),next(counter),len(nodes)-1))
    raise RuntimeError(f'No path within budget: {expanded} expansions, {time.perf_counter()-begin:.2f}s. Goal may be unreachable.')
