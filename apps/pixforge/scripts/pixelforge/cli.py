"""PixForge CLI: run command scripts against a session."""
import argparse
import sys
import json
from pathlib import Path

from .protocol import Executor, PixForgeError


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["gui"]
    if argv[:1] in (["desktop"], ["session"]):
        from .studio_cli import main as desktop_main
        return desktop_main(argv[1:])
    if argv[:1] == ["ui"]:
        from .native_cli import main as native_main
        return native_main(argv[1:])
    if argv[:1] == ["preview"]:
        from .texture_review import main as preview_main
        return preview_main(argv[1:])
    if argv[:1] == ["animation-preview"]:
        from .texture_animation import main as animation_preview_main
        return animation_preview_main(argv[1:])
    parser = argparse.ArgumentParser(
        prog="pixelforge", description="AI-first pixel drawing tool"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="execute a command script ('-' for stdin)")
    p_run.add_argument("script", help="path to .px script, or '-' for stdin")
    p_run.add_argument("-o", "--output", help="render composite to this PNG after running")
    p_run.add_argument("-S", "--scale", type=int, default=1, help="render scale (default 1)")
    p_run.add_argument("-s", "--save", help="save session JSON after running")
    p_run.add_argument("--atomic", action="store_true", help="commit a whole script and its outputs only after success")
    p_run.add_argument("--dry-run", action="store_true", help="preview a transaction without changing canvas/production outputs")
    p_run.add_argument("--preview", type=Path, help="separate native/nearest evidence PNG; also allowed during dry-run")
    p_run.add_argument("--preview-scale", type=int, choices=range(1, 17), default=6)
    p_run.add_argument("--tile", action="store_true", help="include 3x3 in edit preview")
    p_run.add_argument("--backgrounds", nargs="+", choices=("checker", "light", "dark"), default=["checker"])
    p_run.add_argument("--compare", type=Path, help="before-version PNG for edit preview")
    p_run.add_argument("--frame-height", type=int, help="show all frames of a vertical strip in edit preview")
    serve_parser = sub.add_parser("serve", help="host a durable session without importing Qt")
    serve_parser.add_argument("--runtime", type=Path)
    serve_parser.add_argument("--workspace", type=Path)
    mcp_parser = sub.add_parser("mcp", help="connect MCP to the shared independent session")
    mcp_parser.add_argument("--runtime", type=Path)
    mcp_parser.add_argument("--workspace", type=Path)
    gui_parser = sub.add_parser("gui", help="open the live desktop editor")
    gui_parser.add_argument("path", nargs="?", type=Path)
    gui_parser.add_argument("--workspace", type=Path)
    gui_parser.add_argument("--runtime", type=Path)
    gui_parser.add_argument("--native-exe", type=Path)
    sub.add_parser("desktop", help="read/edit/preview the same live document and export after user confirmation")
    sub.add_parser("session", help="draw, preview, approve and export through the independent core")
    sub.add_parser("preview", help="unified PNG/animation evidence, constraints and pending review records")
    sub.add_parser("animation-preview", help="read an explicit playback plan and create a lossless HTML player")
    args = parser.parse_args(argv)

    if args.command == "serve":
        from .service import serve
        return serve(workspace=args.workspace, runtime=args.runtime)

    if args.command == "mcp":
        from .mcp_server import main as mcp_main
        return mcp_main(workspace=args.workspace, runtime=args.runtime)
    if args.command == "gui":
        from .document import StudioError
        from .native_launcher import main as native_main
        try:
            return native_main(args.path, workspace=args.workspace, runtime=args.runtime, executable=args.native_exe)
        except StudioError as error:
            parser.error(str(error))

    if args.script == "-":
        text = sys.stdin.read()
    else:
        with open(args.script, "r", encoding="utf-8") as f:
            text = f.read()

    ex = Executor()
    try:
        if args.preview:
            protected = [Path(value).resolve() for value in (args.output, args.save, args.compare) if value is not None]
            if args.script != "-":
                protected.append(Path(args.script).resolve())
            if args.preview.resolve() in protected:
                raise PixForgeError("preview must not overwrite the script, input, production PNG or session")
        if args.atomic or args.dry_run or args.preview:
            from .texture_review import load_png
            before = load_png(args.compare) if args.compare else None
            result = ex.run_batch(text, dry_run=args.dry_run, output=args.output, scale=args.scale, save=args.save,
                preview_path=args.preview, preview_options={"scale": args.preview_scale, "tile": args.tile,
                "backgrounds": args.backgrounds, "before": before, "frame_height": args.frame_height})
            for line in result.messages:
                print(line)
            print(json.dumps({"batch": result.summary}, ensure_ascii=False))
            return 0
        out = ex.run_script(text)
        if args.output:
            out.extend(ex.cmd_render([args.output, str(args.scale)], []))
        if args.save:
            out.extend(ex.cmd_save([args.save], []))
    except (PixForgeError, OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for line in out:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
