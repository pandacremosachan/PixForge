"""Headless session host and discovery. Uses Pillow, never imports Qt."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .document import StudioError
from .session import Session
from .studio_bridge import StudioBridge, StudioClient, runtime_path


def serve(workspace=None, runtime=None):
    workspace = Path(workspace or Path.cwd()).resolve()
    runtime = runtime_path(workspace, runtime)
    bridge = StudioBridge(runtime, mode="headless")
    session = None
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    def execute(payload):
        if payload.get("action") == "shutdown":
            session.document.guard(payload.get("expected_document_id"), payload.get("expected_revision"))
            stop()
            return {"state": session.document.status()}
        return session.call(payload.get("action", "status"), **{k: v for k, v in payload.items() if k != "action"})

    try:
        session = Session(workspace, runtime)
        session.persist()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, stop)
        while not stopping:
            bridge.pump(execute)
            time.sleep(.015)
    finally:
        if session is not None:
            session.document.end_stroke(cancel=True)
            session.document.recover()
            session.persist()
        bridge.close()
    return 0


def ensure_session(workspace=None, runtime=None):
    workspace = Path(workspace or Path.cwd()).resolve()
    runtime = runtime_path(workspace, runtime)
    client = StudioClient(runtime)
    if client.alive():
        return client
    runtime.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-B", "-m", "pixelforge", "serve", "--workspace", str(workspace), "--runtime", str(runtime)]
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    with (runtime / "service.log").open("ab") as log:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=flags, start_new_session=os.name != "nt", cwd=workspace)
    for _ in range(100):
        if client.alive():
            # The server publishes its address before restoring durable state.
            client.call("status")
            return client
        time.sleep(.1)
    raise StudioError("会话启动失败，请查看 runtime/service.log", "SESSION_UNAVAILABLE")
