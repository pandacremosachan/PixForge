"""Shared native/nearest/background/tile/frame evidence for CLI and MCP edits."""
from .texture_review import animation_preview, preview_sheet


def render_canvas(canvas, *, scale=6, tile=False, backgrounds=("checker",), before=None, frame_height=None):
    if canvas is None:
        raise ValueError("no canvas: run 'new W H' first")
    if type(scale) is not int or not 1 <= scale <= 16:
        raise ValueError("preview scale must be 1..16")
    if not backgrounds or any(value not in ("checker", "light", "dark") for value in backgrounds):
        raise ValueError("preview backgrounds must be checker/light/dark")
    backgrounds = tuple(dict.fromkeys(backgrounds))
    image = canvas.composite()
    if frame_height is not None:
        if type(frame_height) is not int or frame_height < 1 or image.height % frame_height:
            raise ValueError("frame height must be positive and divide the strip height")
        if before is not None:
            raise ValueError("before/after comparison is for static previews")
        frames = [image.crop((0, y, image.width, y + frame_height)) for y in range(0, image.height, frame_height)]
        return animation_preview(frames, None, scale, backgrounds, tiled=tile)[0]
    return preview_sheet(image, None, scale, tile, before=before, backgrounds=backgrounds)
