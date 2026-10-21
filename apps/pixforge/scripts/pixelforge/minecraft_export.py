"""Versioned asset generation and atomic ZIP publication, owned by the app."""
from copy import deepcopy
import io
import json
import math
from pathlib import Path
import zipfile

from PIL import Image

from .document import StudioError
from .minecraft_target import normalize, location
from .minecraft_resources import Audit, digest, encode
from .transactions import commit_files


def _binding(document, config):
    binding = config["binding"]
    if binding is None:
        return {}, [], []
    domain, kind = config["namespace"], binding["kind"]
    identifier, texture = domain + ":" + binding["path"], domain + ":" + binding["texture"]
    files, entries, issues = {}, [], []

    def issue(code, message, severity="error"):
        issues.append((code, message, severity))

    plan = document.animation
    rectangles, steps = plan["rectangles"], plan["steps"]
    w, h = plan["frame_size"]
    if w*h*len(rectangles) > 16_777_216:
        issue("EXPORTED_TEXTURE_TOO_LARGE", "导出帧条超过 16M 像素；请减少帧或尺寸")
        return files, entries, issues
    atlas = Image.new("RGBA", (w, h*len(rectangles)), (0, 0, 0, 0))
    image = document.canvas.composite()
    for index, (x, y, rw, rh) in enumerate(rectangles):
        atlas.paste(image.crop((x, y, x+rw, y+rh)), (0, index*h))
    stream = io.BytesIO()
    atlas.save(stream, format="PNG")
    png = location("texture", texture)
    files[png] = stream.getvalue()
    entries.append({"kind": "texture", "id": texture})
    if len(rectangles) > 1 or len(steps) > 1 or config.get("texture_animation") is not None:
        if not plan["loop"]:
            issue("NON_LOOPING_TEXTURE_UNSUPPORTED", ".mcmeta 纹理动画会循环，不能无损表达当前单次播放；请显式调整时序或使用运行时适配器")
        frames = []
        for step in steps:
            ticks = step["duration_ms"]/50
            if not math.isfinite(ticks) or abs(ticks-round(ticks)) > 1e-9 or ticks < 1:
                issue("ANIMATION_TICK_PRECISION", "Forge 1.20.1 纹理帧时长须为 50 ms 的正整数倍；不会静默四舍五入")
                break
            frames.append({"index": step["frame"], "time": round(ticks)})
        files[png+".mcmeta"] = encode({"animation": {"width": w, "height": h, "interpolate": config.get("texture_animation", {}).get("interpolate", False), "frames": frames}})
    if kind == "texture":
        if document.scene_animation is not None:
            issue("TEXTURE_ONLY_RUNTIME_NOT_INCLUDED", "本次仅导出纹理；部件或粒子仍需项目适配器", "warning")
        return files, entries, issues
    if document.scene_animation is not None:
        issue("SCENE_ADAPTER_REQUIRED", "普通资源包不能承载当前部件 / 粒子 / 状态动画；先使用项目运行时适配器，或明确选择仅纹理导出")
    model = deepcopy(document.shapes["model"])
    if model is None and kind == "block":
        issue("MODEL_REQUIRED", "方块资源需要当前工程的显式模型；纯像素工程可选择仅纹理或物品导出")
        return files, entries, issues
    model_id = domain + ":" + ("block/" if kind == "block" else "item/") + binding["path"]
    if model is None:
        # This is a real resource dependency. The checker resolves the target's
        # actual vanilla template instead of inventing its transforms or bytes.
        model = {"parent": "minecraft:item/generated", "textures": {"layer0": texture}}
    else:
        definitions = model.get("textures", {})
        model["textures"] = {key: value if value.startswith("#") else texture for key, value in definitions.items()}
        model["textures"].setdefault("particle", texture)
        for element in model.get("elements", []):
            for face in element.get("faces", {}).values():
                if not face["texture"].startswith("#"):
                    face["texture"] = texture
    files[location("model", model_id)] = encode(model)
    entries.append({"kind": "model", "id": model_id})
    if kind == "block":
        files[location("blockstate", identifier)] = encode({"variants": {"": {"model": model_id}}})
        item_id = domain + ":item/" + binding["path"]
        files[location("model", item_id)] = encode({"parent": model_id})
        entries += [{"kind": "blockstate", "id": identifier}, {"kind": "model", "id": item_id}]
        issue("BLOCK_REGISTRATION_REQUIRED", "资源包只提供已注册方块的外观；方块注册、物理形状和行为仍由模组代码管理", "warning")
    return files, entries, issues


def inspect(document, *, settings=None, use_document=True, include_generated_code=False):
    if type(use_document) is not bool or type(include_generated_code) is not bool:
        raise StudioError("use_document/include_generated_code 须为布尔值")
    config = normalize(settings if settings is not None else document.minecraft_project, document.workspace)
    if config is None:
        raise StudioError("当前工程尚未配置 Minecraft 目标；先读取 minecraft-capabilities 并配置目标", "MINECRAFT_TARGET_REQUIRED")
    if include_generated_code and (not use_document or not config.get("runtime")):
        raise StudioError("生成代码预览需要包含当前工程的 Forge 运行时配置", "FORGE_RUNTIME_REQUIRED")
    code, runtime_report = {}, None
    if use_document and config.get("runtime"):
        from .forge_export import build
        overlay, entries, code, issues, runtime_report = build(document, config)
    else:
        overlay, entries, issues = _binding(document, config) if use_document else ({}, [], [])
    material_files,material_report={},None
    if use_document and document.material_data is not None:
        from .material_data import build as build_material
        material_files,material_report=build_material(document,config,overlay)
        issues += [(item['code'],item['message'],item['severity']) for item in material_report['issues']]
    audit = Audit(config, overlay=overlay, entries=entries, content_digest=document.art_digest())
    for issue_code, message, severity in issues:
        audit.issue(issue_code, message, severity=severity, source="current-document")
    report = audit.run()
    report.update(document_id=document.document_id, revision=document.revision,
                  current_document_included=use_document and config["binding"] is not None,
                  draft_configuration=settings is not None)
    payload = audit.payload
    if runtime_report is not None:
        report["forge_runtime"] = runtime_report
        report["validation_digest"] = digest(encode({"resources": report["validation_digest"], "forge_runtime": runtime_report}))
        payload = {**payload, **overlay, **code}
        report["export_files"] = sorted(payload)
        report["current_document_included"] = True
        if include_generated_code:
            from .forge_export import project_files
            definition_path = runtime_report.get("runtime_definition_path")
            report["generated_sources"] = {"runtime": {name: raw.decode("utf-8") for name, raw in sorted(code.items())},
                "forge-integration": {name: raw.decode("utf-8") for name, raw in sorted(project_files(config, standalone=False, scene_geometry=runtime_report.get("scene_geometry", True)).items())},
                "forge-mod": {name: raw.decode("utf-8") for name, raw in sorted(project_files(config, standalone=True, scene_geometry=runtime_report.get("scene_geometry", True)).items())}}
            if definition_path in overlay:
                report["generated_sources"]["runtime"][definition_path] = overlay[definition_path].decode("utf-8")
    if material_report is not None:
        report['material_data']=material_report
        payload={**payload,**material_files}
        report['export_files']=sorted(payload)
        report['validation_digest']=digest(encode({'resources':report['validation_digest'],'material_data':material_report}))
        report['current_document_included']=True
    return report, payload


def publish(document, path, *, validation_digest, format="resource-pack", overwrite=False):
    document.guard(observed=False)
    if not document.approved():
        raise StudioError("请先展示并确认当前工程与资源检查结果", "USER_CONFIRMATION_REQUIRED")
    if not isinstance(validation_digest, str) or len(validation_digest) != 64:
        raise StudioError("导出须提交本轮 minecraft-check 返回的 validation_digest", "RESOURCE_VALIDATION_REQUIRED")
    if format not in ("resource-pack", "mod-assets", "forge-integration", "forge-mod") or type(overwrite) is not bool:
        raise StudioError("format 为 resource-pack/mod-assets/forge-integration/forge-mod，overwrite 为布尔值")
    runtime = bool(document.minecraft_project and document.minecraft_project.get("runtime"))
    if runtime != (format in ("forge-integration", "forge-mod")):
        raise StudioError("运行时工程使用 forge-integration 或 forge-mod；普通资源工程使用 resource-pack 或 mod-assets，避免静默省略代码", "FORGE_EXPORT_FORMAT_MISMATCH")
    report, files = inspect(document)
    if not report["passed"]:
        raise StudioError("资源或目标格式检查失败，未写入导出文件", "RESOURCE_VALIDATION_FAILED", details={"validation": report})
    if report["validation_digest"] != validation_digest:
        raise StudioError("工程或依赖文件已有变化；请重新检查、展示并确认", "RESOURCE_VALIDATION_STALE", details={"validation": report})
    if document.approval.get("minecraft_validation_digest") != validation_digest:
        raise StudioError("资源依赖与用户确认时不一致；重新生成证据并确认当前资源", "RESOURCE_REVIEW_REQUIRED")
    path = Path(path).resolve()
    protected = {document.project_path, document.source_path}
    protected.update(Path(item["path"]).resolve() for item in document.minecraft_project["sources"])
    if path.suffix.lower() != ".zip" or path in protected or path.is_relative_to(document.runtime):
        raise StudioError("资源导出使用工程、来源和会话内部文件之外的 .zip 路径")
    if path.exists() and not overwrite:
        raise StudioError("导出文件已存在，选择新路径或明确允许覆盖", "FILE_EXISTS")
    if not files:
        raise StudioError("引用闭包没有可导出的项目文件；dependency 来源只解析，不重新分发", "NO_PROJECT_ASSETS")
    files = dict(files)
    if runtime:
        from .forge_export import project_files
        files = {("src/main/resources/"+name if name.startswith("assets/") else name): raw for name, raw in files.items()}
        files["src/main/resources/pack.mcmeta"] = encode({"pack": {"pack_format": 15, "description": document.minecraft_project["description"]}})
        files.update(project_files(document.minecraft_project, standalone=format == "forge-mod", scene_geometry=report["forge_runtime"].get("scene_geometry", True)))
    if format == "resource-pack":
        files["pack.mcmeta"] = encode({"pack": {"pack_format": 15, "description": document.minecraft_project["description"]}})
    manifest = {"schema": "pixforge.minecraft-export/v1", "exporter_version": "2.9.0", "format": format,
                "target": report["target"], "document_id": document.document_id,
                "content_digest": document.art_digest(), "validation_digest": validation_digest,
                "files": {name: digest(raw) for name, raw in sorted(files.items())},
                "external_dependencies": [{key: value for key, value in item.items() if key in ("path", "source", "sha256", "bytes")} for item in report["external_dependencies"]],
                "warnings": [item for item in report["issues"] if item["severity"] == "warning"],
                "in_game_validated": False,
                "scope": "Generated Forge integration source and authored assets; consuming mod supplies real state, formation and lifecycle. No deployment or game validation." if runtime else "Selected assets only. No code registration, physical shapes, runtime animation adapter or game deployment.",
                **({"forge_runtime": report["forge_runtime"]} if runtime else {}),
                **({'material_data':report['material_data']} if 'material_data' in report else {})}
    files["pixforge-export.json"] = encode(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    raw = stream.getvalue()
    commit_files({path: raw})
    document.event("导出 Forge 1.20.1 资源 " + path.name)
    return {"path": str(path), "format": format, "target": report["target"], "sha256": digest(raw),
            "validation_digest": validation_digest, "content_digest": document.art_digest(),
            "files": sorted(files), "external_dependency_count": len(report["external_dependencies"]),
            "in_game_validated": False}
