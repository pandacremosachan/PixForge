"""MCP adapter for the independent session shared with CLI and optional GUI."""
import json
from .shape_builder import DEFAULT_BUILD_ERROR, DEFAULT_BUILD_TARGET_BOXES


def register(mcp, session):
    from mcp.types import CallToolResult, ImageContent, TextContent

    def call(action, **payload):
        try:
            data, error = session.call(action, **payload), False
        except (ValueError, OSError, KeyError, TypeError) as failure:
            data, error = {"error": str(failure), "code": getattr(failure, "code", "INVALID_ARGUMENT"),
                           "details": getattr(failure, "details", None)}, True
        if isinstance(data.get("validation"), dict) and not data["validation"].get("passed", False):
            error = True
        image = data.pop("image", None)
        content = [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]
        if image:
            content.append(ImageContent(type="image", mimeType="image/png", data=image))
        return CallToolResult(content=content, isError=error)


    @mcp.tool()
    def animation_capabilities() -> CallToolResult:
        """Discover texture/parts/particles mechanisms and the default Forge 1.20.1 target.

        Mechanisms compose on one scene clock. Static work remains the default. Custom
        shaders and skeletal animation are not implemented; previews are offline.
        """
        return call("animation_capabilities")

    @mcp.tool()
    def minecraft_capabilities() -> CallToolResult:
        """Discover exact Minecraft target profiles, supported source types and export limits."""
        return call("minecraft_capabilities")

    @mcp.tool()
    def configure_minecraft_target(settings: dict | None, expected_document_id: str,
                                   expected_revision: int) -> CallToolResult:
        """Apply an undoable application-owned target/source/binding configuration; null clears it.

        Current target: forge-1.20.1. Sources are ordered low to high and have role project
        (selected closure may be exported) or dependency (check only; never redistributed).
        The current canvas binding is optional. Old projects remain unchanged until applied.
        """
        return call("minecraft_configure", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @mcp.tool()
    def check_minecraft_resources(settings: dict | None = None, use_document: bool = True,
                                  include_generated_code: bool = False) -> CallToolResult:
        """Read-only reference graph, actual source winners, target format and export fingerprint.

        Optional settings validates a draft without applying it. use_document=False inspects
        source entries alone. This does not prove in-game rendering or registry coverage.
        include_generated_code=True includes read-only generated Forge Java/build/source
        previews, so code can be inspected before user approval or formal export.
        """
        return call("minecraft_check", settings=settings, use_document=use_document,
                    include_generated_code=include_generated_code)

    @mcp.tool()
    def inspect_minecraft_material(role: str = 'normal', channel: str = 'r', view: str = 'channel',
                                   pixel: list[int] | None = None, resource: str | None = None,
                                   settings: dict | None = None, time_ms: float | None = None, max_size: int = 1024) -> CallToolResult:
        """Read LabPBR 1.3 data channels as opaque data, not layer opacity. Inspect raw/decoded values, normal validity, shader feature declarations and source fingerprints. Optional resource reads real _n/_s sources. No game shader is run."""
        return call('minecraft_material',role=role,channel=channel,view=view,pixel=pixel,resource=resource,settings=settings,time_ms=time_ms,max_size=max_size)

    @mcp.tool()
    def configure_minecraft_material(settings: dict | None, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Configure optional LabPBR 1.3 maps and a versioned shader target as one undo step; null clears data maps. Color layers remain unchanged. Uses project format v4, requiring software 2.7+."""
        return call('minecraft_material_configure',settings=settings,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @mcp.tool()
    def import_minecraft_material(role: str, expected_document_id: str, expected_revision: int,
                                  path: str | None = None, resource: str | None = None, channel: str | None = None) -> CallToolResult:
        """Import exact 8-bit PNG data into normal/specular, or one channel from a mask's red component. Dimensions must match the atlas. Explicit project-owned resource sources may be imported; dependencies are read-only. Requires inspected UV/layout and adds one undo step."""
        return call('minecraft_material_import',role=role,path=path,resource=resource,channel=channel,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @mcp.tool()
    def edit_minecraft_material(role: str, channel: str, operations: list[dict], expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Write 0..255 raw values to one LabPBR channel using rect:[x,y,width,height], value operations. Other channels, hidden RGB, albedo and dimensions stay byte-exact. Requires inspected layout; entire batch is atomic and one undo step. Formal export uses existing resource approval/fingerprint checks."""
        return call('minecraft_material_edit',role=role,channel=channel,operations=operations,expected_document_id=expected_document_id,expected_revision=expected_revision)

    @mcp.tool()
    def inspect_minecraft_animation(metadata: dict | None = None, time_ms: float = 0) -> CallToolResult:
        """Read .mcmeta width/height, frame sequence, tick durations and RGB interpolation; return a source-pixel sample without changing the project."""
        return call("minecraft_animation", metadata=metadata, time_ms=time_ms)

    @mcp.tool()
    def configure_minecraft_animation(metadata: dict, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Apply .mcmeta to the current PNG canvas and configured target as one undoable change. The atlas clock is shared; machine activation belongs to an instance player."""
        return call("minecraft_animation_apply", metadata=metadata, expected_document_id=expected_document_id, expected_revision=expected_revision)


    @mcp.tool()
    def inspect_minecraft_performance(options: dict | None = None) -> CallToolResult:
        """Read whole-scene frame pixels, raw mip memory, layers, dynamic parts, sampled particles and 1..4096 instance scenarios. Optional coverage_view measures a controlled reference viewport, never game FPS."""
        return call("minecraft_performance", options=options)

    @mcp.tool()
    def compare_minecraft_regression(baseline: str, candidate: str, budgets: dict | None = None) -> CallToolResult:
        """Compare actual game capture directories with hashed PNG/log attachments, fixed camera/options/phase checks, pixel deltas and CPU/frame-interval budgets. Does not launch or modify a game."""
        return call("minecraft_regression_compare", baseline=baseline, candidate=candidate, budgets=budgets)

    @mcp.tool()
    def inspect_minecraft_scene(options: dict | None = None, settings: dict | None = None,
                                include_pixels: bool = False) -> CallToolResult:
        """Resolve a read-only Forge 1.20.1 scene from actual resources or the current document.

        Returns model/state cases, source fingerprints, per-face texel density, separate
        block/item tints, Forge face-light data and standard render-layer rules.
        options.subject selects document/model/blockstate/texture. context selects
        block/gui/ground/fixed/head/firstperson_*hand/thirdperson_*hand. include_pixels
        adds actual RGBA data for application rendering. No project or approval changes.
        """
        return call("minecraft_scene", options=options, settings=settings, include_pixels=include_pixels)

    @mcp.tool()
    def preview_minecraft_scene(options: dict | None = None, settings: dict | None = None,
                                batch: bool = False, contexts: list[str] | None = None,
                                case_offset: int = 0, case_limit: int = 16) -> CallToolResult:
        """Return a discussion PNG with mipmaps, alpha/depth, tint and controlled lighting.

        batch compares declared states, weighted alternatives and requested item contexts,
        at most 16 images per page; follow report.next_case_offset for remaining cases.
        Uses actual source pixels. This is a reference preview, not live game validation,
        formal asset export, visual approval or permission to modify the project.
        """
        return call("minecraft_preview", options=options, settings=settings, batch=batch,
                    contexts=contexts, case_offset=case_offset, case_limit=case_limit)

    @mcp.tool()
    def export_minecraft_resources(path: str, validation_digest: str, expected_document_id: str,
                                    expected_revision: int, format: str = "resource-pack",
                                    overwrite: bool = False) -> CallToolResult:
        """Publish a Forge 1.20.1 ZIP after current evidence and real user approval.

        resource-pack/mod-assets export static assets. forge-integration exports application-
        generated Java and resources; forge-mod adds a buildable standalone example entry
        and registries. All formats rescan dependencies/code and reject stale fingerprints.
        No consuming source tree or game installation is modified, and no game is launched.
        """
        return call("minecraft_export", path=path, validation_digest=validation_digest, format=format,
                    overwrite=overwrite, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @mcp.tool()
    def sample_scene(time_ms: float = 0, scene_state: str | None = None, scene_view: dict | None = None) -> CallToolResult:
        """Read a process, canonical named state, or captured native playback context; no mutation."""
        return call("scene_sample", time_ms=time_ms, scene_state=scene_state, scene_view=scene_view)

    @mcp.tool()
    def validate_scene_animation(settings: dict) -> CallToolResult:
        """Validate a generic keyframe/state draft against the current model and texture; no mutation."""
        return call("scene_validate", settings=settings)


    @mcp.tool()
    def model_uv(frame: int | None = None, x: int | None = None, y: int | None = None) -> CallToolResult:
        """Read actual model face names, local directions, UV rotation/mirroring and shared regions.

        Optional x/y are atlas pixel coordinates in the selected frame, matching draw/read.
        Returns ALL faces sampling that texel, including partial overlaps. No model means
        no guessed cube mapping. Read this before editing a particular face of an atlas.
        This read-only query does not change pixels, history or approval.
        """
        return call("model_uv", **{k: v for k, v in dict(frame=frame, x=x, y=y).items() if v is not None})

    @mcp.tool()
    def prepare_animation_frames(settings: dict, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Retain existing cels/layers and add frames/timing in one undo step. Settings: frame_count, optional frame_size/steps/loop/interpolation. Part and particle motion uses configure_scene_animation."""
        return call("animation_prepare", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @mcp.tool()
    def configure_scene_animation(settings: dict | None, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Apply or clear part motion, particles, keyframes and named states in one shared undo step."""
        return call("scene_animation", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @mcp.tool()
    def plan_project(settings: dict | None = None) -> CallToolResult:
        """Plan model-first creation without changing artwork; return dimensions and UV.

        preset: cube_faces (default, separate 3x2 faces), cube_shared, model or pixels.
        Built-in cubes accept face_size (default 16). model accepts a resolved Java
        model object and optional width/height; its UV/rotation/sharing is preserved.
        pixels accepts width/height for an explicitly model-free canvas.
        """
        return call("project_plan", settings=settings)

    @mcp.tool()
    def create_project(settings: dict, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Create one blank project from settings after validating model and UV.

        Replaces the observed document after validation; retains its recovery copy.
        Pixels start transparent; guides never become pixels. Model and UV are saved
        together and drive both the canvas partitions and 3D preview. No export.
        """
        return call("create_project", settings=settings, expected_document_id=expected_document_id,
                    expected_revision=expected_revision)

    @mcp.tool()
    def info() -> CallToolResult:
        """Read shared session state. A desktop window is optional."""
        return call("status")

    def frontend_call(action, **payload):
        from .native_cli import call_frontend
        import base64
        from pathlib import Path
        runtime = getattr(session, "runtime", None)
        if runtime is None and hasattr(session, "document"):
            runtime = session.document.runtime
        try:
            data = call_frontend(action, runtime=runtime, **payload)
            content = [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]
            if action == "ui_capture":
                path = Path(payload["path"]).resolve()
                if Path(data["path"]).resolve() != path or path.suffix.lower() != ".png":
                    raise ValueError("Native capture receipt path mismatch")
                content.append(ImageContent(type="image", mimeType="image/png",
                                            data=base64.b64encode(path.read_bytes()).decode("ascii")))
            return CallToolResult(content=content, isError=False)
        except (ValueError, OSError, KeyError, TypeError) as failure:
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(
                {"error": str(failure), "code": getattr(failure, "code", "INVALID_ARGUMENT")}, ensure_ascii=False))], isError=True)

    @mcp.tool()
    def desktop_help() -> CallToolResult:
        """Discover native C++ view/tool commands. A native window must already be open.

        Artwork editing remains available through every existing core tool without a GUI.
        """
        return frontend_call("ui_help")

    @mcp.tool()
    def desktop_state() -> CallToolResult:
        """Read native window panel, tool, zoom, playback, revision and performance counters."""
        return frontend_call("ui_status")

    @mcp.tool()
    def desktop_scene_context() -> CallToolResult:
        """Read native state entry values and particles in flight for numerical inspection."""
        return frontend_call("ui_scene_context")

    @mcp.tool()
    def desktop_controls() -> CallToolResult:
        """Inspect native control labels, enabled/visible state and nine-point mouse hit tests.

        Offscreen form controls become reachable by scrolling; they are reported separately.
        """
        return frontend_call("ui_controls")

    @mcp.tool()
    def desktop_view(settings: dict) -> CallToolResult:
        """Set native view/tool settings using desktop_help's exact schema.

        Supports panels, tools, RGBA, brush, zoom, pan, pixel grid, 3x3 tiling,
        onion skin, UV guides/pixel or region inspection, step/playing, model angles/overlays and layout. No artwork
        changes, approval, native mouse automation or export commands are exposed.
        """
        return frontend_call("ui_set", settings=settings)

    @mcp.tool()
    def desktop_capture(path: str, overwrite: bool = False) -> CallToolResult:
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

    @mcp.tool()
    def draw(commands: str, expected_document_id: str, expected_revision: int,
             include_preview: bool = True, scale: int = 6, tile: bool = False,
             backgrounds: list[str] | None = None, frame_height: int | None = None,
             label: str = "AI 修改") -> CallToolResult:
        """Apply one atomic .px batch with one shared undo step to the observed version.

        First plan/create a model or explicit pixels project, then inspect its full layout.
        Use palette A=#rrggbbaa, grid/rle/patch, set, rect, clear, layer and read.
        End payload blocks with a blank line. Writes replace RGBA, including transparent '.'.
        new/load/render/save/undo/redo inside scripts are rejected; use their dedicated session tools.
        save_project keeps drafts and export_current
        requires the actual human's approval of the currently shown pixels and timing.
        """
        return call("edit", label=label, **draw_options(commands, expected_document_id, expected_revision,
                    include_preview, scale, tile, backgrounds, frame_height))

    @mcp.tool()
    def validate(commands: str, expected_document_id: str, expected_revision: int,
                 include_preview: bool = True, scale: int = 6, tile: bool = False,
                 backgrounds: list[str] | None = None, frame_height: int | None = None) -> CallToolResult:
        """Preview a batch on a clone; leave pixels, history and production files unchanged."""
        return call("validate", **draw_options(commands, expected_document_id, expected_revision,
                    include_preview, scale, tile, backgrounds, frame_height))

    @mcp.tool()
    def preview(scale: int = 6, tile: bool = False, backgrounds: list[str] | None = None,
                frame_height: int | None = None) -> CallToolResult:
        """Read-only native/nearest discussion image. No approval or GUI needed."""
        options = dict(scale=scale, tile=tile)
        if backgrounds is not None:
            options["backgrounds"] = backgrounds
        if frame_height is not None:
            options["frame_height"] = frame_height
        return call("preview", **options)

    @mcp.tool()
    def preview_animation(scale: int = 6) -> CallToolResult:
        """Return standalone lossless HTML and a timing report from current in-memory frames.

        The caller may display/save this discussion preview. No native PNG export, desktop
        or browser automation is needed. Declared playback does not prove in-game behavior.
        """
        return call("animation_preview", scale=scale)

    @mcp.tool()
    def read(x: int, y: int, w: int, h: int, raw: bool = False) -> CallToolResult:
        """Read composite RGBA as a copyable palette/grid or raw patch fragment."""
        return call("read", x=x, y=y, w=w, h=h, raw=raw)

    @mcp.tool()
    def undo(expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Undo one shared edit; confirmation is invalidated."""
        return call("undo", expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def redo(expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Redo one shared edit."""
        return call("redo", expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def approve_export(user_request: str, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Quote the REAL HUMAN'S explicit approval of THIS shown version.

        AI self-checks, old notes and conditional future instructions are not approval.
        Chat confirmation works without a GUI. An unchanged approved version needs no second confirmation.
        """
        return call("approve", user_request=user_request, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def export_current(path: str, expected_document_id: str, expected_revision: int,
                       frame: int | None = None, overwrite: bool = False) -> CallToolResult:
        """Export native PNG only while real human approval matches the current pixels and timing."""
        return call("export", path=path, frame=frame, overwrite=overwrite,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def render(path: str, expected_document_id: str, expected_revision: int,
               scale: int = 1, overwrite: bool = False) -> CallToolResult:
        """Compatibility export name; uses the SAME human confirmation check."""
        return call("export", path=path, scale=scale, overwrite=overwrite,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def save_project(path: str, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Save editable .pixforge work without exporting or claiming final approval."""
        return call("save", path=path, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def open_project(path: str, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Open a project, PNG or .px, preserving outgoing unsaved work in recovery."""
        return call("open", path=path, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def configure_animation(path: str, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Load explicit timing/rectangles for current pixels, with no early PNG export."""
        return call("animation", path=path, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def configure_shapes(settings: dict, expected_document_id: str, expected_revision: int,
                         validate_only: bool = False) -> CallToolResult:
        """Replace/validate shared base, collision and selection AABBs in 16-unit coordinates.

        collision/selection null inherit base; [] is an independent EMPTY override.
        Each box has id, from:[x,y,z], to:[x,y,z]. Embedded model is optional.
        Changes share undo/history, checkpoint and export approval with pixels/timing.
        """
        return call("shape_validate" if validate_only else "shapes", settings=settings,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def edit_shapes(operations: list[dict], expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Atomic shape operations: add/update/remove; mode inherit/copy/empty on overrides.

        Example: [{"op":"update","target":"base","id":"block","box":{"to":[16,8,16]}}].
        Edit inherited shapes by changing base or explicitly switching their mode first.
        """
        return call("shape_edit", operations=operations, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def import_block_model(model: dict | None, expected_document_id: str, expected_revision: int) -> CallToolResult:
        """Embed a resolved Java elements model for the current atlas; null clears it.

        Import does not guess collision shapes. Supports element rotation and UV rotation.
        Use one resolved texture atlas; unresolved parent-only or multi-texture models are rejected.
        """
        return call("model_import", model=model, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def preview_shapes(size: int = 400, yaw: float = 35, pitch: float = 30,
                       overlays: list[str] | None = None, include_html: bool = False) -> CallToolResult:
        """Read-only textured model and x-ray shape overlay, with optional interactive HTML.

        Overlays are base/collision/selection. Preview is independent of GUI and approval.
        HTML contains lossless frames, playback, orbit, views and separate shape toggles.
        """
        return call("shape_preview", size=size, yaw=yaw, pitch=pitch,
                    overlays=overlays if overlays is not None else ["collision"], html=include_html)

    @mcp.tool()
    def build_shapes(expected_document_id: str, expected_revision: int, target: str = "base",
                     max_error: float = DEFAULT_BUILD_ERROR, target_boxes: int = DEFAULT_BUILD_TARGET_BOXES, symmetry: str = "auto",
                     dry_run: bool = False) -> CallToolResult:
        """Default way to create new shapes: conservative reconstruction of the original model.

        max_error is a Euclidean outward bound in model units (16 = 1 block).
        Never cuts into the source model. Auto symmetry preserves detected source symmetries.
        target_boxes is a search goal; error is not relaxed to meet it. Reports target_met.
        dry_run returns proposed_shapes/report without editing, history or approval changes.
        """
        return call("shape_build", target=target, max_error=max_error, target_boxes=target_boxes,
                    symmetry=symmetry, dry_run=dry_run, expected_document_id=expected_document_id, expected_revision=expected_revision)

    @mcp.tool()
    def optimize_shapes(expected_document_id: str, expected_revision: int, target: str = "base",
                        max_error: float = 0, target_boxes: int = 1, symmetry: str = "auto",
                        dry_run: bool = False) -> CallToolResult:
        """Optional lossless mode for existing boxes; max_error=0 preserves the exact occupied union.

        Positive max_error explicitly allows conservative outward approximation of the INPUT SHAPE.
        Use build_shapes to bound error against the original embedded model instead.
        Greedy maximal-cover search does not claim a globally minimal solution.
        """
        return call("shape_optimize", target=target, max_error=max_error, target_boxes=target_boxes,
                    symmetry=symmetry, dry_run=dry_run, expected_document_id=expected_document_id, expected_revision=expected_revision)


    @mcp.tool()
    def export_shapes(path: str, expected_document_id: str, expected_revision: int,
                      format: str = "json", class_name: str = "BlockShapes", package: str = "",
                      overwrite: bool = False) -> CallToolResult:
        """Export current approved shapes as neutral JSON or Forge 1.20.1 Mojmap Java helper.

        Formats: json / forge-1.20.1. JSON preserves inheritance and empty overrides.
        Java helper needs a registered Block subclass; resource packs alone do not change physics.
        """
        return call("shape_export", path=path, format=format, class_name=class_name, package=package, overwrite=overwrite,
                    expected_document_id=expected_document_id, expected_revision=expected_revision)


def main(*, workspace=None, runtime=None) -> int:
    try:
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:
        from mcp.server.fastmcp import FastMCP as Server
    from .service import ensure_session
    client = ensure_session(workspace, runtime)
    mcp = Server("pixelforge", instructions="Read info for current document_id/revision before edits. Drawing, models, frames and scenes share the desktop history. Use model_uv for actual face mapping and the preview tools to inspect results. Mutations require current tokens. Formal exports require explicit human approval of the current content; saving editable projects does not.")
    register(mcp, client)
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
