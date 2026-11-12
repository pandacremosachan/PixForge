# PixForge 4.1.1

**Windows x64 便携版：** 将 ZIP 完整解压到可写目录，打开 `PixForge` 文件夹，双击 `PixForgeNative.exe`。程序从自身所在目录加载 `backend` 和资源，无需安装 Python、Codex 或 MCP，也不要求固定盘符。换电脑时复制整个 `PixForge` 文件夹，不能只复制 EXE。

后台使用时，从解压目录运行 `.\PixForgeNative.exe serve --workspace "<工程目录>"`。调用方使用新电脑本次启动生成的 `<工程目录>/.runtime/pixelforge-desktop/commands.json`。要带走作品，先保存 `.pixforge` 工程，并一同复制工程引用的外部素材。

PixForge is an independent Windows application for pixels, model UVs, shapes, texture animation, part motion, particles and state editing. One PixForgeNative.exe provides both the C++20/Win32/OpenGL workbench and grouped commands. Both use the same project, undo history, recovery and content approval model. The application has no dependency on a skill installation.

## Commands and workbench

For automation, start `PixForgeNative.exe serve --workspace W --runtime R` once in the background. When ready, the EXE publishes `R/commands.json`. Send commands to that loopback HTTP endpoint from the calling application; keep the connection details for the session. All requests use the same running EXE. `workbench open` displays its native window; closing the window keeps the project available. [PUBLIC_API.md](PUBLIC_API.md) includes a PowerShell example, command discovery and the response contract.

Running the EXE without a subcommand still opens the desktop. The one-shot CLI remains available for existing scripts; `--version --json` and `project info` do not start a project.

The seven command groups are project, canvas, model, animation, minecraft, workbench and asset. They retain 64 validated actions, including native window lifecycle, five editors, source-frame operations, independent PNG/animation checks, atomic drafts, shape construction, LabPBR and Minecraft resources.

Use --workspace and --runtime to reuse the same session. Parameters accept command flags, UTF-8 input files or a JSON request file. Commands return JSON with ok/error codes and preview_path/html_path, with nonzero exit codes on failure. Help is on demand and normal use does not require reading implementation files. No global runtime installation, external client or tool registration is required.

## Desktop and project data

The native desktop supports model-first creation, RGBA layers, selection/move and clipboard, UV inspection, source-frame editing, real playback timing and textured 3D. GPU geometry/texture caching is shared across interaction frames; software rendering is available when OpenGL is unavailable. Stable scene bounds cover articulated models without changing authored geometry or gameplay bounds.

workbench open starts or reuses the visible window. workbench wait/present validates an observed document/revision/digest and captures actual discussion images. Closing the window retains the core. Existing .pixforge files, history and recovery remain compatible. Formal exports use current content-bound human consent and fresh resource fingerprints; editable saves and discussion previews require no export approval.

The built-in Minecraft target is Java 1.20.1 / Forge. Resource resolution, render previews, runtime code generation, animation metadata, performance census and LabPBR byte maps belong to the application. Offline results never imply game validation.
