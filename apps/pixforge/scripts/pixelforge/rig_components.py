"""Bind-pose cube editing: world-space placement, local dimensions, original face coordinates."""
from math import asin, atan2, cos, degrees, radians, sin

ZERO=(0,0,0)
UNIT=(1,1,1)
I=((1,0,0),(0,1,0),(0,0,1))
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,b):return [x*y for x,y in zip(a,b)]
def rot(r):
    x,y,z=map(radians,r);a,b=cos(x),sin(x);c,d=cos(y),sin(y);e,f=cos(z),sin(z)
    return ((c*e,b*d*e-a*f,a*d*e+b*f),(c*f,b*d*f+a*e,a*d*f-b*e),(-d,b*c,a*c))
def mv(r,p):return [sum(v*q for v,q in zip(row,p)) for row in r]
def tr(r):return tuple(zip(*r))
def mm(a,b):return tuple(zip(*(mv(a,v) for v in tr(b))))
def euler(m):
    y=asin(max(-1,min(1,-m[2][0])))
    if abs(cos(y))>1e-8:x,z=atan2(m[2][1],m[2][2]),atan2(m[1][0],m[0][0])
    else:x,z=0,atan2(-m[0][1],m[1][1])
    return [round(degrees(a),8) for a in (x,y,z)]
def clean(p):return [round(n,8) for n in p]

def transform(ids, cubes, groups, parents, op):
    sel=[cubes[i] for i in dict.fromkeys(ids)]
    if not sel:raise ValueError("请先选中方块")
    scale=op.get("scale",UNIT);angles=op.get("rotation",ZERO);delta=op.get("pivot_delta",ZERO)
    if min(scale)<=0:raise ValueError("缩放倍率必须大于零")
    frames={None:(I,ZERO)}
    def parent_frame(uid):
        if uid not in frames:
            g=groups[uid];p=g.get("origin",ZERO);r=rot(g.get("rotation",ZERO));pr,pt=parent_frame(parents[uid])
            frames[uid]=(mm(pr,r),add(mv(pr,sub(p,mv(r,p))),pt))
        return frames[uid]
    rows=[]
    for c in sel:
        gid=parents[c["uuid"]];r,t=parent_frame(gid)
        pivot=c.get("origin",groups[gid].get("origin",ZERO) if gid else ZERO)
        orient=rot(c.get("rotation",ZERO));mid=[(a+b)/2 for a,b in zip(c["from"],c["to"])]
        cn=add(pivot,mv(orient,sub(mid,pivot)));world=add(mv(r,cn),t)
        rows.append((c,r,t,pivot,orient,mid,world))
    anchor=op.get("anchor","selection")
    if anchor=="selection":anchor=[sum(z[-1][i] for z in rows)/len(rows) for i in range(3)]
    turn=rot(angles);resized=list(scale)!=list(UNIT);turned=any(angles)
    for c,r,t,p,old,mid,center in rows:
        anchor0=add(mv(r,p),t) if anchor=="individual" else anchor
        def mapped(v):return add(anchor0,mv(turn,mul(sub(v,anchor0),scale)))
        inv=tr(r);new=mm(inv,mm(turn,mm(r,old))) if turned else old
        world_p=add(mv(r,p),t)
        target_p=op["pivot"] if "pivot" in op else add(mapped(world_p),delta)
        q=mv(inv,sub(target_p,t));newcenter=mv(inv,sub(mapped(center),t))
        newmid=add(q,mv(tr(new),sub(newcenter,q)))
        half=[(z-a)*k/2 for a,z,k in zip(c["from"],c["to"],scale)]
        if any(abs(a-b)>1e-8 for a,b in zip(newmid,mid)) or resized:
            c["from"]=clean(sub(newmid,half));c["to"]=clean(add(newmid,half))
        if any(abs(a-b)>1e-8 for a,b in zip(p,q)):c["origin"]=clean(q)
        if turned:c["rotation"]=euler(new)
        # Explicit UVs keep the six original regions when Blockbench reloads a resized cube.
        if resized:c["box_uv"]=False

def face_uv(ids,cubes,op):
    for uid in dict.fromkeys(ids):
        c=cubes[uid];f=c["faces"][op["face"]];u,v,U,V=f["uv"]
        if "uv" in op:f["uv"]=list(op["uv"])
        elif "offset" in op:
            x,y=op["offset"];f["uv"]=[u+x,v+y,U+x,V+y]
        if "delta" in op:f["uv"]=[a+b for a,b in zip(f["uv"],op["delta"])]
        if "rotation" in op:
            if op["rotation"] not in (0,90,180,270):raise ValueError("UV 旋转为 0、90、180 或 270 度")
            f["rotation"]=op["rotation"]
        if "flip" in op:
            a,b={"u":(0,2),"v":(1,3)}[op["flip"]]
            f["uv"][a],f["uv"][b]=f["uv"][b],f["uv"][a]
        c["box_uv"]=False

