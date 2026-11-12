"""The public, session-bound command transport owned by the resident EXE."""
import json
import os
from pathlib import Path
import secrets

from .transactions import commit_files


ROUTE = "/v1/commands"


class CommandEndpoint:
    def __init__(self, workspace, bridge):
        app = Path(os.environ["PIXFORGE_NATIVE_EXE"]).parent
        self.catalog = json.loads((app / "command-help.json").read_text(encoding="utf-8"))
        self.token = secrets.token_urlsafe(32)
        self.path = bridge.runtime / "commands.json"
        self.record = {"schema": "pixforge.commands/v1", "url": bridge.url + ROUTE,
                       "token": self.token, "pid": os.getpid(), "session_id": bridge.session_id,
                       "workspace": str(workspace), "runtime": str(bridge.runtime)}

    def publish(self):
        commit_files({self.path: json.dumps(self.record, ensure_ascii=False).encode("utf-8")})

    def help(self, path):
        if path == ROUTE:
            return self.catalog["overview"]["json"]
        segments = path.removeprefix(ROUTE + "/").split("/")
        group = self.catalog["groups"].get(segments[0])
        if group and len(segments) == 1:
            return group["help"]["json"]
        if group and len(segments) == 2 and segments[1] in group["actions"]:
            return group["actions"][segments[1]]["json"]
        return None

    @staticmethod
    def execute(payload, dispatch):
        if (not isinstance(payload, dict) or set(payload) - {"group", "command", "params"}
                or not isinstance(payload.get("group"), str) or not isinstance(payload.get("command"), str)
                or not isinstance(payload.get("params", {}), dict)):
            return 400, {"ok": False, "code": "INVALID_ARGUMENT",
                         "error": "Expected {group: string, command: string, params?: object}."}
        return 200, dispatch(payload)
