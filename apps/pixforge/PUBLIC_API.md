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

Seven groups expose 64 actions: project, canvas, model, animation, minecraft, workbench and asset. Top-level help lists groups; group help lists its actions; action help lists only that action's parameters. --json returns an exact params_schema. Help, version and project info do not start or mutate a session.

Command flags use kebab-case; JSON keys use snake_case. Each parameter supports --NAME-file: strings are read as UTF-8 text, other values as JSON. - reads stdin; only one input may consume stdin. --request-file reads a full parameter object (or stdin with -); --request-json accepts an inline object. Duplicate, unexpected and invalid fields are rejected. Boolean flags accept true/false, with a flag alone meaning true. --workspace/--runtime/--json/--result-file may appear before or after the command.

Execution returns a single UTF-8 JSON object with ok. A write requires observed expected_document_id/expected_revision and normally returns the next state. Conflicts require understanding intervening changes, without automatic token refresh/retry. --result-file also saves the response to a new file and rejects an existing output before executing the operation.

Images and HTML players are materialized to new discussion files under R/previews and returned as preview_path/html_path. Window presentation also returns capture and desktop receipts for the exact revision. The caller must inspect the actual files. No base64 image is printed into command output. Formal production files remain guarded by asset approve and asset export-png/export-shapes/export-minecraft.

## Shared workbench

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
