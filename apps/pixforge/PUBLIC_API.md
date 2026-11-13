# PixForge commands, contract 4

The resident PixForgeNative.exe owns command definitions, validation and JSON results. Start it once per workspace/session; the calling application sends requests without launching a process per command.

## Resident interface

Start `PixForgeNative.exe serve --workspace W --runtime R` as a background process. Without `--runtime` the session is `W/.runtime/pixelforge-desktop`. Once the project is ready, the program atomically publishes `R/commands.json` and prints a readiness line with its PID and the file path. A second caller uses the same descriptor. It contains the authenticated loopback endpoint, session ID, workspace and owning EXE PID; keep its token local. After a restart, read the new descriptor. A normal `project shutdown` removes it.

From PowerShell 7, once the host is ready (palette keys are case-sensitive):

```powershell
$c = Get-Content -LiteralPath (Join-Path $runtime 'commands.json') -Raw -Encoding utf8 | ConvertFrom-Json
$headers = @{ 'X-PixForge-Session' = $c.token }
$http = Invoke-WebRequest -Method Post -Uri $c.url -Headers $headers -ContentType 'application/json; charset=utf-8' -Body '{"group":"project","command":"state","params":{}}'
$state = $http.Content | ConvertFrom-Json -AsHashtable
```

`POST /v1/commands` accepts exactly `group`, `command` and optional `params` (an object using the published parameter names). The endpoint is bound to its workspace/runtime. `GET /v1/commands` lists the groups, `GET /v1/commands/canvas` lists canvas actions and `GET /v1/commands/canvas/draw` returns its parameter schema. Use the same header for all requests. POST returns the existing command result with `ok`, including domain failures (HTTP 200, `ok:false`). Invalid envelopes, authentication or routes return an HTTP error. Use the returned revision before the next write; previews return file paths. The optional workbench opens in the resident process; closing it leaves the service running.

## One-shot CLI

Existing scripts may still invoke a command as a process. Running the EXE without a subcommand opens the workbench.

```text
PixForgeNative.exe --version --json
PixForgeNative.exe --help
PixForgeNative.exe canvas --help
PixForgeNative.exe canvas draw --help --json
PixForgeNative.exe project state --workspace W --runtime R --result-file observed.json
PixForgeNative.exe canvas draw --workspace W --runtime R --commands-file draw.px --expected-document-id ID --expected-revision 12
PixForgeNative.exe workbench present --workspace W --runtime R --observed-file observed.json --path discussion.png
```

## Discovery and parameters

The command groups are: project, canvas, model, animation, minecraft, workbench and asset. Top-level help lists groups; group help lists its actions; action help lists only that action's parameters. --json returns an exact params_schema. Help, version and project info do not start or mutate a session.

Command flags use kebab-case; JSON keys use snake_case. Each parameter supports --NAME-file: strings are read as UTF-8 text, other values as JSON. - reads stdin; only one input may consume stdin. --request-file reads a full parameter object (or stdin with -); --request-json accepts an inline object. Duplicate, unexpected and invalid fields are rejected. Boolean flags accept true/false, with a flag alone meaning true. --workspace/--runtime/--json/--result-file may appear before or after the command.

Execution returns a single UTF-8 JSON object with ok. A write requires observed expected_document_id/expected_revision and normally returns the next state. Conflicts require understanding intervening changes, without automatic token refresh/retry. --result-file also saves the response to a new file and rejects an existing output before executing the operation.

Images and HTML players are materialized to new discussion files under R/previews and returned as preview_path/html_path. Window presentation also returns capture and desktop receipts for the exact revision. The caller must inspect the actual files. No base64 image is printed into command output. Formal production files remain guarded by asset approve and asset export-png/export-shapes/export-minecraft.

## Rigged players

Use `project create` settings `{"preset":"player_rig","name":"player","texture_size":[128,128]}` or supply a complete `rig`. The source model is returned in `state.shapes.model.player_rig`. `model edit-rig` updates bones, cubes, UVs and transform keys in one shared undo step. Numeric three-axis rotations are in degrees, key times in milliseconds; rest coordinates are Blockbench coordinates (+Y up, -Z forward). The skeletal viewport samples the active clip directly. Clips and hidden parts remain in the editable project; local transforms propagate to descendants. Select the visible joint using `workbench view` settings `rig_bone` and optionally `rig_cube`; the current selection is reported in `workbench state`.

`model inspect-rig` lists textures, bones, cube IDs and every clip; pass `clip` and optionally `bone` for original keyframes. Use `model edit-rig` with key UUIDs, axis/axis_value, time_ms, interpolation and Bézier handle arrays to adjust only the intended values. add_texture, texture and face_texture manage image sources and per-face assignments. `workbench view` supports scene_state, time_ms, rig_bone/rig_cube, rig_channel, rig_axis, rig_texture and rig_curve. `model preview` and `animation sample` use the same native pose evaluator as the viewport.

`project open` reads multi-image Bedrock cube projects and retains original clip, effect and expression data; `asset export-rig` writes an editable `.bbmodel` or a YSM spec 2 `.zip` (third-person main, arm subtrees and atlas, plus named animations when present). Separate Java block/shape exports and standard PNG skins keep their existing formats.

`rig-component-edit/v1`: select cube UUIDs with `workbench view` (`rig_mode:"model"`, `rig_cubes`, optional `rig_uv_editor`, `rig_face`, `rig_link_faces`). `model inspect-rig {cube_ids:[...]}` returns the original per-face endpoints, binding UUID, rotation and bind geometry. `model edit-rig` supports `transform_cubes {cube_ids, scale, rotation, anchor, pivot_delta|pivot}` and `face_uv {cube_ids, face, offset|delta|uv, rotation?, flip?}`. Center and pivot coordinates are in bind-pose model space; group placement uses model axes and cube dimensions use their local axes. The GUI submits these same atomic operations. UV endpoints follow each texture’s own UV size, including reversed edges.

## Shared workbench

The `minecraft-player-skin/v1` capability adds a project preset: pass
`{"preset":"player_skin","arm_model":"slim"}` as `project create` settings.
`classic` is the default. Both use a 64×64 atlas with opaque base faces,
a transparent outer layer and a matching 12-part model. To edit a skin PNG,
use `project open` with `path` and `arm_model`; it separates the original base
and outer pixels. `model uv`, `canvas draw`, `model preview`, `project save`
and `asset export-png` work on the same document. The native File menu exposes
both arm choices for creation and import.

For this preset, `project plan` and `model uv` include `uv_map.player_skin`.
On the wearer's body, `parts.body.outer.faces.back` is `[32,36,8,12]` (x, y, width, height).
The coordinate origin is top-left; right and bottom bounds are exclusive. For a point
query, `uv_map.point.faces[].skin` gives its part, layer, face, rectangle and name.
The 2D skin inspector uses those same addresses and leaves unmapped padding unlabelled.

In `model preview`, pass `hidden_skin_overlays:["jacket"]` to preview the base under
the jacket; omit it or pass `[]` to show everything. The same list is a `workbench view`
setting and is reported by `workbench state`. Valid clothing switches are `hat`,
`jacket`, `right_sleeve`, `left_sleeve`, `right_pants` and `left_pants`.
These are view settings; they never alter the PNG, editable layers or revision.

The workspace defaults to the calling directory; the session defaults to W/.runtime/pixelforge-desktop unless --runtime is specified. Commands connect to the same existing project as the workbench, rather than recreating it. workbench open/wait/present/close manages the window. Five native editors use workbench editor with --editor-kind and --operation; discover actions and editable_fields from status. Applying a draft validates its original revision and adds shared undo history. Closing the window keeps the core available; project shutdown persists and stops it after the window is closed.

Existing project/history formats, undo, recovery and content consent semantics remain compatible. A saved editable project or discussion preview requires no publication consent. Formal export requires actual human consent bound to the shown content; Minecraft exports rescan resource/code fingerprints. Approval advances revision, so subsequent export uses its returned state.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Operation or declared constraint failed |
| 2 | Invalid command, parameter or input |
| 3 | Document/revision conflict |
| 4 | Output already exists |
| 5 | Busy or timeout |
| 6 | Missing approval or stale export evidence |
| 7 | Session/window unavailable |

Read code/error/details/issues and validation reports, not just the exit code. A timeout after submission does not prove that a write failed; reread state before deciding how to proceed.

The native application is Windows x64. The built-in Minecraft target is Java 1.20.1 / Forge. Capabilities retain minecraft-assets/v1, forge-runtime/v1, minecraft-preview/v1, minecraft-animation/v1, minecraft-regression/v1 and minecraft-material/v1. Offline previews and generated code do not establish game behavior.

Detailed contracts: [resources](MINECRAFT_ASSETS.md), [Forge integration](FORGE_RUNTIME.md), [render preview](MINECRAFT_PREVIEW.md), [animation and regression](MINECRAFT_RUNTIME_WORKBENCH.md), [LabPBR](MINECRAFT_MATERIAL_DATA.md).

`canvas resize --width W --height H` changes the pixel dimensions of each frame using nearest-neighbor sampling. Supply the observed document ID and revision as for `canvas draw`. It preserves layers and playback steps and can be undone in one step. Width and height are 1–4096; the resulting atlas must also fit within 4096 pixels per side. Built-in vanilla player skins retain their required 64 × 64 layout.

On the pixel canvas, the workbench state field `canvas_cursor` reports `pen`, `eraser`, `fill`, `picker`, `line`, `rect`, `ellipse`, `select`, `move`, `grab` or `grabbing`, including temporary Alt/Space overrides. It reports `default` on the model panel.

Workbench view accepts an integer `brush_size` from 1 px through the shorter side of the current source frame (not the full animation atlas). Workbench state exposes this interval as `brush_size_range`. Opacity is a number from 0 to 100 percent; a 0% paint stroke leaves pixels and history unchanged. Resizing or switching to a smaller frame clamps the current brush width.

An interactive launch without a file shows the task chooser, including when the window is already editing a document. Selecting Continue returns to that document. While the chooser is visible, workbench state reports `panel: "start"` and `start_task: "block" | "item" | "model"`. `workbench view` or `workbench present` with an explicit pixels/shapes panel returns to the editor. Opening a document directly and opening a fresh window via the workbench command still go straight to the document.

The Block card creates an editable cube with `cube_shared` (one face tile) or `cube_faces` (a 3 × 2 sheet). Paint in the pixels panel and edit the same parts in the shapes panel with `model inspect-rig` / `model edit-rig`. Both mappings retain Java block coordinates 0..16 and respect `face_size`. Item Texture uses `pixels`. Character Modeling is the only 3D modeling card and always uses `player_rig`. The command-only `component_model` preset remains available for existing scripts with a 64 × 64 atlas.

Editable block models display the same `base`, `collision` and `selection` overlays in the workbench and in `model preview`. These boxes are in block coordinates and stay fixed as the camera or posed parts move. When collision or selection inherits the base, its switch displays the base boxes in that overlay's color. Set `show_model: false` to see only the enabled boxes.
