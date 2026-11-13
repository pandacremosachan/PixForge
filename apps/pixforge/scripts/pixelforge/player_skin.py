"""Modern Minecraft player atlas, viewed facing +Z (the player's right is −X)."""

SIZE = 64
BASE_COLORS = {"head": "#cf997c", "body": "#477779", "right_arm": "#cf997c",
               "left_arm": "#cf997c", "right_leg": "#414d60", "left_leg": "#414d60"}

# Names are relative to the wearer. The coordinates come from the project's
# actual face UVs: neither the workbench nor the skill maintains a second atlas.
PARTS = {
    "head": ("头", "hat", "帽子", "#da9e72"),
    "body": ("躯干", "jacket", "外套", "#70bdb1"),
    "right_arm": ("右臂", "right_sleeve", "右袖", "#7ca5d5"),
    "left_arm": ("左臂", "left_sleeve", "左袖", "#b198d5"),
    "right_leg": ("右腿", "right_pants", "右裤腿", "#c5ac73"),
    "left_leg": ("左腿", "left_pants", "左裤腿", "#d998ac"),
}
FACES = {"up": ("top", "顶"), "down": ("bottom", "底"),
         "west": ("right", "右"), "south": ("front", "前"),
         "east": ("left", "左"), "north": ("back", "后")}


def describe_atlas(model, mapping):
    """Attach semantic addresses to a built-in player atlas; a bare PNG has no arm type."""
    arm = {"player_skin_classic": "classic", "player_skin_slim": "slim"}.get(model.get("name"))
    if not arm or mapping["frame_size"] != [SIZE, SIZE] or model.get("textures", {}).get("skin") != "pixforge:entity/player_skin":
        return
    regions = {r["id"]: r for r in mapping["regions"]}
    parts = {}
    for i, face in enumerate(mapping["faces"]):
        name = face["element_name"]
        p = name.removesuffix("_outer")
        if p not in PARTS:
            continue
        title, toggle, accessory, color = PARTS[p]
        part = parts.setdefault(p, {"label": title, "overlay": toggle, "overlay_label": accessory, "guide_color": color,
                                    "base": {"faces": {}}, "outer": {"faces": {}}})
        layer = "base" if name == p else "outer"
        group = part[layer]
        side, short = FACES[face["direction"]]
        region = regions[face["region_id"]]
        rect = region["pixel_rects"][0]
        group["faces"][side] = rect
        face_label = {"front": "正面", "back": "背面"}.get(side, short+"面")
        face["skin"] = {"part": p, "layer": layer, "face": side, "rect": rect, "short_label": short,
                        "label": f"{title} · {accessory if layer == 'outer' else '基础层'} · {face_label}"}
        region["skin_face_index"] = i
    for part in parts.values():
        for layer in ("base", "outer"):
            rects = part[layer]["faces"].values()
            if rects:
                part[layer]["origin"] = [min(r[i] for r in rects) for i in (0, 1)]
        base = part["base"]["faces"]
        if "front" in base and "top" in base:
            part["dimensions_whd"] = [base["front"][2], base["front"][3], base["top"][3]]
    mapping["player_skin"] = {"schema": "pixforge.player-skin-atlas/v1", "arm_model": arm,
                              "arm_width": 3 if arm == "slim" else 4, "size": [SIZE, SIZE],
                              "coordinates": "[x,y,width,height]; x right, y down from top left; sides are the wearer's",
                              "parts": parts}


def preview_layers(atlas, layout, hidden, frames):
    """Apply Java's clothing switches to a composited preview image only."""
    for part in layout["parts"].values():
        if part["overlay"] in hidden:
            for ox, oy, _, _ in frames:
                for x, y, w, h in part["outer"]["faces"].values():
                    atlas.paste((0, 0, 0, 0), (ox+x, oy+y, ox+x+w, oy+y+h))


def model(arm_model):
    width, drop = {"classic": (4, 0), "slim": (3, .5)}[arm_model]
    # Part, lower corner, width/height/depth, base UV, outer UV, outer inflation.
    parts = (
        ("head", (4, 24, 4), (8, 8, 8), (0, 0), (32, 0), .5),
        ("body", (4, 12, 6), (8, 12, 4), (16, 16), (16, 32), .25),
        ("right_arm", (4-width, 12-drop, 6), (width, 12, 4), (40, 16), (40, 32), .25),
        ("left_arm", (12, 12-drop, 6), (width, 12, 4), (32, 48), (48, 48), .25),
        ("right_leg", (4.1, 0, 6), (4, 12, 4), (0, 16), (0, 32), .25),
        ("left_leg", (7.9, 0, 6), (4, 12, 4), (16, 48), (0, 48), .25),
    )
    elements = []
    for outer in (False, True):
        for name, origin, size, base_uv, outer_uv, thickness in parts:
            w, h, d = size
            u, v = outer_uv if outer else base_uv
            pad = thickness if outer else 0
            a, b, c, end = u+d, u+d+w, u+2*d+w, u+2*d+2*w
            top, foot = v+d, v+d+h
            rects = {"up": (a, v, b, top), "down": (b, top, b+w, v),
                     "west": (u, top, a, foot), "south": (a, top, b, foot),
                     "east": (b, top, c, foot), "north": (c, top, end, foot)}
            elements.append({"name": name + ("_outer" if outer else ""),
                             "from": [p-pad for p in origin],
                             "to": [p+n+pad for p, n in zip(origin, size)],
                             "faces": {face: {"texture": "#skin", "uv": [x*16/SIZE for x in rect]}
                                       for face, rect in rects.items()}})
    return {"name": f"player_skin_{arm_model}", "texture_size": [SIZE, SIZE],
            "textures": {"skin": "pixforge:entity/player_skin"}, "elements": elements}


def layers(canvas, skin_model, image=None):
    """New skins have opaque base faces. Imported skin pixels retain their atlas positions."""
    base = canvas.active
    base.name = "base"
    if image is not None:
        base.img = image.copy()
    canvas.add_layer("outer")
    outer = canvas.active.img
    for part in skin_model["elements"]:
        is_outer = part["name"].endswith("_outer")
        for face in part["faces"].values():
            x, y, X, Y = (round(t * SIZE/16) for t in face["uv"])
            rect = min(x, X), min(y, Y), max(x, X), max(y, Y)
            if is_outer and image is not None:
                outer.paste(image.crop(rect), rect)
                base.img.paste((0, 0, 0, 0), rect)
            elif not is_outer and image is None:
                base.img.paste(BASE_COLORS[part["name"]], rect)
    canvas.use_layer("base")
