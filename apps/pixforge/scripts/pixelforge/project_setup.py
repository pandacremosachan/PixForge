"""Model-first project preparation. The same embedded model drives UV and preview."""
from copy import deepcopy
from fractions import Fraction
import math

from .model_uv import describe
from . import player_skin
from .shapes import boxes, default_shapes, model as normalize_model


PRESETS = ("cube_faces", "cube_shared", "model", "pixels", "player_skin", "player_rig", "component_model")


def _size(value, name, maximum=4096):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} 须为 1..{maximum} 的整数")
    return value


def editable_block(w, h, tiles):
    from PIL import Image
    from .player_rig import SIDES, bone
    from .rig_files import project
    from .rig_studio import compile_model

    faces = {}
    for direction, tile in tiles.items():
        uv = tile["uv"]
        if direction in ("up","down"):
            uv = uv[2:]+uv[:2]
        faces[SIDES[direction]] = {**tile,"uv":uv}
    # The component editor mirrors X/Z on the way to Java block coordinates (0..16).
    part = {"name":"六面方块", "from":[-16,0,-16], "to":[0,16,0], "faces":faces}
    rig = {"name":"block","texture_size":[w,h],"bones":[bone("方块",None,[-8,8,-8],[part])],"clips":[]}
    src = project(rig,Image.new("RGBA",(w,h)))
    src["textures"][0]["name"] = "block.png"
    return compile_model(src,[[0,0,w,h]],(w,h))["model"]


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


def prepare(settings=None):
    if settings is None:
        settings = {}
    if isinstance(settings, dict) and settings.get("preset") in ("player_rig", "component_model"):
        from .player_rig import starter, component_starter
        preset = settings["preset"]
        rig = settings.get("rig") or (component_starter() if preset == "component_model" else
                                      starter(settings.get("name","player"),settings.get("texture_size",[128,128])))
        from .rig_files import project
        from .rig_studio import from_source
        from PIL import Image
        w,h=rig["texture_size"]
        shapes,_=from_source(project(rig,Image.new("RGBA",(w,h))))
        scene=None
        return {"schema":"pixelforge.project-plan/v1","preset":preset,"settings":{"preset":preset,"rig":rig},
                "canvas_size":[w,h],"size_source":"模型纹理图集","shapes":shapes,"scene_animation":scene,
                "uv_map":describe(shapes["model"],[w,h]),"shape_report":None,"warnings":[],"pixels":"editable atlas"}
    if not isinstance(settings, dict) or set(settings) - {"preset", "model", "face_size", "width", "height", "base_boxes", "arm_model"}:
        raise ValueError("未知工程设置；使用 project plan 查询对应预设")
    preset = settings.get("preset", "model" if settings.get("model") is not None else "cube_faces")
    if not isinstance(preset, str):
        raise ValueError("无效新建类型")
    preset = preset.replace("-", "_")
    if preset not in PRESETS:
        raise ValueError("新建类型须为 " + "/".join(PRESETS))
    if "arm_model" in settings and preset != "player_skin":
        raise ValueError("arm_model 用于玩家皮肤")
    normalized = {"preset": preset}
    if preset == "player_skin":
        if set(settings) - {"preset", "arm_model"}:
            raise ValueError("玩家皮肤使用固定的 64×64 图集；选项为 arm_model: classic/slim")
        arm_model = settings.get("arm_model", "classic")
        if arm_model not in ("classic", "slim"):
            raise ValueError("arm_model 须为 classic 或 slim")
        normalized["arm_model"] = arm_model
        model = player_skin.model(arm_model)
        width = height = player_skin.SIZE
        source = "Minecraft 玩家皮肤 · " + arm_model
    elif preset in ("cube_faces", "cube_shared"):
        if any(k in settings for k in ("model", "width", "height")):
            raise ValueError("内置方块请用 face_size 设置每面像素尺寸")
        face_size = _size(settings.get("face_size", 16), "每面尺寸", 1024)
        separate = preset == "cube_faces"
        width,height = (3*face_size,2*face_size) if separate else (face_size,face_size)
        tiles = {}
        for i,direction in enumerate(("up","north","east","south","west","down")):
            x,y = (i%3*face_size,i//3*face_size) if separate else (0,0)
            tiles[direction] = {"uv":[x,y,x+face_size,y+face_size]}
        model = editable_block(width,height,tiles)
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
    if "base_boxes" in settings:
        shapes["base"] = boxes(settings["base_boxes"])
        normalized["base_boxes"] = deepcopy(shapes["base"])
    elif preset in ("model", "pixels", "player_skin"):
        shapes["base"] = []
    mapping = describe(model, [width, height])
    warnings = []
    if mapping["shared_region_count"]:
        warnings.append("部分 UV 被多个面共用，绘制这些区域会同时改变对应面。")
    if model and any(any(n < 0 or n > 16 for n in face["uv"]) for face in mapping["faces"]):
        warnings.append("存在超出 0..16 的 UV，按模型定义在当前纹理帧内重复采样。")
    return {"schema": "pixelforge.project-plan/v1", "preset": preset,
            "settings": normalized, "canvas_size": [width, height], "size_source": source,
            "shapes": shapes, "uv_map": mapping, "shape_report": None,
            "warnings": warnings, "pixels": ("opaque base faces; transparent outer layer and padding"
                                              if preset == "player_skin" else "transparent; UV guides are view-only")}
