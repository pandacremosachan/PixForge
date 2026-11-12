# PixForge 4.2.3

**Windows x64 便携版：** 将 ZIP 完整解压到可写目录，打开 `PixForge` 文件夹，双击 `PixForgeNative.exe`。程序从自身所在目录加载 `backend` 和资源，无需安装 Python、Codex 或 MCP，也不要求固定盘符。换电脑时复制整个 `PixForge` 文件夹，不能只复制 EXE。

后台使用时，从解压目录运行 `.\PixForgeNative.exe serve --workspace "<工程目录>"`。调用方使用新电脑本次启动生成的 `<工程目录>/.runtime/pixelforge-desktop/commands.json`。要带走作品，先保存 `.pixforge` 工程，并一同复制工程引用的外部素材。

材质页将画板、绘图工具、工程调色板和图层并列显示，网格、平铺和 UV 可直接切换。模型页可独立开关模型、基础形状、碰撞框和选中框，通过预设视角或滑块旋转。动画工程另有播放条。

PixForge is an independent Windows application for pixels, model UVs, shapes, texture animation, part motion, particles and state editing. One PixForgeNative.exe provides both the C++20/Win32/OpenGL workbench and grouped commands. Both use the same project, undo history, recovery and content approval model. The application has no dependency on a skill installation.

## Commands and workbench

For automation, start `PixForgeNative.exe serve --workspace W --runtime R` once in the background. When ready, the EXE publishes `R/commands.json`. Send commands to that loopback HTTP endpoint from the calling application; keep the connection details for the session. All requests use the same running EXE. `workbench open` displays its native window; closing the window keeps the project available. [PUBLIC_API.md](PUBLIC_API.md) includes a PowerShell example, command discovery and the response contract.

Running the EXE without a subcommand still opens the desktop. The one-shot CLI remains available for existing scripts; `--version --json` and `project info` do not start a project.

The seven command groups are project, canvas, model, animation, minecraft, workbench and asset. They retain 64 validated actions, including native window lifecycle, five editors, source-frame operations, independent PNG/animation checks, atomic drafts, shape construction, LabPBR and Minecraft resources.

Use --workspace and --runtime to reuse the same session. Parameters accept command flags, UTF-8 input files or a JSON request file. Commands return JSON with ok/error codes and preview_path/html_path, with nonzero exit codes on failure. Help is on demand and normal use does not require reading implementation files. No global runtime installation, external client or tool registration is required.

## Desktop and project data

The main window is a texture and model viewer. Drag to pan or orbit, scroll to zoom, and use Fit to frame the work. Animated projects have a compact player. Tools, brush controls, the project palette and layers sit beside the canvas. The model panel has independent visibility switches, camera presets and orbit sliders. Model construction, frame authoring, resource exports and specialist editors remain available by command.

workbench open starts or reuses the visible window. workbench wait/present validates an observed document/revision/digest and captures actual discussion images. Closing the window retains the core. Existing .pixforge files, history and recovery remain compatible. Formal exports use current content-bound human consent and fresh resource fingerprints; editable saves and discussion previews require no export approval.

The built-in Minecraft target is Java 1.20.1 / Forge. Resource resolution, render previews, runtime code generation, animation metadata, performance census and LabPBR byte maps belong to the application. Offline results never imply game validation.
