# PixForge 2.9.0

PixForge is a standalone Windows creative application for pixels, model UVs, shapes, texture animation, part motion, particles and keyframe/state editing. Its C++20/Win32/OpenGL desktop and private Python core share one project, history, recovery and export approval model. The application has no dependency on a skill, agent host or skill installation directory.

Version 2.8 removes the connected-material/structure workspace, adjacency rules and CTM export adapters. The workspace retains pixels and model/shapes, together with the existing scene, particle and material tools.

Version 2.7 adds the native LabPBR 1.3 data-material editor and `minecraft-material/v1` CLI/MCP capability. Normal/AO/height and smoothness/F0/porosity/SSS/emission planes retain raw bytes independently of color/opacity. The same texture, animation and Forge pipelines derive paired sidecars and enforce explicit shader contracts. See [MINECRAFT_MATERIAL_DATA.md](MINECRAFT_MATERIAL_DATA.md); `examples/forge-labpbr-1.20.1` provides an original project and optional owned diagnostic shader.

Version 2.4.2 fixed a native window hang after visiting the model panel in a model-free project. Heading painting and animation draft creation now read optional model data without changing it. Surface callbacks contain input and painting exceptions, release mouse capture after a failed action, and report the error in the status bar. Menu commands use the same synchronized action dispatch as toolbar buttons.

Preview camera framing supports articulated models. Preview bounds propagate spheres through joint transforms instead of repeatedly enclosing rotation spheres in boxes. Native GPU/software previews and portable HTML use the same stable view envelope; project dimensions, animation data and gameplay/export bounds are unchanged.

## Portable application

Keep `PixForgeNative.exe`, `application.json` and `backend/` together. Double-click the executable or the included launcher. The private core starts automatically; no global Python, Qt or C++ installation is required. Project defaults live in `workspace/`; explicit `--workspace` and `--runtime` select other locations. Existing `.pixforge` files remain compatible.

The public executable is also the integration boundary:

```powershell
.\PixForgeNative.exe --describe
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge status
.\PixForgeNative.exe --cli gui --workspace D:\Project --runtime D:\Project\.runtime\pixforge
.\PixForgeNative.exe --mcp --workspace D:\Project --runtime D:\Project\.runtime\pixforge
```

See [PUBLIC_API.md](PUBLIC_API.md). Skill instructions and their standard-library client are a separately versioned and distributed product. Application users do not need that package; external clients do not import application modules.

## Minecraft resources

The **资源** menu and public CLI/MCP provide optional target configuration, asset reference graphs and versioned exports. The first adapter targets Forge / Minecraft Java 1.20.1 (resource-pack format 15). Directory/ZIP/JAR sources have explicit precedence and project/dependency roles; diagnostics trace model inheritance, texture aliases, state/item references, metadata and generated-sprite inputs. Export checks source fingerprints again and preserves native pixels. See [MINECRAFT_ASSETS.md](MINECRAFT_ASSETS.md) for configuration, capabilities and actual limits.

The portable **打开Minecraft资源示例.cmd** launcher opens the original synthetic [target example](examples/forge-1.20.1/README.md), with a saved target and no machine-specific resource paths.

Old unconfigured projects keep their existing format and content. Configured projects use v2 metadata, readable by PixForge 2.3+; older applications reject it instead of losing the new target settings on save. Core API v1 integrations continue to work, with `minecraft-assets/v1` advertising the additive feature.

## Forge parts and particles

The `forge-runtime/v1` adapter exports actual Forge 1.20.1 Java 17 source and resources. BERs preserve the current element/UV/state program; client particle providers retain birth poses, gravity, color/size curves and alpha/additive blending. Runtime code has explicit common/client boundaries and server-state/snapshot hooks.

Use **打开Forge模组接入示例.cmd** for the original combined example. The resource dialog derives an undoable runtime draft and exposes read-only generated-source previews. `forge-integration` is a mergeable source/resource archive; `forge-mod` adds the standalone example registries, entry point and pinned ForgeGradle build. No target mod source tree or game installation is changed. See [FORGE_RUNTIME.md](FORGE_RUNTIME.md) for exact bindings, public operations, real project hooks and budgets.

Runtime projects use desktop/v3 and require 2.4+; prior projects retain their existing schema until explicitly configured. Public API major version 1 and all existing export formats remain available.

## Development

This folder is the application's single source. Use an existing Python 3.12 environment with the dependencies declared in `scripts/pyproject.toml`, or prepare a local environment through the project's normal package manager. With existing Visual Studio C++ Build Tools:

```powershell
.\scripts\build-native.ps1 -PythonExecutable <private-python.exe>
<private-python.exe> .\scripts\app_entry.py --help
<private-python.exe> .\scripts\package_native.py --binary <PixForgeNative.exe> --output <new-portable-folder>
```

The build writes an adjacent `pixforge-development.json` pointing to this application's `scripts/app_entry.py` and the selected private environment. That file is for development only and is excluded from portable releases. CMake also generates a development descriptor; set `PIXFORGE_PYTHON` to the chosen private executable. No development path is compiled into the executable, and no skill directory is searched.

This source delivery does not add a license to pre-existing user source. Preserve [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), dependency metadata and runtime licenses. Private artwork, credentials, sessions and runtime caches are excluded from releases.

## Forge 1.20.1 rendering preview (2.5)

The resource menu now includes a read-only native model/rendering preview with mipmap and transparency controls, resolved model/state/display contexts, separate tints and controlled lighting/AO. CLI/MCP expose the same scenes and paged comparison images through `minecraft-preview/v1`. See [MINECRAFT_PREVIEW.md](MINECRAFT_PREVIEW.md). Software and skill remain independently installed and versioned; existing project formats, history and export approvals are preserved.

PixForge 2.6 adds `minecraft-animation/v1` and `minecraft-regression/v1` through the standalone application. The native resource workbench reads/applies .mcmeta timing, configures actual per-BE instance lifecycle, counts whole-scene resources, and generates opt-in Forge game fixture/capture code. See [MINECRAFT_RUNTIME_WORKBENCH.md](MINECRAFT_RUNTIME_WORKBENCH.md) for public CLI/MCP examples, exact target versions, independent package boundaries and verification scope. Existing interfaces and unconfigured projects remain supported.
