"""Closed-loop kinematic tracking, with stop at gear cusps and collision veto."""
import math
import numpy as np
from .planner import Vehicle, advance, collision, wrap


def simulate(result, grid, speed=.65, dt=.1, max_steps=4000):
    v=Vehicle(**result['vehicle']); path=result['path']
    pose=(path[0]['x'],path[0]['y'],path[0]['yaw'])
    trace=[]; status='timeout'; index=1; length=0.; switches=0; prev_direction=None
    while index<len(path) and len(trace)<max_steps:
        direction=path[index]['direction']; end=index
        while end+1<len(path) and path[end+1]['direction']==direction: end+=1
        if prev_direction is not None and prev_direction!=direction:
            switches+=1
            trace.append(dict(x=pose[0],y=pose[1],yaw=pose[2],speed=0.,steer=0.,t=len(trace)*dt))
        prev_direction=direction
        while len(trace)<max_steps:
            points=np.array([[p['x'],p['y']] for p in path[index:end+1]])
            nearest=index+int(np.argmin(np.linalg.norm(points-np.array(pose[:2]),axis=1)))
            index=max(index,nearest)
            terminal=path[end]; remaining=math.hypot(pose[0]-terminal['x'],pose[1]-terminal['y'])
            if remaining<.12: index=end+1; break
            target=path[min(index+5,end)]
            dx,dy=target['x']-pose[0],target['y']-pose[1]
            lateral=-math.sin(pose[2])*dx+math.cos(pose[2])*dy
            steer=float(np.clip(math.atan2(2*v.wheelbase*lateral,max(dx*dx+dy*dy,.04)),-v.max_steer,v.max_steer))
            velocity=direction*min(speed,max(.15,remaining))
            nxt=advance(pose,velocity*dt,steer,v)
            if collision(nxt,grid,v): status='collision_stop'; break
            length+=abs(velocity*dt); pose=nxt
            trace.append(dict(x=pose[0],y=pose[1],yaw=pose[2],speed=velocity,steer=steer,t=len(trace)*dt))
        if status=='collision_stop': break
    goal=result['goal']; pe=math.hypot(pose[0]-goal[0],pose[1]-goal[1]); ye=abs(wrap(pose[2]-goal[2]))
    # Grid A* headings are quantized by the map resolution; allow a small
    # quarter-radian terminal tolerance while retaining a separate error state.
    if index>=len(path): status='parked' if pe<.5 and ye<.25 else 'terminal_error'
    trace.append(dict(x=pose[0],y=pose[1],yaw=pose[2],speed=0.,steer=0.,t=len(trace)*dt))
    return dict(status=status,trace=trace,metrics=dict(position_error_m=pe,yaw_error_rad=ye,
                travel_m=length,gear_switches=switches,duration_s=len(trace)*dt))
