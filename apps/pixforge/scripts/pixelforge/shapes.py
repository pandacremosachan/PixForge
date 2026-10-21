"""Shared AABB shapes, embedded Java block models and explicit game adapters. No Qt."""
from copy import deepcopy
import json
import math
import re

SCHEMA = "pixelforge.shapes/v1"
TARGETS = ("base", "collision", "selection")
FACES = ("north", "south", "west", "east", "up", "down")


def default_shapes():
    return {"schema": SCHEMA, "base": [{"id": "block", "from": [0, 0, 0], "to": [16, 16, 16]}],
            "collision": None, "selection": None, "model": None}


def vector(value, length=3):
    if (not isinstance(value, list) or len(value) != length or
            any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1024 for n in value)):
        raise ValueError(f"坐标须为 {length} 个有限数值，范围 -1024..1024")
    return list(value)


def box(value):
    if not isinstance(value, dict) or set(value) - {"id", "from", "to"}:
        raise ValueError("形状盒仅包含 id、from、to")
    name = value.get("id")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
        raise ValueError("形状盒 id 使用 1..80 位字母、数字、下划线、点或连字符")
    start, end = vector(value.get("from")), vector(value.get("to"))
    if any(a >= b for a, b in zip(start, end)):
        raise ValueError("每个形状盒的 from 必须逐轴小于 to；空形状使用 []")
    return {"id": name, "from": start, "to": end}


def boxes(value):
    if not isinstance(value, list) or len(value) > 256:
        raise ValueError("每份形状使用 0..256 个轴对齐盒")
    result = [box(item) for item in value]
    if len({item["id"] for item in result}) != len(result):
        raise ValueError("同一份形状中的盒 id 不能重复")
    return result


def model(value):
    """Embed one resolved Java model; all preview faces use the current atlas."""
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("elements"), list) or not 1 <= len(value["elements"]) <= 256:
        raise ValueError("模型须含 1..256 个显式 elements；先解析父模型")
    result = deepcopy(value)
    textures = set()
    for element in result["elements"]:
        if not isinstance(element, dict):
            raise ValueError("模型 element 须为对象")
        start, end = vector(element.get("from")), vector(element.get("to"))
        if any(a > b for a, b in zip(start, end)) or start == end:
            raise ValueError("模型 from/to 无效")
        rotation = element.get("rotation")
        if rotation is not None:
            if (not isinstance(rotation, dict) or rotation.get("axis") not in ("x", "y", "z") or
                    type(rotation.get("angle")) not in (int, float) or rotation["angle"] not in (-45, -22.5, 0, 22.5, 45) or
                    type(rotation.get("rescale", False)) is not bool):
                raise ValueError("模型旋转须为 Java 的 x/y/z 轴与 0、±22.5、±45 度")
            vector(rotation.get("origin"))
        faces = element.get("faces", {})
        if not isinstance(faces, dict) or not faces or set(faces) - set(FACES):
            raise ValueError("模型须声明有效的六向 faces")
        for face in faces.values():
            if not isinstance(face, dict) or not isinstance(face.get("texture"), str):
                raise ValueError("模型面须声明 texture")
            textures.add(face["texture"])
            if "uv" in face:
                vector(face["uv"], 4)
            if type(face.get("rotation", 0)) is not int or face.get("rotation", 0) not in (0, 90, 180, 270):
                raise ValueError("模型 UV 旋转须为 0/90/180/270")
    # Resolve aliases before checking: a single current atlas is deliberate, not a missing-texture fallback.
    definitions = result.get("textures", {})
    if not isinstance(definitions, dict):
        raise ValueError("模型 textures 须为对象")
    resolved = set()
    for ref in textures:
        seen = set()
        while ref.startswith("#") and ref[1:] in definitions:
            if ref in seen:
                raise ValueError("模型纹理别名循环")
            seen.add(ref)
            ref = definitions[ref[1:]]
            if not isinstance(ref, str):
                raise ValueError("纹理引用须为文字")
        resolved.add(ref)
    if len(resolved) != 1:
        raise ValueError("当前模型预览使用一张图集；多纹理模型请先合并图集")
    return result


def normalize(value):
    if not isinstance(value, dict) or set(value) - {"schema", *TARGETS, "model", "units", "effective"}:
        raise ValueError("形状定义包含未知字段")
    if value.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("不支持的形状格式")
    result = default_shapes()
    result["base"] = boxes(value.get("base", result["base"]))
    for target in TARGETS[1:]:
        result[target] = None if value.get(target) is None else boxes(value[target])
    result["model"] = model(value.get("model"))
    if "units" in value and value["units"] != "model_16":
        raise ValueError("形状单位须为 model_16")
    if "effective" in value and value["effective"] != {t: effective(result,t) for t in TARGETS[1:]}:
        raise ValueError("导出形状的 effective 与基础 / 覆盖数据不一致")
    json.dumps(result, allow_nan=False)
    return result


def effective(value, target):
    if target not in TARGETS:
        raise ValueError("形状目标须为 base/collision/selection")
    return deepcopy(value["base"] if value[target] is None else value[target])


def edit(value, operations):
    candidate = normalize(value)
    if not isinstance(operations, list) or not 1 <= len(operations) <= 256:
        raise ValueError("形状编辑须为 1..256 条操作")
    for op in operations:
        if not isinstance(op, dict) or op.get("target") not in TARGETS:
            raise ValueError("每条操作须有有效 target")
        target, action = op["target"], op.get("op")
        if action == "mode":
            if target == "base" or op.get("mode") not in ("inherit", "copy", "empty"):
                raise ValueError("覆盖模式仅支持 collision/selection 的 inherit/copy/empty")
            candidate[target] = {"inherit": None, "copy": effective(candidate, target), "empty": []}[op["mode"]]
            continue
        if candidate[target] is None:
            raise ValueError("先切换为 copy 或 empty 独立覆盖，再编辑；当前形状继承基础形状")
        items = candidate[target]
        if action == "add":
            items.append(box(op.get("box")))
        elif action in ("update", "remove"):
            index = next((i for i, item in enumerate(items) if item["id"] == op.get("id")), None)
            if index is None:
                raise ValueError("未找到形状盒 id")
            if action == "remove":
                items.pop(index)
            else:
                if not isinstance(op.get("box"), dict):
                    raise ValueError("update 的 box 须为对象")
                items[index] = box({**items[index], **op["box"]})
        else:
            raise ValueError("形状操作须为 add/update/remove/mode")
    return normalize(candidate)


def report(value):
    value = normalize(value)
    warnings = []
    for target in TARGETS:
        if any(any(n < 0 or n > 16 for n in item[side]) for item in effective(value, target) for side in ("from", "to")):
            warnings.append(f"{target} 延伸到单方块边界之外；请确认相邻方块与游戏逻辑")
    complexity = {}
    for target in TARGETS:
        items=effective(value,target)
        intervals=[max(0,len({b[side][axis] for b in items for side in ("from","to")})-1) for axis in range(3)]
        complexity[target]={"coordinate_intervals":intervals,"source_grid_cells":math.prod(intervals),
                            "basis":"source geometry endpoints; runtime may add coordinates"}
    return {"schema": SCHEMA, "units": "Minecraft model units: 16 = 1 block",
            "counts": {t: len(effective(value, t)) for t in TARGETS},
            "modes": {t: "inherit" if value[t] is None else "override" for t in TARGETS[1:]},
            "model_elements": len(value["model"]["elements"]) if value["model"] else 0,
            "complexity":complexity,"warnings": warnings, "in_game_verified": False}


def packed_shapes(value):
    """Lossless export packing; editable definitions/IDs and approval state are untouched."""
    from .shape_builder import optimize_boxes
    value=normalize(value)
    packed=deepcopy(value)
    reports={}
    for target in TARGETS:
        if value[target] is None:
            reports[target]={"inherits":"base"}
        else:
            packed[target],reports[target]=optimize_boxes(value[target],max_error=0)
    return packed,reports


def java_source(value, class_name="BlockShapes", package=""):
    keywords = set("abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null _ record var sealed permits yield".split())
    if not re.fullmatch(r"[A-Za-z_$][\w$]*", class_name, flags=re.ASCII):
        raise ValueError("无效 Java 类名")
    if package and not re.fullmatch(r"[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*", package, flags=re.ASCII):
        raise ValueError("无效 Java 包名")
    if class_name in keywords or any(part in keywords for part in package.split(".")):
        raise ValueError("Java 类名和包名不能使用保留词")
    value,_=packed_shapes(value)
    def expression(items):
        if not items:
            return "Shapes.empty()"
        terms = ["Block.box(" + ", ".join(str(n) for n in item["from"] + item["to"]) + ")" for item in items]
        return terms[0] if len(terms) == 1 else "union(\n            " + ",\n            ".join(terms) + ")"
    prefix = f"package {package};\n\n" if package else ""
    return prefix + """// PixForge adapter: Minecraft Java 1.20.1 / Forge / Mojang mappings.
// Model units: 16 = 1 block. Add these methods to your registered Block subclass:
// Required imports there: net.minecraft.world.level.block.state.BlockState;
// net.minecraft.world.level.BlockGetter; net.minecraft.core.BlockPos;
// net.minecraft.world.phys.shapes.CollisionContext;
// @Override public VoxelShape getShape(BlockState s, BlockGetter w, BlockPos p, CollisionContext c) {
//     return CLASS_NAME.SELECTION;
// }
// @Override public VoxelShape getCollisionShape(BlockState s, BlockGetter w, BlockPos p, CollisionContext c) {
//     return CLASS_NAME.COLLISION;
// }
// This helper does not register a block, change a resource pack's physics, or rotate with blockstate.
import net.minecraft.world.level.block.Block;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

public final class CLASS_NAME {
    private CLASS_NAME() {}
    // Combine a balanced tree without repeatedly optimizing intermediate shapes.
    // Optimize once, then retain immutable static shapes for all runtime queries.
    private static VoxelShape union(VoxelShape... parts) {
        return merge(parts, 0, parts.length).optimize();
    }
    private static VoxelShape merge(VoxelShape[] parts, int start, int end) {
        if (start == end) return Shapes.empty();
        if (end - start == 1) return parts[start];
        int middle = (start + end) >>> 1;
        return Shapes.joinUnoptimized(merge(parts, start, middle), merge(parts, middle, end), BooleanOp.OR);
    }
""".replace("CLASS_NAME", class_name) + f"    public static final VoxelShape BASE = {expression(value['base'])};\n" + "".join(
        f"    public static final VoxelShape {target.upper()} = " + ("BASE" if value[target] is None else expression(value[target])) + ";\n"
        for target in TARGETS[1:]) + "}\n"


def export_data(value, format="json", class_name="BlockShapes", package=""):
    value = normalize(value)
    if format == "json":
        # Keep inheritance and explicit empty overrides, plus resolved values for other adapters.
        return json.dumps({**value, "units": "model_16", "effective": {t: effective(value, t) for t in TARGETS[1:]}},
                          ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if format == "forge-1.20.1":
        return java_source(value, class_name, package).encode("utf-8")
    raise ValueError("形状导出格式须为 json 或 forge-1.20.1")
