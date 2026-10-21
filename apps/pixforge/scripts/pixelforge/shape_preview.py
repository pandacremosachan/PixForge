"""Deterministic model/shape overlay renderer and portable interactive review. Pillow only."""
import base64
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from .shapes import effective, report

NORMALS = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
           "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}
SHADES = {"up": 1, "down": .5, "north": .82, "south": .82, "west": .66, "east": .66}
COLORS = {"base": "#ffca68", "collision": "#ff678b", "selection": "#62e5ff"}
EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def vertices(start, end):
    x, y, z = start
    X, Y, Z = end
    return [(x, y, z), (X, y, z), (X, Y, z), (x, Y, z), (x, y, Z), (X, y, Z), (X, Y, Z), (x, Y, Z)]


def rotate(point, rotation, normal=False):
    if not rotation:
        return point
    origin = (0, 0, 0) if normal else rotation["origin"]
    p = [a - b for a, b in zip(point, origin)]
    axis = "xyz".index(rotation["axis"])
    angle = math.radians(rotation["angle"])
    c, s = math.cos(angle), math.sin(angle)
    if rotation.get("rescale") and not normal:
        p = [n if i == axis else n / c for i, n in enumerate(p)]
    a, b = ((1, 2), (2, 0), (0, 1))[axis]
    p[a], p[b] = c * p[a] - s * p[b], s * p[a] + c * p[b]
    return [a + b for a, b in zip(p, origin)]


def mesh(model):
    output = []
    if model is None:
        return output
    for element_index, element in enumerate(model["elements"]):
        x, y, z = element["from"]
        X, Y, Z = element["to"]
        quads = {"north": [(X,Y,z),(X,y,z),(x,y,z),(x,Y,z)], "south": [(x,Y,Z),(x,y,Z),(X,y,Z),(X,Y,Z)],
                 "west": [(x,Y,z),(x,y,z),(x,y,Z),(x,Y,Z)], "east": [(X,Y,Z),(X,y,Z),(X,y,z),(X,Y,z)],
                 "up": [(x,Y,z),(x,Y,Z),(X,Y,Z),(X,Y,z)], "down": [(x,y,Z),(x,y,z),(X,y,z),(X,y,Z)]}
        defaults = {"down": [x,16-Z,X,16-z], "up": [x,z,X,Z], "north": [16-X,16-Y,16-x,16-y],
                    "south": [x,16-Y,X,16-y], "west": [z,16-Y,Z,16-y], "east": [16-Z,16-Y,16-z,16-y]}
        for face, data in element["faces"].items():
            a, b, c, d = data.get("uv", defaults[face])
            uv = [(a/16,b/16),(a/16,d/16),(c/16,d/16),(c/16,b/16)]
            shift = data.get("rotation", 0) // 90
            uv = uv[shift:] + uv[:shift]
            rotation = element.get("rotation")
            output.append({"element":element_index, "vertices": [rotate(p, rotation) for p in quads[face]], "uv": uv,
                           "normal": rotate(NORMALS[face], rotation, True),
                           "shade": SHADES[face] if element.get("shade", True) else 1})
    return output


def camera(shapes, size, yaw, pitch, scene=None):
    yaw, pitch = map(math.radians, (yaw, pitch))
    right = (math.cos(yaw), 0, -math.sin(yaw))
    up = (-math.sin(pitch)*math.sin(yaw), math.cos(pitch), -math.sin(pitch)*math.cos(yaw))
    depth = (math.cos(pitch)*math.sin(yaw), math.sin(pitch), math.cos(pitch)*math.cos(yaw))
    points = [p for t in ("base", "collision", "selection") for b in effective(shapes, t) for p in vertices(b["from"], b["to"])]
    points += [p for face in mesh(shapes["model"]) for p in face["vertices"]]
    if not points:
        points = vertices([0,0,0], [16,16,16])
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    if scene is not None:
        from .scene_animation import camera_bounds
        center,radius = camera_bounds(scene,shapes,lo,hi)
    else:
        center = [(a+b)/2 for a,b in zip(lo, hi)]
        radius = max(math.dist(lo, hi)/2, 1)
    scale = (size-50)/(2*radius)
    def project(point):
        v = [a-b for a,b in zip(point, center)]
        return (size/2+sum(a*b for a,b in zip(v,right))*scale,
                size/2-sum(a*b for a,b in zip(v,up))*scale, sum(a*b for a,b in zip(v,depth)))
    return project, depth, {"center": center, "radius": radius}


def render(shapes, texture, *, size=400, yaw=35, pitch=30, overlays=("collision", "selection"), show_model=True, scene=None, time_ms=0, annotate=True, scene_view=None, scene_state=None):
    if type(size) is not int or not 128 <= size <= 800:
        raise ValueError("形状预览尺寸须为 128..800")
    if any(type(n) not in (int,float) or not math.isfinite(n) for n in (yaw,pitch)):
        raise ValueError("视角须为有限数值")
    if not isinstance(overlays, (tuple,list)) or any(t not in COLORS for t in overlays):
        raise ValueError("叠加层须为 base/collision/selection")
    project, depth, bounds = camera(shapes, size, yaw, pitch, scene)
    faces = mesh(shapes["model"])
    if scene is not None:
        from .scene_animation import transform, particles, _length
        from .scene_animation import sample as sample_scene
        from .scene_program import resolve
        clip,actual = resolve(scene,time_ms,scene_view,scene_state)
        t = actual["time_ms"]
        faces = [{**f, "vertices":[transform(clip,f["element"],p,t,view=actual) for p in f["vertices"]],
                  "normal":transform(clip,f["element"],f["normal"],t,normal=True,view=actual)} for f in faces]
    out = Image.new("RGBA", (size,size), "#141b25")
    pixels, source = out.load(), texture.convert("RGBA").load()
    tw, th = texture.size
    depths = [-math.inf]*(size*size)
    if show_model:
        for face in faces:
            if sum(a*b for a,b in zip(face["normal"],depth)) <= 1e-9:
                continue
            p = [project(v) for v in face["vertices"]]
            for tri in ((0,1,2),(0,2,3)):
                a,b,c = [p[i] for i in tri]
                ta,tb,tc = [face["uv"][i] for i in tri]
                den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den)<1e-9:
                    continue
                for iy in range(max(0,math.floor(min(a[1],b[1],c[1]))), min(size,math.ceil(max(a[1],b[1],c[1])))):
                    for ix in range(max(0,math.floor(min(a[0],b[0],c[0]))), min(size,math.ceil(max(a[0],b[0],c[0])))):
                        u = ((b[1]-c[1])*(ix+.5-c[0])+(c[0]-b[0])*(iy+.5-c[1]))/den
                        v = ((c[1]-a[1])*(ix+.5-c[0])+(a[0]-c[0])*(iy+.5-c[1]))/den
                        w = 1-u-v
                        if min(u,v,w)<-1e-8:
                            continue
                        z = u*a[2]+v*b[2]+w*c[2]
                        if z < depths[iy*size+ix]-1e-8:
                            continue
                        tx = math.floor((u*ta[0]+v*tb[0]+w*tc[0])*tw) % tw
                        ty = math.floor((u*ta[1]+v*tb[1]+w*tc[1])*th) % th
                        color = source[tx,ty]
                        if not color[3]:
                            continue
                        rgb = tuple(round(n*face["shade"]) for n in color[:3])
                        old = pixels[ix,iy]
                        alpha = color[3]/255
                        pixels[ix,iy] = tuple(round(n*alpha+o*(1-alpha)) for n,o in zip(rgb,old[:3]))+(255,)
                        depths[iy*size+ix]=z
    if scene is not None:
        scale=(size-50)/(2*bounds["radius"])
        for p in sorted(particles(scene,time_ms,view=actual),key=lambda p:sum(a*b for a,b in zip(p["position"],depth))):
            x,y,z=project(p["position"]);half=p["size"]*scale/2;alpha=p["color"][3]/255
            if half<=0 or alpha<=0:continue
            for iy in range(max(0,math.ceil(y-half-.5)),min(size,math.ceil(y+half-.5))):
                for ix in range(max(0,math.ceil(x-half-.5)),min(size,math.ceil(x+half-.5))):
                    if z<depths[iy*size+ix]-1e-8:continue
                    old=pixels[ix,iy]
                    pixels[ix,iy]=tuple(max(0,min(255,round(p["color"][c]*alpha+old[c]*(1 if p["blend"]=="additive" else 1-alpha)))) for c in range(3))+(255,)
    draw = ImageDraw.Draw(out)
    if show_model and texture.getbbox() is None:
        for face in faces:
            if sum(a*b for a, b in zip(face["normal"], depth)) <= 1e-9:
                continue
            pts = [project(v) for v in face["vertices"]]
            draw.line([p[:2] for p in pts] + [pts[0][:2]], fill="#99b0cd", width=1)
    # X-ray outlines intentionally include hidden edges; toggles separate coincident shapes.
    for target in overlays:
        for item in effective(shapes,target):
            pts = [project(v) for v in vertices(item["from"],item["to"])]
            for a,b in EDGES:
                draw.line([pts[a][:2],pts[b][:2]],fill=COLORS[target],width=2 if target=="selection" else 1)
    if annotate:
        draw.text((12,12), "MODEL + SHAPES / offline preview",fill="#cbd7e5")
    for i,target in enumerate(overlays):
        draw.text((12,size-18*(len(overlays)-i)),target+" ("+str(len(effective(shapes,target)))+")",fill=COLORS[target])
    return out


def html(shapes, canvas, animation, metadata, scene=None):
    images = []
    image = canvas.composite()
    for x,y,w,h in animation["rectangles"]:
        stream = io.BytesIO()
        image.crop((x,y,x+w,y+h)).save(stream,format="PNG")
        images.append("data:image/png;base64,"+base64.b64encode(stream.getvalue()).decode("ascii"))
    _, _, bounds = camera(shapes, 520, 35, 30, scene)
    data = {"shapes": {t: effective(shapes,t) for t in COLORS}, "mesh": mesh(shapes["model"]),
            "images": images,"plan":animation, "colors":COLORS,"edges":EDGES, "bounds":bounds,
            "report":report(shapes),"metadata":metadata,"scene":scene}
    template = Path(__file__).with_name("shape_review.html").read_text(encoding="utf-8")
    return template.replace("/*SCENE_RUNTIME*/", Path(__file__).with_name("scene_runtime.js").read_text(encoding="utf-8")).replace("/*DATA*/null",json.dumps(data,ensure_ascii=False,allow_nan=False).replace("<","\\u003c"))
