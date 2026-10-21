"""Authenticated loopback transport; independent of its GUI or headless owner."""
from concurrent.futures import Future, TimeoutError
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, ProxyHandler, build_opener
import uuid

from .document import StudioError
from .transactions import commit_files


def runtime_path(workspace=None, runtime=None):
    return Path(runtime or os.environ.get("PIXFORGE_RUNTIME") or
                (Path(workspace or Path.cwd()) / ".runtime" / "pixelforge-desktop")).resolve()


class StudioBridge:
    def __init__(self, runtime, mode="gui"):
        self.mode = mode
        self.runtime = Path(runtime).resolve()
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.lock = (self.runtime / "desktop.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.lock.seek(0)
                if not self.lock.read(1):
                    self.lock.write(b"0")
                    self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.lock.close()
            raise StudioError("该 runtime 的桌面正在启动或已经打开", "DESKTOP_STARTING") from error
        self.session_path = self.runtime / "session.json"
        self.token, self.session_id = secrets.token_urlsafe(32), uuid.uuid4().hex
        self.requests = queue.Queue(maxsize=64)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, code, value):
                body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionError):
                    pass

            def do_GET(self):
                if self.path == "/health":
                    self.send(200, {"application": "PixForge", "session_id": owner.session_id, "mode": owner.mode})
                else:
                    self.send(404, {"error": "Not found"})

            def do_POST(self):
                if self.path != "/api" or not hmac.compare_digest(self.headers.get("X-PixForge-Session", ""), owner.token):
                    self.send(401, {"error": "需要本地桌面会话凭据", "code": "AUTH_REQUIRED"})
                    return
                if self.headers.get("Origin"):
                    self.send(403, {"error": "不接受浏览器来源请求"})
                    return
                future = None
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16_000_000 or "application/json" not in self.headers.get("Content-Type", ""):
                        raise StudioError("请求须为不超过 16MB 的 JSON")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise StudioError("请求须为 JSON 对象")
                    future = Future()
                    owner.requests.put_nowait((payload, future))
                    self.send(200, {"ok": True, **future.result(timeout=20)})
                except TimeoutError:
                    cancelled = future.cancel()
                    self.send(503, {"error": "桌面繁忙；尚未执行的请求已取消" if cancelled else "请求仍在处理中，重读状态后再决定是否重试", "code": "BUSY"})
                except queue.Full:
                    self.send(503, {"error": "桌面队列已满，稍后重读状态", "code": "BUSY"})
                except (ValueError, OSError, KeyError, TypeError) as error:
                    self.send(400, {"error": str(error), "code": getattr(error, "code", "INVALID_ARGUMENT"),
                                    "details": getattr(error, "details", None)})
                except Exception as error:
                    self.send(500, {"error": "桌面请求执行失败；先重读状态。" + str(error), "code": "INTERNAL_ERROR"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        record = {"url": self.url, "token": self.token, "session_id": self.session_id, "pid": os.getpid(), "mode": self.mode}
        commit_files({self.session_path: json.dumps(record).encode("utf-8")})

    def pump(self, callback):
        changed = False
        for _ in range(8):
            try:
                payload, future = self.requests.get_nowait()
            except queue.Empty:
                break
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(callback(payload))
                changed |= payload.get("action") not in ("status", "preview", "read", "validate")
            except Exception as error:
                future.set_exception(error)
        return changed

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        while not self.requests.empty():
            _, future = self.requests.get_nowait()
            if not future.done():
                future.set_exception(StudioError("桌面已关闭", "CLOSED"))
        try:
            if json.loads(self.session_path.read_text(encoding="utf-8")).get("session_id") == self.session_id:
                self.session_path.unlink()
        except (OSError, ValueError):
            pass
        self.lock.close()


class StudioClient:
    def __init__(self, runtime):
        self.runtime = Path(runtime).resolve()
        self.opener = build_opener(ProxyHandler({}))

    def session(self):
        try:
            value = json.loads((self.runtime / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StudioError("找不到桌面会话；先运行 pixelforge serve，并使用相同 --runtime", "DESKTOP_UNAVAILABLE") from error
        if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in ("url", "token", "session_id")):
            raise StudioError("无效的本地桌面会话文件", "DESKTOP_UNAVAILABLE")
        parsed = urlparse(value.get("url", ""))
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path:
            raise StudioError("无效的本地桌面地址", "DESKTOP_UNAVAILABLE")
        return value

    def alive(self):
        try:
            session = self.session()
            with self.opener.open(session["url"] + "/health", timeout=1) as response:
                value = json.load(response)
            return value.get("application") == "PixForge" and value.get("session_id") == session["session_id"]
        except (StudioError, OSError, ValueError, KeyError):
            return False

    def call(self, action, **payload):
        session = self.session()
        request = Request(session["url"] + "/api", data=json.dumps({"action": action, **payload}).encode("utf-8"),
                          headers={"Content-Type": "application/json", "X-PixForge-Session": session["token"]})
        try:
            with self.opener.open(request, timeout=25) as response:
                result = json.load(response)
        except HTTPError as error:
            result = json.load(error)
            raise StudioError(result.get("error", str(error)), result.get("code", "INVALID_ARGUMENT"),
                              details=result.get("details")) from error
        except (URLError, OSError) as error:
            raise StudioError("会话未响应；检查服务和 runtime 后重读状态", "DESKTOP_UNAVAILABLE") from error
        return result


