"""Launch the native Windows frontend without importing any Qt bindings."""
import os
from pathlib import Path
import subprocess
import sys

from .document import StudioError
from .service import ensure_session
from .studio_bridge import StudioClient, runtime_path


def find_native(executable=None):
    explicit = executable or os.environ.get("PIXFORGE_NATIVE_EXE")
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise StudioError("找不到 PIXFORGE_NATIVE_EXE 指向的原生桌面", "NATIVE_UNAVAILABLE")
        return path
    if os.name != "nt":
        return None
    candidates = [Path(sys.executable).with_name("PixForgeNative.exe"),
                  Path(__file__).parent / "native" / "PixForgeNative.exe"]
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "PixForgeNative.exe")
        candidates.append(parent / ".runtime" / "pixelforge-native" / "bin" / "PixForgeNative.exe")
    return next((p for p in candidates if p.is_file()), None)


def main(path=None, *, workspace=None, runtime=None, executable=None, wait=True):
    binary = find_native(executable)
    if binary is None or os.name != "nt":
        raise StudioError("原生桌面暂支持 Windows。先运行 scripts/build-native.ps1；其他平台可使用核心 CLI/MCP。", "NATIVE_UNAVAILABLE")
    workspace = Path(workspace or Path.cwd()).resolve()
    runtime = runtime_path(workspace, runtime)
    client = ensure_session(workspace, runtime)
    frontend = StudioClient(runtime / "gui")
    if frontend.alive():
        if path:
            state = client.call("status")
            client.call("open", path=str(Path(path).resolve()), expected_document_id=state["document_id"], expected_revision=state["revision"])
        frontend.call("focus")
        return 0
    command = [str(binary), "--workspace", str(workspace), "--runtime", str(runtime)]
    if path:
        command.extend(["--open", str(Path(path).resolve())])
    # A native GUI-subsystem binary creates no console, and owns its own event loop.
    process = subprocess.Popen(command, cwd=workspace)
    return process.wait() if wait else process.pid
