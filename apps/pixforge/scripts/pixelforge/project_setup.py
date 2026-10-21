"""Model-first project preparation. The same embedded model drives UV and preview."""
from copy import deepcopy
from fractions import Fraction
import math

from .model_uv import describe
from .shapes import default_shapes, model as normalize_model


PRESETS = ("cube_faces", "cube_shared", "model", "pixels")


def _size(value, name, maximum=4096):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} 须为 1..{maximum} 的整数")
    return value


def cube(separate=True):
    faces = {}
    for i, direction in enumerate(("up", "north", "east", "south", "west", "down")):
        uv = [i % 3 * 16/3, i//3 * 8, (i % 3+1) * 16/3, (i//3+1) * 8] if separate else [0, 0, 16, 16]
        faces[direction] = {"uv": uv, "texture": "#atlas"}
    return {"textures": {"atlas": "pixforge:block/new_texture", "particle": "#atlas"},
            "elements": [{"name": "六面方块", "from": [0, 0, 0], "to": [16, 16, 16], "faces": faces}]}


def _suggest_size(model):
    declared = model.get("texture_size")
    if declared is not None:
        if not isinstance(declared, list) or len(declared) != 2:
            raise ValueError("模型 texture_size 须为 [宽,高]")
        return [_size(n, "纹理尺寸") for n in declared], "模型 texture_size"
    mapping = describe(model, [16, 16])
    sizes = []
    for axis in (0, 1):
        multiple = 16
        for face in mapping["faces"]:
            for corner in face["uv_corners"]:
                multiple = math.lcm(multiple, Fraction(corner[axis]/16).limit_denominator(4096).denominator)
                if multiple > 4096:
                    break
            if multiple > 4096:
                break
        sizes.append(multiple if multiple <= 4096 else 64)
    return sizes, "按 UV 边界建议；可调整像素分辨率"


def prepare(settings=None, *, build_shapes=False):
    if settings is None:
        settings = {}
    if not isinstance(settings, dict) or set(settings) - {"preset", "model", "face_size", "width", "height"}:
        raise ValueError("新建设置仅支持 preset/model/face_size/width/height")
    preset = settings.get("preset", "model" if settings.get("model") is not None else "cube_faces")
    if not isinstance(preset, str):
        raise ValueError("无效新建类型")
    preset = preset.replace("-", "_")
    if preset not in PRESETS:
        raise ValueError("新建类型须为 cube_faces/cube_shared/model/pixels")
    normalized = {"preset": preset}
    if preset in ("cube_faces", "cube_shared"):
        if any(k in settings for k in ("model", "width", "height")):
            raise ValueError("内置方块请用 face_size 设置每面像素尺寸")
        face_size = _size(settings.get("face_size", 16), "每面尺寸", 1024)
        separate = preset == "cube_faces"
        model = cube(separate)
        width, height = (face_size*3, face_size*2) if separate else (face_size, face_size)
        model["texture_size"] = [width, height]
        normalized["face_size"] = face_size
        source = "内置六面独立图集" if separate else "内置六面共用纹理"
    elif preset == "model":
        if "face_size" in settings:
            raise ValueError("导入模型使用 width/height 调整纹理分辨率")
        model = normalize_model(settings.get("model"))
        if model is None:
            raise ValueError("先选择含显式 elements 和 UV 的模型 JSON")
        suggested, source = _suggest_size(model)
        if ("width" in settings) != ("height" in settings):
            raise ValueError("纹理宽度与高度须同时指定")
        width, height = (_size(settings["width"], "纹理宽度"), _size(settings["height"], "纹理高度")) if "width" in settings else suggested
        normalized.update(model=deepcopy(model), width=width, height=height)
    else:
        if "model" in settings or "face_size" in settings:
            raise ValueError("纯像素工程不指定模型或每面尺寸")
        model = None
        width, height = _size(settings.get("width", 32), "画布宽度"), _size(settings.get("height", 32), "画布高度")
        normalized.update(width=width, height=height)
        source = "纯像素画布"
    # Validate allocation bounds without allocating a preview canvas or touching the session.
    _size(width, "画布宽度")
    _size(height, "画布高度")
    shapes = default_shapes()
    shapes["model"] = deepcopy(model)
    shape_report = None
    shape_warning = None
    if model is not None:
        if build_shapes:
            from .shape_builder import build_model
            try:
                shapes["base"], shape_report = build_model(model)
            except ValueError as error:
                shapes["base"] = []
                shape_report = {"operation": "build-from-model", "built": False, "reason": str(error)}
                shape_warning = "模型 UV 已保留；形状需单独构建：" + str(error)
        else:
            shapes["base"] = []  # Plan preview bounds come from the chosen geometry alone.
    mapping = describe(model, [width, height])
    warnings = []
    if shape_warning:
        warnings.append(shape_warning)
    if mapping["shared_region_count"]:
        warnings.append("部分 UV 被多个面共用，绘制这些区域会同时改变对应面。")
    if model and any(any(n < 0 or n > 16 for n in face["uv"]) for face in mapping["faces"]):
        warnings.append("存在超出 0..16 的 UV，按模型定义在当前纹理帧内重复采样。")
    return {"schema": "pixelforge.project-plan/v1", "preset": preset,
            "settings": normalized, "canvas_size": [width, height], "size_source": source,
            "shapes": shapes, "uv_map": mapping, "shape_report": shape_report,
            "warnings": warnings, "pixels": "transparent; UV guides are view-only"}
