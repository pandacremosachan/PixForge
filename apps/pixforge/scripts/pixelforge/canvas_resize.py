"""Change the resolution shown in the footer: one frame, or every frame of a sheet."""
from PIL import Image

from .canvas import Canvas, Layer
from .document import StudioError, playback
from .protocol import Executor


def _scale_edge(position, old, new):
    # Shared edges must land on the same pixel, including non-square frames.
    return (2 * position * new + old) // (2 * old)


def resize(document, width, height):
    document.guard(observed=False)
    if any(type(n) is not int or not 1 <= n <= 4096 for n in (width, height)):
        raise StudioError("画布宽高须为 1 到 4096 之间的整数")
    old_w, old_h = document.animation["frame_size"]
    if (width, height) == (old_w, old_h):
        return
    model = document.shapes.get("model") or {}
    if (model.get("name") in ("player_skin_classic", "player_skin_slim")
            and model.get("textures", {}).get("skin") == "pixforge:entity/player_skin"):
        raise StudioError("原版玩家皮肤的画布固定为 64 × 64 px")

    def x(v): return _scale_edge(v, old_w, width)
    def y(v): return _scale_edge(v, old_h, height)

    old = document.canvas
    sheet = (x(old.w), y(old.h))
    if max(sheet) > 4096:
        raise StudioError(f"每帧 {width} × {height} 会得到 {sheet[0]} × {sheet[1]} 的图集；图集每边最多 4096 px")
    sources = document.animation["rectangles"]
    rectangles = [[x(left), y(top), width, height] for left, top, _, _ in sources]
    plan = playback({**document.animation, "frame_size": [width, height], "rectangles": rectangles}, sheet)
    # Regular atlases resize in one pass. Align the sampled edges of offset cels as well.
    offsets = [((left, top, left+w, top+h), (x(left), y(top)))
               for left, top, w, h in sources if left % old_w or top % old_h]

    def resample(image):
        result = image.resize(sheet, Image.Resampling.NEAREST)
        for box, origin in offsets:
            result.paste(image.crop(box).resize((width, height), Image.Resampling.NEAREST), origin)
        return result

    candidate = Canvas(*sheet, layers=[Layer(l.name, *sheet, resample(l.img), l.visible) for l in old.layers])
    candidate.active_index, candidate.mirror = old.active_index, old.mirror
    candidate.palette.chars = old.palette.chars.copy()
    material = document.material_data
    if material is not None:
        from .material_data import pack, unpack
        material = {**material, "maps": {role: pack(resample(unpack(row))) for role, row in material["maps"].items()}}

    shapes = document.shapes
    if "rig_source" in model:
        from .rig_studio import resize_atlas
        old_layout = [t["rect"] for t in model["player_rig"]["textures"]]
        layout = [[x(a), y(b), x(a+w)-x(a), y(b+h)-y(b)] for a, b, w, h in old_layout]
        if any(w < 1 or h < 1 for _, _, w, h in layout):
            raise StudioError("这个尺寸会使模型中的一张贴图小于 1 像素，请选择较大的尺寸")
        shapes = {**shapes, "model": resize_atlas(model, layout, candidate.composite())}
    elif "texture_size" in model and "player_rig" not in model:
        shapes = {**shapes, "model": {**model, "texture_size": [width, height]}}

    previous = document.art_digest()
    document.remember(document.snapshot(old))
    document.executor, document.animation = Executor(candidate), plan
    document.material_data, document.shapes = material, shapes
    document.animation_source = None
    document.changed(f"画布尺寸 {old_w} × {old_h} → {width} × {height} px", previous)
