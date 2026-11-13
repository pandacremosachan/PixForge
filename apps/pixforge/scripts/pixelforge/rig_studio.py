"""Lossless Blockbench source and compact workbench geometry. One UV canvas holds all images."""
import base64
import json
import zlib
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from .image_bytes import png_base64
from .player_rig import ZERO, SIDES, mirror_xz, face_pixels
from .shapes import default_shapes

SCHEMA = "pixforge.blockbench/v2"
CHANNELS = ("rotation", "position", "scale")

def pack(source):
    return base64.b64encode(zlib.compress(json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode(), 3)).decode()

@lru_cache(maxsize=2)
def unpack(blob):
    return json.loads(zlib.decompress(base64.b64decode(blob)))

def modern(src):
    return int(str(src["meta"].get("format_version","4")).split(".")[0])>=5

def child_list(src,uid):
    def find(nodes):
        for node in nodes:
            if isinstance(node,dict):
                if node["uuid"]==uid:return node.setdefault("children",[])
                found=find(node.get("children",[]))
                if found is not None:return found
    return find(src["outliner"]) if uid else src["outliner"]

def atlas_image(t):
    return Image.open(BytesIO(base64.b64decode(t["source"].partition(",")[2]))).convert("RGBA")

def embed(image):
    return "data:image/png;base64," + png_base64(image)

def tree(src):
    groups = {g["uuid"]:g for g in src.get("groups", [])}
    parts = {e["uuid"]:e for e in src["elements"]}
    def visit(nodes, parent):
        for n in nodes:
            uid = n if isinstance(n,str) else n["uuid"]
            if uid in parts:
                yield parent, parts[uid], True, nodes
            else:
                g = groups.get(uid, n)
                yield parent, g, False, nodes
                children = n.get("children",g.get("children",[])) if isinstance(n,dict) else g.get("children",[])
                yield from visit(children, g)
    yield from visit(src["outliner"], None)

def from_source(src, directory=None):
    if src["meta"].get("model_format") != "bedrock":
        raise ValueError("选择 Bedrock Entity 格式的 Blockbench 工程")
    images = []
    for t in src["textures"]:
        if not t.get("source","").startswith("data:image/"):
            with Image.open(Path(directory)/(t.get("relative_path") or t["name"])) as im:
                t["source"] = embed(im.convert("RGBA"))
        images.append(atlas_image(t))
        if "width" in t:t["width"]=images[-1].width
        if "height" in t:t["height"]=images[-1].height
    layout=[]; x=y=row_h=width=0
    for im in images:
        if x and x+im.width>4096: x=0;y+=row_h;row_h=0
        layout.append([x,y,im.width,im.height]); x+=im.width
        width=max(width,x);row_h=max(row_h,im.height)
    atlas=Image.new("RGBA",(width,y+row_h))
    for rect,im in zip(layout,images): atlas.paste(im,rect[:2])
    return compile_model(src, layout, atlas.size), atlas

def compile_model(src, layout, size):
    resolution=src["resolution"];w,h=resolution["width"],resolution["height"]
    bones=[];byid={};elements=[];tex=[]
    for i,(t,r) in enumerate(zip(src["textures"],layout)):
        tex.append({"name":t["name"],"uuid":t.get("uuid",str(i)),"rect":r,
                    "uv_size":[t.get("uv_width",w),t.get("uv_height",h)]})
    texture_ids={str(i):t["uuid"] for i,t in enumerate(tex)}
    for parent,node,is_cube,_ in tree(src):
        if not is_cube:
            name=node["name"];uid=node["uuid"]
            b={"name":name,"uuid":uid,"parent":parent["name"] if parent else None,
               "parent_id":parent["uuid"] if parent else None,"pivot":node.get("origin",ZERO),
               "rotation":node.get("rotation",ZERO),"visible":node.get("visibility",True),"cubes":[]}
            bones.append(b);byid[uid]=b;continue
        if node.get("type","cube")!="cube":raise ValueError("骨骼编辑器支持方块；遇到 "+node["type"])
        if parent is None:
            if "" not in byid:
                byid[""]={"name":"(根部方块)","uuid":"","parent":None,"pivot":ZERO,"rotation":ZERO,"visible":True,"cubes":[]};bones.append(byid[""])
            b=byid[""]
        else:b=byid[parent["uuid"]]
        a=node["from"];z=node["to"];pad=node.get("inflate",0)
        faces={};uvs={}
        for side,f in node.get("faces",{}).items():
            tid=f.get("texture")
            if tid is None:continue
            if isinstance(tid,str) and not tid.isdigit(): tid=next(i for i,t in enumerate(tex) if t["uuid"]==tid)
            i=int(tid); tx,ty,tw,th=layout[i]; uw,uh=tex[i]["uv_size"]
            u,v,U,V=f["uv"]
            if side in ("up","down"):u,v,U,V=U,V,u,v
            r=[u/uw,v/uh,U/uw,V/uh];face=SIDES[side];uvs[face]=r
            faces[face]={"texture":"#sheet","uv":[16*(tx+r[0]*tw)/size[0],16*(ty+r[1]*th)/size[1],
                16*(tx+r[2]*tw)/size[0],16*(ty+r[3]*th)/size[1]],"rotation":f.get("rotation",0)}
        aa=mirror_xz(a);zz=mirror_xz(z)
        elements.append({"name":b["name"]+"/"+node["name"],"uuid":node["uuid"],"bone":b["uuid"],
                         "from":[min(v,q)-pad for v,q in zip(aa,zz)],"to":[max(v,q)+pad for v,q in zip(aa,zz)],
                         "faces":faces,"local_uv":uvs,"pivot":node.get("origin",b["pivot"]),"turn":node.get("rotation",ZERO),
                         "visible":node.get("visibility",True)})
        b["cubes"].append({"name":node["name"],"uuid":node["uuid"],"from":a,"to":z,"rotation":node.get("rotation",ZERO),
                           "pivot":node.get("origin",b["pivot"]),"uv":node.get("uv_offset",[0,0]),
                           "faces":{side:{"uv":list(f["uv"]),"rotation":f.get("rotation",0),"texture":texture_ids.get(str(f.get("texture")),f.get("texture"))} for side,f in node.get("faces",{}).items()},
                           "box_uv":node.get("box_uv",src["meta"].get("box_uv",False))})
    clips=[{"name":a["name"],"uuid":a["uuid"],"duration_ms":round(1000*a.get("length",0),6),"loop":a.get("loop","once")} for a in src.get("animations",[])]
    rig={"schema":SCHEMA,"name":src.get("name","Player"),"texture_size":[w,h],"face_coordinates":"texture_uv","textures":tex,"bones":bones,"clips":clips,"key_axes":"model" if modern(src) else "bedrock"}
    model={"name":rig["name"],"texture_size":list(size),"textures":{"sheet":"pixforge:rig/sheet"},"elements":elements,"player_rig":rig,"rig_source":pack(src)}
    return {**default_shapes(),"base":[],"model":model}

def restore_edit_view(shapes,size):
    model=shapes.get("model") or {}
    if "rig_source" in model and not model["player_rig"].get("face_coordinates"):
        rebuilt = compile_model(unpack(model["rig_source"]),[t["rect"] for t in model["player_rig"]["textures"]],size)
        return {**shapes,"model":rebuilt["model"]}
    # Older block presets stored only the Java unit cube and its original face layout.
    if (set(model)=={"textures","elements","texture_size"}
            and model["textures"]=={"atlas":"pixforge:block/new_texture","particle":"#atlas"}
            and len(model["elements"])==1):
        part=model["elements"][0]
        if (set(part)=={"name","from","to","faces"} and part["name"]=="六面方块"
                and part["from"]==[0,0,0] and part["to"]==[16,16,16]
                and all(set(f)=={"uv","texture"} for f in part["faces"].values())):
            from .project_setup import editable_block
            w,h=model["texture_size"]
            faces={side:{"uv":[n*k/16 for n,k in zip(f["uv"],(w,h,w,h))]} for side,f in part["faces"].items()}
            return {**shapes,"model":editable_block(w,h,faces)}
    return shapes

def read(path):
    return from_source(json.loads(path.read_text(encoding="utf-8-sig")),path.parent)

def exported(model,image):
    src=deepcopy(unpack(model["rig_source"]))
    for t,s in zip(src["textures"],model["player_rig"]["textures"]):
        x,y,w,h=s["rect"]; pix=image.crop((x,y,x+w,y+h))
        if atlas_image(t).tobytes()!=pix.tobytes(): t["source"]=embed(pix)
    return src

def block_geometry(model):
    """Translate the editable bind pose into Java block elements."""
    from .rig_components import I, add, sub, mv, mm, rot, tr, euler, clean
    frames={None:(I,ZERO,True)}
    for b in model["player_rig"]["bones"]:
        parent,offset,visible=frames[b.get("parent_id")]
        r=rot(mirror_xz(b["rotation"]));p=mirror_xz(b["pivot"])
        frames[b["uuid"]]=mm(parent,r),add(offset,mv(parent,sub(p,mv(r,p)))),visible and b["visible"]
    elements=[]
    for e in model["elements"]:
        parent,offset,visible=frames[e["bone"]]
        if not (visible and e["visible"]):continue
        p=mirror_xz(e["pivot"]);world=add(mv(parent,p),offset)
        r=mm(parent,rot(mirror_xz(e["turn"])))
        angles=euler(r);axes=[i for i,v in enumerate(angles) if abs(v)>1e-7]
        if len(axes)>1:
            raise ValueError(f'{e["name"]} 的静止旋转含多个轴，Java 方块的单个部件只支持一个旋转轴')
        shift=mv(tr(r),sub(world,p))
        part={"name":e["name"],"from":clean(add(e["from"],shift)),"to":clean(add(e["to"],shift)),"faces":deepcopy(e["faces"])}
        if axes:
            i=axes[0];part["rotation"]={"axis":"xyz"[i],"angle":angles[i],"origin":p}
        elements.append(part)
    return {"textures":dict(model["textures"]),"elements":elements}

def resize_atlas(model, layout, atlas):
    src=deepcopy(unpack(model["rig_source"]))
    for texture,(x,y,w,h) in zip(src["textures"],layout):
        texture["source"]=embed(atlas.crop((x,y,x+w,y+h)))
        texture.update(width=w,height=h)
    # Blockbench's UV resolution is independent from the bitmap's physical size.
    return compile_model(src,layout,atlas.size)["model"]

def resolve(rows,identity):
    rows=list(rows)
    for row in rows:
        if row["uuid"]==identity:return row
    hits=[r for r in rows if r.get("name")==identity]
    if len(hits)!=1:raise ValueError("名称不唯一或未找到，请使用 UUID："+str(identity))
    return hits[0]

def inspect(model,clip=None,bone=None,native=False,cube_ids=None):
    rig=model["player_rig"]
    if cube_ids is not None:
        parts={c["uuid"]:{**c,"bone":b["uuid"],"bone_name":b["name"]} for b in rig["bones"] for c in b["cubes"]}
        return {"cubes":[parts[i] for i in dict.fromkeys(cube_ids)],"textures":rig["textures"]}
    if clip is None:return {"rig":rig}
    src=unpack(model["rig_source"]);a=resolve(src.get("animations",[]),clip)
    if native:
        tracks={}
        for gid,an in a.get("animators",{}).items():
            if an.get("type","bone")!="bone":continue
            ch={}
            for k in an.get("keyframes",[]):
                if k["channel"] in CHANNELS:ch.setdefault(k["channel"],[]).append(k)
            tracks[gid]={c:sorted(ks,key=lambda k:k["time"]) for c,ks in ch.items()}
        return {"tracks":tracks}
    if bone is None:return {"clip":a}
    b=resolve(rig["bones"],bone);return {"bone":b,"clip":a["name"],"animator":a.get("animators",{}).get(b["uuid"],{})}

def find_key(keys,op):
    if op.get("uuid"):return resolve(keys,op["uuid"])
    tm=op.get("from_time_ms",op["time_ms"])/1000
    return next((k for k in keys if k["channel"]==op.get("channel","rotation") and abs(k["time"]-tm)<1e-7),None)

def edit(model,operations):
    src=deepcopy(unpack(model["rig_source"]));tex=model["player_rig"]["textures"]
    for op in operations:
        what=op["op"]; groups={}; cubes={}; locations={};parents={}
        for p,n,is_cube,container in tree(src):
            uid=n["uuid"]; (cubes if is_cube else groups)[uid]=n
            locations[uid]=container;parents[uid]=p["uuid"] if p else None
        if what in ("transform_cubes","face_uv"):
            from .rig_components import transform,face_uv
            if what=="transform_cubes":transform(op["cube_ids"],cubes,groups,parents,op)
            else:face_uv(op["cube_ids"],cubes,op)
            continue
        clips=src.setdefault("animations",[])
        if what=="clip":
            hit=next((a for a in clips if op["name"] in (a["name"],a["uuid"])),None)
            if hit is None:
                hit={"name":op["name"],"uuid":str(uuid4()),"length":2,"animators":{},"loop":"loop","snapping":24};clips.append(hit)
            if "duration_ms" in op:hit["length"]=op["duration_ms"]/1000
            if "loop" in op:hit["loop"]=("loop" if op["loop"] else "once") if isinstance(op["loop"],bool) else op["loop"]
            if "rename" in op:hit["name"]=op["rename"]
            continue
        if what=="delete_clip":clips.remove(resolve(clips,op["name"]));continue
        if what=="add_texture":
            src["textures"].append({"name":op["name"],"uuid":str(uuid4()),"id":str(len(src["textures"])),"source":op["source"],
                                    "internal":True,"mode":"bitmap","uv_width":src["resolution"]["width"],"uv_height":src["resolution"]["height"]})
            continue
        if what=="texture":
            t=resolve(src["textures"],op["texture"])
            if "rename" in op:t["name"]=op["rename"]
            if "source" in op:t["source"]=op["source"]
            continue
        gid=op["bone"]
        if what=="bone" and not any(gid in (r["name"],r["uuid"]) for r in groups.values()):
            b={"name":gid,"uuid":str(uuid4()),"children":[],"origin":op.get("pivot",ZERO)}
            parent=resolve(groups.values(),op["parent"]) if op.get("parent") else None
            children=child_list(src,parent["uuid"] if parent else None)
            if "groups" in src:
                children.append({"uuid":b["uuid"],"children":[]});b.pop("children");src["groups"].append(b)
            else:children.append(b)
        else:b=resolve(groups.values(),gid)
        uid=b["uuid"]
        if what=="bone":
            if "parent" in op and uid in locations:
                dest=resolve(groups.values(),op["parent"])["uuid"] if op["parent"] else None
                if dest!=parents[uid]:
                    ancestors=dest
                    while ancestors is not None:
                        if ancestors==uid:raise ValueError("骨骼不能成为自己的后代")
                        ancestors=parents[ancestors]
                    old=locations[uid];item=next(n for n in old if (n if isinstance(n,str) else n["uuid"])==uid)
                    old.remove(item);child_list(src,dest).append(item)
            for k,d in (("pivot","origin"),("rotation","rotation"),("visible","visibility"),("rename","name")):
                if k in op:b[d]=op[k]
            if "rename" in op:
                for a in clips:
                    if uid in a.get("animators",{}):a["animators"][uid]["name"]=b["name"]
        elif what=="delete_bone":
            dead={uid}
            for i,p in parents.items():
                if p in dead:dead.add(i)
            locations[uid][:]=[n for n in locations[uid] if (n if isinstance(n,str) else n["uuid"])!=uid]
            src["elements"][:]=[e for e in src["elements"] if e["uuid"] not in dead]
            if "groups" in src:src["groups"][:]=[g for g in src["groups"] if g["uuid"] not in dead]
            for a in clips:
                for i in dead:a.get("animators",{}).pop(i,None)
        elif what in ("cube","delete_cube","face_texture"):
            children=[e for i,e in cubes.items() if parents[i]==uid]
            ident=op.get("cube_id",op.get("name"))
            if what=="cube" and not any(ident in (e["uuid"],e["name"]) for e in children):
                e={"uuid":str(uuid4()),"name":op["name"],"from":op["from"],"to":op["to"],"type":"cube","box_uv":True,"uv_offset":[0,0],"faces":{}}
                src["elements"].append(e);child_list(src,uid).append(e["uuid"])
            else:e=resolve(children,ident)
            if what=="delete_cube":src["elements"].remove(e);locations[e["uuid"]].remove(e["uuid"]);continue
            if what=="face_texture":
                t=resolve(src["textures"],op["texture"])
                for f in op.get("faces",e["faces"]):e["faces"][f]["texture"]=src["textures"].index(t)
                continue
            for k,d in (("from","from"),("to","to"),("pivot","origin"),("rotation","rotation"),("rename","name"),("mirror","mirror_uv"),("inflate","inflate"),("visible","visibility")):
                if k in op:e[d]=op[k]
            if "uv" in op:e.update(uv_offset=op["uv"],box_uv=True)
            if "faces" in op:
                e["box_uv"]=False
                for side,f in op["faces"].items():e["faces"][side]={**e["faces"].get(side,{"texture":0}),**f}
            elif e.get("box_uv",src["meta"].get("box_uv")) and ("uv" in op or "from" in op or "to" in op or "mirror" in op):
                for face,f in face_pixels({"from":e["from"],"to":e["to"],"uv":e.get("uv_offset",[0,0]),"mirror":e.get("mirror_uv",False)}).items():
                    e["faces"][face]={**e["faces"].get(face,{"texture":0}),**f}
        elif what in ("key","delete_key"):
            a=resolve(clips,op["clip"]);an=a.setdefault("animators",{}).setdefault(uid,{"name":b["name"],"type":"bone","keyframes":[]})
            keys=an.setdefault("keyframes",[]);k=find_key(keys,op)
            if what=="delete_key":
                if k is not None:keys.remove(k)
                continue
            channel=op.get("channel","rotation")
            if channel not in CHANNELS:raise ValueError("选择 rotation、position 或 scale")
            dest=op["time_ms"]/1000
            if any(other is not k and other["channel"]==channel and abs(other["time"]-dest)<1e-7 for other in keys):raise ValueError("该时刻已有关键帧")
            if k is None:
                k={"uuid":str(uuid4()),"time":dest,"channel":channel,"interpolation":"linear","data_points":[dict.fromkeys("xyz",1 if channel=="scale" else 0)]};keys.append(k)
            k["time"]=dest
            if dest>a.get("length",0):a["length"]=dest
            if "value" in op:k["data_points"][op.get("point",0)].update(zip("xyz",op["value"]))
            if "axis" in op:k["data_points"][op.get("point",0)][op["axis"]]=op["axis_value"]
            if "easing" in op or "interpolation" in op:
                style=op.get("interpolation",op.get("easing"));k["interpolation"]="step" if style=="hold" else style
            for field in ("bezier_left_time","bezier_left_value","bezier_right_time","bezier_right_value","bezier_linked","data_points"):
                if field in op:k[field]=op[field]
        else:raise ValueError("未知骨骼操作："+what)
    return src
