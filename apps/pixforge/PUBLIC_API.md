# PixForge public interfaces

PixForge is an independently installed application. Keep its EXE, `application.json` and private `backend` together. Skills and external clients use its public interfaces; they do not import application modules or modify internal session files. Public transport/schema major version remains 1.

## Discovery and commands

`PixForgeNative.exe --describe` returns the application version, public API version, capabilities and supported interfaces. `application.json` provides the same installation declaration. Clients reject unsupported API major versions before mutation.

`PixForgeNative.exe --cli <arguments...>` forwards arguments, stdin, UTF-8 stdout/stderr and exit status to the application CLI. Groups include `session`, `ui`, `gui`, `run`, `preview` and `animation-preview`. Discover parameters with `--cli --help`, `--cli session --help`, or `--cli ui --runtime <directory> help`.

`PixForgeNative.exe --mcp --workspace <project> --runtime <session>` exposes stdio MCP. Initialize, discover tools and read `info`. Closing MCP leaves the shared core available. MCP dependencies belong to the application, not its external skill.

## Host-independent integration

Any host that can execute a process can use the CLI; any standard MCP stdio host can use the MCP endpoint. Neither transport depends on Codex, skill discovery directories, host-specific tool prefixes or prompt syntax. A companion skill is optional guidance, not an application dependency. `agents/openai.yaml` in a companion package is optional host metadata and is never consumed by PixForge.

CLI commands use separate argv values, UTF-8 JSON results and nonzero failure exit codes. MCP returns JSON in text content and optional PNG image content; clients must inspect `isError`. Session status is a top-level state object; most operations return it in `state`. Resource checks return `validation.passed` and `validation.validation_digest`. Export approval advances revision, so use its returned state for subsequent exports. Never silently refresh a stale write token and retry a mutation over concurrent human edits.

The distributed native desktop is Windows x64. Host independence does not make that executable native to other operating systems. A remote or cross-system host needs an already configured compatible process/MCP bridge. Paths after the application boundary refer to the software host, including workspace, runtime, input files and output previews; the caller needs an explicit file channel or an inline payload such as MCP `draw.commands`. The authenticated loopback endpoint is local, not an unauthenticated remote service.

## Shared editing

Read the current `document_id`, `revision`, layers, frame layout and capabilities before editing. Mutations submit the observed document/revision tokens; conflicts require a fresh read. Manual strokes temporarily block competing writes. CLI, MCP and the C++ desktop share one document, undo/redo, recovery and export approval.

Drawing, model import, shapes, texture timing and part/particle scenes execute directly through their dedicated operations. `project_plan` / MCP `plan_project` optionally previews dimensions and UV layout. `create_project` validates settings and creates the project without a plan receipt. `model_uv` reads actual face mappings; it does not authorize or gate drawing.

`animation_prepare` / CLI `animation-prepare` / MCP `prepare_animation_frames` accepts `frame_count` and optional `frame_size`, `steps`, `loop`, `interpolation`. It retains existing pixels/layers, copies the first source frame into added slots, remaps data-material planes and adds one undo step. Existing manual frame insertion, duplication and deletion use the same packing code. Part/particle animation uses `scene_animation` / MCP `configure_scene_animation`; existing keyframes, states, event transitions and previews are preserved.

Previews and editable project saves do not require approval. Formal PNG, shape and Minecraft exports require real user consent bound to the current content. Changed content invalidates that approval. Resource exports also validate current dependency fingerprints. These checks are independent of procedural stage registries or visual-review receipts.

## Local transport

The authenticated loopback service publishes `runtime/session.json` with `url`, `token`, `session_id`, process and mode. Read `/health`; send JSON such as `{"action":"status"}` to `/api` with `X-PixForge-Session`. Mutations include `expected_document_id` and `expected_revision` alongside operation fields. The service rejects browser-origin requests. Do not log tokens or edit discovery/checkpoint files.

The native view publishes `runtime/gui/session.json`. Its `ui_help` documents view controls, client-area captures and model/animation/material editors. View operations do not approve exports. Closing the native window leaves the core session available.

## Optional Minecraft tools

Capability discovery advertises `minecraft-assets/v1`, `forge-runtime/v1`, `minecraft-preview/v1`, `minecraft-animation/v1`, `minecraft-regression/v1` and `minecraft-material/v1`. Configure targets and inspect real source graphs before export. Detailed settings and supported semantics are documented in [MINECRAFT_ASSETS.md](MINECRAFT_ASSETS.md), [FORGE_RUNTIME.md](FORGE_RUNTIME.md), [MINECRAFT_PREVIEW.md](MINECRAFT_PREVIEW.md), [MINECRAFT_RUNTIME_WORKBENCH.md](MINECRAFT_RUNTIME_WORKBENCH.md) and [MINECRAFT_MATERIAL_DATA.md](MINECRAFT_MATERIAL_DATA.md).

## Independent updates

Software and companion skills are packaged and updated separately. Preserve user workspaces and external projects during application updates. Replacing a skill does not change the application or its runtime. Saved project formats, history and content-bound export approval remain supported.
