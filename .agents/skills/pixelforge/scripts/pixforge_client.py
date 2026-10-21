"""Harness-independent standard-library client for PixForge public API v1."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SKILL_VERSION = "1.8.0"
SUPPORTED_API = {1}


class ConnectionError(RuntimeError):
    pass


class SoftwareError(RuntimeError):
    def __init__(self, result, returncode):
        self.result, self.returncode = result, returncode
        super().__init__(result.get("error", "PixForge operation failed") if isinstance(result, dict) else str(result))


def _application(path):
    target = Path(path).expanduser()
    if target.is_dir():
        target = target / "PixForgeNative.exe"
    if not target.is_file():
        raise ConnectionError("找不到指定的 PixForge 软件：" + str(target))
    return target.resolve()


def resolve_command(explicit=None, config=None):
    """Explicit flags override environment; configured argv never uses a shell."""
    if explicit:
        app = _application(explicit)
        return [str(app)], app
    record_name = config
    if not record_name and os.environ.get("PIXFORGE_APP"):
        app = _application(os.environ["PIXFORGE_APP"])
        return [str(app)], app
    if not record_name:
        record_name = os.environ.get("PIXFORGE_CONNECTION")
    if record_name:
        record = Path(record_name).expanduser().resolve()
        data = json.loads(record.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or set(data) - {"application", "command"} or len(data) != 1:
            raise ConnectionError("连接配置只指定 application 路径或 command 参数数组其中一项。")
        if "command" in data:
            command = data["command"]
            if (not isinstance(command, list) or not command
                    or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in command)):
                raise ConnectionError("command 须为非空字符串参数数组；不会通过 shell 解释。")
            if not Path(command[0]).is_absolute() and any(c in command[0] for c in ("/", "\\")):
                command[0] = str((record.parent / command[0]).resolve())
            return command, None
        if not isinstance(data.get("application"), str) or not data["application"].strip():
            raise ConnectionError("application 须为非空路径字符串。")
        target = Path(data["application"]).expanduser()
        app = _application(target if target.is_absolute() else record.parent / target)
        return [str(app)], app
    for name in ("PixForgeNative.exe", "PixForgeNative"):
        found = shutil.which(name)
        if found:
            app = Path(found).resolve()
            return [str(app)], app
    candidates = []
    for parent in Path(__file__).resolve().parents:
        candidates.extend(parent / name for name in (
            "PixForge-Cpp/PixForgeNative.exe", "PixForge/PixForgeNative.exe",
            ".runtime/pixelforge-native/bin/PixForgeNative.exe"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs/PixForge/PixForgeNative.exe")
    for candidate in candidates:
        if candidate.is_file():
            app = candidate.resolve()
            return [str(app)], app
    raise ConnectionError("找不到 PixForge。使用 --app 路径、--config 连接文件或 PIXFORGE_APP；无需特定 harness 的目录。")


def _valid_description(data):
    return (isinstance(data, dict) and data.get("schema") == "pixforge.application/v1"
            and type(data.get("public_api_version")) is int
            and data["public_api_version"] in SUPPORTED_API)


def describe(command, application=None):
    if application is not None:
        descriptor = application.with_name("application.json")
        if not descriptor.is_file() or not _valid_description(json.loads(descriptor.read_text(encoding="utf-8-sig"))):
            raise ConnectionError("软件缺少兼容的 application.json；请使用完整 API v1 安装包。")
    result = subprocess.run([*command, "--describe"], capture_output=True, encoding="utf-8", timeout=15,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ConnectionError(result.stderr.strip() or result.stdout.strip() or "软件接口查询失败")
    actual = json.loads(result.stdout)
    if not _valid_description(actual):
        raise ConnectionError("软件公开接口不兼容；本 skill 支持 API 主版本 1，工程未被修改。")
    if not {"cli", "mcp-stdio"}.issubset(actual.get("interfaces", [])):
        raise ConnectionError("软件未提供所需的 CLI/MCP 公开接口。")
    return actual


def require_capabilities(info, arguments):
    """Fail before mutation when a known optional adapter is absent."""
    if not arguments or arguments[0] not in ("session", "desktop", "ui"):
        return
    index = 1
    while index < len(arguments) and arguments[index].startswith("--"):
        if arguments[index] in ("--runtime", "--workspace"):
            index += 2
        elif arguments[index].startswith(("--runtime=", "--workspace=")):
            index += 1
        else:
            break
    if index >= len(arguments):
        return
    action = arguments[index]
    required = set()
    if action.startswith("minecraft-"):
        required.add("minecraft-assets/v1")
    if action in ("minecraft-scene", "minecraft-preview"):
        required.add("minecraft-preview/v1")
    if action.startswith("minecraft-material"):
        required.add("minecraft-material/v1")
    if action in ("minecraft-animation", "minecraft-animation-apply"):
        required.add("minecraft-animation/v1")
    if action in ("minecraft-performance", "minecraft-regression-compare", "minecraft-workbench"):
        required.add("minecraft-regression/v1")

    def argument(name):
        for position in range(index + 1, len(arguments)):
            value = arguments[position]
            if value == name and position + 1 < len(arguments):
                return arguments[position + 1]
            if value.startswith(name + "="):
                return value.split("=", 1)[1]
        return None

    if ((action == "minecraft-export" and argument("--format") in ("forge-integration", "forge-mod"))
            or (action == "minecraft-check" and "--include-generated-code" in arguments)
            or (arguments[0] == "ui" and action == "minecraft-editor"
                and argument("--name") in ("runtime", "prepare_runtime", "preview_code"))):
        required.add("forge-runtime/v1")
    if action in ("minecraft-configure", "minecraft-check") and argument("--config"):
        settings = json.loads(Path(argument("--config")).expanduser().read_text(encoding="utf-8-sig"))
        if isinstance(settings, dict):
            runtime = settings.get("runtime")
            if runtime is not None or settings.get("schema") == "pixforge.minecraft-project/v2":
                required.add("forge-runtime/v1")
            if settings.get("texture_animation") is not None:
                required.add("minecraft-animation/v1")
            if isinstance(runtime, dict):
                scene = runtime.get("scene")
                if runtime.get("regression"):
                    required.add("minecraft-regression/v1")
                elif isinstance(scene, dict) and scene.get("lifecycle") is not None:
                    required.add("minecraft-animation/v1")
    missing = required - set(info.get("capabilities", []))
    if missing:
        raise ConnectionError("软件缺少 " + ", ".join(sorted(missing)) + "；独立更新软件，工程未被修改。")


class Client:
    """Optional Python API; calls only public CLI, never imports application code.

    write(observed, ...) uses ONLY the caller's observed token. It never fetches
    a newer token or retries, so concurrent human edits stay protected.
    """
    def __init__(self, *, workspace, runtime, app=None, config=None):
        self.command, self.application = resolve_command(app, config)
        self.software = describe(self.command, self.application)
        self.workspace, self.runtime = str(Path(workspace).resolve()), str(Path(runtime).resolve())

    def run_json(self, *arguments, input_text=None):
        args = [str(arg) for arg in arguments]
        require_capabilities(self.software, args)
        result = subprocess.run([*self.command, "--cli", *args], input=input_text, capture_output=True,
                                encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        raw = result.stdout.strip() or result.stderr.strip()
        try:
            data = json.loads(raw)
        except ValueError:
            raise SoftwareError({"error": raw or "PixForge returned no JSON"}, result.returncode) from None
        if result.returncode:
            raise SoftwareError(data, result.returncode)
        return data

    def read(self, action="status", *arguments):
        return self.run_json("session", "--workspace", self.workspace, "--runtime", self.runtime, action, *arguments)

    def write(self, observed, action, *arguments, input_text=None):
        state = observed.get("state", observed)
        if not isinstance(state.get("document_id"), str) or type(state.get("revision")) is not int:
            raise ValueError("write requires the observed status or operation result")
        return self.run_json("session", "--workspace", self.workspace, "--runtime", self.runtime,
                             action, *arguments, "--expected-document-id", state["document_id"],
                             "--expected-revision", state["revision"], input_text=input_text)


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--app")
    parser.add_argument("--config")
    parser.add_argument("--help", action="store_true", dest="client_help")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args(sys.argv[1:] if argv is None else argv)
    arguments = options.arguments
    if options.client_help or not arguments or arguments == ["--help"]:
        print("PixForge portable skill client " + SKILL_VERSION + " (public API v1)\n"
              "python pixforge_client.py [--app EXE|DIRECTORY | --config connection.json] doctor\n"
              "python pixforge_client.py [--app EXE] session --workspace DIR --runtime DIR status\n"
              "python pixforge_client.py [--app EXE] gui --workspace DIR --runtime DIR\n"
              "python pixforge_client.py [--app EXE] mcp --workspace DIR --runtime DIR\n"
              "Other arguments pass unchanged to the software public CLI. Use help for software commands.")
        return 0
    try:
        command, app = resolve_command(options.app, options.config)
        info = describe(command, app)
        require_capabilities(info, arguments)
        if arguments == ["doctor"]:
            print(json.dumps({"connected": True, "skill_version": SKILL_VERSION,
                              "application": str(app) if app else "configured command", "software": info},
                             ensure_ascii=False, indent=2))
            return 0
        forwarded = (["--mcp", *arguments[1:]] if arguments[0] == "mcp"
                     else ["--cli", *(["--help"] if arguments == ["help"] else arguments)])
        return subprocess.run([*command, *forwarded], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
    except (ConnectionError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": str(error), "code": "PIXFORGE_CONNECTION_ERROR"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
