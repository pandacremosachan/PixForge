"""Discover and control a native desktop through its documented local API."""
import argparse
import json
from pathlib import Path
import sys

from .document import StudioError
from .studio_bridge import StudioClient, runtime_path


def call_frontend(action="ui_status", *, workspace=None, runtime=None, **payload):
    client = StudioClient(runtime_path(workspace, runtime) / "gui")
    return client.call(action, **payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, help="core session directory, not its gui subdirectory")
    parser.add_argument("--workspace", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "help", "metrics", "controls", "focus", "scene-context"):
        sub.add_parser(command)
    sample = sub.add_parser("scene-sample", help="read native C++ scene sample for the current view")
    sample.add_argument("--time-ms", type=float)
    sample.add_argument("--scene-state", help="canonical named state; omit to inspect current playback")
    editor = sub.add_parser("scene-editor", help="control this application's draft keyframe/state editor")
    editor.add_argument("operation", choices=("open","status","cancel","apply","field","invoke","capture"))
    editor.add_argument("--name", help="field or action id, as shown in editor status")
    editor.add_argument("--value", help="field value as JSON; use a JSON string for text input")
    editor.add_argument("--path", type=Path)
    editor.add_argument("--overwrite", action="store_true")
    target_editor = sub.add_parser("minecraft-editor", help="control the draft target/resource editor; no approval or export")
    target_editor.add_argument("operation", choices=("open", "status", "cancel", "apply", "field", "invoke", "capture"))
    target_editor.add_argument("--name")
    target_editor.add_argument("--value", help="JSON field value")
    target_editor.add_argument("--path", type=Path)
    target_editor.add_argument("--overwrite", action="store_true")
    preview = sub.add_parser("minecraft-preview", help="read-only native Minecraft render preview")
    preview.add_argument("operation", choices=("open","status","cancel","configure","field","invoke","camera","capture"))
    preview.add_argument("--name")
    preview.add_argument("--value", help="JSON field value or options object for configure/camera")
    preview.add_argument("--path", type=Path)
    preview.add_argument("--overwrite", action="store_true")
    workbench = sub.add_parser("minecraft-workbench", help="animation and whole-scene regression workbench")
    workbench.add_argument("operation", choices=("open","status","cancel","field","invoke","capture"))
    workbench.add_argument("--name")
    workbench.add_argument("--value", help="JSON field value")
    workbench.add_argument("--path", type=Path)
    workbench.add_argument("--overwrite", action="store_true")
    material=sub.add_parser('minecraft-material-editor',help='independent LabPBR byte channels and shader-target contract')
    material.add_argument('operation',choices=('open','status','cancel','field','invoke','paint','capture'))
    material.add_argument('--name');material.add_argument('--value',help='JSON field value or raw operation list for paint');material.add_argument('--path',type=Path);material.add_argument('--overwrite',action='store_true')
    settings = sub.add_parser("set", help="change view/tool settings; never modifies artwork")
    settings.add_argument("settings", help="JSON object, @file.json or '-' for stdin")
    capture = sub.add_parser("capture", help="capture only PixForge's own client area for discussion")
    capture.add_argument("path", type=Path)
    capture.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        fields = {}
        if args.command in ("scene-editor", "minecraft-editor", "minecraft-preview", "minecraft-workbench", "minecraft-material-editor"):
            fields["operation"] = args.operation
            if args.name is not None:fields["name"] = args.name
            if args.value is not None:fields["value"] = json.loads(args.value)
            if args.path is not None:fields["path"] = str(args.path.resolve())
            if args.overwrite:fields["overwrite"] = True
        if args.command=='minecraft-material-editor' and args.operation=='paint':fields['operations']=fields.pop('value',[])
        if args.command == "minecraft-preview" and args.operation == "configure":
            fields["options"] = fields.pop("value", {})
        if args.command == "minecraft-preview" and args.operation == "camera":
            fields.update(fields.pop("value", {}))
        if args.command == "scene-sample" and args.time_ms is not None:
            fields["time_ms"] = args.time_ms
        if args.command == "scene-sample" and args.scene_state is not None:
            fields["scene_state"] = args.scene_state
        if args.command == "set":
            raw = (sys.stdin.read() if args.settings == "-" else
                   Path(args.settings[1:]).read_text(encoding="utf-8") if args.settings.startswith("@") else args.settings)
            fields["settings"] = json.loads(raw)
        elif args.command == "capture":
            fields = {"path": str(args.path.resolve()), "overwrite": args.overwrite}
        result = call_frontend("focus" if args.command == "focus" else "ui_" + args.command.replace("-", "_"),
                               runtime=args.runtime, workspace=args.workspace, **fields)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error), "code": getattr(error, "code", "INVALID_ARGUMENT")}, ensure_ascii=False), file=sys.stderr)
        return 1
