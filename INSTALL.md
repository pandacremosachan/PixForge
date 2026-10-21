# Agent installation guide

Use this guide when the user asks you to install and configure the PixForge companion skill. Follow the user's installation scope and the target project's existing rules. Complete routine setup within that scope; ask only for missing information or a conflicting existing installation that you cannot resolve from the environment.

The skill is `pixelforge` **1.8.0**, with **PixForge 2.9.0 / public API 1** as its application baseline. The skill and application are separate packages. This guide does not start an artwork task.

## 1. Obtain the repository

Reuse an existing local checkout of `https://github.com/pandacremosachan/PixForge` when available. Otherwise, clone that repository into a new directory using the environment's existing authenticated Git access. Read this file from the resulting checkout and resolve its relative links there.

For a private repository, a public URL fetch may return 404 even when the user is signed in to a browser. Use the agent's existing authorized GitHub connection or Git credentials; do not put credentials in URLs or configuration files. If no authorized reader is available, report that repository access is required and stop setup at that point.

Record the checked-out commit. Read [SKILL.md](.agents/skills/pixelforge/SKILL.md), [connection.md](.agents/skills/pixelforge/references/connection.md) and [operations.md](.agents/skills/pixelforge/references/operations.md). The application source is not needed for installation.

## 2. Register the complete skill

The installable directory is **`.agents/skills/pixelforge/`**, not the repository root or just `SKILL.md`. Keep its `scripts/`, `references/`, `assets/` and other packaged files together under the name `pixelforge`.

Use the harness's supported skill discovery or registration mechanism. Determine the destination from the user's requested scope, the existing skill setup or the harness's current documentation. Reuse an authoritative local skill directory when present; if the harness supports links or registered paths, point it there. Otherwise, install the complete directory into the supported skill location. Preserve an existing installation's local edits and resolve a conflicting destination before replacing it.

The source repository's `.agents/skills/` layout is not a requirement for every harness. `agents/openai.yaml` is optional metadata; it is not needed to run the client or workflows. A harness without native skills can explicitly load `SKILL.md` and the referenced workflow files using its supported instruction mechanism. Report that mode accurately. If the harness requires a reload or new session to discover a skill, state that requirement.

## 3. Locate or install the independent application

Reuse an existing compatible application. The client accepts `--app`, `--config`, `PIXFORGE_APP`, `PIXFORGE_CONNECTION` or a native launcher on PATH; exact precedence is in [connection.md](.agents/skills/pixelforge/references/connection.md). An explicit connection error must be resolved before choosing another connection.

If the application is missing on Windows x64, download **`PixForge-Cpp-Windows-x64.zip`** from [v2.9.0](https://github.com/pandacremosachan/PixForge/releases/tag/v2.9.0) through authorized access. Verify its SHA-256 against [RELEASE_SHA256.txt](RELEASE_SHA256.txt), then extract the complete `PixForge-Cpp` folder to the user's chosen or established local application location. Keep `PixForgeNative.exe`, `application.json`, the backend and all companion files together. The source ZIP and skill ZIP do not replace the application package.

On Linux, macOS, WSL or a remote harness, use an existing compatible launcher or MCP bridge to a software host. The Windows package is not a native binary for those environments. If no such connection exists, finish the available skill registration and report application connection as pending. Do not invent a bridge or claim the workbench is ready.

The application bundle supplies its own runtime. Direct EXE CLI/MCP requires no separately installed Python. The optional skill client and template helper use an existing Python **3.10+**, with only the standard library. Do not install global runtimes or third-party Python packages for this setup.

## 4. Configure one supported transport

For a harness that can execute processes, use the public CLI. With an existing Python, a connection file outside the skill directory can contain:

```json
{"application":"C:/Tools/PixForge-Cpp/PixForgeNative.exe"}
```

Replace that example with the real absolute application path. Pass `--config <connection-file>` before the client command, or persist `PIXFORGE_CONNECTION` through the harness's supported environment settings. A variable set in one subprocess alone is not a persistent installation. An existing launcher can instead use the documented `command` argument array.

For a harness with MCP stdio, register this process description in its native MCP configuration:

```json
{
  "command":"C:/Tools/PixForge-Cpp/PixForgeNative.exe",
  "args":["--mcp","--workspace","C:/Project","--runtime","C:/Project/.runtime/pixforge"]
}
```

Replace all example paths with the actual software, target project and runtime paths. Preserve the harness's configuration format and other servers; the top-level key is not assumed to be `mcpServers`. For a remote bridge, workspace/runtime and input/output paths belong to the software host. This direct MCP mode does not require the Python client.

Use the transport supported by the current harness. A text-only environment can read the skill and supply setup instructions, but cannot verify application execution.

## 5. Verify with read-only application queries

For a harness that can execute processes, run the real application with `--describe` and capture its JSON output. For example, this is an argument array, not shell syntax:

```json
["C:/Tools/PixForge-Cpp/PixForgeNative.exe","--describe"]
```

Require `schema` equal to `pixforge.application/v1`, integer `public_api_version` equal to `1`, and `interfaces` containing `cli` and `mcp-stdio`. For a local executable, check the adjacent `application.json` against the same schema and API version.

An MCP-only harness can use the public description supplied by the existing software-host setup and verify the MCP connection below. State which metadata checks were performed directly and which came from that setup. If application/API compatibility cannot be established, report that check as pending.

If using the optional Python client, run the following after replacing every placeholder and using the existing Python executable:

```text
python <skill-dir>/scripts/pixforge_client.py --config <connection-file> doctor
python <skill-dir>/scripts/scaffold.py --list
```

`doctor` must actually return `connected: true` and the compatible application description. `--list` must return the nine template recipes. With direct CLI/MCP and no Python, read [workflows.json](.agents/skills/pixelforge/assets/workflows.json) instead of installing Python for the template check. For MCP, also perform the standard initialization, list tools and call `info`, checking the returned content for errors.

Verify native skill discovery when the harness exposes it; otherwise confirm the explicit instruction-loading path. File existence alone is not proof that a harness has loaded the skill or that the application is connected. Setup verification must not create, open, redraw, save, approve or export user artwork, or start a game.

## 6. Report the actual result

Give the user the skill version and installed path, source commit, loading mode, application version/API and path or launcher, configuration location, chosen transport and the verification results. Distinguish completed skill registration, a reload still needed, and a connection that remains pending. Include one concrete next action for each unresolved prerequisite.

After successful setup, load the workflow for the user's next task from [SKILL.md](.agents/skills/pixelforge/SKILL.md). Installation does not authorize content approval or formal asset export; those follow the normal workbench contract and the user's actual task authorization.
