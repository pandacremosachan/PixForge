"""Minecraft 1.20.1 atlas timing, authored independently of machine instance clocks."""
from copy import deepcopy
import base64
import io
import math
from PIL import Image, ImageDraw
from .document import StudioError, playback

CAPABILITY = "minecraft-animation/v1"


def metadata_plan(metadata, size):
    if not isinstance(metadata, dict) or not isinstance(metadata.get("animation"), dict):
        raise StudioError(".mcmeta 须包含 animation 对象", "INVALID_ANIMATION_METADATA")
    raw = metadata["animation"]
    if set(raw)-{"width", "height", "frametime", "frames", "interpolate"}:
        raise StudioError("未知 animation 字段；不会静默丢弃动画规则")
    for key in ("width", "height", "frametime"):
        if key in raw and (type(raw[key]) is not int or not 1 <= raw[key] <= 2_147_483_647):
            raise StudioError(key+" 须为正整数")
    iw, ih = size
    fw, fh = raw.get("width"), raw.get("height")
    if fw is None and fh is None: fw = fh = min(iw, ih)
    else: fw, fh = fw if fw is not None else iw, fh if fh is not None else ih
    if iw % fw or ih % fh or fw > iw or fh > ih:
        raise StudioError(".mcmeta 帧宽高须整除 PNG 尺寸")
    count = iw//fw*(ih//fh)
    frames = raw.get("frames", [])
    if not isinstance(frames, list) or len(frames) > 10000:
        raise StudioError("frames 须为至多 10000 步的数组")
    if type(raw.get("interpolate", False)) is not bool:
        raise StudioError("interpolate 须为布尔值")
    steps = []
    for frame in frames or list(range(count)):
        if isinstance(frame, dict):
            if set(frame)-{"index", "time"}: raise StudioError("帧对象只包含 index/time")
            index, duration = frame.get("index"), frame.get("time", raw.get("frametime", 1))
        else: index, duration = frame, raw.get("frametime", 1)
        if type(index) is not int or not 0 <= index < count or type(duration) is not int or not 1 <= duration <= 2_147_483_647:
            raise StudioError(".mcmeta 帧索引越界或 tick 时长无效")
        steps.append({"frame": index, "duration_ms": duration*50})
    plan = playback({"frame_size": [fw, fh], "steps": steps, "loop": True,
                     "provenance": "Minecraft 1.20.1 .mcmeta; 50 ms/tick"}, size)
    return plan, {"interpolate": raw.get("interpolate", False)}


def to_metadata(plan, interpolate=False):
    if not plan["loop"]: raise StudioError("原版图集动画必定循环；单次动画使用机器实例播放器")
    steps = []
    for step in plan["steps"]:
        ticks = step["duration_ms"]/50
        if not math.isfinite(ticks) or ticks < 1 or ticks > 2_147_483_647 or abs(ticks-round(ticks)) > 1e-9:
            raise StudioError(".mcmeta 时长须为 50 ms 的正整数倍，不进行量化")
        steps.append({"index": step["frame"], "time": round(ticks)})
    return {"animation": {"width": plan["frame_size"][0], "height": plan["frame_size"][1],
                          "interpolate": interpolate, "frames": steps}}


def enabled(document):
    return bool((document.minecraft_project or {}).get("texture_animation", {}).get("interpolate", False))


def sample(image, plan, time_ms, interpolate=False, held=None):
    if type(time_ms) not in (int, float) or not math.isfinite(time_ms) or time_ms < 0:
        raise StudioError("动画时间须为非负有限毫秒数")
    elapsed = int(time_ms//50)*50 if interpolate else time_ms
    total = sum(s["duration_ms"] for s in plan["steps"])
    elapsed = elapsed % total if plan["loop"] else min(elapsed, total)
    index = len(plan["steps"])-1
    for i, step in enumerate(plan["steps"]):
        if elapsed < step["duration_ms"]: index = i; break
        elapsed -= step["duration_ms"]
    step = plan["steps"][index]; frame = step["frame"] if held is None else held
    def crop(n):
        x, y, w, h = plan["rectangles"][n]; return image.crop((x, y, x+w, y+h))
    result = crop(frame)
    next_frame = plan["steps"][(index+1) % len(plan["steps"])]["frame"]
    if interpolate and held is None and elapsed and next_frame != frame and (plan["loop"] or index+1 < len(plan["steps"])):
        delta = 1-min(1, elapsed/step["duration_ms"]); other = crop(next_frame)
        result.putdata([tuple(int(delta*a[c]+(1-delta)*b[c]) for c in range(3))+(a[3],)
                        for a,b in zip(result.getdata(),other.getdata())])
    return result, {"frame": frame, "step": index, "next_frame": next_frame,
                    "step_elapsed_ms": elapsed, "interpolate": interpolate, "tick": int(time_ms//50)}


def expanded(document):
    """Bake finite tick RGB samples for instance-controlled BER textures, no global atlas clock."""
    if getattr(document,'_material_role',None):
        from .material_data import expanded_map
        return expanded_map(document._material_source,document._material_role,document._material_plan)
    plan, image = document.animation, document.canvas.composite()
    if not enabled(document):
        return [image.crop((x,y,x+w,y+h)) for x,y,w,h in plan["rectangles"]], deepcopy(plan)
    to_metadata(plan, True)
    ticks = sum(round(s["duration_ms"]/50) for s in plan["steps"])
    material_factor=1+len((getattr(document,'material_data',None) or {}).get('maps',{}))
    if ticks > 4096 or ticks*math.prod(plan["frame_size"])*material_factor > 16_777_216:
        raise StudioError("实例插值烘焙超过 4096 tick / 16M 像素预算，请减少帧时长或尺寸")
    # Original indices remain valid for per-state texture hold(frame), including
    # source frames absent from the looping sequence. Append only new RGB samples.
    frames = [image.crop((x,y,x+w,y+h)) for x,y,w,h in plan["rectangles"]]
    lookup, steps = {}, []
    material_images={}
    if getattr(document,'material_data',None):
        from .material_data import unpack
        material_images={role:unpack(row) for role,row in sorted(document.material_data['maps'].items())}
    def key(frame,at=None,index=None):
        values=[frame.tobytes()]
        for image in material_images.values():
            if index is not None:
                x,y,w,h=plan['rectangles'][index];values.append(image.crop((x,y,x+w,y+h)).tobytes())
            else:values.append(sample(image,plan,at,True)[0].tobytes())
        return tuple(values)
    for index, frame in enumerate(frames):lookup.setdefault(key(frame,index=index), index)
    for t in range(ticks):
        frame, _ = sample(image, plan, t*50, True); raw = key(frame,at=t*50)
        if raw not in lookup:
            if (len(frames)+1)*math.prod(plan["frame_size"])*material_factor > 16_777_216:
                raise StudioError("实例插值纹理（含未播放的原始帧）超过 16M 像素预算")
            lookup[raw] = len(frames); frames.append(frame)
        index = lookup[raw]
        if steps and steps[-1]["frame"] == index: steps[-1]["duration_ms"] += 50
        else: steps.append({"frame": index, "duration_ms": 50})
    return frames, {**deepcopy(plan), "steps": steps, "rectangles": [[0,i*plan["frame_size"][1],*plan["frame_size"]] for i in range(len(frames))]}


def inspect(document, metadata=None, time_ms=0):
    if metadata is None:
        plan, options = document.animation, {"interpolate": enabled(document)}
    else: plan, options = metadata_plan(metadata, (document.canvas.w, document.canvas.h))
    output = to_metadata(plan, options["interpolate"])
    image, position = sample(document.canvas.composite(), plan, time_ms, **options)
    stream = io.BytesIO(); image.save(stream, format="PNG")
    return {"schema": "pixforge.minecraft-animation/v1", "plan": plan, "metadata": output,
            "texture_animation": options, "sample": position, "period_ticks": sum(s["time"] for s in output["animation"]["frames"]),
            "image_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
            "clock": "shared atlas; machine activation requires per-BlockEntity instance player",
            "alpha_rule": "interpolate RGB at whole game ticks; preserve current frame alpha"}
