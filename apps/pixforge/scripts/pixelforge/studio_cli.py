"""CLI adapter for a durable session, with an optional GUI attached."""
import argparse
import base64
import json
from pathlib import Path
import sys

from .studio_bridge import StudioClient, runtime_path
from .document import StudioError
from .service import ensure_session
from .transactions import commit_files
from .shape_builder import DEFAULT_BUILD_ERROR, DEFAULT_BUILD_TARGET_BOXES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, help="same session directory as the GUI")
    parser.add_argument("--workspace", type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status", help="read project id/revision, user feedback and export approval")
    sub.add_parser("animation-capabilities", help="discover combinable mechanisms; default target Forge 1.20.1")
    sub.add_parser("minecraft-capabilities", help="discover versioned target profiles and asset adapter boundaries")
    check = sub.add_parser("minecraft-check", help="read-only reference graph, source precedence and target checks")
    check.add_argument("--config", type=Path, help="optional draft configuration; does not apply it")
    check.add_argument("--sources-only", action="store_true", help="inspect declared source entries without the current texture overlay")
    check.add_argument("--include-generated-code", action="store_true", help="include read-only Forge Java/build/definition previews before approval/export")
    material=sub.add_parser('minecraft-material',help='inspect LabPBR 1.3 raw channels, decoded meanings and shader contract; read only')
    material.add_argument('--role',choices=('normal','specular'),default='normal');material.add_argument('--channel',default='r')
    material.add_argument('--view',choices=('channel','packed','normal_vectors','decoded'),default='channel')
    material.add_argument('--pixel',nargs=2,type=int);material.add_argument('--resource');material.add_argument('--config',type=Path);material.add_argument('--time-ms',type=float)
    material.add_argument('--output',type=Path);material.add_argument('--overwrite',action='store_true')
    material.add_argument('--max-size',type=int,default=1024)
    material_config=sub.add_parser('minecraft-material-configure',help='configure optional raw data maps/shader contract, one undo step')
    material_config.add_argument('--settings',help='JSON, @file or -; null clears the data maps',required=True)
    material_import=sub.add_parser('minecraft-material-import',help='import exact PNG map or one mask channel without compositing')
    material_import.add_argument('--role',choices=('normal','specular'),required=True);material_import.add_argument('--path',type=Path);material_import.add_argument('--resource');material_import.add_argument('--channel')
    material_edit=sub.add_parser('minecraft-material-edit',help='atomic raw-byte rectangle edits to one data channel')
    material_edit.add_argument('--role',choices=('normal','specular'),required=True);material_edit.add_argument('--channel',required=True)
    material_edit.add_argument('--operations',required=True,help='JSON list, @file or -: rect [x,y,width,height], value 0..255')
    for command in (material_config,material_import,material_edit):
        command.add_argument('--expected-document-id',required=True);command.add_argument('--expected-revision',type=int,required=True)
    animation_meta = sub.add_parser("minecraft-animation", help="inspect .mcmeta timing and target interpolation, read only")
    animation_meta.add_argument("--metadata", type=Path)
    animation_meta.add_argument("--time-ms", type=float, default=0)
    animation_meta.add_argument("--output", type=Path)
    animation_meta.add_argument("--overwrite", action="store_true")
    apply_meta = sub.add_parser("minecraft-animation-apply", help="apply .mcmeta timing and interpolation as one undoable change")
    apply_meta.add_argument("--metadata", type=Path, required=True)
    apply_meta.add_argument("--expected-document-id", required=True)
    apply_meta.add_argument("--expected-revision", type=int, required=True)
    performance = sub.add_parser("minecraft-performance", help="read-only whole-scene census; optional controlled alpha coverage view")
    performance.add_argument("--options", help="JSON, @file.json or -")
    performance.add_argument("--output", type=Path)
    performance.add_argument("--overwrite", action="store_true")
    regression = sub.add_parser("minecraft-regression-compare", help="compare supplied actual game capture directories, pixels and CPU observations")
    regression.add_argument("baseline", type=Path)
    regression.add_argument("candidate", type=Path)
    regression.add_argument("--budgets", help="pixel_threshold/changed_fraction/p95_ratio JSON")
    for command in ("minecraft-scene", "minecraft-preview"):
        mc_view = sub.add_parser(command, help="read-only Forge 1.20.1 material/state/lighting reference preview")
        mc_view.add_argument("--config", type=Path, help="optional target/source draft; never applies it")
        mc_view.add_argument("--options", help="view options as JSON, @file.json or - for stdin")
        if command == "minecraft-scene":
            mc_view.add_argument("--include-pixels", action="store_true", help="include actual RGBA texture data")
        else:
            mc_view.add_argument("--output", type=Path, required=True, help="discussion PNG, never a production texture")
            mc_view.add_argument("--overwrite", action="store_true")
            mc_view.add_argument("--batch", action="store_true", help="paged state/weighted/context comparison")
            mc_view.add_argument("--contexts", nargs="+")
            mc_view.add_argument("--case-offset", type=int, default=0)
            mc_view.add_argument("--case-limit", type=int, default=16)
    configure = sub.add_parser("minecraft-configure", help="apply or clear an undoable target configuration")
    config_choice = configure.add_mutually_exclusive_group(required=True)
    config_choice.add_argument("--config", type=Path)
    config_choice.add_argument("--clear", action="store_true")
    configure.add_argument("--expected-document-id", required=True)
    configure.add_argument("--expected-revision", type=int, required=True)
    minecraft_export = sub.add_parser("minecraft-export", help="validate and publish a versioned asset ZIP after current user approval")
    minecraft_export.add_argument("path", type=Path)
    minecraft_export.add_argument("--validation-digest", required=True)
    minecraft_export.add_argument("--format", choices=("resource-pack", "mod-assets", "forge-integration", "forge-mod"), default="resource-pack")
    minecraft_export.add_argument("--overwrite", action="store_true")
    minecraft_export.add_argument("--expected-document-id", required=True)
    minecraft_export.add_argument("--expected-revision", type=int, required=True)
    scene_sample = sub.add_parser("scene-sample", help="read deterministic part and particle samples")
    scene_sample.add_argument("--time-ms", type=float, default=0)
    scene_sample.add_argument("--scene-state", help="named state id; otherwise sample the complete process")
    scene_validate = sub.add_parser("scene-validate", help="validate an animation draft without applying it")
    scene_validate.add_argument("definition", type=Path)
    prepare = sub.add_parser("animation-prepare", help="add source frames and timing in one undoable change")
    prepare.add_argument("definition", type=Path)
    prepare.add_argument("--expected-document-id", required=True)
    prepare.add_argument("--expected-revision", type=int, required=True)
    for name in ("project-plan", "create-project"):
        setup = sub.add_parser(name, help="model-first project with an automatically matched UV canvas")
        setup.add_argument("--preset", choices=("cube-faces", "cube-shared", "model", "pixels"))
        setup.add_argument("--model", type=Path, help="resolved single-atlas Java model JSON")
        setup.add_argument("--face-size", type=int)
        setup.add_argument("--width", type=int)
        setup.add_argument("--height", type=int)
        if name == "create-project":
            setup.add_argument("--expected-document-id", required=True)
            setup.add_argument("--expected-revision", type=int, required=True)
    uv = sub.add_parser("model-uv", help="read actual model faces, UV regions and shared/overlapping pixel ownership")
    uv.add_argument("--frame", type=int)
    uv.add_argument("--x", type=int, help="atlas pixel x; supply together with --y")
    uv.add_argument("--y", type=int, help="atlas pixel y within the selected frame")
    preview = sub.add_parser("preview", help="save labeled discussion evidence, not a production texture")
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--scale", type=int, default=6)
    preview.add_argument("--tile", action="store_true")
    preview.add_argument("--overwrite", action="store_true")
    player = sub.add_parser("animation-preview", help="standalone timed HTML from in-memory frames; no native PNG export")
    player.add_argument("--output", type=Path, required=True)
    player.add_argument("--scale", type=int, default=6)
    player.add_argument("--overwrite", action="store_true")
    shape_preview = sub.add_parser("shape-preview", help="PNG or interactive standalone HTML discussion preview")
    shape_preview.add_argument("--output", type=Path, required=True)
    shape_preview.add_argument("--size", type=int, default=400)
    shape_preview.add_argument("--yaw", type=float, default=35)
    shape_preview.add_argument("--pitch", type=float, default=30)
    shape_preview.add_argument("--overlays", nargs="*", choices=("base", "collision", "selection"), default=["collision"])
    shape_preview.add_argument("--frame", type=int)
    shape_preview.add_argument("--overwrite", action="store_true")
    for action in ("edit", "validate", "undo", "redo", "new", "open", "save", "animation", "scene-animation", "approve", "export", "note", "shutdown", "shapes", "shape-edit", "shape-validate", "model-import", "shape-export", "shape-build", "shape-optimize"):
        descriptions={"shape-build":"default for new shapes: conservative reconstruction from the original model",
                      "shape-optimize":"optional lossless cleanup of existing shapes (default error 0)"}
        command = sub.add_parser(action, **({"help":descriptions[action]} if action in descriptions else {}))
        command.add_argument("--expected-document-id", required=True)
        command.add_argument("--expected-revision", type=int, required=True)
        if action in ("edit", "validate"):
            command.add_argument("script", help=".px file, or '-' for stdin")
            command.add_argument("--label", default="AI 修改")
            command.add_argument("--preview", type=Path)
            command.add_argument("--overwrite-preview", action="store_true")
        elif action == "new":
            command.add_argument("width", type=int)
            command.add_argument("height", type=int)
        elif action in ("open", "save", "animation", "scene-animation", "export", "shapes", "shape-edit", "shape-validate", "model-import", "shape-export"):
            command.add_argument("path", type=Path)
            if action in ("export", "shape-export"):
                command.add_argument("--overwrite", action="store_true")
            if action == "export":
                command.add_argument("--frame", type=int)
                command.add_argument("--scale", type=int, default=1)
            if action == "shape-export":
                command.add_argument("--format", choices=("json", "forge-1.20.1"), default="json")
                command.add_argument("--class-name", default="BlockShapes")
                command.add_argument("--package", default="")
        elif action == "approve":
            command.add_argument("--user-request", required=True, help="quote the actual human's approval of THIS version; never infer approval from AI checks")
        elif action in ("shape-build", "shape-optimize"):
            command.add_argument("--target", choices=("base","collision","selection"), default="base")
            command.add_argument("--max-error", type=float, default=DEFAULT_BUILD_ERROR if action=="shape-build" else 0,
                help="outward error in model units; new shapes use conservative model reconstruction (default: %(default)s)")
            command.add_argument("--target-boxes", type=int, default=DEFAULT_BUILD_TARGET_BOXES if action=="shape-build" else 1,
                help="search goal within the error bound (default: %(default)s)")
            command.add_argument("--symmetry", choices=("auto","none"), default="auto")
            command.add_argument("--dry-run", action="store_true")
        elif action == "note":
            command.add_argument("text")
    args = parser.parse_args(argv)
    try:
        client = ensure_session(args.workspace, args.runtime)
        payload = {}
        if args.action in ("minecraft-configure", "minecraft-check", "minecraft-scene", "minecraft-preview", "minecraft-material"):
            if args.config is not None:
                payload["settings"] = json.loads(args.config.read_text(encoding="utf-8-sig"))
            if args.action == "minecraft-configure" and args.clear:
                payload["settings"] = None
            if args.action == "minecraft-check":
                payload["use_document"] = not args.sources_only
        if args.action.startswith('minecraft-material'):
            for key in ('settings','operations'):
                if hasattr(args,key) and getattr(args,key) is not None:
                    value=getattr(args,key);raw=sys.stdin.read() if value=='-' else Path(value[1:]).read_text(encoding='utf-8-sig') if value.startswith('@') else value;payload[key]=json.loads(raw)
            for key in ('role','channel','view','pixel','resource','max_size'):
                if hasattr(args,key) and getattr(args,key) is not None:payload[key]=getattr(args,key)
        if args.action in ("minecraft-animation", "minecraft-animation-apply"):
            if args.metadata is not None:payload["metadata"] = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
            if args.action == "minecraft-animation":payload["time_ms"] = args.time_ms
        if args.action == "minecraft-regression-compare":
            payload.update(baseline=str(args.baseline.resolve()), candidate=str(args.candidate.resolve()))
            if args.budgets:payload["budgets"] = json.loads(args.budgets)
        if args.action == "minecraft-performance" and args.options is not None:
            raw = sys.stdin.read() if args.options == "-" else Path(args.options[1:]).read_text(encoding="utf-8-sig") if args.options.startswith("@") else args.options
            payload["options"] = json.loads(raw)
        if args.action in ("minecraft-scene", "minecraft-preview"):
            if args.options is not None:
                raw = sys.stdin.read() if args.options == "-" else Path(args.options[1:]).read_text(encoding="utf-8-sig") if args.options.startswith("@") else args.options
                payload["options"] = json.loads(raw)
            for key in ("include_pixels", "batch", "contexts", "case_offset", "case_limit"):
                if hasattr(args, key) and getattr(args, key) is not None:
                    payload[key] = getattr(args, key)
        if args.action in ("scene-validate", "animation-prepare"):
            payload["settings"] = json.loads(args.definition.read_text(encoding="utf-8-sig"))
        if args.action in ("project-plan", "create-project"):
            settings = {k: getattr(args, k) for k in ("preset", "face_size", "width", "height") if getattr(args, k) is not None}
            if args.model is not None:
                settings["model"] = json.loads(args.model.read_text(encoding="utf-8-sig"))
            payload["settings"] = settings
        for key in ("expected_document_id", "expected_revision", "validation_digest", "width", "height", "label", "frame", "x", "y", "scale", "overwrite", "user_request", "text", "tile", "size", "yaw", "pitch", "overlays", "format", "class_name", "package", "target", "max_error", "target_boxes", "symmetry", "dry_run", "include_hidden", "include_generated_code", "time_ms", "scene_state"):
            if hasattr(args, key) and getattr(args,key) is not None:
                payload[key] = getattr(args, key)
        if args.action in ("project-plan", "create-project"):
            payload = {k: v for k, v in payload.items() if k in ("settings", "expected_document_id", "expected_revision")}
        if hasattr(args, "path") and args.path is not None:
            payload["path"] = str(args.path.resolve())
        if args.action == "scene-animation":
            payload = {key: value for key, value in payload.items() if key != "path"}
            payload["settings"] = json.loads(args.path.read_text(encoding="utf-8-sig"))
        if args.action in ("edit", "validate"):
            payload["commands"] = sys.stdin.read() if args.script == "-" else Path(args.script).read_text(encoding="utf-8")
            payload["include_preview"] = args.preview is not None
        evidence = args.output if args.action in ("preview", "animation-preview", "shape-preview", "minecraft-preview", "minecraft-animation", "minecraft-performance", "minecraft-material") else getattr(args, "preview", None)
        if evidence is not None:
            if evidence.exists() and not (getattr(args, "overwrite", False) or getattr(args, "overwrite_preview", False)):
                raise StudioError("预览文件已存在，选新路径或明确允许覆盖", "FILE_EXISTS")
            state = client.call("status")
            protected = [Path(value).resolve() for value in (state.get("project_path"), state.get("source_path")) if value]
            if hasattr(args, "script") and args.script != "-":
                protected.append(Path(args.script).resolve())
            if evidence.resolve() in protected:
                raise StudioError("讨论预览不能覆盖工程、源图或脚本")
            if args.action == "animation-preview" and evidence.suffix.lower() != ".html":
                raise StudioError("动画预览使用 .html 文件")
            if args.action in ("minecraft-preview","minecraft-material") and evidence.suffix.lower() != ".png":
                raise StudioError("Minecraft 讨论预览使用 .png 文件")
            if args.action == "shape-preview":
                if evidence.suffix.lower() not in (".png", ".html"):
                    raise StudioError("形状预览使用 .png 或 .html 文件")
                payload["html"] = evidence.suffix.lower() == ".html"
        result = client.call(args.action.replace("-", "_"), **payload)
        image = result.pop("image", None)
        html = result.pop("html", None)
        if evidence is not None and image and not html:
            commit_files({evidence.resolve(): base64.b64decode(image)})
            result["preview"] = str(evidence.resolve())
        if evidence is not None and html:
            commit_files({evidence.resolve(): html.encode("utf-8")})
            result["preview"] = str(evidence.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.action in ("minecraft-check", "minecraft-scene", "minecraft-preview") and not result["validation"]["passed"] else 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error), "code": getattr(error, "code", "INVALID_ARGUMENT"),
                          "details": getattr(error, "details", None)}, ensure_ascii=False), file=sys.stderr)
        return 1
