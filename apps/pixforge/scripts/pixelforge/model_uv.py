"""Read-only model-face to atlas mapping. UV guides never become artwork pixels."""
import math

from .document import StudioError


DIRECTIONS = {
    "down": "下（局部 −Y）", "up": "上（局部 +Y）",
    "north": "北（局部 −Z）", "south": "南（局部 +Z）",
    "west": "西（局部 −X）", "east": "东（局部 +X）",
}


def _default_uv(element, direction):
    x, y, z = element["from"]
    X, Y, Z = element["to"]
    return {
        "down": [x, 16-Z, X, 16-z], "up": [x, z, X, Z],
        "north": [16-X, 16-Y, 16-x, 16-y], "south": [x, 16-Y, X, 16-y],
        "west": [z, 16-Y, Z, 16-y], "east": [16-Z, 16-Y, 16-z, 16-y],
    }[direction]


def _intervals(a, b, size):
    """Continuous wrapped intervals, preserving zero-width UV sampling."""
    lo, hi = sorted((a, b))
    if hi-lo >= size:
        return [[0, size]]
    start = lo % size
    end = start + hi-lo
    if end <= size:
        return [[start, end]]
    return [[0, end-size], [start, size]]


def _texels(interval, size):
    lo, hi = interval
    first = min(size-1, math.floor(lo))
    end = min(size, max(first+1, math.ceil(hi)))
    return first, end


def describe(model, frame_size):
    """Map actual element faces; no model means no inferred cube or guessed UV."""
    width, height = frame_size
    result = {
        "schema": "pixelforge.model-uv/v1", "frame_size": [width, height],
        "uv_units": 16, "coordinates": "pixel rectangles are frame-local [x,y,width,height]; end exclusive",
        "direction_space": "element-local; element_rotation changes world-facing direction",
        "sampling": "nearest texel; UV outside 0..16 wraps within the active frame",
        "model_present": model is not None, "element_count": 0,
        "faces": [], "regions": [], "shared_region_count": 0,
    }
    if not model:
        return result
    result["element_count"] = len(model.get("elements", []))
    groups = {}
    textures = model.get("textures", {})
    for index, element in enumerate(model.get("elements", [])):
        for direction in DIRECTIONS:
            if direction not in element.get("faces", {}):
                continue
            definition = element["faces"][direction]
            uv = definition.get("uv", _default_uv(element, direction))
            u0, v0, u1, v1 = uv
            corners = [[u0, v0], [u0, v1], [u1, v1], [u1, v0]]
            shift = definition.get("rotation", 0)//90
            corners = corners[shift:] + corners[:shift]
            xs = _intervals(u0*width/16, u1*width/16, width)
            ys = _intervals(v0*height/16, v1*height/16, height)
            bounds = [[a, c, b-a, d-c] for a, b in xs for c, d in ys]
            pixel_rects = []
            for a, b in xs:
                left, right = _texels([a, b], width)
                for c, d in ys:
                    top, bottom = _texels([c, d], height)
                    pixel_rects.append([left, top, right-left, bottom-top])
            # Identical coverage shares a region even when rotation/mirroring differs.
            key = tuple(tuple(rect) for rect in bounds)
            if key not in groups:
                group = {"id": f"R{len(groups)+1:02d}", "bounds": bounds,
                         "pixel_rects": pixel_rects, "face_ids": [], "face_count": 0}
                groups[key] = group
                result["regions"].append(group)
            group = groups[key]
            reference = definition.get("texture", "")
            texture = reference
            visited = set()
            while texture.startswith("#") and texture not in visited:
                visited.add(texture)
                texture = textures.get(texture[1:], texture)
            face_id = f"element:{index}/{direction}"
            result["faces"].append({
                "id": face_id, "element_index": index,
                "element_name": element.get("name", f"部件 {index+1}"),
                "direction": direction, "direction_label": DIRECTIONS[direction],
                "uv": uv, "uv_explicit": "uv" in definition,
                "rotation": definition.get("rotation", 0),
                "uv_corners": corners,
                "pixel_corners": [[u*width/16, v*height/16] for u, v in corners],
                "corner_order": "face vertices: top-left, bottom-left, bottom-right, top-right before UV rotation",
                "element_rotation": element.get("rotation"),
                "texture_reference": reference, "texture": texture,
                "region_id": group["id"],
            })
            group["face_ids"].append(face_id)
            group["face_count"] += 1
    result["shared_region_count"] = sum(g["face_count"] > 1 for g in result["regions"])
    return result


def query(document, *, frame=None, x=None, y=None):
    frame = document.view_frame if frame is None else frame
    rectangles = document.animation["rectangles"]
    if type(frame) is not int or not 0 <= frame < len(rectangles):
        raise StudioError("UV 查询帧索引超出范围")
    ox, oy, width, height = rectangles[frame]
    result = describe(document.shapes.get("model"), [width, height])
    result["frame"] = frame
    result["atlas_frame_rect"] = [ox, oy, width, height]
    if x is not None or y is not None:
        if type(x) is not int or type(y) is not int or not (ox <= x < ox+width and oy <= y < oy+height):
            raise StudioError("UV 查询 x/y 须为当前帧内的画布像素整数坐标")
        local_x, local_y = x-ox, y-oy
        regions = [g for g in result["regions"] if any(
            a <= local_x < a+w and b <= local_y < b+h for a, b, w, h in g["pixel_rects"])]
        ids = {i for g in regions for i in g["face_ids"]}
        result["point"] = {"atlas": [x, y], "frame_local": [local_x, local_y],
                           "region_ids": [g["id"] for g in regions],
                           "faces": [f for f in result["faces"] if f["id"] in ids],
                           "unmapped": not ids}
    return result
