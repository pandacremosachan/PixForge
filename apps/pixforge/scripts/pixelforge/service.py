"""Persistent project and command host inside the native application."""
import json
import os
from pathlib import Path
import signal
import time
import threading

from .session import Session
from .studio_bridge import StudioBridge, StudioClient, runtime_path


def serve(workspace=None, runtime=None, workbench=False):
    workspace = Path(workspace or Path.cwd()).resolve()
    runtime = runtime_path(workspace, runtime)
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)  # File parameters resolve in the bound workspace, as for CLI-created sessions.
    bridge = StudioBridge(runtime, mode="headless")
    session = None
    stopping = False
    command_lock = threading.Lock()
    commands = None

    def stop(*_):
        nonlocal stopping
        stopping = True

    def execute(payload):
        if payload.get("action") == "shutdown":
            session.document.guard(payload.get("expected_document_id"), payload.get("expected_revision"))
            stop()
            return {"state": session.document.status()}
        return session.call(payload.get("action", "status"), **{k: v for k, v in payload.items() if k != "action"})

    def execute_command(payload):
        nonlocal commands
        if not command_lock.acquire(blocking=False):
            return {"ok": False, "error": "另一个命令仍在执行；读取状态后再继续", "code": "BUSY"}
        try:
            from .commands import build_commands
            from .command_output import artifacts
            if commands is None:
                commands = build_commands(StudioClient(runtime), workspace=workspace, runtime=runtime)
            result = commands["dispatch"](payload.get("group"), payload.get("command"), payload.get("params"))
            return {**artifacts(result.data, runtime), "ok": not result.is_error}
        except (ValueError, OSError, KeyError, TypeError) as error:
            return {"ok": False, "error": str(error), "code": getattr(error, "code", "INVALID_ARGUMENT")}
        finally:
            command_lock.release()

    try:
        session = Session(workspace, runtime)
        session.persist()
        initial_window = None
        if workbench:
            from .native_launcher import open_window
            initial_window = open_window(workspace, runtime)
        bridge.publish_commands(workspace, execute_command)
        print(json.dumps({"ok": True, "pid": bridge.commands.record["pid"],
                          "connection_file": str(bridge.commands.path)}), flush=True)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, stop)
        while not stopping:
            bridge.pump(execute)
            if initial_window is not None and initial_window.done():
                if initial_window.result():
                    raise RuntimeError("Could not open the PixForge workbench")
                initial_window = None
            time.sleep(.015)
    finally:
        if session is not None:
            session.document.end_stroke(cancel=True)
            session.document.recover()
            session.persist()
        bridge.close()
    return 0
