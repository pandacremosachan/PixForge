"""Blockbench Bedrock project interchange and YSM spec-2 package writer."""
import base64
from io import BytesIO
import json
from uuid import uuid5,NAMESPACE_URL
from zipfile import ZipFile,ZIP_DEFLATED
from .image_bytes import png
from .player_rig import ZERO, face_pixels, topology

def encoded(obj):return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf-8")

def project(rig,image):
    def uid(*path):return str(uuid5(NAMESPACE_URL,json.dumps(["pixforge",rig["name"],*path],ensure_ascii=False)))
    groups={};elements=[];roots=[]
    for b in rig["bones"]:
        n=b["name"];children=[]
        groups[n]={"name":n,"origin":b["pivot"],"rotation":b.get("rotation",ZERO),"uuid":uid("bone",n),"children":children,"isOpen":True}
        for c in b["cubes"]:
            tag=uid("cube",n,c["name"]);children.append(tag)
            faces={k:{"uv":v["uv"],"rotation":v.get("rotation",0),"texture":0} for k,v in face_pixels(c).items()}
            elements.append({"type":"cube","name":c["name"],"from":c["from"],"to":c["to"],
                             "origin":c.get("pivot",b["pivot"]),"rotation":c.get("rotation",ZERO),
                             "inflate":c.get("inflate",0),"box_uv":"faces" not in c,"mirror_uv":c.get("mirror",False),
                             "uv_offset":c.get("uv",[0,0]),"autouv":0,"uuid":tag,
                             "faces":{n:faces.get(n,{"texture":None,"uv":[0,0,0,0]}) for n in ("north","east","south","west","up","down")}})
    for b in rig["bones"]:
        (groups[b["parent"]]["children"] if b.get("parent") else roots).append(groups[b["name"]])
    animations=[]
    for clip in rig["clips"]:
        animators={}
        for name,channels in clip.get("tracks",{}).items():
            keys=[]
            for channel,frames in channels.items():
                for k in frames:
                    keys.append({"channel":channel,"time":k["time_ms"]/1000,"uuid":uid("key",clip["name"],name,channel,k["time_ms"]),
                                 "interpolation":"step" if k.get("easing")=="hold" else "linear",
                                 "data_points":[dict(zip("xyz",k["value"]))]})
            animators[uid("bone",name)]={"name":name,"type":"bone","keyframes":keys}
        animations.append({"uuid":uid("clip",clip["name"]),"name":clip["name"],"loop":"loop" if clip.get("loop",True) else "once",
                           "length":clip["duration_ms"]/1000,"snapping":20,"animators":animators})
    w,h=rig["texture_size"]
    return {"meta":{"format_version":"4.10","model_format":"bedrock","box_uv":all(c["box_uv"] for c in elements)},
            "name":rig["name"],"model_identifier":rig["name"],"resolution":{"width":w,"height":h},
            "elements":elements,"outliner":roots,"textures":[{"name":"skin.png","id":"0","uuid":uid("atlas"),
            "width":image.width,"height":image.height,"uv_width":w,"uv_height":h,"mode":"bitmap",
            "source":"data:image/png;base64,"+base64.b64encode(png(image)).decode("ascii")}],"animations":animations}

def geometry(rig,arms=False):
    bones,paths=topology(rig);rows=[]
    if arms and not {"LeftArm","RightArm"} <= bones.keys():
        raise ValueError("YSM 第一人称模型需要命名为 LeftArm 和 RightArm 的两组手臂")
    def pos(v):return [-v[0],v[1],v[2]]
    def rot(v):return [-v[0],-v[1],v[2]]
    for name,b in bones.items():
        if arms and not any(p in ("LeftArm","RightArm") for p in paths[name]):continue
        row={"name":name,"pivot":pos(b["pivot"])}
        armroot=arms and name in ("LeftArm","RightArm")
        if not armroot:
            if b.get("parent"):row["parent"]=b["parent"]
            if any(b.get("rotation",ZERO)):row["rotation"]=rot(b["rotation"])
        for c in b["cubes"]:
            a,t=c["from"],c["to"];size=[T-A for A,T in zip(a,t)]
            box={"origin":[-t[0],a[1],a[2]],"size":size}
            if "faces" not in c:
                box["uv"]=c["uv"]
                if c.get("mirror"):box["mirror"]=True
            else:
                per={}
                for side,f in c["faces"].items():
                    u,v,U,V=f["uv"]
                    if side in ("up","down"):u,v,U,V=U,V,u,v
                    per[side]={"uv":[u,v],"uv_size":[U-u,V-v],**({"uv_rotation":f["rotation"]} if f.get("rotation") else {})}
                box["uv"]=per
            if any(c.get("rotation",ZERO)):box.update(pivot=pos(c.get("pivot",b["pivot"])),rotation=rot(c["rotation"]))
            if c.get("inflate"):box["inflate"]=c["inflate"]
            row.setdefault("cubes",[]).append(box)
        rows.append(row)
    points=[p for b in rig["bones"] for c in b["cubes"] for p in (c["from"],c["to"])]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    meta={"identifier":"geometry.pixforge."+("arms" if arms else "player"),"texture_width":rig["texture_size"][0],"texture_height":rig["texture_size"][1],
          "visible_bounds_width":max(3,(max(hi[0]-lo[0],hi[2]-lo[2])+16)/16),
          "visible_bounds_height":max(3,(hi[1]-lo[1]+16)/16),"visible_bounds_offset":[0,(hi[1]+lo[1])/32,0]}
    ver="1.21.0" if any(f.get("rotation") for b in rig["bones"] for c in b["cubes"] for f in c.get("faces",{}).values()) else "1.12.0"
    return {"format_version":ver,"minecraft:geometry":[{"description":meta,"bones":rows}]}

def animations(rig):
    result={}
    for clip in rig["clips"]:
        channels={}
        for name,data in clip.get("tracks",{}).items():
            for kind,keys in data.items():
                prev=None;curve={}
                for key in sorted(keys,key=lambda k:k["time_ms"]):
                    v=key["value"];curve[str(key["time_ms"]/1000)]={"pre":prev["value"],"post":v} if prev and prev.get("easing")=="hold" else v
                    prev=key
                if curve:channels.setdefault(name,{})[kind]=curve
        result[clip["name"]]={"loop":clip.get("loop",True),"animation_length":clip["duration_ms"]/1000,"bones":channels}
    return {"format_version":"1.8.0","animations":result}

def ysm(rig,image,metadata=None):
    info={"spec":2,"metadata":{"name":rig["name"],**(metadata or {})},
          "properties":{"default_texture":"skin"},
          "files":{"player":{"model":{"main":"models/main.json","arm":"models/arm.json"},"texture":["textures/skin.png"]}}}
    files={"models/main.json":encoded(geometry(rig)),"models/arm.json":encoded(geometry(rig,arms=True)),"textures/skin.png":png(image)}
    if any(c.get("tracks") for c in rig["clips"]):
        info["files"]["player"]["animation"]={"main":"animations/main.animation.json"}
        info["properties"]["preview_animation"]=next((c["name"] for c in rig["clips"] if c["name"]=="idle"),rig["clips"][0]["name"])
        files["animations/main.animation.json"]=encoded(animations(rig))
    files["ysm.json"]=encoded(info)
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as bundle:
        for path,data in files.items():bundle.writestr(path,data)
    return out.getvalue()
