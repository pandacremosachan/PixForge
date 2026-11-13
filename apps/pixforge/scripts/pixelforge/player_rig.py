"""Editable Bedrock player rigs. Source coordinates follow Blockbench's modeling space.

Compile once per edit to the workbench's existing textured mesh and timeline. Children
are transformed around their own pivots before their parents, just as in the outliner.
"""
from copy import deepcopy
from math import floor
from .shapes import default_shapes
from .scene_animation import ADVANCED_SCHEMA

SCHEMA = "pixforge.player-rig/v1"
ZERO = [0, 0, 0]
ONE = [1, 1, 1]
SIDES = {"north":"south","south":"north","east":"west","west":"east","up":"up","down":"down"}

def bone(name, parent, pivot, cubes=()):
    return {"name": name, "parent": parent, "pivot": list(pivot), "rotation": ZERO.copy(), "cubes": list(cubes)}

def cube(name, a, b, uv):
    return {"name":name, "from":list(a), "to":list(b), "uv":list(uv)}

def component_starter():
    return {"schema": SCHEMA, "name": "model", "texture_size": [64, 64],
            "bones": [bone("Root", None, ZERO, [cube("Cube", [-8, 0, -8], [8, 16, 8], [0, 0])])],
            "clips": []}

def starter(name="player", texture_size=(128,128)):
    return {"schema":SCHEMA,"name":name,"texture_size":list(texture_size),"bones":[
        bone("Root",None,ZERO),bone("AllBody","Root",[0,12,0]),bone("UpBody","AllBody",[0,12,0]),
        bone("Body","UpBody",[0,12,0],[cube("torso",[-4,12,-2],[4,24,2],[16,16])]),
        bone("AllHead","UpBody",[0,24,0]),bone("Head","AllHead",[0,24,0],[cube("head",[-4,24,-4],[4,32,4],[0,0])]),
        bone("ViewLocator","Head",[0,28,0]),
        bone("RightArm","UpBody",[5,22,0],[cube("right_arm",[4,12,-2],[8,24,2],[40,16])]),
        bone("RightHandLocator","RightArm",[6,12,0]),
        bone("LeftArm","UpBody",[-5,22,0],[cube("left_arm",[-8,12,-2],[-4,24,2],[32,48])]),
        bone("LeftHandLocator","LeftArm",[-6,12,0]),
        bone("RightLeg","AllBody",[2,12,0],[cube("right_leg",[0,0,-2],[4,12,2],[0,16])]),
        bone("LeftLeg","AllBody",[-2,12,0],[cube("left_leg",[-4,0,-2],[0,12,2],[16,48])])],
        "clips":[{"name":"idle","duration_ms":2000,"loop":True,"tracks":{}}]}

def by_name(rows):
    return {row["name"]:row for row in rows}

def topology(rig):
    bones=by_name(rig["bones"])
    if len(bones)!=len(rig["bones"]): raise ValueError("骨骼名称须唯一")
    paths={}
    def lineage(key,visiting):
        if key not in paths:
            if key in visiting: raise ValueError("父子骨骼形成循环："+key)
            parent=bones[key].get("parent")
            paths[key]=[key]+(lineage(parent,visiting|{key}) if parent else [])
        return paths[key]
    for name in bones:lineage(name,set())
    return bones,paths

def mirror_xz(p):return [-p[0],p[1],-p[2]]

def face_pixels(c):
    """Blockbench per-face endpoint UVs, including its lid orientation."""
    if "faces" in c:return {n:v for n,v in c["faces"].items()}
    x,y=c["uv"];w,h,d=[floor(b-a+1e-7) for a,b in zip(c["from"],c["to"])]
    rects={"east":[x,y+d,x+d,y+d+h],"north":[x+d,y+d,x+d+w,y+d+h],
           "west":[x+d+w,y+d,x+2*d+w,y+d+h],"south":[x+2*d+w,y+d,x+2*d+2*w,y+d+h],
           "up":[x+d+w,y+d,x+d,y],"down":[x+d+2*w,y,x+d+w,y+d]}
    if c.get("mirror"):
        rects={n:[r[2],r[1],r[0],r[3]] for n,r in rects.items()}
        rects["east"],rects["west"]=rects["west"],rects["east"]
    return {n:{"uv":v} for n,v in rects.items()}

def compile_rig(rig):
    from .scene_animation import normalize
    bones,paths=topology(rig)
    w,h=rig["texture_size"];elements=[];members={name:[] for name in bones};rotations=[]
    for name,b in bones.items():
        if len(by_name(b["cubes"]))!=len(b["cubes"]):raise ValueError("同一骨骼中的方块名称须唯一："+name)
        for c in b["cubes"]:
            i=len(elements);f,t=c["from"],c["to"];pad=c.get("inflate",0)
            lo=[min(a,b)-pad for a,b in zip(mirror_xz(f),mirror_xz(t))]
            hi=[max(a,b)+pad for a,b in zip(mirror_xz(f),mirror_xz(t))]
            faces={}
            for side,row in face_pixels(c).items():
                r=row["uv"]
                if side in ("up","down"):r=[r[2],r[3],r[0],r[1]]
                faces[SIDES[side]]={"texture":"#avatar","uv":[16*n/(w if k%2==0 else h) for k,n in enumerate(r)],
                                    **({"rotation":row["rotation"]} if row.get("rotation") else {})}
            elements.append({"name":name+"/"+c["name"],"from":lo,"to":hi,"faces":faces})
            for ancestor in paths[name]:members[ancestor].append(i)
            if any(c.get("rotation",ZERO)):
                rotations.append((str(i),[i],mirror_xz(c.get("pivot",b["pivot"])),mirror_xz(c["rotation"])))
    if not elements:raise ValueError("角色至少需要一个方块")
    model={"name":rig["name"],"texture_size":[w,h],"textures":{"avatar":"pixforge:player/model"},"elements":elements,"player_rig":deepcopy(rig)}
    clips=rig.get("clips") or [{"name":"idle","duration_ms":1000,"loop":True,"tracks":{}}]
    used={c["name"] for c in clips}
    if len(used)!=len(clips):raise ValueError("动作名称须唯一")
    for clip in clips:
        for name,channels in clip.get("tracks",{}).items():
            if name not in bones:raise ValueError("关键帧引用了不存在的骨骼："+name)
            if set(channels)-{"rotation","position","scale"}:raise ValueError("使用 rotation、position 或 scale 关键帧")
    def channel(name,k,axis=None):
        for clip in clips:
            for key in clip.get("tracks",{}).get(name,{}).get(k,[]):
                if axis is None or key["value"][axis]!=0:return True
        return False
    # A stable track order across clips also makes their names selectable in the native player.
    desc=[]
    axes=[[1,0,0],[0,1,0],[0,0,1]]
    for tag,indices,pivot,rotation in rotations:
        for k,angle in enumerate(rotation):
            if angle:desc.append((f"cube_{tag}_{k}",indices,pivot,"rotate",k,angle,None))
    for idx,name in enumerate(sorted(bones,key=lambda n:-len(paths[n]))):
        ids=members[name]
        if not ids:continue
        pivot=mirror_xz(bones[name]["pivot"])
        if channel(name,"scale"):desc.append((f"sz_{idx}",ids,pivot,"scale",None,ONE,name))
        for k,angle in enumerate(mirror_xz(bones[name].get("rotation",ZERO))):
            if angle or channel(name,"rotation",k):desc.append((f"r_{idx}_{k}",ids,pivot,"rotate",k,angle,name))
        if channel(name,"position"):desc.append((f"p_{idx}",ids,pivot,"translate",None,ZERO,name))
    scene=None
    if desc:
        states=[]
        for clip in clips:
            duration=clip["duration_ms"];tracks=[]
            for tag,ids,pivot,kind,axis,base,name in desc:
                field={"rotate":"rotation","translate":"position","scale":"scale"}[kind]
                keys=sorted(clip.get("tracks",{}).get(name,{}).get(field,[]),key=lambda r:r["time_ms"])
                values=[]
                for key in keys:
                    v=key["value"]
                    # Keyframe numbers in .bbmodel are Bedrock animation coordinates.
                    val=(base+v[axis]*[1,-1,-1][axis] if kind=="rotate" else [v[0],v[1],-v[2]] if kind=="translate" else list(v))
                    ease=key.get("easing","linear")
                    if ease not in ("linear","hold"):raise ValueError("骨骼关键帧支持 linear 或 hold")
                    values.append({"time_ms":key["time_ms"],"value":val,"easing":ease})
                if not values:values=[{"time_ms":0,"value":base,"easing":"linear"}]
                if values[0]["time_ms"]!=0:values.insert(0,{**values[0],"time_ms":0})
                if values[-1]["time_ms"]!=duration:values.append({**values[-1],"time_ms":duration})
                if clip.get("loop",True) and values[-1]["value"]!=values[0]["value"]:
                    # Bedrock can jump at the loop boundary. The workbench timeline
                    # represents the last sub-frame explicitly rather than smoothing it out.
                    values[-1]["time_ms"]=duration-min(.0001,(duration-values[-2]["time_ms"])/2)
                    values[-1]["easing"]="hold";values.append({"time_ms":duration,"value":values[0]["value"],"easing":"linear"})
                tracks.append({"id":tag,"type":kind,"elements":ids,"pivot":pivot,"keyframes":values,
                              **({"axis":axes[axis]} if kind=="rotate" else {})})
            states.append({"id":clip["name"],"label":clip["name"],"duration_ms":duration,"loop":clip.get("loop",True),"transforms":tracks,"emitters":[]})
        routes=[{"from":s["id"],"event":"start","to":states[(i+1)%len(states)]["id"]} for i,s in enumerate(states)] if len(states)>1 else []
        scene=normalize({"schema":ADVANCED_SCHEMA,"initial_state":states[0]["id"],"states":states,"transitions":routes,
                         "preview_sequence":[{"state":s["id"],"duration_ms":s["duration_ms"]} for s in states],"loop":True},model)
    return {**default_shapes(),"base":[],"model":model},scene

def paint_template(canvas,rig):
    from PIL import ImageDraw
    d=ImageDraw.Draw(canvas.active.img)
    colors={"Head":"#c9906f","Body":"#376f78","LeftArm":"#c9906f","RightArm":"#c9906f",
            "LeftLeg":"#43546d","RightLeg":"#43546d"}
    for b in rig["bones"]:
        for c in b["cubes"]:
            for face in face_pixels(c).values():
                x,y,X,Y=face["uv"]
                if x!=X and y!=Y:d.rectangle((min(x,X),min(y,Y),max(x,X)-1,max(y,Y)-1),fill=colors.get(b["name"],"#899aa6"))

def edited(source,operations):
    rig=deepcopy(source)
    for op in operations:
        action=op["op"];bs=by_name(rig["bones"]);name=op.get("bone")
        if action=="bone":
            b=bs.get(name)
            if b is None:
                b=bone(name,op.get("parent"),op.get("pivot",ZERO));rig["bones"].append(b)
            for k in ("pivot","parent","rotation"):
                if k in op:b[k]=op[k]
            if op.get("rename") and op["rename"]!=name:
                new=op["rename"];b["name"]=new
                for child in rig["bones"]:
                    if child.get("parent")==name:child["parent"]=new
                for clip in rig["clips"]:
                    tracks=clip.get("tracks",{})
                    if name in tracks:tracks[new]=tracks.pop(name)
        elif action=="cube":
            cubes=bs[name]["cubes"];c=by_name(cubes).get(op["name"])
            if c is None:
                c=cube(op["name"],op["from"],op["to"],op.get("uv",[0,0]));cubes.append(c)
            if "uv" in op:c.pop("faces",None)
            c.update({k:op[k] for k in ("from","to","uv","faces","pivot","rotation","mirror","inflate") if k in op})
            if op.get("rename"):c["name"]=op["rename"]
        elif action=="delete_cube":
            cubes=bs[name]["cubes"];cubes.remove(by_name(cubes)[op["name"]])
        elif action=="delete_bone":
            _,paths=topology(rig);deleted={n for n,v in paths.items() if name in v}
            rig["bones"]=[b for b in rig["bones"] if b["name"] not in deleted]
            for clip in rig["clips"]:
                for n in deleted:clip.get("tracks",{}).pop(n,None)
        elif action=="clip":
            clips=rig.setdefault("clips",[]);clip=by_name(clips).get(op["name"])
            if clip is None:
                clip={"name":op["name"],"duration_ms":2000,"loop":True,"tracks":{}};clips.append(clip)
            clip.update({k:op[k] for k in ("duration_ms","loop","tracks") if k in op})
        elif action in ("key","delete_key"):
            ch=by_name(rig["clips"])[op["clip"]]["tracks"].setdefault(name,{}).setdefault(op.get("channel","rotation"),[])
            ch[:]=[k for k in ch if k["time_ms"]!=op["time_ms"]]
            if action=="key":
                ch.append({"time_ms":op["time_ms"],"value":op["value"],"easing":op.get("easing","linear")})
                ch.sort(key=lambda k:k["time_ms"])
        else:raise ValueError("未知骨骼编辑操作："+action)
    return rig
