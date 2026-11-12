"""Exercise the installed public endpoint; count even short-lived child processes."""
import argparse
import ctypes as c
from ctypes import wintypes as wt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request
import uuid


def verify(executable, workspace, desktop_start=False):
    kernel = c.WinDLL("kernel32", use_last_error=True)
    user = c.WinDLL("user32", use_last_error=True)

    def api(dll, name, result, *types):
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = types, result
        return fn

    # A Job accounts for the host and every process it starts, including ones
    # that exit before our next request. Use a private desktop for the UI check.
    job = api(kernel, "CreateJobObjectW", wt.HANDLE, wt.LPVOID, wt.LPCWSTR)(None, None)
    desk_name = "PixForgeTest_" + uuid.uuid4().hex
    desk = api(user, "CreateDesktopW", wt.HANDLE, wt.LPCWSTR, wt.LPCWSTR, wt.LPVOID, wt.DWORD, wt.DWORD, wt.LPVOID)(
        desk_name, None, None, 0, 0x10000000, None)
    assert job and desk, c.WinError(c.get_last_error())
    startup = subprocess.STARTUPINFO()
    # Windows selects the desktop inherited by the child when lpDesktop is NULL.
    os.set_handle_inheritable(desk, True)
    startup.lpAttributeList = {"handle_list": [desk]}
    runtime = workspace / "shared session"
    record = runtime / "commands.json"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PIXFORGE_NATIVE_EXE")}
    env["PATH"] = ""
    opener = build_opener(ProxyHandler({}))
    with (workspace / "host.log").open("w+b") as log:
        host = subprocess.Popen([str(executable), *([] if desktop_start else ["serve"]), "--workspace", str(workspace), "--runtime", str(runtime)],
                                cwd=executable.parent, env=env, startupinfo=startup, creationflags=subprocess.DETACHED_PROCESS,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            assert api(kernel, "AssignProcessToJobObject", wt.BOOL, wt.HANDLE, wt.HANDLE)(job, int(host._handle)), c.WinError(c.get_last_error())
            until = time.monotonic() + 20
            while not record.exists() and host.poll() is None and time.monotonic() < until:
                time.sleep(.04)
            if not record.exists():
                log.seek(0)
                raise AssertionError("Host did not publish a connection: " + log.read().decode("utf-8", "replace"))
            conn = json.loads(record.read_text(encoding="utf-8"))
            assert conn["pid"] == host.pid and Path(conn["workspace"]) == workspace and Path(conn["runtime"]) == runtime

            def request(body=None, suffix="", token=None):
                req = Request(conn["url"] + suffix, data=None if body is None else json.dumps(body).encode("utf-8"),
                              headers={"X-PixForge-Session": conn["token"] if token is None else token,
                                       "Content-Type": "application/json"})
                try:
                    with opener.open(req, timeout=30) as resp:
                        return resp.status, json.load(resp)
                except HTTPError as error:
                    return error.code, json.load(error)

            def command(group, action, **params):
                status, result = request({"group": group, "command": action, "params": params})
                assert status == 200 and result.get("ok"), result
                return result

            def guard(state):
                return {"expected_document_id": state["document_id"], "expected_revision": state["revision"]}

            assert request(token="wrong")[0] == 401
            schema = request(suffix="/canvas/draw")[1]["params_schema"]
            assert "commands" in schema["required"]
            assert request({"action": "shutdown"})[0] == 400
            state = command("project", "state")
            backend = executable.parent / "backend"
            if backend.is_dir():
                # A developer PC can have Python installed even with an empty PATH.
                # Check the interpreter and compiled extensions the release actually loaded.
                handles, needed = (wt.HMODULE * 1024)(), wt.DWORD()
                assert api(kernel, "K32EnumProcessModules", wt.BOOL, wt.HANDLE, c.POINTER(wt.HMODULE), wt.DWORD, wt.LPDWORD)(
                    int(host._handle), handles, c.sizeof(handles), c.byref(needed)) and needed.value <= c.sizeof(handles)
                filename = api(kernel, "K32GetModuleFileNameExW", wt.DWORD, wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD)
                loaded = set()
                for handle in handles[:needed.value // c.sizeof(wt.HMODULE)]:
                    buf = c.create_unicode_buffer(32768)
                    assert filename(int(host._handle), handle, buf, len(buf))
                    path = Path(buf.value)
                    name = path.name.lower()
                    if path.suffix.lower() == ".pyd" or (name.startswith("python") and name.endswith(".dll")):
                        assert path.resolve().is_relative_to(backend), f"External runtime module: {path}"
                        loaded.add(name.split(".")[0])
                assert {"python312", "_imaging", "_pydantic_core"} <= loaded, loaded
            state = command("project", "create", settings={"preset": "cube_shared", "face_size": 4}, **guard(state))["state"]
            old = guard(state)
            bad = request({"group": "canvas", "command": "draw", "params": {**old, "commands": ["wrong type"]}})[1]
            assert not bad["ok"] and bad["code"] == "INVALID_ARGUMENT"
            state = command("canvas", "draw", commands="rect 0 0 1 1 #996633ff", **old)["state"]
            stale = request({"group": "canvas", "command": "draw", "params": {**old, "commands": "rect 0 0 1 1 #ffffffff"}})[1]
            assert not stale["ok"] and stale["code"] == "REVISION_CONFLICT", stale
            started = time.perf_counter()
            for _ in range(100):
                observed = command("project", "state")
                assert guard(observed) == guard(state) and observed["content_digest"] == state["content_digest"]
            elapsed = time.perf_counter() - started
            state = command("project", "save", path="smoke.pixforge", **guard(state))["state"]
            assert (workspace / "smoke.pixforge").is_file()
            opened = command("workbench", "open")
            assert opened["reused"] == desktop_start and opened["desktop"]["content_digest"] == state["content_digest"]
            assert json.loads((runtime / "gui/session.json").read_bytes())["pid"] == host.pid
            assert command("workbench", "open")["reused"]
            command("workbench", "close", **guard(state))
            assert command("project", "state")["document_id"] == state["document_id"]
            command("project", "shutdown", **guard(state))
            assert host.wait(10) == 0 and not record.exists()
            class Accounting(c.Structure):
                _fields_ = [("times", c.c_int64 * 4), ("faults", wt.DWORD), ("total", wt.DWORD),
                            ("active", wt.DWORD), ("terminated", wt.DWORD)]
            count = Accounting()
            assert api(kernel, "QueryInformationJobObject", wt.BOOL, wt.HANDLE, c.c_int, wt.LPVOID, wt.DWORD, wt.LPVOID)(
                job, 1, c.byref(count), c.sizeof(count), None), c.WinError(c.get_last_error())
            assert count.total == 1, f"{count.total} processes ran in the host job"
            return {"state_requests": 100, "host_processes_including_children": count.total,
                    "state_requests_seconds": round(elapsed, 3), "workbench_same_pid": True,
                    "schema_validation_and_revision_conflict": True, "clean_shutdown": True}
        finally:
            if host.poll() is None:
                host.kill()
                host.wait()
            api(user, "CloseDesktop", wt.BOOL, wt.HANDLE)(desk)
            api(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--desktop-start", action="store_true", help="exercise direct GUI launch on the private desktop")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="PixForge 常驻 ") as directory:
        print(json.dumps(verify(args.executable.resolve(), Path(directory).resolve(), args.desktop_start), indent=2))
