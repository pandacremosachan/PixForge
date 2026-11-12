"""Application-owned commands shared with the native workbench."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import inspect
import re

from pydantic import ConfigDict, ValidationError, create_model
from .command_catalog import CATALOG, PURPOSES
from .shape_builder import DEFAULT_BUILD_ERROR, DEFAULT_BUILD_TARGET_BOXES


@dataclass
class CommandResult:
    data: dict
    is_error: bool = False


def build_commands(session, *, workspace=None, runtime=None):
    from .workbench import Workbench
    from .protocol import PixForgeError
    workspace = Path(workspace or Path.cwd()).resolve()
    runtime = Path(runtime or getattr(session, "runtime", workspace / ".runtime/pixelforge-desktop")).resolve()
    window = Workbench(session, workspace, runtime)

    handlers = {}
    parameter_models = {}

    def operation():
        def collect(function):
            if function.__name__ in handlers:
                raise ValueError("Duplicate command operation: " + function.__name__)
            fields = {name: (parameter.annotation, ... if parameter.default is inspect.Parameter.empty else parameter.default)
                      for name, parameter in inspect.signature(function).parameters.items()}
            handlers[function.__name__] = function
            parameter_models[function.__name__] = create_model(
                "Parameters_" + function.__name__, __config__=ConfigDict(extra="forbid"), **fields)
            return function
        return collect

    def result(data, error=False):
        data = dict(data)
        if isinstance(data.get("validation"), dict) and not data["validation"].get("passed", False):
            error = True
        if isinstance(data.get("report"), dict) and data["report"].get("constraints_passed") is False:
            error = True
        return CommandResult(data, error)

    def perform(operation, *args, **kwargs):
        try:
            return result(operation(*args, **kwargs))
        except (ValueError, OSError, KeyError, TypeError, OverflowError, PixForgeError) as failure:
            return result({"error": str(failure), "code": getattr(failure, "code", "INVALID_ARGUMENT"),
                           "details": getattr(failure, "details", None)}, True)

    def call(action, **payload):
        try:
            data, error = session.call(action, **payload), False
        except (ValueError, OSError, KeyError, TypeError) as failure:
            data, error = {"error": str(failure), "code": getattr(failure, "code", "INVALID_ARGUMENT"),
                           "details": getattr(failure, "details", None)}, True
        return result(data, error)

    @operation()
    def application_info() -> CommandResult:
        """Read application version, command interfaces, platform and supported capabilities."""
        import json
        import os
        app = Path(os.environ["PIXFORGE_NATIVE_EXE"]).with_name("application.json")
        return result({**json.loads(app.read_text(encoding="utf-8")), "platform": "windows-x64",
                       "workspace": str(workspace), "runtime": str(runtime)})


    @operation()
    def animation_capabilities() -> CommandResult:
        """Discover texture/parts/particles mechanisms and the default Forge 1.20.1 target.

        Mechanisms compose on one scene clock. Static work remains the default. Custom
        shaders and skeletal animation are not implemented; previews are offline.
        """
        return call("animation_capabilities")

    @operation()
    def minecraft_capabilities() -> CommandResult:
        """Discover exact Minecraft target profiles, supported source types and export limits."""
        return call("minecraft_capabilities")

    @operation()
    def configure_minecraft_target(settings: dict | None, expected_document_id: str,
                                   expected_revision: int) -> CommandResult:
        """Apply an undoable application-owned target/source/binding configuration; null clears it.

        Current target: forge-1.20.1. Sources are ordered low to high and have role project
        (selected closure may be exported) or dependency (check only; never redistributed).
        The current canvas binding is optional. Old projects remain unchanged until applied.
        """
        return call("minecraft_configure", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @operation()
    def check_minecraft_resources(settings: dict | None = None, use_document: bool = True,
                                  include_generated_code: bool = False) -> CommandResult:
        """Read-only reference graph, actual source winners, target format and export fingerprint.

        Optional settings validates a draft without applying it. use_document=False inspects
        source entries alone. This does not prove in-game rendering or registry coverage.
        include_generated_code=True includes read-only generated Forge Java/build/source
        previews, so code can be inspected before user approval or formal export.
        """
        return call("minecraft_check", settings=settings, use_document=use_document,
                    include_generated_code=include_generated_code)

    @operation()
    def inspect_minecraft_material(role: str = 'normal', channel: str = 'r', view: str = 'channel',
                                   pixel: list[int] | None = None, resource: str | None = None,
                                   settings: dict | None = None, time_ms: float | None = None, max_size: int = 1024) -> CommandResult:
        """Read LabPBR 1.3 data channels as opaque data, not layer opacity. Inspect raw/decoded values, normal validity, shader feature declarations and source fingerprints. Optional resource reads real _n/_s sources. No game shader is run."""
        return call('minecraft_material',role=role,channel=channel,view=view,pixel=pixel,resource=resource,settings=settings,time_ms=time_ms,max_size=max_size)

    @operation()
    def configure_minecraft_material(settings: dict | None, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Configure optional LabPBR 1.3 maps and a versioned shader target as one undo step; null clears data maps. Color layers remain unchanged. Uses project format v4, requiring software 2.7+."""
        return call('minecraft_material_configure',settings=settings,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @operation()
    def import_minecraft_material(role: str, expected_document_id: str, expected_revision: int,
                                  path: str | None = None, resource: str | None = None, channel: str | None = None) -> CommandResult:
        """Import exact 8-bit PNG data into normal/specular, or one channel from a mask's red component. Dimensions must match the atlas. Explicit project-owned resource sources may be imported; dependencies are read-only. Requires inspected UV/layout and adds one undo step."""
        return call('minecraft_material_import',role=role,path=path,resource=resource,channel=channel,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @operation()
    def edit_minecraft_material(role: str, channel: str, operations: list[dict], expected_document_id: str, expected_revision: int) -> CommandResult:
        """Write 0..255 raw values to one LabPBR channel using rect:[x,y,width,height], value operations. Other channels, hidden RGB, albedo and dimensions stay byte-exact. Requires inspected layout; entire batch is atomic and one undo step. Formal export uses existing resource approval/fingerprint checks."""
        return call('minecraft_material_edit',role=role,channel=channel,operations=operations,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @operation()
    def inspect_minecraft_animation(metadata: dict | None = None, time_ms: float = 0) -> CommandResult:
        """Read .mcmeta width/height, frame sequence, tick durations and RGB interpolation; return a source-pixel sample without changing the project."""
        return call("minecraft_animation", metadata=metadata, time_ms=time_ms)

    @operation()
    def configure_minecraft_animation(metadata: dict, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Apply .mcmeta to the current PNG canvas and configured target as one undoable change. The atlas clock is shared; machine activation belongs to an instance player."""
        return call("minecraft_animation_apply", metadata=metadata, expected_document_id=expected_document_id, expected_revision=expected_revision)


    @operation()
    def inspect_minecraft_performance(options: dict | None = None) -> CommandResult:
        """Read whole-scene frame pixels, raw mip memory, layers, dynamic parts, sampled particles and 1..4096 instance scenarios. Optional coverage_view measures a controlled reference viewport, never game FPS."""
        return call("minecraft_performance", options=options)

    @operation()
    def compare_minecraft_regression(baseline: str, candidate: str, budgets: dict | None = None) -> CommandResult:
        """Compare actual game capture directories with hashed PNG/log attachments, fixed camera/options/phase checks, pixel deltas and CPU/frame-interval budgets. Does not launch or modify a game."""
        return call("minecraft_regression_compare", baseline=baseline, candidate=candidate, budgets=budgets)

    @operation()
    def inspect_minecraft_scene(options: dict | None = None, settings: dict | None = None,
                                include_pixels: bool = False) -> CommandResult:
        """Resolve a read-only Forge 1.20.1 scene from actual resources or the current document.

        Returns model/state cases, source fingerprints, per-face texel density, separate
        block/item tints, Forge face-light data and standard render-layer rules.
        options.subject selects document/model/blockstate/texture. context selects
        block/gui/ground/fixed/head/firstperson_*hand/thirdperson_*hand. include_pixels
        adds actual RGBA data for application rendering. No project or approval changes.
        """
        return call("minecraft_scene", options=options, settings=settings, include_pixels=include_pixels)

    @operation()
    def preview_minecraft_scene(options: dict | None = None, settings: dict | None = None,
                                batch: bool = False, contexts: list[str] | None = None,
                                case_offset: int = 0, case_limit: int = 16) -> CommandResult:
        """Return a discussion PNG with mipmaps, alpha/depth, tint and controlled lighting.

        batch compares declared states, weighted alternatives and requested item contexts,
        at most 16 images per page; follow report.next_case_offset for remaining cases.
        Uses actual source pixels. This is a reference preview, not live game validation,
        formal asset export, visual approval or permission to modify the project.
        """
        return call("minecraft_preview", options=options, settings=settings, batch=batch,
                    contexts=contexts, case_offset=case_offset, case_limit=case_limit)

    @operation()
    def export_minecraft_resources(path: str, validation_digest: str, expected_document_id: str,
                                    expected_revision: int, format: str = "resource-pack",
                                    overwrite: bool = False) -> CommandResult:
        """Publish a Forge 1.20.1 ZIP after current evidence and real user approval.

        resource-pack/mod-assets export static assets. forge-integration exports application-
        generated Java and resources; forge-mod adds a buildable standalone example entry
        and registries. All formats rescan dependencies/code and reject stale fingerprints.
        No consuming source tree or game installation is modified, and no game is launched.
        """
        return call("minecraft_export", path=path, validation_digest=validation_digest, format=format,
                    overwrite=overwrite, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @operation()
    def sample_scene(time_ms: float = 0, scene_state: str | None = None, scene_view: dict | None = None) -> CommandResult:
        """Read a process, canonical named state, or captured native playback context; no mutation."""
        return call("scene_sample", time_ms=time_ms, scene_state=scene_state, scene_view=scene_view)

    @operation()
    def validate_scene_animation(settings: dict) -> CommandResult:
        """Validate a generic keyframe/state draft against the current model and texture; no mutation."""
        return call("scene_validate", settings=settings)


    @operation()
    def model_uv(frame: int | None = None, x: int | None = None, y: int | None = None) -> CommandResult:
        """Read actual model face names, local directions, UV rotation/mirroring and shared regions.

        Optional x/y are atlas pixel coordinates in the selected frame, matching draw/read.
        Returns ALL faces sampling that texel, including partial overlaps. No model means
        no guessed cube mapping. Read this before editing a particular face of an atlas.
        This read-only query does not change pixels, history or approval.
        """
        return call("model_uv", **{k: v for k, v in dict(frame=frame, x=x, y=y).items() if v is not None})

    @operation()
    def prepare_animation_frames(settings: dict, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Retain existing cels/layers and add frames/timing in one undo step. Settings: frame_count, optional frame_size/steps/loop/interpolation. Part and particle motion uses configure_scene_animation."""
        return call("animation_prepare", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @operation()
    def configure_scene_animation(settings: dict | None, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Apply or clear part motion, particles, keyframes and named states in one shared undo step."""
        return call("scene_animation", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @operation()
    def plan_project(settings: dict | None = None) -> CommandResult:
        """Plan model-first creation without changing artwork; return dimensions and UV.

        preset: cube_faces (default, separate 3x2 faces), cube_shared, model or pixels.
        Built-in cubes accept face_size (default 16). model accepts a resolved Java
        model object and optional width/height; its UV/rotation/sharing is preserved.
        pixels accepts width/height for an explicitly model-free canvas. Models and
        pixels start without interaction boxes; cube presets use one full block.
        Supply base_boxes [{id, from, to}, ...] for a placeable object's main volumes.
        """
        return call("project_plan", settings=settings)

    @operation()
    def create_project(settings: dict, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Create one blank project from settings after validating model and UV.

        Replaces the observed document after validation; retains its recovery copy.
        Pixels start transparent; guides never become pixels. Model and UV are saved
        together and drive both the canvas partitions and 3D preview. base_boxes
        sets collision/selection geometry independently of visible elements.
        """
        return call("create_project", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @operation()
    def info() -> CommandResult:
        """Read shared session state. A desktop window is optional."""
        return call("status")

    def frontend_call(action, **payload):
        try:
            data = window.frontend.call(action, **payload)
            if action == "ui_capture" or payload.get("operation") == "capture":
                path = Path(payload["path"]).resolve()
                if Path(data["path"]).resolve() != path or path.suffix.lower() != ".png":
                    raise ValueError("Native capture receipt path mismatch")
                data["preview_path"] = str(path)
            return result(data)
        except (ValueError, OSError, KeyError, TypeError) as failure:
            return result({"error": str(failure), "code": getattr(failure, "code", "INVALID_ARGUMENT")}, True)

    @operation()
    def desktop_help() -> CommandResult:
        """Discover native C++ view/tool commands. A native window must already be open.

        Artwork editing remains available through every existing core tool without a GUI.
        """
        return frontend_call("ui_help")

    @operation()
    def desktop_state() -> CommandResult:
        """Read native window panel, tool, zoom, playback, revision and performance counters."""
        return frontend_call("ui_status")

    @operation()
    def desktop_scene_context() -> CommandResult:
        """Read native state entry values and particles in flight for numerical inspection."""
        return frontend_call("ui_scene_context")

    @operation()
    def desktop_controls() -> CommandResult:
        """Inspect native control labels, enabled/visible state and nine-point mouse hit tests.

        Offscreen form controls become reachable by scrolling; they are reported separately.
        """
        return frontend_call("ui_controls")

    @operation()
    def desktop_view(settings: dict) -> CommandResult:
        """Set native view/tool settings using desktop_help's exact schema.

        Supports panels, tools, RGBA, brush, zoom, pan, pixel grid, 3x3 tiling,
        onion skin, UV guides/pixel or region inspection, step/playing, model angles/overlays and layout. No artwork
        changes, approval, native mouse automation or export commands are exposed.
        """
        return frontend_call("ui_set", settings=settings)

    @operation()
    def desktop_capture(path: str, overwrite: bool = False) -> CommandResult:
        """Return an image of only PixForge's own client area for discussion.

        Requires an absolute PNG output path. Cannot overwrite a source artwork.
        This is a window preview, not a native-resolution production export.
        """
        return frontend_call("ui_capture", path=path, overwrite=overwrite)

    def draw_options(commands, expected_document_id, expected_revision, include_preview, scale, tile, backgrounds, frame_height):
        options = dict(commands=commands, expected_document_id=expected_document_id, expected_revision=expected_revision,
                       include_preview=include_preview, scale=scale, tile=tile)
        if backgrounds is not None:
            options["backgrounds"] = backgrounds
        if frame_height is not None:
            options["frame_height"] = frame_height
        return options

    @operation()
    def draw(commands: str, expected_document_id: str, expected_revision: int,
             include_preview: bool = True, scale: int = 6, tile: bool = False,
             backgrounds: list[str] | None = None, frame_height: int | None = None,
             label: str = "AI 修改") -> CommandResult:
        """Apply one atomic .px batch with one shared undo step to the observed version.

        First plan/create a model or explicit pixels project, then inspect its full layout.
        Use palette A=#rrggbbaa, grid/rle/patch, set, rect, clear, layer and read.
        End payload blocks with a blank line. Writes replace RGBA, including transparent '.'.
        new/load/render/save/undo/redo inside drawing batches are rejected; use their dedicated commands.
        save_project keeps drafts and export_current
        requires the actual human's approval of the currently shown pixels and timing.
        """
        return call("edit", label=label, **draw_options(commands, expected_document_id, expected_revision,
                    include_preview, scale, tile, backgrounds, frame_height))

    @operation()
    def validate(commands: str, expected_document_id: str, expected_revision: int,
                 include_preview: bool = True, scale: int = 6, tile: bool = False,
                 backgrounds: list[str] | None = None, frame_height: int | None = None) -> CommandResult:
        """Preview a batch on a clone; leave pixels, history and production files unchanged."""
        return call("validate", **draw_options(commands, expected_document_id, expected_revision,
                    include_preview, scale, tile, backgrounds, frame_height))

    @operation()
    def preview(scale: int = 6, tile: bool = False, backgrounds: list[str] | None = None,
                frame_height: int | None = None) -> CommandResult:
        """Read-only native/nearest discussion image. No approval or GUI needed."""
        options = dict(scale=scale, tile=tile)
        if backgrounds is not None:
            options["backgrounds"] = backgrounds
        if frame_height is not None:
            options["frame_height"] = frame_height
        return call("preview", **options)

    @operation()
    def preview_animation(scale: int = 6) -> CommandResult:
        """Return standalone lossless HTML and a timing report from current in-memory frames.

        The caller may display/save this discussion preview. No native PNG export, desktop
        or browser automation is needed. Declared playback does not prove in-game behavior.
        """
        return call("animation_preview", scale=scale)

    @operation()
    def read(x: int, y: int, w: int, h: int, raw: bool = False) -> CommandResult:
        """Read composite RGBA as a copyable palette/grid or raw patch fragment."""
        return call("read", x=x, y=y, w=w, h=h, raw=raw)

    @operation()
    def undo(expected_document_id: str, expected_revision: int) -> CommandResult:
        """Undo one shared edit; confirmation is invalidated."""
        return call("undo", expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def redo(expected_document_id: str, expected_revision: int) -> CommandResult:
        """Redo one shared edit."""
        return call("redo", expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def approve_export(user_request: str, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Quote the REAL HUMAN'S explicit approval of THIS shown version.

        AI self-checks, old notes and conditional future instructions are not approval.
        Chat confirmation works without a GUI. An unchanged approved version needs no second confirmation.
        """
        return call("approve", user_request=user_request, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def export_current(path: str, expected_document_id: str, expected_revision: int,
                       frame: int | None = None, overwrite: bool = False, scale: int = 1) -> CommandResult:
        """Export native PNG only while real human approval matches the current pixels and timing."""
        return call("export", path=path, frame=frame, overwrite=overwrite, scale=scale,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def save_project(path: str, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Save editable .pixforge work without exporting or claiming final approval."""
        return call("save", path=path, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def open_project(path: str, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Open a project, PNG or .px, preserving outgoing unsaved work in recovery."""
        return call("open", path=path, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def configure_animation(expected_document_id: str, expected_revision: int,
                            path: str | None = None, settings: dict | None = None) -> CommandResult:
        """Apply inline timing/rectangles or a definition file; specify exactly one of settings/path."""
        if (path is None) == (settings is None):
            return result({"error": "指定 settings 或 path 其中一项", "code": "INVALID_ARGUMENT"}, True)
        return call("animation", **({"path": path} if path is not None else {"settings": settings}),
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def configure_shapes(settings: dict, expected_document_id: str, expected_revision: int,
                         validate_only: bool = False) -> CommandResult:
        """Replace/validate shared base, collision and selection AABBs in 16-unit coordinates.

        collision/selection null inherit base; [] is an independent EMPTY override.
        Each box has id, from:[x,y,z], to:[x,y,z]. Embedded model is optional.
        Changes share undo/history, checkpoint and export approval with pixels/timing.
        """
        return call("shape_validate" if validate_only else "shapes", settings=settings,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def edit_shapes(operations: list[dict], expected_document_id: str, expected_revision: int) -> CommandResult:
        """Atomic shape operations: add/update/remove; mode inherit/copy/empty on overrides.

        Example: [{"op":"update","target":"base","id":"block","box":{"to":[16,8,16]}}].
        Edit inherited shapes by changing base or explicitly switching their mode first.
        """
        return call("shape_edit", operations=operations, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def import_block_model(model: dict | None, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Embed a resolved Java elements model for the current atlas; null clears it.

        Import does not guess collision shapes. Supports element rotation and UV rotation.
        Use one resolved texture atlas; unresolved parent-only or multi-texture models are rejected.
        """
        return call("model_import", model=model, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def preview_shapes(size: int = 400, yaw: float = 35, pitch: float = 30,
                       overlays: list[str] | None = None, include_html: bool = False,
                       frame: int | None = None, time_ms: float = 0, show_model: bool = True) -> CommandResult:
        """Read-only textured model and x-ray shape overlay, with optional interactive HTML.

        Overlays are base/collision/selection. Preview is independent of GUI and approval.
        PNG and HTML share camera and visibility. The HTML for a bound item
        also shows its actual Minecraft GUI transform alongside the orbit view.
        """
        return call("shape_preview", size=size, yaw=yaw, pitch=pitch,
                    overlays=overlays if overlays is not None else [], html=include_html,
                    time_ms=time_ms, show_model=show_model, **({"frame": frame} if frame is not None else {}))

    @operation()
    def build_shapes(expected_document_id: str, expected_revision: int, target: str = "base",
                     max_error: float = DEFAULT_BUILD_ERROR, target_boxes: int = DEFAULT_BUILD_TARGET_BOXES, symmetry: str = "auto",
                     dry_run: bool = False) -> CommandResult:
        """Explicitly reconstruct shapes from the original visual geometry.

        max_error is a Euclidean outward bound in model units (16 = 1 block).
        Never cuts into the source model. Auto symmetry preserves detected source symmetries.
        target_boxes is a search goal; error is not relaxed to meet it. Reports target_met.
        dry_run returns proposed_shapes/report without editing, history or approval changes.
        """
        return call("shape_build", target=target, max_error=max_error, target_boxes=target_boxes,
                    symmetry=symmetry, dry_run=dry_run, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def optimize_shapes(expected_document_id: str, expected_revision: int, target: str = "base",
                        max_error: float = 0, target_boxes: int = 1, symmetry: str = "auto",
                        dry_run: bool = False) -> CommandResult:
        """Optional lossless mode for existing boxes; max_error=0 preserves the exact occupied union.

        Positive max_error explicitly allows conservative outward approximation of the INPUT SHAPE.
        Use build_shapes to bound error against the original embedded model instead.
        Greedy maximal-cover search does not claim a globally minimal solution.
        """
        return call("shape_optimize", target=target, max_error=max_error, target_boxes=target_boxes,
                    symmetry=symmetry, dry_run=dry_run, expected_document_id=expected_document_id, expected_revision=expected_revision)


    @operation()
    def export_shapes(path: str, expected_document_id: str, expected_revision: int,
                      format: str = "json", class_name: str = "BlockShapes", package: str = "",
                      overwrite: bool = False) -> CommandResult:
        """Export current approved shapes as neutral JSON or Forge 1.20.1 Mojmap Java helper.

        Formats: json / forge-1.20.1. JSON preserves inheritance and empty overrides.
        Java helper needs a registered Block subclass; resource packs alone do not change physics.
        """
        return call("shape_export", path=path, format=format, class_name=class_name, package=package, overwrite=overwrite,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def open_workbench(timeout: float = 20) -> CommandResult:
        """Open or reuse this session's visible workbench; verify paths and exact content synchronization."""
        return perform(window.open, timeout)

    @operation()
    def wait_workbench(observed: dict, timeout: float = 20) -> CommandResult:
        """Wait for the observed document/revision/digest without replacing a stale token."""
        return perform(lambda: {"desktop": window.wait(window.observed(observed), window.deadline(timeout))})

    @operation()
    def present_workbench(observed: dict, path: str, panel: str = "pixels", timeout: float = 20) -> CommandResult:
        """Synchronize, frame and capture this exact revision. Return the PNG; inspect it for visual quality."""
        return perform(window.present, observed, path, panel, timeout)

    @operation()
    def close_workbench(expected_document_id: str, expected_revision: int, timeout: float = 20) -> CommandResult:
        """Close the synchronized workbench while retaining core history and editable recovery."""
        return perform(window.close, expected_document_id, expected_revision, timeout)

    @operation()
    def desktop_focus() -> CommandResult:
        """Bring this application's existing workbench to the foreground."""
        return frontend_call("focus")

    @operation()
    def desktop_metrics() -> CommandResult:
        """Read native rendering and interaction performance counters, not game FPS."""
        return frontend_call("ui_metrics")

    @operation()
    def desktop_sample_scene(time_ms: float | None = None, scene_state: str | None = None) -> CommandResult:
        """Sample native playback, including its current transition and live particles."""
        return frontend_call("ui_scene_sample", **{k: v for k, v in {"time_ms": time_ms, "scene_state": scene_state}.items() if v is not None})

    def editor(action, operation, name, value, path, overwrite):
        payload = {"operation": operation}
        if name is not None:
            payload["name"] = name
        if operation in ("configure", "camera"):
            if not isinstance(value, dict):
                return result({"error": "configure/camera 的 value 须为对象", "code": "INVALID_ARGUMENT"}, True)
            payload.update({"options": value} if operation == "configure" else value)
        elif operation == "paint":
            payload["operations"] = value
        elif operation == "field":
            payload["value"] = value
        elif value is not None:
            payload["value"] = value
        if path is not None:
            payload["path"] = str(Path(path).resolve())
        if overwrite:
            payload["overwrite"] = True
        return frontend_call(action, **payload)

    @operation()
    def editor_control(editor_kind: Literal["scene", "target", "preview", "regression", "material"],
                       operation: str, name: str | None = None, value: Any = None,
                       path: str | None = None, overwrite: bool = False) -> CommandResult:
        """Control a native editor. Read status for actions and editable_fields. scene/target: open/status/field/invoke/apply/cancel/capture; preview also configure/camera; regression omits apply; material also paint. Draft application checks its original revision and never grants export approval."""
        actions = {"scene": "ui_scene_editor", "target": "ui_minecraft_editor", "preview": "ui_minecraft_preview",
                   "regression": "ui_minecraft_workbench", "material": "ui_minecraft_material_editor"}
        return editor(actions[editor_kind], operation, name, value, path, overwrite)

    @operation()
    def edit_animation_frames(operation: str, step_index: int, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Add, duplicate or delete a source frame at a playback step. Preserves retained pixels/layers/timing; operation is add/duplicate/delete and one undo step."""
        return call("frame_edit", operation=operation, step_index=step_index,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def add_project_note(text: str, expected_document_id: str, expected_revision: int) -> CommandResult:
        """Record a project note on the observed document without inventing user feedback."""
        return call("note", text=text, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def create_recovery_copy(expected_document_id: str, expected_revision: int) -> CommandResult:
        """Preserve unsaved content in the application's recovery area; does not restore or replace the current document."""
        return call("recover", expected_document_id=expected_document_id, expected_revision=expected_revision)

    @operation()
    def shutdown_session(expected_document_id: str, expected_revision: int) -> CommandResult:
        """Persist and stop this core session. Close its workbench first; the command returns after persistence."""
        if window.frontend.alive():
            return result({"error": "先调用 close_workbench", "code": "DESKTOP_CONNECTED"}, True)
        return call("shutdown", expected_document_id=expected_document_id, expected_revision=expected_revision)

    def publish(data, preview_path, html_path, report_path, overwrite):
        from .standalone import publish_discussion
        current = session.call("status")
        data = publish_discussion(data, preview_path=preview_path, html_path=html_path, report_path=report_path,
            overwrite=overwrite, protected=[current.get("project_path"), current.get("source_path")])
        for key, path in (("preview_path", preview_path), ("html_path", html_path), ("report_path", report_path)):
            if path:
                data[key] = str(Path(path).resolve())
        return data

    @operation()
    def inspect_texture(path: str, options: dict | None = None, preview_path: str | None = None,
                        html_path: str | None = None, report_path: str | None = None, overwrite: bool = False) -> CommandResult:
        """Inspect an independent PNG without opening it as the current project. options: expect_size, opaque, binary_alpha, symmetry, symmetry_space, alpha_cutoff, region, clusters, max_isolated_pixels, compare, palette (RGBA array/path), preserve_mask, tile, match_edges, scale, backgrounds, display_size, frame_height OR animation_plan (object/path). Returns actual preview and all declared constraints; file outputs are discussion artifacts."""
        from .standalone import inspect_texture as inspect
        return perform(lambda: publish(inspect(path, options), preview_path, html_path, report_path, overwrite))

    @operation()
    def preview_texture_animation(plan: dict | str, scale: int = 6, html_path: str | None = None,
                                   report_path: str | None = None, overwrite: bool = False) -> CommandResult:
        """Build a lossless player from an independent PNG and explicit playback plan (inline object or file). Inline image paths resolve against workspace. Preserves frame order/duration; never retimes the current project."""
        from .standalone import preview_animation
        return perform(lambda: publish(preview_animation(plan, scale, workspace), None, html_path, report_path, overwrite))

    @operation()
    def run_offline_batch(commands: str, dry_run: bool = True, project_path: str | None = None,
                          scale: int = 6, tile: bool = False, backgrounds: list[str] | None = None,
                          overwrite: bool = False) -> CommandResult:
        """Execute an atomic independent .px draft, leaving the shared document unchanged. Dry-run returns a preview; commit requires a new .pixforge project_path. Batch output requests stay deferred. Open the saved draft and use the normal content-bound approval/export tools for production files."""
        from .standalone import offline_batch
        return perform(offline_batch, commands, workspace, dry_run=dry_run, project_path=project_path,
                       scale=scale, tile=tile, backgrounds=backgrounds, overwrite=overwrite)

    expected = {handler for group in CATALOG.values() for handler in group.values()}
    if set(handlers) != expected:
        raise ValueError("Command catalog does not match registered operations")

    def dispatch(topic, action, params):
        if topic not in CATALOG:
            return result({"error": "未知命令分组", "code": "UNKNOWN_ACTION"}, True)
        name = CATALOG[topic].get(action)
        if name is None:
            return result({"error": "未知操作", "code": "UNKNOWN_ACTION", "actions": list(CATALOG[topic])}, True)
        try:
            values = parameter_models[name].model_validate({} if params is None else params, strict=True)
        except ValidationError as failure:
            return result({"error": "操作参数无效", "code": "INVALID_ARGUMENT",
                           "issues": failure.errors(include_url=False, include_input=False)}, True)
        return handlers[name](**values.model_dump())

    def describe(name):
        text = inspect.getdoc(handlers[name]) or ""
        labels = {handler: group + " " + action for group, actions in CATALOG.items() for action, handler in actions.items()}
        labels.update({"scene_editor": "workbench editor --editor-kind scene",
            "minecraft_target_editor": "workbench editor --editor-kind target",
            "minecraft_preview_editor": "workbench editor --editor-kind preview",
            "minecraft_regression_workbench": "workbench editor --editor-kind regression",
            "minecraft_material_editor": "workbench editor --editor-kind material"})
        for old in sorted(labels, key=len, reverse=True):
            if "_" in old:
                text = re.sub(r"\b" + re.escape(old) + r"\b", labels[old], text)
        return text

    return {"dispatch": dispatch, "describe": describe, "models": parameter_models, "handlers": handlers}
