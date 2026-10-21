"""Read-only Java resource graph with explicit sources and Forge 1.20.1 rules."""
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

from PIL import Image

from .document import StudioError
from .minecraft_target import PROFILES, location, resource_id, resource_path

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_FILES = 4096
BUILTINS = {"minecraft:builtin/generated", "minecraft:builtin/entity"}
FACES = {"north", "south", "east", "west", "up", "down"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def parse_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("重复 JSON 字段: " + key)
            out[key] = value
        return out

    def constant(value):
        raise ValueError("JSON 不允许 " + value)

    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("资源 JSON 须为对象")
    return value


class Source:
    def __init__(self, setting, overlay=None):
        self.name, self.role = setting["name"], setting["role"]
        self.path = setting.get("path")
        self.overlay, self.archive, self.base = overlay, None, None
        self.index, self.duplicates = {}, set()
        if overlay is not None:
            self.index = {name: name for name in overlay}
        else:
            path = Path(self.path)
            if path.is_dir():
                self.base = path.parent if path.name == "assets" else path
                assets = self.base/"assets"
                for file in assets.rglob("*") if assets.is_dir() else []:
                    if file.is_file():
                        resolved = file.resolve()
                        if not resolved.is_relative_to(self.base.resolve()):
                            raise ValueError("资源目录中的链接指向来源目录以外: " + str(file))
                        self.index[file.relative_to(self.base).as_posix()] = file
                if (self.base/"pack.mcmeta").is_file():
                    self.index["pack.mcmeta"] = self.base/"pack.mcmeta"
            elif path.is_file() and path.suffix.lower() in (".zip", ".jar"):
                self.archive = zipfile.ZipFile(path)
                for info in self.archive.infolist():
                    if info.is_dir() or not (info.filename.startswith("assets/") or info.filename == "pack.mcmeta"):
                        continue
                    if ("\\" in info.filename or any(p in ("", ".", "..") for p in info.filename.split("/"))):
                        raise ValueError("归档中的资源路径无效: " + info.filename)
                    if info.filename in self.index:
                        self.duplicates.add(info.filename)
                    self.index[info.filename] = info
            else:
                raise ValueError("来源不存在，或不是资源目录 / ZIP / JAR")
        if len(self.index) > 150000:
            raise ValueError("单个来源超过 150000 个资源文件")
        self.folded = {name.casefold(): name for name in self.index}

    def read(self, name):
        if name in self.duplicates:
            raise ValueError("归档包含重复条目，无法确定生效内容: " + name)
        value = self.index[name]
        size = len(self.overlay[name]) if self.overlay is not None else value.file_size if self.archive else value.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError("资源文件超过 32 MiB: " + name)
        if self.overlay is not None:
            return self.overlay[name]
        if self.archive:
            return self.archive.read(value)
        raw = value.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("资源文件超过 32 MiB: " + name)
        return raw

    def close(self):
        if self.archive:
            self.archive.close()


class Audit:
    def __init__(self, config, *, overlay=None, entries=None, content_digest=None):
        self.config = config
        self.sources, self.issues, self.nodes, self.edges, self.overrides = [], [], {}, [], {}
        self.raw, self.models, self.checked_models, self.checked_textures = {}, {}, set(), set()
        self.atlas_layers, self.sprites, self.used_sprites = {}, {}, {}
        self.has_block_atlas = False
        self.payload, self.total_bytes = {}, 0
        self._issue_keys = set()
        self.content_digest = content_digest
        self.entries = list(config["entries"]) + list(entries or [])
        self.overlay = overlay or {}

    def issue(self, code, message, resource=None, *, severity="error", source=None, chain=None):
        key = (severity, code, resource, source, message)
        if key not in self._issue_keys:
            self._issue_keys.add(key)
            self.issues.append({"severity": severity, "code": code, "message": message,
                                "resource": resource, "source": source, "chain": chain or []})

    def edge(self, start, end, relation):
        value = {"from": start, "to": end, "relation": relation}
        if value not in self.edges:
            self.edges.append(value)

    def _open(self):
        for setting in self.config["sources"]:
            source = None
            try:
                source = Source(setting)
                self.sources.append(source)
                if "pack.mcmeta" in source.index:
                    metadata = parse_json(source.read("pack.mcmeta"))
                    if "filter" in metadata:
                        self.issue("UNSUPPORTED_PACK_FILTER", "来源使用资源过滤规则，需要专门适配后才能证明引用结果", source=source.name)
                    if source.role == "project":
                        pack = metadata.get("pack", {})
                        if not isinstance(pack, dict):
                            raise ValueError("pack 元数据须为对象")
                        actual = pack.get("pack_format")
                        if actual != 15:
                            self.issue("SOURCE_PACK_FORMAT", f"来源声明 pack_format={actual!r}；将逐项检查并按目标格式 15 导出", severity="warning", source=source.name)
                        if "overlays" in metadata:
                            self.issue("UNSUPPORTED_PACK_OVERLAYS", "Forge 1.20.1 不支持来源包的 overlays 规则", source=source.name)
            except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
                self.issue("SOURCE_UNAVAILABLE", str(error), source=setting["name"])
        if self.overlay:
            self.sources.append(Source({"name": "current-document", "role": "project"}, self.overlay))

    def _read(self, relative, *, required=True, minimum=0, chain=None):
        key = (relative, minimum)
        if key in self.raw:
            return self.raw[key]
        matches = [(i, source) for i, source in enumerate(self.sources) if i >= minimum and relative in source.index]
        if not matches:
            if required:
                alternatives = [f"{s.name}:{s.folded[relative.casefold()]}" for s in self.sources if relative.casefold() in s.folded]
                code = "RESOURCE_CASE_MISMATCH" if alternatives else "MISSING_RESOURCE"
                detail = "；仅找到大小写不同的文件 " + ", ".join(alternatives) if alternatives else ""
                self.issue(code, "找不到资源 " + relative + detail, relative, chain=chain)
            self.raw[key] = None
            return None
        index, source = matches[-1]
        try:
            if len(self.nodes) >= MAX_FILES and relative not in self.nodes:
                raise ValueError("本次引用闭包超过 4096 个文件，请缩小入口范围")
            raw = source.read(relative)
            self.total_bytes += len(raw)
            if self.total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("本次引用闭包超过 128 MiB，请缩小入口范围")
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
            self.issue("RESOURCE_READ_ERROR", str(error), relative, source=source.name, chain=chain)
            self.raw[key] = None
            return None
        record = {"path": relative, "source": source.name, "role": source.role,
                  "sha256": digest(raw), "bytes": len(raw)}
        self.nodes[relative] = record
        if source.role == "project":
            self.payload[relative] = raw
        if len(matches) > 1:
            self.overrides[relative] = {"path": relative, "winner": source.name,
                                        "shadowed": [item.name for _, item in matches[:-1]]}
        result = (raw, record, index)
        self.raw[key] = result
        return result

    def _json(self, relative, *, chain=None):
        found = self._read(relative, chain=chain)
        if found:
            try:
                return parse_json(found[0])
            except (ValueError, UnicodeError) as error:
                self.issue("INVALID_JSON", str(error), relative, source=found[1]["source"], chain=chain)
        return None

    def _reference(self, kind, identifier, start, relation):
        try:
            value = resource_id(identifier)
            self.edge(start, location(kind, value), relation)
            return value
        except (StudioError, TypeError) as error:
            self.issue("INVALID_RESOURCE_ID", str(error), start)
            return None

    def _model_structure(self, model, relative):
        if "loader" in model:
            self.issue("UNSUPPORTED_MODEL_LOADER", "模型使用自定义 loader，需要对应适配器: " + str(model["loader"]), relative)
        if "gui_light" in model and model["gui_light"] not in ("front", "side"):
            self.issue("TARGET_MODEL_FORMAT", "gui_light 须为 front 或 side", relative)
        if "ambientocclusion" in model and type(model["ambientocclusion"]) is not bool:
            self.issue("TARGET_MODEL_FORMAT", "ambientocclusion 须为布尔值", relative)
        display = model.get("display", {})
        if not isinstance(display, dict):
            self.issue("TARGET_MODEL_FORMAT", "display 须为对象", relative)
        else:
            for perspective, transform in display.items():
                if not isinstance(transform, dict):
                    self.issue("TARGET_MODEL_FORMAT", "display 变换须为对象: " + perspective, relative)
                    continue
                for key in ("rotation", "translation", "scale", "right_rotation"):
                    value = transform.get(key)
                    if value is not None and (not isinstance(value, list) or len(value) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in value)):
                        self.issue("TARGET_MODEL_FORMAT", f"display {perspective}/{key} 须为有限三维向量", relative)
        textures = model.get("textures", {})
        if not isinstance(textures, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in textures.items()):
            self.issue("TARGET_MODEL_FORMAT", "Forge 1.20.1 的 textures 使用字符串引用，不能使用新版材质对象", relative)
        elements = model.get("elements", [])
        if not isinstance(elements, list) or len(elements) > 4096:
            self.issue("TARGET_MODEL_FORMAT", "elements 须为最多 4096 项的数组", relative)
            return
        for index, element in enumerate(elements):
            if not isinstance(element, dict):
                self.issue("TARGET_MODEL_FORMAT", f"element {index} 须为对象", relative)
                continue
            if "forge_data" in element:
                try:
                    from .minecraft_sampling import forge_face_data
                    forge_face_data(element["forge_data"])
                except ValueError as error:
                    self.issue("TARGET_FACE_DATA", str(error), relative)
            for key in ("from", "to"):
                v = element.get(key)
                if not isinstance(v, list) or len(v) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) or not -16 <= n <= 32 for n in v):
                    self.issue("TARGET_MODEL_FORMAT", f"element {index} 的 {key} 须为 -16..32 的三维坐标", relative)
            rotation = element.get("rotation")
            if rotation is not None:
                if (not isinstance(rotation, dict) or rotation.get("axis") not in ("x", "y", "z")
                        or type(rotation.get("angle")) not in (int, float) or rotation["angle"] not in (-45, -22.5, 0, 22.5, 45)):
                    self.issue("TARGET_MODEL_FORMAT", f"element {index} 的旋转超出 Forge 1.20.1 格式", relative)
                else:
                    origin = rotation.get("origin")
                    if not isinstance(origin, list) or len(origin) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in origin):
                        self.issue("TARGET_MODEL_FORMAT", f"element {index} 的 rotation.origin 须为有限三维向量", relative)
                    if type(rotation.get("rescale", False)) is not bool:
                        self.issue("TARGET_MODEL_FORMAT", f"element {index} 的 rescale 须为布尔值", relative)
            if type(element.get("shade", True)) is not bool:
                self.issue("TARGET_MODEL_FORMAT", f"element {index} 的 shade 须为布尔值", relative)
            faces = element.get("faces", {})
            if not isinstance(faces, dict) or set(faces)-FACES:
                self.issue("TARGET_MODEL_FORMAT", f"element {index} 的 faces 无效", relative)
                continue
            for direction, face in faces.items():
                if not isinstance(face, dict) or not isinstance(face.get("texture"), str):
                    self.issue("TARGET_MODEL_FORMAT", f"element {index}/{direction} 缺少 texture 字符串", relative)
                    continue
                if "forge_data" in face:
                    try:
                        from .minecraft_sampling import forge_face_data
                        forge_face_data(face["forge_data"])
                    except ValueError as error:
                        self.issue("TARGET_FACE_DATA", str(error), relative)
                if type(face.get("rotation", 0)) is not int or face.get("rotation", 0) not in (0, 90, 180, 270):
                    self.issue("TARGET_MODEL_FORMAT", f"element {index}/{direction} 的 UV 旋转无效", relative)
                uv = face.get("uv")
                if uv is not None and (not isinstance(uv, list) or len(uv) != 4 or any(type(n) not in (int, float) or not math.isfinite(n) for n in uv)):
                    self.issue("TARGET_MODEL_FORMAT", f"element {index}/{direction} 的 UV 无效", relative)
                if "cullface" in face:
                    if not isinstance(face["cullface"], str):
                        self.issue("TARGET_MODEL_FORMAT", f"element {index}/{direction} 的 cullface 须为字符串", relative)
                    elif face["cullface"] and face["cullface"] not in FACES:
                        self.issue("UNKNOWN_CULLFACE", f"element {index}/{direction} 的 cullface 不匹配方向；目标游戏将其按不指定方向处理", relative, severity="warning")
                if "tintindex" in face and type(face["tintindex"]) is not int:
                    self.issue("TARGET_MODEL_FORMAT", f"element {index}/{direction} 的 tintindex 须为整数", relative)

    def _resolve_model(self, identifier, chain=()):
        relative = location("model", identifier)
        if identifier in BUILTINS:
            return {"textures": {}}
        if identifier in chain or len(chain) >= 64:
            self.issue("MODEL_PARENT_CYCLE" if identifier in chain else "MODEL_PARENT_DEPTH", "父模型继承循环或深度超限", relative, chain=[*chain, identifier])
            return None
        if identifier in self.models:
            return self.models[identifier]
        value = self._json(relative, chain=[*chain, identifier])
        if value is None:
            return None
        self._model_structure(value, relative)
        parent = {}
        if "parent" in value:
            parent_id = self._reference("model", value["parent"], relative, "parent")
            parent = self._resolve_model(parent_id, (*chain, identifier)) if parent_id else None
            if parent is None:
                return None
        result = {**deepcopy(parent), **deepcopy(value)}
        # Java 1.20.1 inherits parent geometry when the child's elements list is
        # empty, while item overrides always belong to the current model.
        if not value.get("elements") and "elements" in parent:
            result["elements"] = deepcopy(parent["elements"])
        result["overrides"] = deepcopy(value.get("overrides", []))
        inherited_display = deepcopy(parent.get("display", {}))
        local_display = deepcopy(value.get("display", {}))
        if isinstance(inherited_display, dict) and isinstance(local_display, dict):
            for right, left in (("firstperson_righthand", "firstperson_lefthand"),
                                ("thirdperson_righthand", "thirdperson_lefthand")):
                if right in local_display and left not in local_display:
                    local_display[left] = deepcopy(local_display[right])
            if inherited_display or local_display:
                result["display"] = {**inherited_display, **local_display}
        inherited, local = parent.get("textures", {}), value.get("textures", {})
        result["textures"] = {**(inherited if isinstance(inherited, dict) else {}), **(local if isinstance(local, dict) else {})}
        self.models[identifier] = result
        return result

    def model(self, identifier):
        if identifier in self.checked_models:
            return
        self.checked_models.add(identifier)
        relative = location("model", identifier)
        model = self._resolve_model(identifier)
        if model is None:
            return
        textures = model.get("textures", {})
        required = ["#"+key for key in textures]
        elements = model.get("elements", [])
        for element in elements if isinstance(elements, list) else []:
            faces = element.get("faces", {}) if isinstance(element, dict) else {}
            for face in faces.values() if isinstance(faces, dict) else []:
                if isinstance(face, dict) and isinstance(face.get("texture"), str):
                    required.append(face["texture"])
        for reference in dict.fromkeys(required):
            seen, current = [], reference
            while isinstance(current, str) and current.startswith("#"):
                key = current[1:]
                if key in seen:
                    self.issue("TEXTURE_ALIAS_CYCLE", "纹理别名循环: " + " -> ".join([*seen, key]), relative)
                    current = None
                    break
                seen.append(key)
                if key not in textures:
                    self.issue("UNRESOLVED_TEXTURE_ALIAS", "纹理别名未绑定: #" + key, relative)
                    current = None
                    break
                current = textures[key]
            if current is not None:
                value = self._reference("texture", current, relative, "texture:" + reference)
                if value:
                    self.texture(value, sprite=True)
        overrides = model.get("overrides", [])
        if not isinstance(overrides, list):
            self.issue("TARGET_MODEL_FORMAT", "overrides 须为数组", relative)
        else:
            for override in overrides:
                if not isinstance(override, dict) or not isinstance(override.get("predicate"), dict):
                    self.issue("TARGET_MODEL_FORMAT", "物品 override 须包含 predicate 对象与 model", relative)
                    continue
                if any(type(n) not in (int, float) or not math.isfinite(n) for n in override["predicate"].values()):
                    self.issue("TARGET_MODEL_FORMAT", "物品 override 的 predicate 值须为有限数值", relative)
                value = self._reference("model", override.get("model"), relative, "item_override")
                if value:
                    self.model(value)

    def _configured_model(self, value, relative):
        rows = value if isinstance(value, list) else [value]
        if not rows:
            self.issue("INVALID_BLOCKSTATE", "模型选择数组不能为空", relative)
        for row in rows:
            if not isinstance(row, dict):
                self.issue("INVALID_BLOCKSTATE", "方块状态模型须为对象", relative)
                continue
            identifier = self._reference("model", row.get("model"), relative, "blockstate_model")
            for axis in ("x", "y"):
                if type(row.get(axis, 0)) is not int or row.get(axis, 0) not in (0, 90, 180, 270):
                    self.issue("TARGET_BLOCKSTATE_ROTATION", axis + " 旋转须为 0/90/180/270", relative)
            if type(row.get("uvlock", False)) is not bool or type(row.get("weight", 1)) is not int or row.get("weight", 1) < 1:
                self.issue("INVALID_BLOCKSTATE", "uvlock 须为布尔值，weight 须为正整数", relative)
            if identifier:
                self.model(identifier)

    def blockstate(self, identifier):
        relative = location("blockstate", identifier)
        value = self._json(relative)
        if value is None:
            return
        if ("variants" in value) == ("multipart" in value):
            self.issue("INVALID_BLOCKSTATE", "方块状态须选择 variants 或 multipart", relative)
        variants = value.get("variants")
        if variants is not None:
            if not isinstance(variants, dict) or not variants:
                self.issue("INVALID_BLOCKSTATE", "variants 须为非空对象", relative)
            else:
                for row in variants.values():
                    self._configured_model(row, relative)
        multipart = value.get("multipart")
        if multipart is not None:
            if not isinstance(multipart, list) or not multipart:
                self.issue("INVALID_BLOCKSTATE", "multipart 须为非空数组", relative)
            else:
                for row in multipart:
                    if not isinstance(row, dict) or "apply" not in row or ("when" in row and not isinstance(row["when"], dict)):
                        self.issue("INVALID_BLOCKSTATE", "multipart 包含可选 when 对象及 apply", relative)
                    else:
                        self._configured_model(row["apply"], relative)

    def _animation(self, metadata, size, relative):
        animation = metadata.get("animation")
        if animation is None:
            return
        if not isinstance(animation, dict):
            self.issue("INVALID_ANIMATION_METADATA", "animation 须为对象", relative)
            return
        iw, ih = size
        if any(key in animation and (type(animation[key]) is not int or animation[key] < 1) for key in ("width", "height")):
            self.issue("INVALID_ANIMATION_METADATA", "显式帧宽高须为正整数", relative)
            return
        fw, fh = animation.get("width"), animation.get("height")
        if fw is None and fh is None:
            fw = fh = min(iw, ih)
        else:
            fw, fh = fw if fw is not None else iw, fh if fh is not None else ih
        if any(type(n) is not int or n < 1 for n in (fw, fh)) or iw % fw or ih % fh:
            self.issue("INVALID_ANIMATION_METADATA", "帧尺寸须为正整数并整除 PNG 尺寸", relative)
            return
        if type(animation.get("frametime", 1)) is not int or animation.get("frametime", 1) < 1:
            self.issue("INVALID_ANIMATION_METADATA", "frametime 须为正整数 tick", relative)
        if type(animation.get("interpolate", False)) is not bool:
            self.issue("INVALID_ANIMATION_METADATA", "interpolate 须为布尔值", relative)
        count = iw//fw*(ih//fh)
        frames = animation.get("frames", [])
        if not isinstance(frames, list) or len(frames) > 10000:
            self.issue("INVALID_ANIMATION_METADATA", "frames 须为数组，最多 10000 步；空数组沿用默认帧序", relative)
            return
        if not frames:
            frames = list(range(count))
        for frame in frames:
            index = frame.get("index") if isinstance(frame, dict) else frame
            duration = frame.get("time", animation.get("frametime", 1)) if isinstance(frame, dict) else animation.get("frametime", 1)
            if type(index) is not int or not 0 <= index < count or type(duration) is not int or duration < 1:
                self.issue("INVALID_ANIMATION_FRAME", "动画帧索引越界或时长不是正整数 tick", relative)
                break
        return fw, fh

    def texture(self, identifier, *, sprite=False):
        key = (identifier, sprite)
        if key in self.checked_textures:
            return
        self.checked_textures.add(key)
        relative = location("texture", identifier)
        if sprite and self.has_block_atlas:
            rule = self.sprites.get(identifier)
            if rule is None:
                self.issue("UNREGISTERED_ATLAS_SPRITE", "模型引用的精灵未注册到目标 blocks 图集: " + identifier, relative)
                return
            self.used_sprites[identifier] = deepcopy(rule)
            for dependency in rule["inputs"]:
                if dependency != identifier or rule["type"] != "directory":
                    self.edge(relative, location("texture", dependency), "sprite_input")
                self.texture(dependency)
            if rule["type"] == "paletted_permutations":
                self._palette_size(rule["inputs"][1], rule["inputs"][2], relative)
            return
        if sprite and not self.has_block_atlas and not identifier.split(":", 1)[1].startswith(("block/", "item/")):
            self.issue("ATLAS_DECLARATION_REQUIRED", "模型使用默认 block/item 目录以外的精灵；请提供目标 blocks 图集声明及来源", relative)
            return
        found = self._read(relative)
        if found is None:
            return
        size = None
        try:
            with Image.open(io.BytesIO(found[0])) as image:
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Minecraft 素材须为普通 PNG；APNG 不能代替动画条")
                if image.width*image.height > 16_777_216:
                    raise ValueError("单张纹理超过 16M 像素")
                image.load()
                size = image.size
                self.nodes[relative]["image_size"] = list(size)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            self.issue("INVALID_PNG", str(error), relative)
        # Metadata below the winning PNG is not inherited. A metadata-only pack
        # above it may supply metadata, matching the Java fallback resource stack.
        metadata_path = relative + ".mcmeta"
        metadata = self._read(metadata_path, required=False, minimum=found[2])
        mip_size = size
        if metadata is not None:
            self.edge(relative, metadata_path, "texture_metadata")
            try:
                value = parse_json(metadata[0])
                texture = value.get("texture", {})
                if not isinstance(texture, dict):
                    raise ValueError("texture 元数据须为对象")
                if set(texture) & {"mipmap_strategy", "alpha_cutoff_bias"}:
                    self.issue("TARGET_TEXTURE_METADATA", "Forge 1.20.1 不支持 mipmap_strategy / alpha_cutoff_bias", metadata_path)
                for flag in ("blur", "clamp"):
                    if flag in texture and type(texture[flag]) is not bool:
                        raise ValueError(flag + " 须为布尔值")
                if "gui" in value:
                    self.issue("TARGET_TEXTURE_METADATA", "GUI sprite scaling 元数据不属于当前 Forge 1.20.1 适配器", metadata_path)
                custom = set(value) - {"texture", "animation", "gui"}
                if custom:
                    self.issue("CUSTOM_TEXTURE_METADATA", "纹理包含尚未适配的扩展元数据: " + ", ".join(sorted(custom)), metadata_path)
                if size:
                    frame_size = self._animation(value, size, metadata_path)
                    if "animation" in value:
                        mip_size = frame_size
            except (ValueError, UnicodeError) as error:
                self.issue("INVALID_TEXTURE_METADATA", str(error), metadata_path)
        if mip_size and any(n & (n-1) for n in mip_size):
            self.issue("NON_POWER_OF_TWO_TEXTURE", "单帧纹理尺寸不是 2 的幂；请核对目标图集的 mipmap 限制，导出不缩放原像素", relative, severity="warning")

    def _atlas_layers(self, identifier):
        relative = location("atlas", identifier)
        if relative in self.atlas_layers:
            return self.atlas_layers[relative]
        layers = [(index, source) for index, source in enumerate(self.sources) if relative in source.index]
        if not layers:
            self._read(relative)
            return []
        rows_by_source, project_sources = [], []
        # Atlas definitions use the complete resource stack, not the ordinary
        # last-file-wins rule used for models and PNGs.
        for index, source in layers:
            try:
                raw = source.read(relative)
                value = parse_json(raw)
                rows = value.get("sources")
                if not isinstance(rows, list):
                    raise ValueError("atlas 须包含 sources 数组")
                if len(self.nodes) >= MAX_FILES:
                    raise ValueError("本次引用闭包超过 4096 个文件")
                self.total_bytes += len(raw)
                if self.total_bytes > MAX_TOTAL_BYTES:
                    raise ValueError("本次引用闭包超过 128 MiB")
                self.nodes[relative+"@"+str(index)] = {"path": relative, "source": source.name, "role": source.role,
                    "sha256": digest(raw), "bytes": len(raw), "merge": "atlas-source-stack"}
                rows_by_source.append((source, rows))
                if source.role == "project":
                    project_sources.extend(rows)
            except (OSError, ValueError, UnicodeError, RuntimeError, zipfile.BadZipFile) as error:
                self.issue("INVALID_ATLAS", str(error), relative, source=source.name)
        if project_sources:
            self.payload[relative] = encode({"sources": project_sources})
        self.atlas_layers[relative] = rows_by_source
        return rows_by_source

    def _directory_textures(self, directory):
        return sorted({name for item in self.sources for name in item.index if name.endswith(".png")
                       and len(name.split("/", 3)) == 4 and name.split("/", 3)[2] == "textures"
                       and (not directory or name.split("/textures/", 1)[1].startswith(directory+"/"))})

    def _palette_size(self, key, palette, relative):
        try:
            left = self.nodes.get(location("texture", key), {}).get("image_size")
            right = self.nodes.get(location("texture", palette), {}).get("image_size")
            if left and right and math.prod(left) != math.prod(right):
                self.issue("PALETTE_SIZE_MISMATCH", "调色板与 palette_key 的像素数量不同，目标图集无法生成该精灵", relative)
        except StudioError:
            pass  # malformed references already carry their own diagnostics

    def _index_sprites(self):
        relative = location("atlas", "minecraft:blocks")
        self.has_block_atlas = any(relative in source.index for source in self.sources)
        if not self.has_block_atlas:
            return
        layers = self._atlas_layers("minecraft:blocks")
        if not any(owner.role == "dependency" for owner, _ in layers):
            # The target's ordinary block/item directory rules still exist when
            # only a mod's additive atlas declarations were supplied. No vanilla
            # image/model bytes are fabricated or redistributed by this rule.
            for directory in ("block", "item"):
                for name in self._directory_textures(directory):
                    domain, path = name.split("/", 2)[1], name.split("/textures/", 1)[1][:-4]
                    self.sprites[domain+":"+path] = {"type": "directory", "inputs": [domain+":"+path],
                        "atlas": relative, "source": "forge-1.20.1-default-directories"}
        for owner, rows in layers:
            for source in rows:
                try:
                    if not isinstance(source, dict) or not isinstance(source.get("type"), str):
                        raise ValueError("atlas source 须包含 type 字符串")
                    kind = source["type"].removeprefix("minecraft:")
                    if kind == "directory":
                        directory = source.get("source")
                        if directory != "":
                            resource_path(directory)
                        prefix = source.get("prefix")
                        if not isinstance(prefix, str):
                            raise ValueError("directory source 须指定 prefix 字符串")
                        for name in self._directory_textures(directory):
                            domain, path = name.split("/", 2)[1], name.split("/textures/", 1)[1][:-4]
                            suffix = path[len(directory)+1:] if directory else path
                            sprite_id = resource_id(domain+":"+prefix+suffix)
                            self.sprites[sprite_id] = {"type": kind, "inputs": [domain+":"+path], "atlas": relative, "source": owner.name}
                    elif kind == "single":
                        texture_id = resource_id(source.get("resource"))
                        sprite_id = resource_id(source.get("sprite", texture_id))
                        self.sprites[sprite_id] = {"type": kind, "inputs": [texture_id], "atlas": relative, "source": owner.name}
                    elif kind == "paletted_permutations":
                        textures, permutations = source.get("textures"), source.get("permutations")
                        if not isinstance(textures, list) or not isinstance(permutations, dict):
                            raise ValueError("paletted_permutations 须包含 textures 数组及 permutations 对象")
                        palette_key = resource_id(source.get("palette_key"))
                        for texture in textures:
                            texture_id = resource_id(texture)
                            for suffix, palette in permutations.items():
                                sprite_id = resource_id(texture_id+"_"+suffix)
                                self.sprites[sprite_id] = {"type": kind, "inputs": [texture_id, palette_key, resource_id(palette)], "atlas": relative, "source": owner.name}
                    elif kind == "filter":
                        pattern = source.get("pattern")
                        if not isinstance(pattern, dict) or set(pattern)-{"namespace", "path"}:
                            raise ValueError("filter pattern 仅包含 namespace/path 正则")
                        domain = re.compile(pattern.get("namespace", ".*"))
                        path = re.compile(pattern.get("path", ".*"))
                        for sprite_id in list(self.sprites):
                            ns, name = sprite_id.split(":", 1)
                            if domain.fullmatch(ns) and path.fullmatch(name):
                                del self.sprites[sprite_id]
                    else:
                        self.issue("UNSUPPORTED_ATLAS_SOURCE", "blocks 图集使用尚未适配的 source: " + kind, relative, source=owner.name)
                except (StudioError, ValueError, TypeError, re.error) as error:
                    self.issue("INVALID_ATLAS", str(error), relative, source=owner.name)
        # Project atlas declarations will be redistributed, so validate all of
        # their inputs. Dependency declarations stay external and are resolved
        # lazily for the selected models rather than copying the whole game.
        if any(source.role == "project" for source, _ in layers):
            self.atlas("minecraft:blocks", project_only=True)

    def atlas(self, identifier, *, project_only=False):
        relative = location("atlas", identifier)
        layers = self._atlas_layers(identifier)
        sources = [row for owner, rows in layers if not project_only or owner.role == "project" for row in rows]
        for source in sources:
            if not isinstance(source, dict):
                self.issue("INVALID_ATLAS", "atlas source 须为对象", relative)
                continue
            kind = source.get("type", "")
            if isinstance(kind, str) and kind.startswith("minecraft:"):
                kind = kind.split(":", 1)[1]
            if kind == "single":
                value = self._reference("texture", source.get("resource"), relative, "atlas_single")
                if value:
                    self.texture(value)
            elif kind == "directory":
                try:
                    directory = source.get("source")
                    if directory != "":
                        resource_path(directory)
                    for name in self._directory_textures(directory):
                        domain = name.split("/", 2)[1]
                        value = domain + ":" + name.split("/textures/", 1)[1][:-4]
                        self.edge(relative, name, "atlas_directory")
                        self.texture(value)
                except StudioError as error:
                    self.issue("INVALID_ATLAS", str(error), relative)
            elif kind == "paletted_permutations":
                textures, permutations = source.get("textures"), source.get("permutations")
                if not isinstance(textures, list) or not isinstance(permutations, dict):
                    self.issue("INVALID_ATLAS", "paletted_permutations 须包含 textures 数组与 permutations 对象", relative)
                    continue
                for reference in [*textures, source.get("palette_key"), *permutations.values()]:
                    value = self._reference("texture", reference, relative, "atlas_palette_input")
                    if value:
                        self.texture(value)
                for palette in permutations.values():
                    self._palette_size(source.get("palette_key"), palette, relative)
            elif kind == "filter":
                if not isinstance(source.get("pattern"), dict) or any(not isinstance(v, str) for v in source["pattern"].values()):
                    self.issue("INVALID_ATLAS", "filter 须包含字符串正则组成的 pattern 对象", relative)
            else:
                self.issue("UNSUPPORTED_ATLAS_SOURCE", "尚未适配的 atlas source: " + str(kind), relative)

    def run(self):
        try:
            self._open()
            self._index_sprites()
            if not self.entries:
                self.issue("NO_RESOURCE_ENTRIES", "先添加资源入口，或绑定当前画布的导出用途")
            for entry in self.entries:
                {"model": self.model, "blockstate": self.blockstate, "texture": self.texture, "atlas": self.atlas}[entry["kind"]](entry["id"])
            return self.report()
        finally:
            for source in self.sources:
                source.close()

    def report(self):
        files = sorted(self.nodes.values(), key=lambda item: item["path"])
        external = [deepcopy(item) for item in files if item["role"] == "dependency"]
        errors = sum(issue["severity"] == "error" for issue in self.issues)
        warnings = sum(issue["severity"] == "warning" for issue in self.issues)
        target = {"profile": self.config["profile"], **PROFILES[self.config["profile"]]}
        fingerprint = digest(encode({"config": self.config, "target": target, "content_digest": self.content_digest,
                                     "entries": self.entries, "files": files, "issues": self.issues, "edges": self.edges}))
        return {"schema": "pixforge.minecraft-validation/v1", "passed": errors == 0,
                "target": target, "validation_digest": fingerprint, "content_digest": self.content_digest,
                "errors": errors, "warnings": warnings, "issues": deepcopy(self.issues),
                "entries": deepcopy(self.entries), "files": files, "edges": deepcopy(self.edges),
                "sprites": [{"id": identifier, **rule} for identifier, rule in sorted(self.used_sprites.items())],
                "overrides": sorted(self.overrides.values(), key=lambda item: item["path"]),
                "source_stack": [{"name": s.name, "path": s.path, "role": s.role, "indexed_files": len(s.index)} for s in self.sources],
                "export_files": sorted(self.payload), "external_dependencies": external,
                "in_game_validated": False,
                "scope": "Explicit asset reference closure and target-format checks; registry coverage, actual pack order, rendering and mod runtime are not executed."}
