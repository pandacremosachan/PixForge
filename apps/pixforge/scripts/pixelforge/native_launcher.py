"""Open the Win32 workbench on a UI thread of the resident PixForge EXE."""
from concurrent.futures import Future
import ctypes
from threading import Lock, Thread

_lock = Lock()
_window = None


def open_window(workspace, runtime):
    global _window
    with _lock:
        if _window is None or _window.done():
            _window = _start_window(workspace, runtime)
        return _window


def _start_window(workspace, runtime):
    module = ctypes.windll.kernel32.GetModuleHandleW
    module.argtypes, module.restype = [ctypes.c_wchar_p], ctypes.c_void_p
    native = ctypes.WinDLL("PixForgeNative", handle=module(None)).PixForgeRunWorkbench
    native.argtypes, native.restype = [ctypes.c_wchar_p, ctypes.c_wchar_p], ctypes.c_int
    finished = Future()

    def run():
        try:
            finished.set_result(native(str(workspace), str(runtime)))
        except Exception as error:
            finished.set_exception(error)

    Thread(target=run, name="PixForge workbench", daemon=False).start()
    return finished
