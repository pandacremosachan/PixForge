"""Shared lossless frame packing for manual editing and direct animation preparation."""
from PIL import Image
from .document import StudioError, playback


def repack_frames(canvas, rectangles, order, *, complete=True):
    width, height = rectangles[0][2:]
    count = len(order)
    if not 1 <= count <= 4096:
        raise StudioError("帧数量须为 1..4096")
    columns = next((n for n in range(1, min(count, 4096 // width) + 1)
                    if (not complete or count % n == 0) and ((count + n - 1) // n) * height <= 4096), None)
    if columns is None:
        raise StudioError("新图集超出画布尺寸上限；请减少帧数或帧尺寸")
    candidate = canvas.clone()
    candidate.w, candidate.h = columns * width, ((count + columns - 1) // columns) * height
    packed = [[i % columns * width, i // columns * height, width, height] for i in range(count)]
    for layer in candidate.layers:
        image = Image.new("RGBA", (candidate.w, candidate.h))
        for i, old in enumerate(order):
            if old is not None:
                x, y, w, h = rectangles[old]
                image.paste(layer.img.crop((x, y, x + w, y + h)), packed[i][:2])
        layer.img = image
    return candidate, packed


def prepare_frames(document, settings):
    """Retain existing cels/layers and duplicate the first cel into added slots, in one undo step."""
    document.guard(observed=False)
    fields = {"frame_count", "frame_size", "steps", "loop", "interpolation"}
    if not isinstance(settings, dict) or set(settings) - fields:
        raise StudioError("动画分帧设置使用 frame_count/frame_size/steps/loop/interpolation")
    size = settings.get("frame_size", document.animation["frame_size"])
    if size != document.animation["frame_size"]:
        raise StudioError("源帧尺寸须与当前工程一致")
    count = settings.get("frame_count")
    old = document.animation["rectangles"]
    if type(count) is not int or not len(old) <= count <= 4096:
        raise StudioError("frame_count 须保留现有源帧，且不超过 4096")
    w, h = size
    expected = {(x, y, w, h) for y in range(0, document.canvas.h, h) for x in range(0, document.canvas.w, w)}
    occupied = set(map(tuple, old))
    if (document.canvas.w % w or document.canvas.h % h or len(occupied) != len(old) or not occupied <= expected):
        raise StudioError("动画分帧要求规则、不重叠的帧")
    for x, y, rw, rh in expected - occupied:
        if any(any(layer.img.crop((x, y, x + rw, y + rh)).tobytes()) for layer in document.canvas.layers):
            raise StudioError("未分配区域仍有像素；请先明确帧布局")
    order = [*range(len(old)), *([0] * (count - len(old)))]
    candidate, rectangles = repack_frames(document.canvas, old, order, complete=False)
    plan = playback({"frame_size": size, "rectangles": rectangles,
        "steps": settings.get("steps", [{"frame": i, "duration_ms": 100} for i in range(count)]),
        "loop": settings.get("loop", document.animation["loop"]),
        "interpolation": settings.get("interpolation", document.animation["interpolation"])}, (candidate.w, candidate.h))
    from .scene_program import validate_binding
    validate_binding(document.scene_animation, plan)
    from .material_data import remap
    material = remap(document.material_data, old, order, rectangles, (candidate.w, candidate.h))
    before, previous = document.snapshot(), document.art_digest()
    from .protocol import Executor
    document.executor, document.animation = Executor(candidate), plan
    document.animation_source, document.material_data = None, material
    if previous != document.art_digest():
        document.remember(before)
        document.changed("准备动画源帧与时序", previous)
    return {"source_frame_count": count, "retained_source_frames": len(old),
            "duplicated_seed_frames": count - len(old), "atlas_size": [candidate.w, candidate.h]}
