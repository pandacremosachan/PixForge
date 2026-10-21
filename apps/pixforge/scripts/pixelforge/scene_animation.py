"""Bounded, deterministic scene animation shared by native preview and adapters.

Positions use Java model units (16 = one block), time uses milliseconds, and
velocities use units/second. This describes an offline preview, not a mod install.
"""
from copy import deepcopy
import math

SCHEMA = "pixelforge.scene-animation/v1"
ADVANCED_SCHEMA = "pixelforge.scene-animation/v2"
DEFAULT_TARGET = {"loader": "forge", "minecraft": "1.20.1"}


def capabilities():
    return {"schema": ADVANCED_SCHEMA, "supported_schemas": [SCHEMA, ADVANCED_SCHEMA], "default": "static unless explicitly requested",
            "target": deepcopy(DEFAULT_TARGET), "combinable": ["texture", "parts", "particles"],
            "parts": ["rotate", "translate", "scale"], "particles": ["alpha", "additive"],
            "keyframes": ["hold", "linear", "smooth", "ease_in", "ease_out"],
            "states": ["named clips", "start/stop events", "automatic next state", "entry pose inheritance", "particle carry", "process preview"],
            "unsupported": ["custom GLSL shaders", "skeletal animation", "automatic game installation"],
            "units": "Java model units; 16 units/block; velocities units/second; time milliseconds",
            "loop": "closed keyframes or periodic channels; integer full rotation turns; seeded particle births; states may be nonlooping",
            "limits": {"tracks": 64, "emitters": 16, "live_particles": 2048, "states": 16, "keys_per_channel": 128, "total_keys": 4096}}


def integration(scene):
    from .scene_program import all_entries
    target = deepcopy(scene["target"])
    forge = target == DEFAULT_TARGET
    return {"status":"offline_preview_only", "target":target, "installed_in_game":False,
            "model_units_per_block":16, "milliseconds_per_tick":50,
            "parts": {"elements":sorted({i for t in all_entries(scene,"transforms") for i in t["elements"]}),
                      "suggested_hook":"BlockEntityRenderer.render / PoseStack" if forge else "project renderer adapter required"},
            "particles": {"emitters":[e["id"] for e in all_entries(scene,"emitters")],
                          "suggested_hook":"client ParticleProvider / RegisterParticleProvidersEvent" if forge else "project particle adapter required"},
            "states": [{"id":s["id"],"label":s["label"],"next":s["next"]} for s in scene.get("states",[])],
            "requires_project_binding":["mod namespace and resource ids", "BlockEntityType and renderer registration",
                                        "client particle type/provider and sprite resources", "working-state synchronization and activation"],
            "preview_differences":["untextured color particle billboards", "no world collision or wind",
                                   "no custom shaders or Minecraft lighting", "additive blending needs a matching game RenderType"],
            "references":["https://docs.minecraftforge.net/en/1.20.x/blockentities/ber/",
                          "https://docs.minecraftforge.net/en/1.20.1/gameeffects/particles/"] if forge else []}


def normalize(value, model):
    from .document import StudioError
    def fail(message):
        raise StudioError(message, "INVALID_SCENE_ANIMATION")
    def num(v, name, low=-4096, high=4096):
        if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
            fail(name+" 超出有限数值范围")
        return v
    def integer(v, name, low, high):
        if type(v) is not int or not low <= v <= high:
            fail(name+" 须为范围内整数")
        return v
    def vector(v, name, low=-4096, high=4096, count=3):
        if not isinstance(v, list) or len(v) != count:
            fail(name+" 须为 "+str(count)+" 维数组")
        return [num(n, name, low, high) for n in v]
    def keys(v, allowed):
        if not isinstance(v, dict) or set(v)-set(allowed):
            fail("场景包含未知字段或非对象值")
    if value is None:
        return None
    if isinstance(value,dict) and value.get("schema") == ADVANCED_SCHEMA and "states" in value:
        from .scene_program import normalize_program
        return normalize_program(value,model)
    advanced = isinstance(value,dict) and value.get("schema") == ADVANCED_SCHEMA
    keys(value, ("schema", "duration_ms", "loop", "seed", "target", "transforms", "emitters") + (("texture",) if advanced else ()))
    if value.get("schema", SCHEMA) not in (SCHEMA,ADVANCED_SCHEMA):
        fail("不支持的场景动画格式")
    duration = num(value.get("duration_ms"), "duration_ms", 100, 120000)
    loop = value.get("loop", True)
    if type(loop) is not bool:
        fail("loop 须为布尔值")
    target = value.get("target", DEFAULT_TARGET)
    keys(target, ("loader", "minecraft"))
    if any(not isinstance(target.get(k), str) or not 1 <= len(target[k]) <= 80 for k in DEFAULT_TARGET):
        fail("target 须明确 loader 与 minecraft 版本")
    elements = (model or {}).get("elements", [])
    transforms, emitters = value.get("transforms", []), value.get("emitters", [])
    if not isinstance(transforms, list) or len(transforms) > 64 or not isinstance(emitters, list) or len(emitters) > 16:
        fail("至多 64 条部件轨道、16 个发射器")
    if not transforms and not emitters and not advanced:
        fail("场景动画须含部件运动或粒子发射器")
    used, tracks, effects = set(), [], []
    def identity(row):
        v = row.get("id")
        if not isinstance(v, str) or not v.strip() or len(v) > 100 or v in used:
            fail("场景轨道 id 须为唯一的非空文字")
        used.add(v)
        return v
    for track in transforms:
        keys(track, ("id", "type", "elements", "pivot", "axis", "turns", "amplitude", "cycles", "phase_deg") + (("keyframes","entry") if advanced else ()))
        ids = track.get("elements")
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            fail("部件轨道须指定不重复的真实模型 element 索引")
        ids = [integer(i, "element", 0, len(elements)-1) for i in ids]
        kind = track.get("type")
        row = {"id": identity(track), "type": kind, "elements": ids,
               "pivot": vector(track.get("pivot", [8,8,8]), "pivot"),
               "phase_deg": num(track.get("phase_deg", 0), "phase_deg", -360, 360)}
        if kind not in ("rotate","translate","scale"):
            fail("部件轨道 type 使用 rotate/translate/scale")
        if advanced:
            mode = track.get("entry","absolute")
            if mode not in ("absolute","relative","from_current") or (mode == "relative" and kind != "rotate"):
                fail("entry 使用 absolute/from_current；旋转另支持 relative")
            if mode == "from_current" and "keyframes" not in track:
                fail("from_current 仅用于关键帧轨道")
            row["entry"] = mode
        if "keyframes" in track:
            from .scene_curves import normalize_keys
            if set(track) & {"turns","amplitude","cycles"} or row["phase_deg"] != 0:
                fail("关键帧值不与 turns/amplitude/cycles/phase_deg 混用")
            row["keyframes"] = normalize_keys(track["keyframes"],duration,dimensions=0 if kind == "rotate" else 3,
                low=.05 if kind == "scale" else -23040 if kind == "rotate" else -256,
                high=8 if kind == "scale" else 23040 if kind == "rotate" else 256,loop=loop,rotation=kind == "rotate")
            if kind == "rotate":
                axis = vector(track.get("axis",[0,1,0]),"axis",-1,1)
                magnitude = math.sqrt(sum(n*n for n in axis))
                if magnitude < 1e-9:fail("旋转轴不可为零")
                row["axis"] = axis if abs(magnitude-1)<1e-12 else [n/magnitude for n in axis]
            elif "axis" in track:
                fail("位移与缩放不使用 axis")
        elif kind == "rotate":
            if set(track) & {"amplitude", "cycles"}:
                fail("rotate 使用 axis/turns")
            axis = vector(track.get("axis", [0,1,0]), "axis", -1, 1)
            size = math.sqrt(sum(n*n for n in axis))
            turns = integer(track.get("turns", 1), "turns", -64, 64)
            if size < 1e-9 or turns == 0:
                fail("旋转轴与圈数不可为零")
            row.update(axis=axis if abs(size-1)<1e-12 else [n/size for n in axis], turns=turns)
        elif kind in ("translate", "scale"):
            if set(track) & {"axis", "turns"}:
                fail("translate/scale 使用 amplitude/cycles")
            amp = vector(track.get("amplitude"), "amplitude", -.95 if kind == "scale" else -256,
                         .95 if kind == "scale" else 256)
            if not any(amp):
                fail("位移或缩放幅度不可全零")
            row.update(amplitude=amp, cycles=integer(track.get("cycles", 1), "cycles", 1, 64))
        else:
            fail("部件轨道 type 使用 rotate/translate/scale")
        tracks.append(row)
    budget = 0
    for emitter in emitters:
        keys(emitter, ("id", "position", "direction", "spread", "speed", "gravity", "lifetime_ms",
                       "count_per_cycle", "size", "color", "blend", "anchor_element") + (("emission",) if advanced else ()))
        direction = vector(emitter.get("direction", [0,1,0]), "direction", -1, 1)
        length = math.sqrt(sum(n*n for n in direction))
        if length < 1e-9:
            fail("粒子初速度方向不可为零")
        life = num(emitter.get("lifetime_ms", min(1000,duration)), "lifetime_ms", 10, duration)
        count = integer(emitter.get("count_per_cycle", 80), "count_per_cycle", 1, 1024)
        size = vector(emitter.get("size", [.5,0]), "size", 0, 16, 2)
        if not any(size):
            fail("粒子尺寸不可全零")
        colors = emitter.get("color", [[100,190,255,220],[100,190,255,0]])
        if not isinstance(colors, list) or len(colors) != 2:
            fail("color 为起止 RGBA 数组")
        colors = [vector(c, "RGBA", 0, 255, 4) for c in colors]
        if not any(c[3] for c in colors):
            fail("粒子起止 alpha 不可全零")
        blend = emitter.get("blend", "alpha")
        if blend not in ("alpha", "additive"):
            fail("blend 使用 alpha/additive")
        anchor = emitter.get("anchor_element")
        if anchor is not None:
            integer(anchor, "anchor_element", 0, len(elements)-1)
        effects.append({"id": identity(emitter), "position": vector(emitter.get("position", [8,16,8]), "position"),
                        "direction": direction if abs(length-1)<1e-12 else [n/length for n in direction], "spread": vector(emitter.get("spread", [0,0,0]), "spread", 0, 2),
                        "speed": num(emitter.get("speed", 8), "speed", 0, 256),
                        "gravity": vector(emitter.get("gravity", [0,-16,0]), "gravity", -256, 256),
                        "lifetime_ms": life, "count_per_cycle": count, "size": size, "color": colors,
                        "blend": blend, "anchor_element": anchor})
        if advanced:
            from .scene_curves import normalize_keys
            effects[-1]["emission"] = normalize_keys(emitter.get("emission",[{"time_ms":0,"value":1},{"time_ms":duration,"value":1}]),duration,low=0,high=1)
        budget += math.ceil(count*life/duration)+1
    if budget > 2048:
        fail("同时存活粒子超过 2048，请减少发射数量或寿命")
    result = {"schema": ADVANCED_SCHEMA if advanced else SCHEMA, "duration_ms": duration, "loop": loop,
            "seed": integer(value.get("seed", 1), "seed", 0, 2147483647),
            "target": deepcopy(target), "transforms": tracks, "emitters": effects}
    if advanced:
        texture = value.get("texture",{"mode":"play","speed":1})
        keys(texture,("mode","speed","frame"))
        mode = texture.get("mode","play")
        if mode not in ("play","hold") or (mode == "hold" and "speed" in texture) or (mode == "play" and "frame" in texture):
            fail("状态材质使用 play/speed 或 hold/可选 frame")
        result["texture"] = {"mode":mode}
        if mode == "play":result["texture"]["speed"] = num(texture.get("speed",1),"texture.speed",0,8)
        elif "frame" in texture:result["texture"]["frame"] = integer(texture["frame"],"texture.frame",0,4095)
    return result


def _add(a,b): return [x+y for x,y in zip(a,b)]
def _sub(a,b): return [x-y for x,y in zip(a,b)]
def _mul(a,s): return [x*s for x in a]
def _length(a): return math.sqrt(sum(x*x for x in a))


def _clip_transform(scene, element, point, time_ms, *, normal=False, view=None):
    from .scene_curves import track_value
    from .scene_program import clip_moment
    p = list(point)
    for track in scene["transforms"]:
        if element not in track["elements"]:
            continue
        phase = track["phase_deg"]*math.pi/180
        t = time_ms/scene["duration_ms"]
        pivot = [0,0,0] if normal else track["pivot"]
        advanced = "entry" in track or "keyframes" in track
        value = track_value(track,scene["duration_ms"],clip_moment(scene,time_ms),
                            (view or {}).get("entry_values"), (view or {}).get("first_cycle",True) and 0 <= time_ms < scene["duration_ms"]) if advanced else None
        if track["type"] == "rotate":
            p = _sub(p,pivot)
            a = value*math.pi/180 if advanced else phase+2*math.pi*track["turns"]*t
            axis, c, s = track["axis"], math.cos(a), math.sin(a)
            dot = sum(x*y for x,y in zip(axis,p))
            cross = [axis[1]*p[2]-axis[2]*p[1],axis[2]*p[0]-axis[0]*p[2],axis[0]*p[1]-axis[1]*p[0]]
            p = _add(pivot,[p[i]*c+cross[i]*s+axis[i]*dot*(1-c) for i in range(3)])
        else:
            wave = math.sin(phase+2*math.pi*track.get("cycles",1)*t)
            amp = track.get("amplitude",[0,0,0])
            if track["type"] == "translate":
                if not normal:
                    p = _add(p,value if advanced else _mul(amp,wave))
            else:
                scales = value if advanced else [1+a*wave for a in amp]
                p = [pivot[i]+(p[i]-pivot[i])*(1/scales[i] if normal else scales[i]) for i in range(3)]
    if normal:
        length = _length(p)
        p = _mul(p,1/length) if length else p
    return p


def transform(scene, element, point, time_ms, *, normal=False, view=None, state=None):
    from .scene_program import resolve
    clip,actual = resolve(scene,time_ms,view,state)
    return _clip_transform(clip,element,point,actual["time_ms"],normal=normal,view=actual)


def _random(seed):
    seed &= 0xffffffff
    seed ^= seed >> 16
    seed = seed*0x7feb352d & 0xffffffff
    seed ^= seed >> 15
    seed = seed*0x846ca68b & 0xffffffff
    seed ^= seed >> 16
    return seed/4294967296


def _clip_particles(scene, time_ms, view=None):
    from .scene_curves import curve
    if scene is None:
        return []
    duration = scene["duration_ms"]
    advanced = scene["schema"] == ADVANCED_SCHEMA
    t = time_ms if advanced and scene["loop"] else time_ms % duration if scene["loop"] else min(duration,max(0,time_ms))
    result = []
    for ei,e in enumerate(scene["emitters"]):
        spacing = duration/e["count_per_cycle"]
        last = math.floor(t/spacing+1e-10)
        first = math.floor((t-e["lifetime_ms"])/spacing)+1
        for birth in range(first,last+1):
            if not scene["loop"] and (birth < 0 or birth >= e["count_per_cycle"]):
                continue
            if advanced and birth < 0 and not (view or {}).get("prewarm",scene["loop"]):
                continue
            age_ms = t-birth*spacing
            if not 0 <= age_ms < e["lifetime_ms"]:
                continue
            identity = birth % e["count_per_cycle"]
            seed = (scene["seed"]+ei*1000003+identity*9176)&0xffffffff
            if advanced:
                at = (birth*spacing)%duration if scene["loop"] else birth*spacing
                intensity = curve(e["emission"],at)
                if intensity <= 0 or (intensity < 1 and _random(seed ^ 0x9e3779b9) >= intensity):
                    continue
            direction = [e["direction"][i]+(2*_random(seed+i*374761393)-1)*e["spread"][i] for i in range(3)]
            length = _length(direction)
            direction = _mul(direction,1/length) if length > 1e-9 else e["direction"]
            origin = e["position"]
            if e["anchor_element"] is not None:
                end = _clip_transform(scene,e["anchor_element"],_add(origin,direction),birth*spacing,view=view)
                origin = _clip_transform(scene,e["anchor_element"],origin,birth*spacing,view=view)
                direction = _sub(end,origin)
                direction = _mul(direction,1/_length(direction))
            age, ratio = age_ms/1000, age_ms/e["lifetime_ms"]
            result.append({"emitter":e["id"], "birth_id":identity, "age_ms":age_ms,
                           "position":[origin[i]+direction[i]*e["speed"]*age+.5*e["gravity"][i]*age*age for i in range(3)],
                           "size":e["size"][0]*(1-ratio)+e["size"][1]*ratio,
                           "color":[a*(1-ratio)+b*ratio for a,b in zip(*e["color"])], "blend":e["blend"],
                           "_velocity":[direction[i]*e["speed"]+e["gravity"][i]*age for i in range(3)],
                           "_gravity":list(e["gravity"]),"_remaining_ms":e["lifetime_ms"]-age_ms,
                           "_end_size":e["size"][1],"_end_color":list(e["color"][1])})
    return result


def _public_particles(values):
    return [{k:v for k,v in p.items() if not k.startswith("_")} for p in values]


def particles(scene, time_ms, view=None, state=None):
    if scene is None:
        return []
    from .scene_program import resolve, carry_particles
    clip,actual = resolve(scene,time_ms,view,state)
    return _public_particles((_clip_particles(clip,actual["time_ms"],actual)+carry_particles(actual.get("carry",[]),actual["time_ms"]))[:2048])


def sample(scene, model, time_ms, view=None, state=None):
    from .scene_program import resolve, clip_moment, carry_particles, is_program, texture_control
    clip,actual = resolve(scene,time_ms,view,state)
    posed = []
    t = clip_moment(clip,actual["time_ms"])
    pose_time = actual["time_ms"] if clip["schema"] == ADVANCED_SCHEMA else t
    for element in range(len((model or {}).get("elements",[]))):
        posed.append({"element":element, "origin":_clip_transform(clip,element,[0,0,0],pose_time,view=actual),
                      "basis":[_clip_transform(clip,element,p,pose_time,view=actual) for p in ([1,0,0],[0,1,0],[0,0,1])]})
    result = {"time_ms":t, "parts":posed,"particles":_public_particles((_clip_particles(clip,actual["time_ms"],actual)+carry_particles(actual.get("carry",[]),actual["time_ms"]))[:2048])}
    if is_program(scene):
        result.update(scene_state=clip["id"],state_label=clip["label"],texture=texture_control(scene,time_ms,actual))
    return result


def point_bounds(scene, element, lo, hi):
    from .shape_preview import vertices
    from .scene_program import all_entries, channel_ranges
    lo,hi = list(lo),list(hi)
    ranges = channel_ranges(scene)
    for track in all_entries(scene,"transforms"):
        if element not in track["elements"]:
            continue
        pivot = track["pivot"]
        if track["type"] == "rotate":
            r = max(math.dist(p,pivot) for p in vertices(lo,hi))
            lo,hi = [p-r for p in pivot],[p+r for p in pivot]
        elif track["type"] == "translate":
            lower,upper = ranges[track["id"]]
            lo,hi = [a+b for a,b in zip(lo,lower)],[a+b for a,b in zip(hi,upper)]
        else:
            lower,upper = ranges[track["id"]]
            for i in range(3):
                a,b = lo[i]-pivot[i],hi[i]-pivot[i]
                values = [a*lower[i],a*upper[i],b*lower[i],b*upper[i]]
                lo[i],hi[i] = pivot[i]+min(values),pivot[i]+max(values)
    return lo,hi


def point_sphere(scene, element, lo, hi):
    """Bound a whole transform chain without reboxing a sphere at each joint.

    A rotation sweeps the center around its axis while preserving the existing
    radius. Its enclosing sphere adds only that center's orbit radius. In
    particular, rotations about the same joint never multiply the radius.
    Full orbits also cover relative rotation and inherited state entry poses.
    """
    from .scene_program import all_entries, channel_ranges
    center = [(a+b)/2 for a,b in zip(lo,hi)]
    radius = math.dist(lo,hi)/2
    ranges = channel_ranges(scene)
    for track in all_entries(scene,"transforms"):
        if element not in track["elements"]:
            continue
        pivot = track["pivot"]
        if track["type"] == "rotate":
            axis = track["axis"]
            offset = _sub(center,pivot)
            along = sum(a*b for a,b in zip(axis,offset))
            projected = _add(pivot,[a*along for a in axis])
            radius += math.dist(center,projected)
            center = projected
        elif track["type"] == "translate":
            lower,upper = ranges[track["id"]]
            center = [v+(a+b)/2 for v,a,b in zip(center,lower,upper)]
            radius += math.dist(lower,upper)/2
        else:
            lower,upper = ranges[track["id"]]
            offset = _sub(center,pivot)
            center = [p+v*(a+b)/2 for p,v,a,b in zip(pivot,offset,lower,upper)]
            variation = [v*(b-a)/2 for v,a,b in zip(offset,lower,upper)]
            radius = radius*max(abs(v) for v in (*lower,*upper))+_length(variation)
    return center,radius


def camera_bounds(scene, shapes, lo, hi):
    """Stable conservative view sphere; gameplay/export AABBs stay separate."""
    from .shape_preview import mesh
    from .scene_program import clips
    initial_lo,initial_hi = list(lo),list(hi)
    spheres = []
    by_element = {}
    for face in mesh(shapes["model"]):
        by_element.setdefault(face["element"],[]).extend(face["vertices"])
    for element,points in by_element.items():
        a = [min(p[i] for p in points) for i in range(3)]
        b = [max(p[i] for p in points) for i in range(3)]
        spheres.append(point_sphere(scene,element,a,b))
    for clip in clips(scene):
        for e in clip["emitters"]:
            origin,radius = (list(e["position"]),0) if e["anchor_element"] is None else point_sphere(scene,e["anchor_element"],e["position"],e["position"])
            life = e["lifetime_ms"]/1000
            radius += e["speed"]*life+_length(e["gravity"])*.5*life*life+max(e["size"])/2
            spheres.append((origin,radius))
    for center,radius in spheres:
        lo = [min(a,c-radius) for a,c in zip(lo,center)]
        hi = [max(a,c+radius) for a,c in zip(hi,center)]
    center = [(a+b)/2 for a,b in zip(lo,hi)]
    # Fit the spheres themselves, rather than the corners of their outer boxes.
    from .shape_preview import vertices
    radius = max(1,*(math.dist(p,center) for p in vertices(initial_lo,initial_hi)),
                 *(math.dist(c,center)+r for c,r in spheres))
    return center,radius


def bounds(scene, shapes, lo, hi):
    from .shape_preview import mesh
    from .scene_program import clips
    lo,hi = list(lo),list(hi)
    def include(a,b):
        for i in range(3):
            lo[i],hi[i] = min(lo[i],a[i]),max(hi[i],b[i])
    faces = mesh(shapes["model"])
    for element in range(len((shapes["model"] or {}).get("elements",[]))):
        points = [p for f in faces if f["element"] == element for p in f["vertices"]]
        if points:
            a,b = [min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]
            include(*point_bounds(scene,element,a,b))
    for e in (e for clip in clips(scene) for e in clip["emitters"]):
        a,b = (list(e["position"]),list(e["position"])) if e["anchor_element"] is None else point_bounds(scene,e["anchor_element"],e["position"],e["position"])
        life = e["lifetime_ms"]/1000
        for i in range(3):
            a[i] -= e["speed"]*life+max(e["size"])/2+max(0,-e["gravity"][i])*.5*life*life
            b[i] += e["speed"]*life+max(e["size"])/2+max(0,e["gravity"][i])*.5*life*life
        include(a,b)
    return lo,hi


def analyze(scene, model):
    from .document import StudioError
    from .scene_program import is_program
    if is_program(scene):
        return analyze_program(scene,model)
    duration = scene["duration_ms"]
    samples = [sample(scene,model,duration*i/131) for i in range(132)]
    rows = []
    advanced = scene["schema"] == ADVANCED_SCHEMA
    for track in scene["transforms"]:
        # Include noncentral points so a stationary pivot does not mask rotation.
        values = [tuple(round(c,8) for eid in track["elements"] for p in ([0,0,0],[1,0,0],[0,1,0],[0,0,1])
                        for c in transform(scene,eid,p,duration*i/131)) for i in range(132)]
        if len(set(values)) < 2:
            if advanced:
                rows.append({"id":track["id"],"mechanism":"parts","sampled_motion":False,"intentional_hold":True})
                continue
            raise StudioError("部件轨道组合后无实际运动："+track["id"], "ANIMATION_TRACK_STATIC")
        rows.append({"id":track["id"], "mechanism":"parts", "sampled_motion":True})
    for e in scene["emitters"]:
        visible = sum(sum(p["emitter"] == e["id"] and p["size"] > 0 and p["color"][3] > 0 for p in s["particles"]) for s in samples)
        if not visible:
            if advanced:
                rows.append({"id":e["id"],"mechanism":"particles","visible_samples":0,"disabled":True})
                continue
            raise StudioError("发射器未产生可见粒子："+e["id"], "ANIMATION_TRACK_STATIC")
        signatures = {tuple(sorted(tuple(round(c,8) for c in p["position"]+[p["size"]]+p["color"])
                                    for p in s["particles"] if p["emitter"] == e["id"] and p["size"]>0 and p["color"][3]>0)) for s in samples}
        if len(signatures)<2:
            raise StudioError("发射器仅产生静止、无渐变的重复粒子："+e["id"], "ANIMATION_TRACK_STATIC")
        rows.append({"id":e["id"], "mechanism":"particles", "visible_samples":visible})
    if not any(r.get("sampled_motion") or r.get("visible_samples",0) for r in rows):
        raise StudioError("关键帧场景只有保持姿态，未产生实际动画","ANIMATION_TRACK_STATIC")
    return {"passed":True, "duration_ms":duration, "tracks":rows, "scene_schema":SCHEMA,
            "target":deepcopy(scene["target"]), "integration":integration(scene), "loop_continuity_requires_visual_inspection":scene["loop"],
            "not_human_approval":True, "not_aesthetic_or_game_validation":True}


def analyze_program(scene,model):
    from .document import StudioError
    from .scene_program import all_entries
    cases = []
    states = []
    for clip in scene["states"]:
        duration = clip["duration_ms"]
        times = {duration*i/16 for i in range(17)}
        for track in clip["transforms"]:
            keys = track.get("keyframes",[])
            times.update(k["time_ms"] for k in keys)
            times.update((a["time_ms"]+b["time_ms"])/2 for a,b in zip(keys,keys[1:]))
        for e in clip["emitters"]:
            times.update(k["time_ms"] for k in e["emission"])
        frames = [sample(scene,model,t,state=clip["id"]) for t in sorted(times)]
        cases.extend(frames)
        states.append({"id":clip["id"],"label":clip["label"],"duration_ms":duration,"loop":clip["loop"],
                       "next":clip["next"],"sampled_frames":len(frames),"visible_particles":max(len(s["particles"]) for s in frames)})
    cases.extend(sample(scene,model,scene["duration_ms"]*i/64) for i in range(65))
    rows = []
    for track in all_entries(scene,"transforms"):
        signatures = {tuple(round(n,8) for p in s["parts"] if p["element"] in track["elements"]
                            for row in [p["origin"]]+p["basis"] for n in row) for s in cases}
        moving = len(signatures)>1
        rows.append({"id":track["id"],"mechanism":"parts","sampled_motion":moving,"intentional_hold":not moving})
    for e in all_entries(scene,"emitters"):
        signatures = {tuple(tuple(round(n,8) for n in p["position"]+[p["size"]]+p["color"])
                            for p in s["particles"] if p["emitter"]==e["id"] and p["size"]>0 and p["color"][3]>0) for s in cases}
        visible = sum(sum(p["emitter"]==e["id"] and p["size"]>0 and p["color"][3]>0 for p in s["particles"]) for s in cases)
        rows.append({"id":e["id"],"mechanism":"particles","visible_samples":visible,
                     "sampled_motion":visible>0 and len(signatures)>1,"disabled":not visible})
    if not any(r.get("sampled_motion") for r in rows):
        raise StudioError("全部状态均为静止或关闭效果，没有实际动画","ANIMATION_TRACK_STATIC")
    return {"passed":True,"duration_ms":scene["duration_ms"],"tracks":rows,"states":states,
            "transitions":deepcopy(scene["transitions"]),"scene_schema":scene["schema"],"target":deepcopy(scene["target"]),
            "integration":integration(scene),"loop_continuity_requires_visual_inspection":True,
            "state_switches_inherit_pose_and_inflight_particles":True,"not_human_approval":True,"not_aesthetic_or_game_validation":True}
