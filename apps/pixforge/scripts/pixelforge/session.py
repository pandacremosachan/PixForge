"""Frontend-independent document operations and durable session state. No Qt imports."""
import base64
import json
from pathlib import Path
import secrets
import threading
import time

from .canvas import Canvas
from .document import Document, StudioError, encoded, playback
from .preview import render_canvas
from .image_bytes import png
from .protocol import Executor, PixForgeError
from .transactions import commit_files
from .shapes import default_shapes, normalize as normalize_shapes


def image_data(image):
    return base64.b64encode(png(image)).decode("ascii")


def dispatch(document, payload, *, focus=None):
    """One command contract for embedded GUI, local API, CLI and MCP clients."""
    action = payload.get("action", "status")
    if action == "view_poll":
        # Native and other asynchronous frontends only need a change token here.
        # status() hashes/base64-encodes full canvases and reports every shape;
        # doing that on every idle poll makes the GUI and core compete for CPU.
        return {"document_id": document.document_id, "revision": document.revision,
                "project_path": str(document.project_path) if document.project_path else None,
                "saved_digest": document.saved_digest, "dependency_current": document.dependency_current(),
                "manual_stroke_active": document.stroke is not None, "view_frame": document.view_frame}
    if action == "animation_capabilities":
        from .scene_animation import capabilities
        return {"capabilities": capabilities(), "state": document.status()}
    if action == "minecraft_capabilities":
        from .minecraft_target import capabilities
        return {"capabilities": capabilities(), "state": document.status()}
    if action == "minecraft_check":
        return {"state": document.status(), "validation": document.check_minecraft(
            settings=payload.get("settings"), use_document=payload.get("use_document", True),
            include_generated_code=payload.get("include_generated_code", False))}
    if action == "minecraft_animation":
        from .minecraft_animation import inspect
        result = inspect(document, payload.get("metadata"), payload.get("time_ms", 0))
        return {"state": document.status(), "image": result.pop("image_base64"), "animation": result}
    if action == "minecraft_performance":
        from .minecraft_performance import inspect
        return {"state": document.status(), **inspect(document, payload.get("options"))}
    if action == "minecraft_regression_compare":
        from .minecraft_regression import compare
        return {"state": document.status(), "report": compare(payload.get("baseline"), payload.get("candidate"), payload.get("budgets"),require_material=document.material_data is not None)}
    if action == "minecraft_material":
        from .material_data import inspect
        fields={k:payload[k] for k in ('role','channel','view','pixel','resource','settings','time_ms','max_size') if k in payload}
        return {"state":document.status(),**inspect(document,**fields)}
    if action == "minecraft_scene":
        from .minecraft_view import build_scene
        include_pixels = payload.get("include_pixels", False)
        if type(include_pixels) is not bool:
            raise StudioError("include_pixels 须为布尔值")
        scene = build_scene(document, settings=payload.get("settings"), view=payload.get("options"))
        if not include_pixels:
            for texture in scene["textures"]:
                texture.pop("rgba", None)
        return {"state": document.status(), "scene": scene, "validation": scene["validation"]}
    if action == "minecraft_preview":
        from .minecraft_review import preview
        return {"state": document.status(), **preview(document, settings=payload.get("settings"),
            view=payload.get("options"), batch=payload.get("batch", False), contexts=payload.get("contexts"),
            case_offset=payload.get("case_offset", 0), case_limit=payload.get("case_limit", 16))}
    if action == "scene_sample":
        from .scene_animation import sample
        from .scene_program import validate_view, is_program
        if document.scene_animation is None:
            raise StudioError("当前工程没有场景动画")
        moment = payload.get("time_ms", 0)
        if type(moment) not in (int,float) or not __import__("math").isfinite(moment) or not 0 <= moment <= 120000:
            raise StudioError("time_ms 须为 0..120000 的有限毫秒数")
        view = validate_view(document.scene_animation,payload["scene_view"]) if payload.get("scene_view") is not None else None
        state = payload.get("scene_state")
        if state is not None and (view is not None or not is_program(document.scene_animation) or not isinstance(state,str) or state not in {s["id"] for s in document.scene_animation["states"]}):
            raise StudioError("scene_state 须为当前状态机中的状态，且不与 scene_view 同传","INVALID_SCENE_STATE")
        return {"state": document.status(), "sample": sample(document.scene_animation, document.shapes["model"], moment,view=view,state=state)}
    if action == "scene_validate":
        from .scene_animation import normalize
        from .scene_program import validate_binding, all_entries
        if payload.get("expected_document_id") is not None:
            document.guard(payload.get("expected_document_id"),payload.get("expected_revision"))
        scene = normalize(payload.get("settings"),document.shapes["model"])
        validate_binding(scene,document.animation)
        return {"state":document.status(),"scene":scene,"report":{"valid":True,"scene_schema":scene["schema"] if scene else None,
                "states":[{"id":s["id"],"label":s["label"]} for s in (scene or {}).get("states",[])],
                "transform_tracks":len(all_entries(scene,"transforms")),"emitters":len(all_entries(scene,"emitters")),"not_applied":True}}
    if action == "status":
        return document.status()
    if action == "model_uv":
        from .model_uv import query
        return {"document_id": document.document_id, "revision": document.revision,
                "uv_map": query(document, **{k: payload[k] for k in ("frame", "x", "y") if k in payload})}
    if action == "project_plan":
        from .project_setup import prepare
        return {"document_id": document.document_id, "revision": document.revision,
                "plan": prepare(payload.get("settings"))}
    if action == "focus":
        if focus:
            focus()
        return document.status()
    if action == "view":
        frame = payload.get("frame")
        if type(frame) is not int or not 0 <= frame < len(document.animation["rectangles"]):
            raise StudioError("预览帧索引超出范围")
        document.view_frame = frame
        return {"state": document.status()}
    if action == "snapshot":
        from .model_uv import describe
        return {"state": document.status(), "canvas": document.canvas.to_dict(),
                "model_uv": describe(document.shapes.get("model"), document.animation["frame_size"]),
                "native_protocol": {"version": 1, "fast_poll": True, "stroke_patches": True},
                "undo_count": len(document.undo_stack), "redo_count": len(document.redo_stack)}
    if action == "preview":
        options = {k: payload[k] for k in ("scale", "tile", "backgrounds", "frame_height") if k in payload}
        return {"state": document.status(), "image": image_data(render_canvas(document.canvas, **options))}
    if action == "animation_preview":
        if document.scene_animation is not None:
            from .scene_preview import preview
            return preview(document, payload)
        from .texture_animation import build_report, player_html
        plan = document.animation
        image = document.canvas.composite()
        frames = [image.crop((x, y, x + w, y + h)) for x, y, w, h in plan["rectangles"]]
        report = build_report(plan, "in-memory:" + document.art_digest(), plan["rectangles"], frames)
        report["document_id"], report["revision"] = document.document_id, document.revision
        report["content_digest"] = document.art_digest()
        return {"state": document.status(), "report": report,
                "html": player_html(report, frames, payload.get("scale", 6))}
    if action == "read":
        values = [payload.get(k) for k in ("x", "y", "w", "h")]
        if any(type(n) is not int for n in values):
            raise StudioError("read 的 x/y/w/h 须为整数")
        lines = Executor(document.canvas.clone()).run_script("read " + " ".join(map(str, values)) +
                                                             (" raw" if payload.get("raw") else ""))
        return {"state": document.status(), "text": "\n".join(lines)}
    if action == "shape_preview":
        from .shape_preview import render, html
        frame = payload.get("frame", document.view_frame)
        if type(frame) is not int or not 0 <= frame < len(document.animation["rectangles"]):
            raise StudioError("形状预览帧索引超出范围")
        x,y,w,h = document.animation["rectangles"][frame]
        options = {k: payload[k] for k in ("size", "yaw", "pitch", "overlays", "show_model") if k in payload}
        image = render(document.shapes, document.canvas.composite().crop((x,y,x+w,y+h)), scene=document.scene_animation, time_ms=payload.get("time_ms",0), **options)
        state = document.status()
        result = {"state": state, "image": image_data(image), "report": state["shape_report"]}
        if payload.get("html", False):
            metadata = {k: state[k] for k in ("document_id", "revision", "content_digest")}
            metadata["project_name"] = document.project_path.name if document.project_path else "未命名工程"
            result["html"] = html(document.shapes, document.canvas, document.animation, metadata, scene=document.scene_animation)
        return result
    document.guard(payload.get("expected_document_id"), payload.get("expected_revision"))
    if action in ("edit", "validate"):
        if not isinstance(payload.get("commands"), str):
            raise StudioError("commands 须为 .px 文字")
        options = {k: payload[k] for k in ("scale", "tile", "backgrounds", "frame_height") if k in payload}
        batch = document.edit(payload["commands"], dry_run=action == "validate",
                              document_id=document.document_id, revision=document.revision,
                              source="AI", label=payload.get("label", "AI 修改"),
                              include_preview=payload.get("include_preview", True), preview_options=options)
        response = {"state": document.status(), "messages": batch.messages, "batch": batch.summary}
        if batch.preview is not None:
            response["image"] = image_data(batch.preview)
        return response
    if action in ("undo", "redo"):
        document.history(action)
    elif action == "new":
        document.new(payload.get("width", 32), payload.get("height", 32))
    elif action == "create_project":
        plan = document.create_project(payload.get("settings"))
        return {"state": document.status(), "plan": plan}
    elif action == "open":
        document.open(payload["path"])
    elif action == "save":
        document.save(payload["path"])
    elif action == "animation":
        if payload.get("path"):
            path = Path(payload["path"]).resolve()
            document.configure_animation(json.loads(path.read_text(encoding="utf-8")), path)
        else:
            document.configure_animation(payload["settings"])
    elif action == "scene_animation":
        document.configure_scene(payload.get("settings"))
    elif action == "minecraft_configure":
        document.configure_minecraft(payload.get("settings"))
    elif action == "minecraft_animation_apply":
        document.configure_minecraft_animation(payload.get("metadata"))
    elif action == "minecraft_material_configure":
        document.configure_material(payload.get("settings"))
    elif action == "minecraft_material_import":
        document.import_material(payload.get("role"),path=payload.get("path"),resource=payload.get("resource"),channel=payload.get("channel"))
    elif action == "minecraft_material_edit":
        document.edit_material(payload.get("role"),payload.get("channel"),payload.get("operations"))
    elif action == "minecraft_export":
        receipt = document.export_minecraft(payload["path"], validation_digest=payload.get("validation_digest"),
            format=payload.get("format", "resource-pack"), overwrite=payload.get("overwrite", False))
        return {"state": document.status(), "export": receipt}
    elif action == "animation_prepare":
        from .animation_frames import prepare_frames
        report = prepare_frames(document, payload["settings"])
        return {"state": document.status(), "preparation": report}
    elif action in ("shapes", "shape_edit", "shape_validate"):
        value = json.loads(Path(payload["path"]).read_text(encoding="utf-8")) if payload.get("path") else payload.get("settings")
        operations = (payload.get("operations", value) if action == "shape_edit" else payload.get("operations"))
        report = document.configure_shapes(value, operations=operations, dry_run=action == "shape_validate")
        return {"state": document.status(), "report": report}
    elif action == "model_import":
        value = json.loads(Path(payload["path"]).read_text(encoding="utf-8")) if payload.get("path") else payload.get("model")
        document.import_model(value)
    elif action in ("shape_build", "shape_optimize"):
        options={key:payload[key] for key in ("target","max_error","target_boxes","symmetry","dry_run") if key in payload}
        result=document.construct_shapes("build" if action=="shape_build" else "optimize",**options)
        return {"state":document.status(),**result}
    elif action == "shape_export":
        receipt = document.export_shapes(payload["path"], format=payload.get("format", "json"),
            class_name=payload.get("class_name", "BlockShapes"), package=payload.get("package", ""), overwrite=payload.get("overwrite", False))
        return {"state": document.status(), "export": receipt}
    elif action == "approve":
        document.approve(payload.get("user_request"), source=payload.get("source", "conversation"),
                         minecraft_validation_digest=payload.get("minecraft_validation_digest"))
    elif action == "note":
        document.add_note(payload.get("text"), source=payload.get("source", "AI"))
    elif action == "export":
        receipt = document.export(payload["path"], frame=payload.get("frame"), scale=payload.get("scale", 1),
                                  overwrite=payload.get("overwrite", False))
        return {"state": document.status(), "export": receipt}
    elif action == "canvas_replace":
        candidate = Canvas.from_dict(payload["canvas"])
        if (candidate.w, candidate.h) != (document.canvas.w, document.canvas.h):
            raise StudioError("手动编辑不能改变画布尺寸")
        document.change_canvas(lambda canvas: canvas.__dict__.update(candidate.__dict__), payload.get("label", "手动修改"))
    elif action == "layer_select":
        document.select_layer(payload["name"])
    elif action == "frame_edit":
        step = document.edit_frame(payload["operation"], payload["step_index"])
        return {"state": document.status(), "step_index": step}
    elif action == "recover":
        document.recover()
    else:
        raise StudioError("未知会话操作: " + str(action))
    return {"state": document.status()}


class Session:
    """Serialized owner of a Document; hosting and GUI event loops are adapters."""
    def __init__(self, workspace, runtime, *, restore=True):
        self.document = Document(workspace, runtime)
        self._lock = threading.RLock()
        self.checkpoint = Path(runtime).resolve() / "state.json"
        self.stroke_lease, self.stroke_deadline = None, None
        self.stroke_target = None
        if restore and self.checkpoint.exists():
            self._restore(json.loads(self.checkpoint.read_text(encoding="utf-8")))

    @staticmethod
    def _pack(snapshot):
        return [snapshot[0].to_dict(), *snapshot[1:]]

    @staticmethod
    def _unpack(snapshot):
        canvas = Canvas.from_dict(snapshot[0])
        animation=playback(snapshot[1], (canvas.w, canvas.h))
        shapes = normalize_shapes(snapshot[3]) if len(snapshot)>3 else default_shapes()
        result = (canvas, animation, snapshot[2], shapes, None)
        if len(snapshot)>5:
            from .scene_animation import normalize
            from .scene_program import validate_binding
            scene = normalize(snapshot[5], shapes["model"])
            validate_binding(scene,animation)
            result += (scene,)
            if len(snapshot)>6:
                from .minecraft_target import normalize as normalize_minecraft
                result += (normalize_minecraft(snapshot[6]),)
            if len(snapshot)>7:
                from .material_data import normalize as normalize_material
                result += (normalize_material(snapshot[7],(canvas.w,canvas.h)),)
            return result
        return result

    def persist(self):
        d = self.document
        minecraft_history = d.minecraft_project is not None or any(len(s)>6 for s in [*d.undo_stack, *d.redo_stack])
        runtime_history = bool(d.minecraft_project and d.minecraft_project.get("runtime")) or any(len(s)>6 and s[6] and s[6].get("runtime") for s in [*d.undo_stack, *d.redo_stack])
        material_history = d.material_data is not None or any(len(s)>7 for s in [*d.undo_stack,*d.redo_stack])
        schema = "pixelforge.session/v4" if material_history else "pixelforge.session/v3" if runtime_history else "pixelforge.session/v2" if minecraft_history else "pixelforge.session/v1"
        commit_files({self.checkpoint: encoded({"schema": schema, "project": d.project_data(),
            "revision": d.revision, "saved_digest": d.saved_digest,
            "project_path": str(d.project_path) if d.project_path else None, "project_stamp": d.project_stamp,
            "source_path": str(d.source_path) if d.source_path else None, "events": d.events,
            "undo": [self._pack(s) for s in d.undo_stack], "redo": [self._pack(s) for s in d.redo_stack]})})

    def _restore(self, record):
        if record.get("schema") not in ("pixelforge.session/v1", "pixelforge.session/v2", "pixelforge.session/v3", "pixelforge.session/v4"):
            raise StudioError("不支持的会话恢复格式")
        d, data = self.document, record["project"]
        canvas = Canvas.from_dict(data)
        metadata = data["pixelforge_desktop"]  # retain the existing .pixforge format
        if not isinstance(metadata, dict) or metadata.get("schema") not in ("pixelforge.desktop/v1", "pixelforge.desktop/v2", "pixelforge.desktop/v3", "pixelforge.desktop/v4"):
            raise StudioError("不支持的工程恢复格式")
        animation = playback(metadata["animation"], (canvas.w, canvas.h))
        undo, redo = [self._unpack(s) for s in record["undo"]], [self._unpack(s) for s in record["redo"]]
        d.executor, d.animation = Executor(canvas), animation
        d.document_id, d.revision = metadata["document_id"], record["revision"] + 1
        d.animation_source, d.approval, d.notes = metadata.get("animation_source"), metadata.get("approval"), metadata.get("notes", [])
        d.shapes = normalize_shapes(metadata.get("shapes", default_shapes()))
        from .scene_animation import normalize as normalize_scene
        d.scene_animation = normalize_scene(metadata.get("scene_animation"), d.shapes["model"])
        from .minecraft_target import normalize as normalize_minecraft
        d.minecraft_project = normalize_minecraft(metadata.get("minecraft_project"), d.workspace)
        from .material_data import normalize as normalize_material
        d.material_data = normalize_material(metadata.get("material_data"),(canvas.w,canvas.h),d.workspace)
        if d.material_data is not None and (record.get('schema')!='pixelforge.session/v4' or metadata.get('schema')!='pixelforge.desktop/v4'):
            raise StudioError("数据材质恢复稿须使用 v4 格式")
        from .scene_program import validate_binding
        validate_binding(d.scene_animation,animation)
        d.undo_stack, d.redo_stack, d.events = undo, redo, record.get("events", [])
        d.canvas._undo = [snapshot[0]._snapshot() for snapshot in undo]
        d.canvas._redo = [snapshot[0]._snapshot() for snapshot in redo]
        d.project_path = Path(record["project_path"]) if record.get("project_path") else None
        d.source_path = Path(record["source_path"]) if record.get("source_path") else None
        d.project_stamp, d.saved_digest = record.get("project_stamp"), record["saved_digest"]
        if not d.approved():
            d.approval = None

    def call(self, action, **payload):
        with self._lock:
            return self._call(action, **payload)

    def _call(self, action, **payload):
        d = self.document
        if action in ("save", "export", "shape_export", "minecraft_export") and Path(payload.get("path", "")).resolve() in {
                self.checkpoint, d.runtime / "session.json", d.runtime / "approvals.json"}:
            raise StudioError("工程不能覆盖会话内部状态文件")
        if self.stroke_deadline is not None and time.monotonic() > self.stroke_deadline:
            d.end_stroke(cancel=True)
            self.stroke_lease = self.stroke_deadline = None
            self.stroke_target = None
        if action == "stroke_begin":
            d.guard(payload.get("expected_document_id"), payload.get("expected_revision"))
            frame = payload.get("frame", d.view_frame)
            if type(frame) is not int or not 0 <= frame < len(d.animation["rectangles"]):
                raise StudioError("笔画源帧索引无效")
            d.begin_stroke()
            self.stroke_lease = secrets.token_urlsafe(24)
            self.stroke_deadline = time.monotonic() + 120
            self.stroke_target = (d.canvas.active.name, d.animation["rectangles"][frame])
            return {"state": d.status(), "lease": self.stroke_lease}
        if action in ("stroke_end", "stroke_keepalive", "stroke_patch"):
            if not self.stroke_lease or payload.get("lease") != self.stroke_lease:
                raise StudioError("笔画已过期或属于另一个客户端", "STROKE_CONFLICT")
            if action == "stroke_keepalive":
                self.stroke_deadline = time.monotonic() + 120
                return {"state": d.status()}
            if action == "stroke_patch":
                # Stream bounded replacement RGBA into the leased candidate.
                # A large atlas is never resent for each mouse movement or patch.
                from PIL import Image
                rect, name = payload.get("rect"), payload.get("layer")
                if (not isinstance(rect, list) or len(rect) != 4
                        or any(type(n) is not int for n in rect) or self.stroke_target is None
                        or name != self.stroke_target[0]):
                    raise StudioError("笔画贴片须使用锁定的图层与整数区域")
                x, y, w, h = rect
                rx, ry, rw, rh = self.stroke_target[1]
                if w < 1 or h < 1 or w * h > 262144 or x < rx or y < ry or x+w > rx+rw or y+h > ry+rh:
                    raise StudioError("笔画贴片须位于锁定的源帧内，且不超过 262144 像素")
                data = payload.get("data")
                if not isinstance(data, str) or len(data) > 1_398_104:
                    raise StudioError("无效的笔画 RGBA 贴片")
                try:
                    raw = base64.b64decode(data, validate=True)
                except (ValueError, TypeError) as error:
                    raise StudioError("无效的笔画 RGBA 编码") from error
                if len(raw) != w*h*4:
                    raise StudioError("笔画 RGBA 字节数与区域不一致")
                d.stroke["canvas"].active.img.paste(Image.frombytes("RGBA", (w, h), raw), (x, y))
                self.stroke_deadline = time.monotonic() + 120
                return {"patch_received": True}
            if not payload.get("cancel") and "canvas" in payload:
                canvas = Canvas.from_dict(payload["canvas"])
                if (canvas.w, canvas.h) != (d.canvas.w, d.canvas.h):
                    raise StudioError("笔画不能改变画布尺寸")
                d.stroke["canvas"] = canvas
            d.end_stroke(cancel=payload.get("cancel", False))
            self.stroke_lease = self.stroke_deadline = None
            self.stroke_target = None
            result = {"state": d.status()}
        else:
            try:
                result = dispatch(d, {"action": action, **payload})
            except PixForgeError as error:
                raise StudioError(str(error), "DRAWING_ERROR") from error
        if action not in ("status", "view_poll", "snapshot", "model_uv", "animation_capabilities", "minecraft_capabilities", "minecraft_check", "minecraft_scene", "minecraft_preview", "minecraft_animation", "minecraft_performance", "minecraft_regression_compare", "minecraft_material", "scene_sample", "scene_validate", "project_plan", "preview", "animation_preview", "shape_preview", "shape_validate", "read", "validate", "focus", "view") and not (action in ("shape_build","shape_optimize") and payload.get("dry_run")):
            self.persist()
        return result
