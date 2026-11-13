"""Application-owned window lifecycle and exact-revision presentation."""
import math
import os
from pathlib import Path
import time

from .document import StudioError
from .studio_bridge import StudioClient


class Workbench:
    def __init__(self, session, workspace, runtime):
        self.session = session
        self.workspace, self.runtime = Path(workspace).resolve(), Path(runtime).resolve()
        self.frontend = StudioClient(self.runtime / "gui")

    @staticmethod
    def observed(value):
        if not isinstance(value, dict):
            raise StudioError("传入已观察到的工程状态")
        state = value.get("state", value)
        if (not isinstance(state, dict) or not isinstance(state.get("document_id"), str)
                or type(state.get("revision")) is not int or not isinstance(state.get("content_digest"), str)):
            raise StudioError("状态须包含 document_id、revision 和 content_digest")
        return state

    @staticmethod
    def deadline(timeout):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise StudioError("timeout 须为 0..60 秒内的有限正数")
        return time.monotonic() + timeout

    @staticmethod
    def same(a, b):
        return all(a.get(k) == b.get(k) for k in ("document_id", "revision", "content_digest"))

    def check_core(self, expected):
        current = self.session.call("status")
        if not self.same(current, expected):
            raise StudioError("工程已变化；读取并理解改动后再操作", "REVISION_CONFLICT")
        return current

    def check_paths(self, state):
        for key, expected in (("workspace", self.workspace), ("runtime", self.runtime)):
            actual = state.get(key)
            if not isinstance(actual, str) or os.path.normcase(str(Path(actual).resolve())) != os.path.normcase(str(expected)):
                raise StudioError("窗口与命令的 " + key + " 不一致", "SESSION_MISMATCH")

    def wait(self, expected, deadline, panel=None):
        while time.monotonic() < deadline:
            self.check_core(expected)
            state = self.frontend.call("ui_status")
            if state.get("loaded"):
                self.check_paths(state)
                if (self.same(state, expected) and state.get("pending") is False
                        and (panel is None or state.get("panel") == panel)
                        and (panel != "shapes" or state.get("scene_ready") is True)):
                    return state
            time.sleep(.1)
        raise StudioError("工作台尚未同步到指定版本", "DESKTOP_TIMEOUT")

    def open(self, timeout=20):
        deadline = self.deadline(timeout)
        reused = self.frontend.alive()
        window = None
        if not reused:
            from .native_launcher import open_window
            window = open_window(self.workspace, self.runtime)
        while time.monotonic() < deadline:
            if window is not None and window.done():
                window.result()
                raise StudioError("工作台在就绪前已关闭", "NATIVE_UNAVAILABLE")
            if self.frontend.alive():
                expected = self.observed(self.session.call("status"))
                desktop = self.wait(expected, deadline)
                self.frontend.call("focus")
                return {"opened": not reused, "reused": reused, "desktop": desktop}
            time.sleep(.1)
        raise StudioError("工作台启动超时", "DESKTOP_TIMEOUT")

    def present(self, observed, path, panel="pixels", timeout=20):
        expected, deadline = self.observed(observed), self.deadline(timeout)
        path = Path(path).resolve()
        if panel not in ("pixels", "shapes") or path.suffix.lower() != ".png":
            raise StudioError("panel 使用 pixels/shapes，截图路径使用 .png")
        if path.exists():
            raise StudioError("截图路径已存在，使用本轮新路径", "FILE_EXISTS")
        self.wait(expected, deadline)
        if panel == "shapes" and self.session.call("model_uv").get("uv_map", {}).get("model_present") is not True:
            raise StudioError("当前工程没有真实模型，使用目标资源预览")
        settings = {"panel": panel, **({"fit": True} if panel == "pixels" else {})}
        self.frontend.call("ui_set", settings=settings)
        self.wait(expected, deadline, panel)
        self.frontend.call("focus")
        capture = self.frontend.call("ui_capture", path=str(path), overwrite=False)
        desktop = self.wait(expected, deadline, panel)
        if capture.get("document_id") != expected["document_id"] or capture.get("revision") != expected["revision"]:
            raise StudioError("截图版本与本轮工程不一致", "REVISION_CONFLICT")
        from .image_bytes import png_base64
        from .texture_review import load_png
        return {"desktop": desktop, "capture": capture, "visual_review_required": True, "image": png_base64(load_png(path))}

    def close(self, document_id, revision, timeout=20):
        deadline = self.deadline(timeout)
        expected = self.session.call("status")
        if (expected["document_id"], expected["revision"]) != (document_id, revision):
            raise StudioError("工程已变化，请重新读取版本", "REVISION_CONFLICT")
        while True:
            self.wait(expected, deadline)
            try:
                self.frontend.call("ui_close", expected_document_id=document_id, expected_revision=revision)
                break
            except StudioError as error:
                # Only a read-only refresh rejected *before* accepting the close can be retried.
                if error.code != "VIEW_SYNC_PENDING":
                    raise
        while time.monotonic() < deadline:
            if not self.frontend.alive():
                return {"closed": True, "state": self.session.call("status")}
            time.sleep(.1)
        raise StudioError("窗口关闭尚未完成", "DESKTOP_TIMEOUT")
