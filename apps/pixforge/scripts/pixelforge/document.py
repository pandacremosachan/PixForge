"""Independent pixel document, history, animation and content-bound export approval."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import uuid

from PIL import Image

from .canvas import Canvas
from .palette import color_to_hex
from .protocol import Executor
from .transactions import canvas_digest, commit_files
from . import shapes as shape_core
from .shape_builder import construction_defaults, DEFAULT_BUILD_OPERATION

SCHEMA = "pixelforge.desktop/v1"
MINECRAFT_SCHEMA = "pixelforge.desktop/v2"
RUNTIME_SCHEMA = "pixelforge.desktop/v3"
MATERIAL_SCHEMA = "pixelforge.desktop/v4"


class StudioError(ValueError):
    def __init__(self, message, code="INVALID_ARGUMENT", *, details=None):
        super().__init__(message)
        self.code = code
        self.details = details


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def playback(value, size):
    """Validate timing against in-memory pixels; no premature PNG export required."""
    if not isinstance(value, dict):
        raise StudioError("动画定义必须是 JSON 对象")
    if value.get("interpolation", "none") != "none":
        raise StudioError("桌面预览目前支持显式 none 插值；游戏插值需项目适配器")
    frame_size = value.get("frame_size", list(size))
    if not isinstance(frame_size, list) or len(frame_size) != 2 or any(type(n) is not int or n < 1 for n in frame_size):
        raise StudioError("frame_size 必须是正整数宽高")
    rectangles = value.get("rectangles")
    if rectangles is None:
        w, h = frame_size
        if size[0] % w or size[1] % h:
            raise StudioError("帧尺寸必须整除画布，或显式提供帧矩形")
        rectangles = [[x, y, w, h] for y in range(0, size[1], h) for x in range(0, size[0], w)]
    if not isinstance(rectangles, list) or not 1 <= len(rectangles) <= 4096:
        raise StudioError("帧矩形数量必须在 1..4096 之间")
    for rect in rectangles:
        if not isinstance(rect, list) or len(rect) != 4 or any(type(n) is not int or n < 0 for n in rect):
            raise StudioError("帧矩形使用非负整数 [x,y,width,height]")
        x, y, w, h = rect
        if [w, h] != frame_size or x + w > size[0] or y + h > size[1]:
            raise StudioError("帧矩形须符合帧尺寸并位于画布内")
    steps = value.get("steps", [{"frame": i, "duration_ms": 100} for i in range(len(rectangles))])
    if not isinstance(steps, list) or not 1 <= len(steps) <= 10000:
        raise StudioError("播放步骤数量必须在 1..10000 之间")
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"frame", "duration_ms"}:
            raise StudioError("每个播放步骤须包含 frame 和 duration_ms")
        frame, duration = step["frame"], step["duration_ms"]
        if type(frame) is not int or not 0 <= frame < len(rectangles):
            raise StudioError("播放帧索引超出范围")
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise StudioError("帧时长须为有限的正毫秒数")
    if not math.isfinite(sum(step["duration_ms"] for step in steps)):
        raise StudioError("动画总时长超出范围")
    if type(value.get("loop", True)) is not bool or not isinstance(value.get("provenance", ""), str):
        raise StudioError("loop 必须是布尔值，provenance 必须是文字")
    return {"frame_size": frame_size, "rectangles": deepcopy(rectangles), "steps": deepcopy(steps),
            "loop": value.get("loop", True), "interpolation": "none",
            "provenance": value.get("provenance", "编辑器预览设置；尚未核对游戏元数据")}


class Document:
    def __init__(self, workspace, runtime, width=32, height=32):
        self.workspace, self.runtime = Path(workspace).resolve(), Path(runtime).resolve()
        self.executor = Executor(Canvas(width, height))
        self.document_id, self.revision = uuid.uuid4().hex, 0
        self.animation = playback({}, (width, height))
        self.animation_source = None
        self.scene_animation = None
        self.minecraft_project = None
        self.material_data = None
        self.shapes = shape_core.default_shapes()
        self.approval, self.project_path, self.project_stamp = None, None, None
        self.notes, self.events, self.undo_stack, self.redo_stack = [], [], [], []
        self.stroke = None
        self.view_frame, self.source_path = 0, None
        try:
            self.approval_ledger = json.loads((self.runtime / "approvals.json").read_text(encoding="utf-8"))
            if not isinstance(self.approval_ledger, dict):
                self.approval_ledger = {}
        except (OSError, ValueError):
            self.approval_ledger = {}
        self.saved_digest = self.project_digest()

    @property
    def canvas(self):
        return self.executor.canvas

    def art_digest(self):
        data = self.canvas.to_dict()
        data.pop("active", None)
        data.pop("mirror", None)
        data.pop("palette", None)
        content = {"canvas": data, "animation": self.animation, "animation_source": self.animation_source}
        if self.shapes != shape_core.default_shapes():
            content["shapes"] = self.shapes
        if self.scene_animation is not None:
            content["scene_animation"] = self.scene_animation
        if self.minecraft_project is not None:
            content["minecraft_project"] = self.minecraft_project
        if self.material_data is not None:
            content["material_data"] = self.material_data
        return checksum(encoded(content))

    def project_digest(self):
        data = self.canvas.to_dict()
        data.pop("active", None)
        content = {"canvas": data, "animation": self.animation, "animation_source": self.animation_source,
                   "approval": self.approval, "notes": self.notes}
        if self.shapes != shape_core.default_shapes():
            content["shapes"] = self.shapes
        if self.scene_animation is not None:
            content["scene_animation"] = self.scene_animation
        if self.minecraft_project is not None:
            content["minecraft_project"] = self.minecraft_project
        if self.material_data is not None:
            content["material_data"] = self.material_data
        return checksum(encoded(content))

    @property
    def dirty(self):
        return self.project_digest() != self.saved_digest

    def dependency_current(self):
        if self.animation_source:
            try:
                return checksum(Path(self.animation_source["path"]).read_bytes()) == self.animation_source["sha256"]
            except OSError:
                return False
        return True

    def approved(self):
        return bool(self.approval and self.approval["document_id"] == self.document_id
                    and self.approval_ledger.get(self.document_id) == self.approval
                    and self.approval["content_digest"] == self.art_digest() and self.dependency_current())

    def status(self):
        from .material_data import summary as material_summary
        return {"document_id": self.document_id, "revision": self.revision, "content_digest": self.art_digest(),
                "size": [self.canvas.w, self.canvas.h], "active_layer": self.canvas.active.name,
                "layers": [{"name": layer.name, "visible": layer.visible} for layer in self.canvas.layers],
                "palette": {char: color_to_hex(color) for char, color in self.canvas.palette.chars.items()},
                "animation": self.animation, "animation_source_current": self.dependency_current(),
                "scene_animation": deepcopy(self.scene_animation),
                "minecraft_project": deepcopy(self.minecraft_project),
                "material_data": material_summary(self.material_data),
                "shapes": deepcopy(self.shapes), "shape_report": shape_core.report(self.shapes),
                "shape_construction_defaults": construction_defaults(),
                "approved_for_export": self.approved(), "approval": self.approval,
                "project_path": str(self.project_path) if self.project_path else None, "dirty": self.dirty,
                "source_path": str(self.source_path) if self.source_path else None,
                "view_frame": min(self.view_frame, len(self.animation["rectangles"]) - 1),
                "manual_stroke_active": self.stroke is not None, "notes": self.notes[-30:], "events": self.events[-15:],
                "workspace": str(self.workspace), "runtime": str(self.runtime)}

    def guard(self, document_id=None, revision=None, *, observed=True):
        if self.stroke is not None:
            raise StudioError("用户正在绘制；本轮笔画结束后重读状态再修改", "BUSY")
        if observed and document_id != self.document_id:
            raise StudioError("工程已切换；先读取当前 document_id", "DOCUMENT_CONFLICT")
        if observed and (type(revision) is not int or revision != self.revision):
            raise StudioError("工程已有新改动；先读取当前 revision", "REVISION_CONFLICT")

    def event(self, label, source="desktop"):
        self.events.append({"time": now(), "label": str(label)[:500], "source": source, "revision": self.revision})
        self.events = self.events[-100:]

    def snapshot(self):
        result = (self.canvas.clone(), deepcopy(self.animation), deepcopy(self.animation_source), deepcopy(self.shapes), None)  # Reserved history slot; keep scene/material indices stable.
        if self.material_data is not None:
            return result + (deepcopy(self.scene_animation), deepcopy(self.minecraft_project), deepcopy(self.material_data))
        if self.minecraft_project is not None:
            return result + (deepcopy(self.scene_animation), deepcopy(self.minecraft_project))
        return result + (deepcopy(self.scene_animation),) if self.scene_animation is not None else result

    def remember(self, snapshot):
        self.undo_stack.append(snapshot)
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()

    def changed(self, label, previous_digest, source="desktop"):
        self.revision += 1
        if previous_digest != self.art_digest():
            self.approval = None
        self.event(label, source)

    def edit(self, script, *, dry_run=False, document_id=None, revision=None, source="AI", label="AI 修改",
             include_preview=False, preview_options=None):
        self.guard(document_id, revision)
        if not isinstance(script, str):
            raise StudioError("commands 须为 .px 文字")
        for line in script.splitlines():
            words = line.strip().split()
            if words and words[0].lower() in {"new", "load", "render", "save", "undo", "redo"}:
                raise StudioError("共享绘图批次只编辑当前工程；新建、打开、保存、导出和撤销使用各自接口")
        previous, snapshot = self.art_digest(), self.snapshot()
        batch = self.executor.run_batch(script, dry_run=dry_run, publish_outputs=False,
                                        include_preview=include_preview, preview_options=preview_options)
        candidate_animation=self.animation
        resized=[batch.canvas.w,batch.canvas.h]!=[snapshot[0].w,snapshot[0].h]
        if resized and self.material_data is not None:
            if not dry_run:self.executor=Executor(snapshot[0])
            raise StudioError("已绑定数据图集；尺寸修改须同步数据贴图。增删动画帧会自动同步，普通绘制不能隐式缩放数据", "MATERIAL_SIZE_LOCKED")
        if resized:candidate_animation=playback({},(batch.canvas.w,batch.canvas.h))
        try:
            from .scene_program import validate_binding
            validate_binding(self.scene_animation,candidate_animation)
        except ValueError:
            if not dry_run:self.executor=Executor(snapshot[0])
            raise
        if not dry_run and batch.summary["state_changed"]:
            # Canvas-changing scripts reset only a now-invalid frame layout.
            if [self.canvas.w, self.canvas.h] != [snapshot[0].w, snapshot[0].h]:
                self.animation = playback({}, (self.canvas.w, self.canvas.h))
                self.animation_source = None
            self.remember(snapshot)
            self.changed(label, previous, source)
        return batch

    def history(self, action):
        self.guard(observed=False)
        stack, opposite = (self.undo_stack, self.redo_stack) if action == "undo" else (self.redo_stack, self.undo_stack)
        if not stack:
            return False
        opposite.append(self.snapshot())
        restored = stack.pop()
        canvas, self.animation, self.animation_source, self.shapes = restored[:4]
        self.scene_animation = deepcopy(restored[5]) if len(restored)>5 else None
        self.minecraft_project = deepcopy(restored[6]) if len(restored)>6 else None
        self.material_data = deepcopy(restored[7]) if len(restored)>7 else None
        self.executor = Executor(canvas)
        self.approval = None
        self.revision += 1
        self.event("撤销" if action == "undo" else "重做")
        return True

    def begin_stroke(self):
        self.guard(observed=False)
        self.stroke = {"canvas": self.canvas.clone(), "before": self.snapshot(), "digest": self.art_digest()}

    def change_canvas(self, callback, label):
        self.guard(observed=False)
        candidate, before, previous = self.canvas.clone(), self.snapshot(), self.art_digest()
        callback(candidate)
        if canvas_digest(candidate) != canvas_digest(self.canvas):
            candidate._undo = [*self.canvas._undo, self.canvas._snapshot()][-50:]
            candidate._redo.clear()
            self.executor.canvas = candidate
            self.remember(before)
            self.changed(label, previous)

    def select_layer(self, name):
        self.guard(observed=False)
        if name != self.canvas.active.name:
            self.canvas.use_layer(name)
            self.revision += 1

    def end_stroke(self, cancel=False):
        if self.stroke is None:
            return
        stroke, self.stroke = self.stroke, None
        if not cancel and canvas_digest(stroke["canvas"]) != canvas_digest(self.canvas):
            stroke["canvas"]._undo = [*self.canvas._undo, self.canvas._snapshot()][-50:]
            stroke["canvas"]._redo.clear()
            self.executor.canvas = stroke["canvas"]
            self.remember(stroke["before"])
            self.changed("手动笔画", stroke["digest"])

    def configure_animation(self, value, source_path=None):
        self.guard(observed=False)
        setting = playback(value, (self.canvas.w, self.canvas.h))
        from .scene_program import validate_binding
        validate_binding(self.scene_animation,setting)
        dependency = None
        if source_path:
            path = Path(source_path).resolve()
            content = path.read_bytes()
            if json.loads(content) != value:
                raise StudioError("动画定义在读取期间已有变化，请重新载入", "DEPENDENCY_CHANGED")
            dependency = {"path": str(path), "sha256": checksum(content)}
        snapshot, previous = self.snapshot(), self.art_digest()
        self.animation = setting
        self.animation_source = dependency
        if previous != self.art_digest():
            self.remember(snapshot)
            self.changed("更新动画时序", previous)

    def configure_scene(self, value):
        self.guard(observed=False)
        from .scene_animation import normalize
        setting = normalize(value, self.shapes["model"])
        from .scene_program import validate_binding
        validate_binding(setting,self.animation)
        if setting != self.scene_animation:
            before, previous = self.snapshot(), self.art_digest()
            self.scene_animation = setting
            self.remember(before)
            self.changed("更新部件与粒子场景动画", previous)

    def configure_minecraft(self, value):
        self.guard(observed=False)
        from .minecraft_target import normalize
        setting = normalize(value, self.workspace)
        if setting != self.minecraft_project:
            before, previous = self.snapshot(), self.art_digest()
            self.minecraft_project = setting
            self.remember(before)
            self.changed("更新 Minecraft 目标与资源绑定", previous)

    def _accept_material(self, candidate, label):
        self.guard(observed=False)
        if candidate != self.material_data:
            before, previous = self.snapshot(), self.art_digest()
            self.material_data = candidate
            self.remember(before)
            self.changed(label, previous)

    def configure_material(self, settings):
        from .material_data import configure
        self._accept_material(configure(self,settings), "配置 LabPBR 数据材质")

    def import_material(self, role, path=None, resource=None, channel=None):
        from .material_data import configure, ROLES, resource_maps, read_png, pack, unpack, channel_index, MAX_PNG
        self.guard(observed=False)
        if role not in ROLES or bool(path)==bool(resource):
            raise StudioError("指定 normal/specular，并提供一个 PNG 路径或资源 id")
        candidate=configure(self,{})
        if role not in candidate['maps']:
            candidate=configure(self,{'maps':[*candidate['maps'],role]})
        if resource:
            if self.minecraft_project is None:raise StudioError("先配置实际资源来源")
            sources=resource_maps(self.minecraft_project,resource)
            if role not in sources:raise StudioError("资源缺少对应的数据贴图")
            if sources[role]['source']['role']=='dependency':raise StudioError("dependency 数据贴图仅供只读检查；导入须使用用户拥有的显式 PNG 副本", "DEPENDENCY_READ_ONLY")
            image=sources[role]['image']
        else:
            source=Path(path).resolve()
            if source.stat().st_size>MAX_PNG:raise StudioError("数据 PNG 超过 32 MiB")
            image=read_png(source.read_bytes())
        if image.size!=(self.canvas.w,self.canvas.h):raise StudioError("数据贴图尺寸须与颜色图集相同；不会自动缩放")
        if channel is not None:
            index=channel_index(role,channel);channels=list(unpack(candidate['maps'][role]).split());channels[index]=image.getchannel('R');image=Image.merge('RGBA',channels)
        candidate['maps'][role]=pack(image)
        self._accept_material(candidate,"导入 LabPBR 数据通道" if channel is not None else "导入 LabPBR 数据贴图")

    def edit_material(self, role, channel, operations):
        from .material_data import edit
        self.guard(observed=False)
        self._accept_material(edit(self.material_data,role,channel,operations),"编辑 LabPBR 独立数据通道")

    def configure_minecraft_animation(self, metadata):
        self.guard(observed=False)
        from .minecraft_animation import metadata_plan
        from .minecraft_target import normalize
        from .scene_program import validate_binding
        if self.minecraft_project is None:
            raise StudioError("先配置 Minecraft 目标，再导入 .mcmeta")
        animation, option = metadata_plan(metadata, (self.canvas.w, self.canvas.h))
        validate_binding(self.scene_animation, animation)
        config = normalize({**deepcopy(self.minecraft_project), "texture_animation": option}, self.workspace)
        if animation != self.animation or config != self.minecraft_project:
            before, previous = self.snapshot(), self.art_digest()
            self.animation, self.animation_source, self.minecraft_project = animation, None, config
            self.view_frame = 0
            self.remember(before)
            self.changed("导入 Minecraft 动画元数据", previous)

    def check_minecraft(self, *, settings=None, use_document=True, include_generated_code=False):
        from .minecraft_export import inspect
        return inspect(self, settings=settings, use_document=use_document, include_generated_code=include_generated_code)[0]

    def export_minecraft(self, path, **options):
        from .minecraft_export import publish
        return publish(self, path, **options)

    def add_note(self, text, source="user"):
        self.guard(observed=False)
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise StudioError("请填写 1..4000 字的讨论意见")
        self.notes.append({"text": text.strip(), "source": source, "time": now(), "revision": self.revision,
                           "frame": self.view_frame})
        self.notes = self.notes[-100:]
        self.revision += 1
        # New user feedback reopens discussion even if no pixels have changed yet.
        if source == "user":
            self.approval = None
        self.event("新增讨论意见", source)

    def configure_shapes(self, value, *, operations=None, dry_run=False):
        self.guard(observed=False)
        candidate = shape_core.edit(self.shapes, operations) if operations is not None else shape_core.normalize(value)
        if self.scene_animation is not None and candidate["model"] != self.shapes["model"]:
            raise StudioError("当前场景绑定了模型部件；请先清除或重设场景动画，再替换模型", "SCENE_MODEL_BOUND")
        if not dry_run and candidate != self.shapes:
            before, previous = self.snapshot(), self.art_digest()
            self.shapes = candidate
            self.remember(before)
            self.changed("更新模型与碰撞 / 选中形状", previous)
        return shape_core.report(candidate)

    def import_model(self, value):
        return self.configure_shapes({**self.shapes, "model": value})




    def construct_shapes(self, operation=DEFAULT_BUILD_OPERATION, *, target="base", max_error=None, target_boxes=None, symmetry="auto", dry_run=False):
        from .shape_builder import optimize_boxes, build_model
        self.guard(observed=False)
        if type(dry_run) is not bool:
            raise StudioError("dry_run 须为布尔值")
        if target not in shape_core.TARGETS or self.shapes[target] is None:
            raise StudioError("请选择基础形状，或先将目标切换为独立覆盖")
        if operation=="build":
            defaults=construction_defaults()
            items,report=build_model(self.shapes["model"],max_error=defaults["max_error"] if max_error is None else max_error,
                target_boxes=defaults["target_boxes"] if target_boxes is None else target_boxes,symmetry=symmetry)
        elif operation=="optimize":
            items,report=optimize_boxes(self.shapes[target],max_error=0 if max_error is None else max_error,
                target_boxes=1 if target_boxes is None else target_boxes,symmetry=symmetry)
        else:
            raise StudioError("构建操作须为 build 或 optimize")
        candidate=shape_core.normalize({**self.shapes,target:items})
        report.update(target=target,dry_run=bool(dry_run),settings_changed=candidate!=self.shapes)
        if not dry_run:
            self.configure_shapes(candidate)
        return {"report":report,"proposed_shapes":candidate}

    def export_shapes(self, path, *, format="json", class_name="BlockShapes", package="", overwrite=False):
        self.guard(observed=False)
        if not self.approved():
            raise StudioError("请先让用户查看并确认当前模型、形状与纹理", "USER_CONFIRMATION_REQUIRED")
        path = Path(path).resolve()
        suffix = ".json" if format == "json" else ".java"
        if path.suffix.lower() != suffix:
            raise StudioError("形状导出文件后缀须为 " + suffix)
        if format == "forge-1.20.1" and path.stem != class_name:
            raise StudioError("Java 文件名必须与 class_name 一致")
        if path in (self.project_path, self.source_path) or (path.exists() and not overwrite):
            raise StudioError("导出不能覆盖工程、源文件或未经允许覆盖现有文件", "FILE_EXISTS")
        commit_files({path: shape_core.export_data(self.shapes, format, class_name, package)})
        self.event("导出形状 " + path.name)
        return {"path": str(path), "format": format, "content_digest": self.art_digest(),
                "shape_report": shape_core.report(self.shapes),
                "lossless_packing":shape_core.packed_shapes(self.shapes)[1] if format=="forge-1.20.1" else None}

    def edit_frame(self, action, step_index):
        """Insert/duplicate/delete a source cel and its playback entry atomically.

        Repack complete regular atlases without changing any retained RGBA pixel,
        layer, palette or custom playback duration. Arbitrary partial UV layouts
        require an explicit layout decision instead of silently dropping pixels.
        """
        self.guard(observed=False)
        steps, rectangles = self.animation["steps"], self.animation["rectangles"]
        if action not in ("add", "duplicate", "delete") or type(step_index) is not int or not 0 <= step_index < len(steps):
            raise StudioError("帧操作或播放步骤无效")
        width, height = self.animation["frame_size"]
        expected = {(x, y, width, height) for y in range(0, self.canvas.h, height)
                    for x in range(0, self.canvas.w, width)}
        if (self.canvas.w % width or self.canvas.h % height or len(set(map(tuple, rectangles))) != len(rectangles)
                or set(map(tuple, rectangles)) != expected):
            raise StudioError("增删帧需要覆盖完整画布的规则图集；请先按实际帧尺寸分帧")
        frame = steps[step_index]["frame"]
        if action == "delete" and len(rectangles) == 1:
            raise StudioError("至少保留一帧")
        order = list(range(len(rectangles)))
        if action == "delete":
            order.pop(frame)
        else:
            order.insert(frame + 1, frame if action == "duplicate" else None)
        from .animation_frames import repack_frames
        candidate, new_rectangles = repack_frames(self.canvas, rectangles, order)
        new_steps = []
        for index, step in enumerate(steps):
            old = step["frame"]
            if action == "delete":
                if old == frame:
                    continue
                mapped = old - (old > frame)
            else:
                mapped = old + (old > frame)
            new_steps.append({"frame": mapped, "duration_ms": step["duration_ms"]})
            if action != "delete" and index == step_index:
                new_steps.append({"frame": frame + 1, "duration_ms": step["duration_ms"]})
        if not new_steps:
            raise StudioError("删除后播放序列将为空，请先为其他帧建立播放步骤")
        if len(new_steps) > 10000:
            raise StudioError("播放步骤数量不能超过 10000")
        animation = playback({**self.animation, "rectangles": new_rectangles, "steps": new_steps},
                             (candidate.w, candidate.h))
        from .scene_program import remap_texture_frames, validate_binding
        mapping = {}
        for index,source in enumerate(order):
            if source is not None:
                mapping.setdefault(source,index)
        scene = remap_texture_frames(self.scene_animation,mapping)
        validate_binding(scene,animation)
        from .material_data import remap as remap_material
        material=remap_material(self.material_data,rectangles,order,new_rectangles,(candidate.w,candidate.h))
        before, previous = self.snapshot(), self.art_digest()
        candidate._undo = [*self.canvas._undo, self.canvas._snapshot()][-50:]
        candidate._redo.clear()
        self.executor = Executor(candidate)
        self.animation, self.animation_source = animation, None
        self.scene_animation = scene
        self.material_data = material
        self.remember(before)
        self.changed({"add": "新增空白帧", "duplicate": "复制帧", "delete": "删除帧"}[action], previous)
        return min(step_index if action == "delete" else step_index + 1, len(new_steps) - 1)

    def approve(self, user_request, *, source="conversation", minecraft_validation_digest=None):
        self.guard(observed=False)
        if not isinstance(user_request, str) or not user_request.strip() or len(user_request) > 4000:
            raise StudioError("确认须引用真实用户针对当前版本的明确同意；AI 自查不是用户授权", "USER_CONFIRMATION_REQUIRED")
        if not self.dependency_current():
            raise StudioError("动画定义文件已有变化，请重新载入并查看后确认", "DEPENDENCY_CHANGED")
        approval = {"document_id": self.document_id, "content_digest": self.art_digest(),
                    "user_request": user_request.strip(), "source": source, "time": now()}
        if self.minecraft_project is not None:
            validation = self.check_minecraft()
            if minecraft_validation_digest is not None and minecraft_validation_digest != validation["validation_digest"]:
                raise StudioError("资源自展示检查后已有变化；重新检查并确认", "RESOURCE_VALIDATION_STALE")
            if validation["passed"]:
                approval["minecraft_validation_digest"] = validation["validation_digest"]
        ledger = {**self.approval_ledger, self.document_id: approval}
        commit_files({self.runtime / "approvals.json": encoded(ledger)})
        self.approval, self.approval_ledger = approval, ledger
        self.revision += 1
        self.event("用户确认当前版本", source)

    def new(self, width, height):
        self.guard(observed=False)
        candidate = Canvas(width, height)
        self.recover()
        self.executor = Executor(candidate)
        self.document_id, self.revision = uuid.uuid4().hex, self.revision + 1
        self.animation, self.animation_source = playback({}, (width, height)), None
        self.scene_animation = None
        self.minecraft_project = None
        self.material_data = None
        self.shapes = shape_core.default_shapes()
        self.approval, self.project_path, self.project_stamp = None, None, None
        self.view_frame, self.source_path = 0, None
        self.notes, self.undo_stack, self.redo_stack = [], [], []
        self.saved_digest = self.project_digest()
        self.event("新建工程")

    def create_project(self, settings=None):
        """Prepare completely before replacing the old document; commit one new identity."""
        self.guard(observed=False)
        from .project_setup import prepare
        plan = prepare(settings, build_shapes=True)
        # new() allocates/validates the blank canvas before recovery/replacement.
        self.new(*plan["canvas_size"])
        self.shapes = deepcopy(plan["shapes"])
        if self.shapes["model"] is not None:
            self.saved_digest = "new-model-project-unsaved"
        self.event("按模型 UV 新建工程：" + plan["preset"])
        return plan

    def project_data(self):
        schema = MATERIAL_SCHEMA if self.material_data is not None else RUNTIME_SCHEMA if self.minecraft_project and self.minecraft_project.get("runtime") else MINECRAFT_SCHEMA if self.minecraft_project is not None else SCHEMA
        return {**self.canvas.to_dict(), "pixelforge_desktop": {"schema": schema, "document_id": self.document_id,
                "animation": self.animation, "animation_source": self.animation_source,
                "shapes": self.shapes,
                "approval": self.approval, "notes": self.notes,
                **({"minecraft_project": self.minecraft_project} if self.minecraft_project is not None else {}),
                **({"material_data": self.material_data} if self.material_data is not None else {}),
                **({"scene_animation": self.scene_animation} if self.scene_animation is not None else {})}}

    def recover(self):
        if self.dirty:
            path = self.runtime / "recovery" / f"{self.document_id}.pixforge"
            content = encoded(self.project_data())
            if getattr(self, "_last_recovery", None) != (str(path), checksum(content)):
                commit_files({path: content})
                self._last_recovery = (str(path), checksum(content))
            return path
        return None

    def save(self, path):
        self.guard(observed=False)
        path = Path(path).resolve()
        if path.suffix.lower() not in (".pixforge", ".json"):
            raise StudioError("可编辑工程使用 .pixforge 或 .json；PNG 请在用户确认后导出")
        if self.project_path == path and path.exists() and self.project_stamp != checksum(path.read_bytes()):
            raise StudioError("工程文件被外部修改，请另存副本", "FILE_CONFLICT")
        data = encoded(self.project_data())
        commit_files({path: data})
        self.project_path, self.project_stamp = path, checksum(data)
        self.saved_digest = self.project_digest()
        self.event("保存可编辑工程")
        return path

    def open(self, path):
        self.guard(observed=False)
        path = Path(path).resolve()
        metadata = {}
        project_content = None
        if path.suffix.lower() == ".png":
            from .texture_review import load_png
            image = load_png(path)
            canvas = Canvas(*image.size)
            canvas.active.img = image
        elif path.suffix.lower() == ".px":
            candidate = Executor()
            candidate.run_batch(path.read_text(encoding="utf-8"), publish_outputs=False)
            canvas = candidate.canvas
            if canvas is None:
                raise StudioError("脚本没有创建画布")
        else:
            project_content = path.read_bytes()
            data = json.loads(project_content)
            canvas = Canvas.from_dict(data)
            metadata = data.get("pixelforge_desktop", {})
            if not isinstance(metadata, dict):
                raise StudioError("桌面工程元数据须为对象")
            if metadata and metadata.get("schema") not in (SCHEMA, MINECRAFT_SCHEMA, RUNTIME_SCHEMA, MATERIAL_SCHEMA):
                raise StudioError("不支持的桌面工程格式")
        animation = playback(metadata.get("animation", {}), (canvas.w, canvas.h))
        shapes = shape_core.normalize(metadata.get("shapes", shape_core.default_shapes()))
        from .scene_animation import normalize as normalize_scene
        scene = normalize_scene(metadata.get("scene_animation"), shapes["model"])
        from .scene_program import validate_binding
        validate_binding(scene,animation)
        from .minecraft_target import normalize as normalize_minecraft
        minecraft_project = normalize_minecraft(metadata.get("minecraft_project"), self.workspace)
        from .material_data import normalize as normalize_material
        material_data = normalize_material(metadata.get("material_data"),(canvas.w,canvas.h),self.workspace)
        if material_data is not None and metadata.get("schema") != MATERIAL_SCHEMA:
            raise StudioError("数据材质工程须使用 v4 元数据，避免旧软件遗漏数据通道")
        if metadata.get("document_id") is not None and (not isinstance(metadata["document_id"], str) or not metadata["document_id"]):
            raise StudioError("无效工程 ID")
        notes = metadata.get("notes", [])
        if not isinstance(notes, list) or len(notes) > 100 or any(not isinstance(note, dict) or
                not isinstance(note.get("text"), str) or not isinstance(note.get("source"), str) for note in notes):
            raise StudioError("无效讨论记录")
        approval = metadata.get("approval")
        if approval is not None and (not isinstance(approval, dict) or any(key not in approval for key in ("document_id", "content_digest", "user_request", "source", "time"))):
            raise StudioError("无效确认记录")
        dependency = metadata.get("animation_source")
        if dependency is not None and (not isinstance(dependency, dict) or not isinstance(dependency.get("path"), str) or not isinstance(dependency.get("sha256"), str)):
            raise StudioError("无效动画来源记录")
        self.recover()
        self.executor = Executor(canvas)
        # Keep revisions monotonic across switches: reopening the same project
        # must never make an old observation valid again in this session.
        self.document_id, self.revision = metadata.get("document_id") or uuid.uuid4().hex, self.revision + 1
        self.animation, self.animation_source = animation, metadata.get("animation_source")
        self.shapes = shapes
        self.scene_animation = scene
        self.minecraft_project = minecraft_project
        self.material_data = material_data
        self.view_frame, self.source_path = 0, path
        self.approval, self.notes = metadata.get("approval"), metadata.get("notes", [])
        self.undo_stack, self.redo_stack = [], []
        self.project_path = path if path.suffix.lower() not in (".png", ".px") else None
        self.project_stamp = checksum(project_content) if self.project_path else None
        if self.approval and not self.approved():
            self.approval = None
        self.saved_digest = self.project_digest() if self.project_path else "imported-unsaved"
        self.event("打开 " + path.name)

    def export(self, path, *, frame=None, scale=1, overwrite=False):
        self.guard(observed=False)
        if not self.approved():
            raise StudioError("请先与用户讨论并确认当前版本；修改后需要重新确认", "USER_CONFIRMATION_REQUIRED")
        if type(scale) is not int or not 1 <= scale <= 64:
            raise StudioError("导出倍率须为 1..64，生产材质通常使用原生 1 倍")
        path = Path(path).resolve()
        if path.suffix.lower() != ".png":
            raise StudioError("素材导出路径须使用 .png")
        if path == self.project_path or (path.exists() and not overwrite):
            raise StudioError("文件已存在，请选择新路径或明确允许覆盖", "FILE_EXISTS")
        image = self.canvas.composite()
        if frame is not None:
            if type(frame) is not int or not 0 <= frame < len(self.animation["rectangles"]):
                raise StudioError("帧索引超出范围")
            x, y, w, h = self.animation["rectangles"][frame]
            image = image.crop((x, y, x + w, y + h))
        if scale != 1:
            image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        from .image_bytes import png
        commit_files({path: png(image)})
        self.event("导出 " + path.name)
        return {"path": str(path), "size": list(image.size), "frame": frame, "content_digest": self.art_digest()}
