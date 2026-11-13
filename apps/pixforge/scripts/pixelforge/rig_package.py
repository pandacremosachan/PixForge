"""Bedrock/YSM export from the authored project. The .bbmodel remains the native master."""
from collections import defaultdict
from io import BytesIO
from pathlib import PureWindowsPath
from zipfile import ZipFile, ZIP_DEFLATED
from .rig_studio import CHANNELS, ZERO, atlas_image, tree, from_source, modern
from copy import deepcopy
from .rig_files import encoded, geometry
from .image_bytes import png

def xyz(p):
    def one(v):
        try:return float(v)
        except (ValueError,TypeError):return v
    return [one(p.get(axis,0)) for axis in "xyz"]

def bezier(a,b,sec):
    def cubic(x,y,z,w,t):
        r=1-t;return r*r*r*x+3*r*r*t*y+3*r*t*t*z+t*t*t*w
    out=[];dt=b["time"]-a["time"]
    av=xyz(a["data_points"][-1]);bv=xyz(b["data_points"][0])
    for i in range(3):
        if not isinstance(av[i],(int,float)) or not isinstance(bv[i],(int,float)):
            raise ValueError("含表达式的贝塞尔曲线请保留为 .bbmodel，或烘焙后再导出 YSM")
        x1=max(0,min(dt,a.get("bezier_right_time",[.1]*3)[i]));x2=dt+max(-dt,min(0,b.get("bezier_left_time",[-.1]*3)[i]))
        lo=0;hi=1
        for _ in range(22):
            t=(lo+hi)/2
            if cubic(0,x1,x2,dt,t)<sec-a["time"]:lo=t
            else:hi=t
        y=av[i]+a.get("bezier_right_value",ZERO)[i];z=bv[i]+b.get("bezier_left_value",ZERO)[i]
        out.append(round(cubic(av[i],y,z,bv[i],(hi+lo)/2),6))
    return out

def bedrock_clips(source):
    if modern(source):
        source=deepcopy(source)
        def invert(v):
            try:return -float(v)
            except (TypeError, ValueError):return "-("+str(v)+")"
        for a in source.get("animations",[]):
            for animator in a.get("animators",{}).values():
                for k in animator.get("keyframes",[]):
                    axes={"rotation":"xy","position":"x"}.get(k["channel"],"")
                    for axis in axes:
                        for point in k.get("data_points",[]):
                            if axis in point:point[axis]=invert(point[axis])
                        for h in ("bezier_left_value","bezier_right_value"):
                            if h in k:k[h]["xyz".index(axis)]*=-1
    result={}
    for a in source.get("animations",[]):
        row={"animation_length":a.get("length",0),"bones":{}}
        if a.get("loop")=="loop":row["loop"]=True
        elif a.get("loop")=="hold":row["loop"]="hold_on_last_frame"
        for k in ("anim_time_update","blend_weight","start_delay","loop_delay"):
            if a.get(k):row[k]=a[k]
        if a.get("override"):row["override_previous_animation"]=True
        for an in a.get("animators",{}).values():
            chans=defaultdict(list)
            for k in an.get("keyframes",[]):chans[k["channel"]].append(k)
            for ch,keys in chans.items():
                keys=sorted(keys,key=lambda k:k["time"]);curve={};prev=None
                for k in keys:
                    tm=str(k["time"]);points=k["data_points"];style=k.get("interpolation","linear")
                    if ch=="timeline":
                        scripts=[p["script"] for p in points if p.get("script")];curve[tm]=scripts[0] if len(scripts)==1 else scripts
                    elif ch in ("particle","sound"):
                        cues=[{"effect":p["effect"],**({"locator":p["locator"]} if p.get("locator") else {}),**({"pre_effect_script":p["script"]} if p.get("script") else {})} for p in points if p.get("effect")]
                        curve[tm]=cues[0] if len(cues)==1 else cues
                    elif ch in CHANNELS:
                        pre=xyz(points[0]);post=xyz(points[-1])
                        if style=="catmullrom":
                            curve[tm]={"post":post,"lerp_mode":style}
                            if (not prev and k["time"]>0) or (prev and prev.get("interpolation")!="catmullrom") or len(points)>1:curve[tm]["pre"]=pre
                        elif len(points)>1:curve[tm]={"pre":pre,"post":post}
                        elif prev and prev.get("interpolation")=="step":curve[tm]={"pre":xyz(prev["data_points"][-1]),"post":post}
                        else:curve[tm]=post
                        if prev and ("bezier" in (prev.get("interpolation"),style)):
                            rate=a.get("snapping",24) or 24;u=prev["time"]+1/rate
                            while u<k["time"]-1e-6:
                                curve[str(round(u,6))]=bezier(prev,k,u);u+=1/rate
                    prev=k
                if ch in CHANNELS:
                    bone=row["bones"].setdefault(an["name"],{});bone[ch]=curve
                    if an.get("rotation_global"):bone["relative_to"]={"rotation":"entity"}
                elif ch in ("timeline","sound","particle"):row[{"timeline":"timeline","sound":"sound_effects","particle":"particle_effects"}[ch]]=curve
        result[a["name"]]=row
    return {"format_version":"1.8.0","animations":result}

def ysm_package(source,metadata=None):
    binding={f["texture"] for e in source["elements"] for f in e.get("faces",{}).values() if f.get("texture") is not None}
    sheet,mapping=(from_source(source) if len(binding)>1 else (None,None))
    byid={};bones=[];res=source["resolution"];ts=[res["width"],res["height"]]
    tex=source["textures"]
    for p,n,cube,_ in tree(source):
        parent=byid.get(p["uuid"]) if p else None
        if n.get("export",True)==False or (p and parent is None):continue
        if not cube:
            b={"name":n["name"],"parent":parent["name"] if parent else None,"pivot":n.get("origin",ZERO),"rotation":n.get("rotation",ZERO),"cubes":[]}
            byid[n["uuid"]]=b;bones.append(b);continue
        if parent is None:
            parent=byid.get("")
            if parent is None:
                parent={"name":"PixForgeRoot","parent":None,"pivot":ZERO,"cubes":[]};byid[""]=parent;bones.append(parent)
        c={"name":n["name"],"from":n["from"],"to":n["to"],"pivot":n.get("origin",parent["pivot"]),"rotation":n.get("rotation",ZERO),"inflate":n.get("inflate",0)}
        if not sheet and n.get("box_uv",source["meta"].get("box_uv",False)):
            c.update(uv=n.get("uv_offset",[0,0]),mirror=n.get("mirror_uv",False))
        else:
            c["faces"]={}
            for side,f in n.get("faces",{}).items():
                idx=f.get("texture");uv=f["uv"]
                if idx is None:continue
                if sheet:
                    if isinstance(idx,str) and not idx.isdigit():idx=next(i for i,t in enumerate(tex) if t["uuid"]==idx)
                    tile=sheet["model"]["player_rig"]["textures"][int(idx)];x,y,w,h=tile["rect"];uw,uh=tile["uv_size"]
                    uv=[(x+v*w/uw) if i%2==0 else (y+v*h/uh) for i,v in enumerate(uv)]
                c["faces"][side]={"uv":uv,**({"rotation":f["rotation"]} if f.get("rotation") else {})}
        parent["cubes"].append(c)
    rig={"name":source.get("name","player"),"bones":bones,"texture_size":list(mapping.size) if sheet else ts}
    player={"model":{"main":"models/main.json","arm":"models/arm.json"},"texture":[]}
    files={tag:encoded(geometry(rig,arms=(a=="arm"))) for a,tag in player["model"].items()}
    alltex=[("combined.png",mapping)] if sheet else [(PureWindowsPath(t["name"]).stem+".png", atlas_image(t)) for t in tex]
    for i,(name,img) in enumerate(alltex):
        path="textures/"+name
        if path in files:path=f"textures/{i}_{name}"
        files[path]=png(img);player["texture"].append(path)
    primary=0
    if not sheet and binding:
        target=next(iter(binding));primary=int(target) if isinstance(target,int) or str(target).isdigit() else next(i for i,t in enumerate(tex) if t.get("uuid")==target)
    info={"spec":2,"metadata":{"name":rig["name"],**(metadata or {})},"properties":{"default_texture":PureWindowsPath(player["texture"][primary]).stem},"files":{"player":player}}
    anim=bedrock_clips(source)
    if anim["animations"]:
        path="animations/main.animation.json";player["animation"]={"main":path};files[path]=encoded(anim)
        info["properties"]["preview_animation"]="idle" if "idle" in anim["animations"] else next(iter(anim["animations"]))
    files["ysm.json"]=encoded(info);stream=BytesIO()
    with ZipFile(stream,"w",ZIP_DEFLATED) as z:
        for k,data in files.items():z.writestr(k,data)
    return stream.getvalue()

