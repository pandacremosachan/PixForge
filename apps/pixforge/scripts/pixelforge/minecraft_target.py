"""Application-owned Minecraft target configuration. No skill/runtime coupling."""
from copy import deepcopy
from pathlib import Path
import re

from .document import StudioError

SCHEMA = "pixforge.minecraft-project/v1"
RUNTIME_SCHEMA = "pixforge.minecraft-project/v2"
EXTENDED_SCHEMA = "pixforge.minecraft-project/v3"
CAPABILITY = "minecraft-assets/v1"
PROFILES = {
    "forge-1.20.1": {
        "edition": "java", "minecraft": "1.20.1", "loader": "forge",
        "resource_pack_format": 15, "adapter_version": 1,
        "item_definition": "models/item", "texture_tick_ms": 50,
        "references": [
            "https://docs.minecraftforge.net/en/1.20.1/concepts/resources/",
            "https://docs.minecraftforge.net/en/1.20.1/datagen/client/modelproviders/",
            "https://www.minecraft.net/en-us/article/trails-tales-update-out-today-java",
        ],
    }
}
KINDS = ("blockstate", "model", "texture", "atlas")
_NAMESPACE = re.compile(r"[a-z0-9_.-]+\Z")
_PATH = re.compile(r"[a-z0-9_./-]+\Z")


def fail(message, code="INVALID_MINECRAFT_CONFIG"):
    raise StudioError(message, code)


def namespace(value):
    if not isinstance(value, str) or not _NAMESPACE.fullmatch(value) or value in (".", ".."):
        fail("namespace 使用小写字母、数字、下划线、点或连字符")
    return value


def resource_path(value):
    if (not isinstance(value, str) or not value or len(value) > 240 or not _PATH.fullmatch(value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        fail("资源路径须为小写的相对路径，不含空段、反斜线、. 或 ..")
    return value


def resource_id(value):
    if not isinstance(value, str) or value.count(":") > 1:
        fail("资源引用须为 namespace:path 字符串")
    domain, path = value.split(":", 1) if ":" in value else ("minecraft", value)
    return namespace(domain) + ":" + resource_path(path)


def location(kind, identifier):
    identifier = resource_id(identifier)
    domain, path = identifier.split(":", 1)
    folder, suffix = {"blockstate": ("blockstates", ".json"), "model": ("models", ".json"),
                      "texture": ("textures", ".png"), "atlas": ("atlases", ".json")}[kind]
    return f"assets/{domain}/{folder}/{path}{suffix}"


def capabilities():
    from .minecraft_view import capabilities as preview_capabilities
    return {"capability": CAPABILITY, "schema": SCHEMA, "profiles": deepcopy(PROFILES),
            "preview": preview_capabilities(),
            "source_order": "low to high; current document binding is the final overlay",
            "source_types": ["resource directory", "resource-pack ZIP", "mod/client JAR"],
            "entry_kinds": list(KINDS), "export_formats": ["resource-pack", "mod-assets", "forge-integration", "forge-mod"],
            "additional_capabilities": ["forge-runtime/v1", "minecraft-preview/v1", "minecraft-animation/v1", "minecraft-regression/v1", "minecraft-material/v1"], "runtime_schema": "pixforge.forge-runtime/v1",
            "project_formats": ["pixelforge.desktop/v1", "pixelforge.desktop/v2", "pixelforge.desktop/v3", "pixelforge.desktop/v4"],
            "configured_projects_require": "Assets: PixForge 2.3+; Forge runtime: 2.4+; data materials: 2.7+; old projects retain their existing format",
            "checks": ["reference closure", "parent and texture aliases", "source precedence",
                       "PNG and animation metadata", "target model format", "export fingerprints"],
            "limitations": ["offline assets only; no game execution or registry/state coverage proof",
                            "unrecognized third-party loaders and custom shaders require separate adapters",
                            "Forge runtime export generates code; consuming mods supply real server state",
                            "dependency sources are checked but not redistributed",
                            "old projects remain unconfigured until a target is explicitly applied"]}


def normalize(value, base=None):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"schema", "profile", "namespace", "sources", "entries", "binding", "description", "runtime", "texture_animation"}:
        fail("目标配置仅包含 schema/profile/namespace/sources/entries/binding/description/runtime")
    if value.get("schema", SCHEMA) not in (SCHEMA, RUNTIME_SCHEMA, EXTENDED_SCHEMA):
        fail("不支持的 Minecraft 工程配置格式")
    profile = value.get("profile", "forge-1.20.1")
    if not isinstance(profile, str) or profile not in PROFILES:
        fail("当前可导出目标为 forge-1.20.1；其他版本需要对应适配器", "UNSUPPORTED_MINECRAFT_TARGET")
    domain = namespace(value.get("namespace", "examplemod"))
    sources = value.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 16:
        fail("sources 使用最多 16 个按低到高排序的资源来源")
    normalized_sources, names = [], set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) - {"name", "path", "role"}:
            fail("每个来源仅包含 name/path/role")
        name, path, role = source.get("name", f"source-{index+1}"), source.get("path"), source.get("role", "project")
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or name in names or name == "current-document":
            fail("来源名称须非空、唯一，不使用保留名称 current-document")
        if not isinstance(path, str) or not path.strip() or len(path) > 2000:
            fail("资源来源须指定目录、ZIP 或 JAR 路径")
        if role not in ("project", "dependency"):
            fail("来源 role 为 project（随选中资源导出）或 dependency（仅解析，不复制）")
        if base is not None:
            file = Path(path).expanduser()
            path = str((file if file.is_absolute() else Path(base)/file).resolve())
        names.add(name)
        normalized_sources.append({"name": name, "path": path, "role": role})
    entries = value.get("entries", [])
    if not isinstance(entries, list) or len(entries) > 256:
        fail("entries 使用最多 256 个资源入口")
    normalized_entries = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"kind", "id"} or entry.get("kind") not in KINDS:
            fail("资源入口包含 kind（blockstate/model/texture/atlas）与 id")
        item = {"kind": entry["kind"], "id": resource_id(entry["id"])}
        if item not in normalized_entries:
            normalized_entries.append(item)
    binding = value.get("binding")
    if binding is not None:
        if not isinstance(binding, dict) or set(binding) - {"kind", "path", "texture"}:
            fail("画布绑定仅包含 kind/path/texture")
        kind = binding.get("kind", "texture")
        if kind not in ("block", "item", "texture"):
            fail("画布绑定 kind 为 block/item/texture")
        path = resource_path(binding.get("path", "new_asset"))
        texture = resource_path(binding.get("texture", ("item/" if kind == "item" else "block/") + path))
        binding = {"kind": kind, "path": path, "texture": texture}
    description = value.get("description", "PixForge · Forge 1.20.1 resources")
    if not isinstance(description, str) or not description.strip() or len(description) > 500:
        fail("资源包说明须为 1..500 字的文字")
    result = {"schema": SCHEMA, "profile": profile, "namespace": domain,
            "sources": normalized_sources, "entries": normalized_entries,
            "binding": binding, "description": description}
    if value.get("runtime") is not None:
        from .forge_export import normalize as normalize_runtime
        result["runtime"] = normalize_runtime(value["runtime"], domain)
        result["schema"] = RUNTIME_SCHEMA
    if value.get("texture_animation") is not None:
        option = value["texture_animation"]
        if not isinstance(option, dict) or set(option) != {"interpolate"} or type(option["interpolate"]) is not bool:
            fail("texture_animation 使用 {interpolate: true/false}")
        result["texture_animation"] = {"interpolate": option["interpolate"]}
        result["schema"] = EXTENDED_SCHEMA
    return result
