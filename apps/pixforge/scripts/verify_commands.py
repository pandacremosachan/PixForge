"""Exercise the executable commands against isolated fixtures and an optional native window."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image


class Connection:
    def __init__(self, executable, workspace, isolated=False):
        self.executable, self.workspace, self.sequence = executable, workspace, 0
        self.environment = dict(os.environ)
        if isolated:
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIXFORGE_NATIVE_EXE"):
                self.environment.pop(key, None)
            self.environment["PATH"] = ""

    def run(self, arguments, *, error=False, input_text=None):
        result = subprocess.run([str(self.executable), *arguments, "--workspace", str(self.workspace),
            "--runtime", str(self.workspace / "session"), "--json"], input=input_text, capture_output=True,
            encoding="utf-8", env=self.environment, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(result.stdout)
        self.last_code = result.returncode
        if error is not None:
            assert (result.returncode != 0) == error, (arguments, result.returncode, data, result.stderr)
        assert "Traceback" not in result.stderr, result.stderr
        if data.get("preview_path"):
            Image.open(data["preview_path"]).verify()
        return data

    def tool(self, name, arguments=None, *, error=False):
        assert name == "help"
        arguments = arguments or {}
        command = [arguments["topic"]] if arguments.get("topic") else []
        if arguments.get("action"):
            command.append(arguments["action"].replace("_", "-"))
        return self.run([*command, "--help"], error=error)

    def action(self, topic, action, params=None, *, error=False):
        self.sequence += 1
        request = self.workspace / ("request-" + str(self.sequence) + ".json")
        request.write_text(json.dumps(params or {}, ensure_ascii=False), encoding="utf-8")
        return self.run([topic, action.replace("_", "-"), "--request-file", str(request)], error=error)

    def write(self, topic, action, arguments=None, *, error=False):
        state = self.action("project", "state")
        return self.action(topic, action, {**(arguments or {}), "expected_document_id": state["document_id"],
            "expected_revision": state["revision"]}, error=error)

    def close(self):
        pass


def verify(executable, workspace, desktop, isolated=False):
    connection = Connection(executable, workspace, isolated)
    checks = []
    try:
        overview = connection.tool("help")
        assert set(overview["groups"]) == {"project", "canvas", "model", "animation", "minecraft", "workbench", "asset"}
        operations = 0
        for topic in overview["groups"]:
            summary = connection.tool("help", {"topic": topic})
            for action in summary["actions"]:
                schema = connection.tool("help", {"topic": topic, "action": action})["params_schema"]
                assert schema["additionalProperties"] is False
                operations += 1
        assert operations == 64, operations
        assert not (workspace / "session/session.json").exists(), "Help must not start a session"
        metadata = connection.action("project", "info")
        assert {"command-line", "resident-http"} <= set(metadata["interfaces"]) and metadata["public_api_version"] == 4
        assert not (workspace / "session/session.json").exists(), "Info must not start a session"
        preview_schema = connection.tool("help", {"topic": "model", "action": "preview"})["params_schema"]
        assert {"frame", "time_ms", "show_model"} <= preview_schema["properties"].keys()
        export_schema = connection.tool("help", {"topic": "asset", "action": "export-png"})["params_schema"]
        assert {"frame", "scale"} <= export_schema["properties"].keys()
        connection.tool("help", {"topic": "project", "action": "canvas-replace"}, error=True)
        connection.action("canvas", "draw", {"commands": "rect 0 0 1 1 #ffffffff", "extra": 1}, error=True)
        connection.action("canvas", "read", {"x": "invalid", "y": 0, "w": 1, "h": 1}, error=True)
        assert connection.last_code == 2
        for retired in ("--mcp", "--cli", "--describe"):
            connection.run([retired], error=True)
        assert not (workspace / "session/session.json").exists(), "Bad arguments must not start a session"
        checks.append("64 command help schemas, lazy startup and rejected invalid inputs")
        state = connection.action("project", "state")
        connection.action("canvas", "draw", {"commands": "rect 0 0 1 1 #ffffffff", "expected_document_id": "stale",
            "expected_revision": state["revision"]}, error=True)
        assert connection.last_code == 3
        assert connection.action("project", "state")["revision"] == state["revision"]
        settings = workspace / "project settings.json"
        settings.write_text(json.dumps({"preset": "cube_shared", "face_size": 4}), encoding="utf-8")
        connection.run(["project", "create", "--settings-file", str(settings), "--expected-document-id", state["document_id"],
            "--expected-revision", str(state["revision"])])
        state = connection.action("project", "state")
        drawing = workspace / "绘图 batch.px"
        drawing.write_text("rect 0 0 3 3 #336699ff\n", encoding="utf-8")
        result = connection.run(["canvas", "draw", "--commands-file", str(drawing), "--expected-document-id", state["document_id"],
            "--expected-revision", str(state["revision"]), "--tile", "false"])
        assert "image" not in result and Path(result["preview_path"]).is_file()
        read_params = {"x": 0, "y": 0, "w": 1, "h": 1}
        read_flags = connection.run(["canvas", "read", "--x", "0", "--y", "0", "--w", "1", "--h", "1"])
        read_stdin = connection.run(["canvas", "read", "--request-file", "-"], input_text=json.dumps(read_params))
        assert read_flags == read_stdin
        state = connection.action("project", "state")
        note = '中文 "quoted" $() `literal` \\tail'
        note_result = connection.run(["project", "note", "--text-file", "-", "--expected-document-id", state["document_id"],
            "--expected-revision", str(state["revision"])], input_text=note)
        assert note_result["state"]["notes"][-1]["text"] == note
        observed_file = workspace / "observed.json"
        recorded = connection.run(["project", "state", "--result-file", str(observed_file)])
        assert json.loads(observed_file.read_text(encoding="utf-8")) == recorded
        connection.run(["project", "note", "--text", "must not execute", "--expected-document-id", recorded["document_id"],
            "--expected-revision", str(recorded["revision"]), "--result-file", str(observed_file)], error=True)
        assert connection.last_code == 4
        assert connection.action("project", "state")["revision"] == recorded["revision"]
        connection.run(["canvas", "read", "--request-json", json.dumps(read_params), "--x", "0"], error=True)
        connection.run(["canvas", "read", "--x-file", "-", "--y-file", "-"], input_text="0", error=True)
        checks.append("typed flags, text/JSON files, stdin, literal Unicode input and protected response files")
        state = connection.action("project", "state")
        connection.write("canvas", "validate", {"commands": "rect 0 0 3 3 #ffffffff"})
        assert connection.action("project", "state")["content_digest"] == state["content_digest"]
        connection.write("animation", "prepare_frames", {"settings": {"frame_count": 2}})
        connection.write("animation", "edit_frames", {"operation": "duplicate", "step_index": 0})
        assert len(connection.action("project", "state")["animation"]["rectangles"]) == 3
        connection.write("animation", "edit_frames", {"operation": "delete", "step_index": 1})
        connection.write("animation", "configure", {"settings": {"frame_size": [4, 4],
            "steps": [{"frame": 1, "duration_ms": 150}, {"frame": 0, "duration_ms": 100}], "loop": True}})
        connection.action("model", "preview", {"frame": 1, "time_ms": 50})
        connection.write("project", "save", {"path": str(workspace / "shared.pixforge")})
        connection.write("asset", "export_png", {"path": str(workspace / "unapproved.png")}, error=True)
        assert connection.last_code == 6
        assert not (workspace / "unapproved.png").exists()
        checks.append("conflicts, dry-run, frame edits, inline timing and export guard")
        before = connection.action("project", "state")
        image = Image.new("RGBA", (2, 2), "#336699ff")
        image.save(workspace / "source.png")
        image.save(workspace / "before.png")
        Image.new("RGBA", (2, 2), "#ffffffff").save(workspace / "mask.png")
        source = str(workspace / "source.png")
        result = connection.action("asset", "inspect", {"path": source, "options": {"expect_size": [2, 2],
            "opaque": True, "symmetry": "d4", "palette": ["#336699ff"], "compare": str(workspace / "before.png"),
            "preserve_mask": str(workspace / "mask.png"), "clusters": True, "tile": True, "match_edges": True},
            "preview_path": str(workspace / "review.png"), "report_path": str(workspace / "review.json")})
        assert result["report"]["constraints_passed"]
        assert result["preview_path"] == str(workspace / "review.png")
        connection.action("asset", "inspect", {"path": source, "options": {"expect_size": [3, 2]}}, error=True)
        connection.action("asset", "inspect", {"path": source, "preview_path": source, "overwrite": True}, error=True)
        Image.new("RGBA", (2, 4), "#336699ff").save(workspace / "strip.png")
        plan = {"schema": "pixelforge.animation-review/v1", "image": str(workspace / "strip.png"),
            "frame_size": [2, 2], "loop": True, "interpolation": "none",
            "steps": [{"frame": 1, "duration_ms": 75}, {"frame": 0, "duration_ms": 125}]}
        result = connection.action("asset", "playback", {"plan": plan, "html_path": str(workspace / "player.html")})
        assert result["html_path"] == str(workspace / "player.html")
        connection.action("asset", "inspect", {"path": str(workspace / "strip.png"), "options": {"animation_plan": plan},
            "html_path": str(workspace / "checked-player.html")})
        commands = "new 4 4\nrect 0 0 3 3 #336699ff\nrender deferred.png"
        connection.action("asset", "batch", {"commands": commands})
        connection.action("asset", "batch", {"commands": commands + "\ninvalid-command"}, error=True)
        connection.action("asset", "batch", {"commands": commands, "dry_run": False,
            "project_path": str(workspace / "offline.pixforge")})
        assert not (workspace / "deferred.png").exists()
        assert not (Path.cwd() / "deferred.png").exists()
        assert (workspace / "offline.pixforge").is_file()
        assert connection.action("project", "state")["content_digest"] == before["content_digest"]
        checks.append("independent PNG/animation inspection, output guards and offline isolation")
        if desktop:
            connection.action("workbench", "open")
            connection.action("workbench", "open")
            assert connection.action("workbench", "state")["version"] == metadata["version"]
            original = connection.action("project", "state")
            edited = connection.write("canvas", "draw", {"commands": "rect 0 0 1 1 #000000ff"})["state"]
            live = connection.action("workbench", "wait", {"observed": edited})["desktop"]
            assert all(live[key] == edited[key] for key in ("document_id", "revision", "content_digest"))
            restored = connection.write("project", "undo")["state"]
            assert restored["content_digest"] == original["content_digest"]
            live = connection.action("workbench", "wait", {"observed": restored})["desktop"]
            assert all(live[key] == restored[key] for key in ("document_id", "revision", "content_digest"))
            checks.append("command edits and shared undo reflected in the native window")
            state = connection.action("project", "state")
            connection.action("workbench", "present", {"observed": state, "path": str(workspace / "pixels.png")})
            connection.action("workbench", "present", {"observed": state, "path": str(workspace / "model.png"), "panel": "shapes"})
            connection.action("workbench", "metrics")
            connection.action("workbench", "controls")
            for kind in ["scene", "target", "preview", "regression", "material"]:
                def editor(operation, **params):
                    return connection.action("workbench", "editor", {"editor_kind": kind, "operation": operation, **params})
                editor("open")
                status = editor("status")
                assert status["open"] and status["actions"] and status["editable_fields"], kind
                if kind == "scene":
                    connection.write("workbench", "close", error=True)
                key = status["editable_fields"][0]
                editor("field", name=key, value=status["fields"][key])
                editor("capture", path=str(workspace / (kind + ".png")))
                safe_action = {"preview": "reset_camera", "regression": "toggle_data",
                               "material": "page_channels", "target": "page_target"}.get(kind)
                if safe_action and safe_action in status["actions"]:
                    editor("invoke", name=safe_action)
                editor("cancel")
            connection.write("project", "shutdown", error=True)
            connection.action("workbench", "close", {"expected_document_id": "stale", "expected_revision": 0}, error=True)
            connection.write("workbench", "close")
            checks.append("window reuse, exact-revision captures, five native editors and guarded close")
        print(json.dumps({"groups": len(overview["groups"]), "actions": operations,
            "checks": checks, "isolated": isolated, "workspace": str(workspace)}, ensure_ascii=False, indent=2))
    finally:
        try:
            state = connection.action("project", "state")
            for kind in ["scene", "target", "preview", "regression", "material"]:
                connection.action("workbench", "editor", {"editor_kind": kind, "operation": "cancel"}, error=None)
            connection.action("workbench", "close", {
                "expected_document_id": state["document_id"], "expected_revision": state["revision"]}, error=None)
            connection.write("project", "shutdown")
        finally:
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args()
    args.output_parent.mkdir(parents=True, exist_ok=True)
    verify(args.executable.resolve(), Path(tempfile.mkdtemp(prefix="command-check-", dir=args.output_parent)), args.desktop, args.isolated)
