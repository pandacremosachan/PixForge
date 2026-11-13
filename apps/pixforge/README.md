# PixForge 4.12.1

双击 PixForge 后，按作品选择入口。做方块、家具或机器，选**「方块」**：选六面共用或六面分别绘制后，在「材质」画贴图，点「模型」即可调整方块、添加部件，再切回「材质」继续画。两个视图共用同一份工程。「物品贴图」从透明画布起步；**「三维建模 → 角色建模」**直接从玩家骨架开始。

「打开已有文件…」可打开工程、模型或贴图；有上次工程时也可以直接继续。编辑中再次双击 EXE 或按 **Ctrl+N**（「文件 → 新建工程…」），都会回到任务选择页。点「继续当前工程」即可回到原来的编辑位置。双击工程文件则直接打开该文件。

在方块的「模型」页，右侧「模型显示」可开关「材质模型」「基础形状」「碰撞框」「选中框」。打开「碰撞框」显示粉红色线框；关闭「材质模型」可以单看它。未单独设置碰撞时，它继承基础形状，新方块默认为一整个方块。

在材质画布上，鼠标指针跟随左侧当前工具。画笔和取色管以尖端定位；形状和选区以十字中心定位。空格临时平移，Alt 临时取色，松开后回到当前工具。

笔宽和不透明度可以单击输入，按住数值向左或向右拖动，也可以点击右侧上下箭头微调。笔宽从 1 px 到当前帧短边，不透明度为 0–100%；Enter 确认，Esc 取消输入。

画布尺寸和编辑器选择框使用同一套深色菜单。鼠标移入时背景提亮；可用方向键浏览、Enter 确定、Esc 取消。

点击左下角的 **宽 × 高 px** 可以切换画布分辨率，或选「自定义宽高…」。所有图层使用最近邻缩放；动画按每帧调整并保留时序，Ctrl+Z 可撤销。原版玩家皮肤固定为 64 × 64。

**部件建模：** 在模型视图里 Shift / Ctrl 点选一组方块，按共同中心或各自支点调整大小、旋转和支点。打开「逐面 UV」，点表面后拖贴图上的框或角，左侧模型实时更新。需要精确数值时用侧栏「输入数值…」。操作作用于静止模型，原动作保留。

**骨骼角色工作台：** 打开 Bedrock `.bbmodel`，在模型页点选部件，选择动作、时间、通道和轴，左拖调整姿势；右拖转视角。曲线节点可拖动时间与数值，支持线性、阶跃、Catmull–Rom 和贝塞尔。贴图下拉可查看不同外观；「更多」可添加 PNG、绑定到所选面或修改贝塞尔手柄。编辑命令见 `model inspect-rig` 和 `model edit-rig`。

**Windows x64 便携版：** 将 ZIP 完整解压到可写目录，打开 `PixForge` 文件夹，双击 `PixForgeNative.exe`。程序从自身所在目录加载 `backend` 和资源，无需安装 Python、Codex 或 MCP，也不要求固定盘符。换电脑时复制整个 `PixForge` 文件夹，不能只复制 EXE。

本地更新沿用同一个 `PixForge` 文件夹和同名便携包。更新后仍用原来的 EXE 或快捷方式，`workspace` 中的工程和恢复记录保留。

后台使用时，从解压目录运行 `.\PixForgeNative.exe serve --workspace "<工程目录>"`。调用方使用新电脑本次启动生成的 `<工程目录>/.runtime/pixelforge-desktop/commands.json`。要带走作品，先保存 `.pixforge` 工程，并一同复制工程引用的外部素材。

材质页将画板、绘图工具、工程调色板和图层并列显示，网格、平铺和 UV 可直接切换。模型页可独立开关模型、基础形状、碰撞框和选中框，通过预设视角或滑块旋转。动画工程另有播放条。

PixForge is an independent Windows application for pixels, model UVs, shapes, texture animation, part motion, particles and state editing. One PixForgeNative.exe provides both the C++20/Win32/OpenGL workbench and grouped commands. Both use the same project, undo history, recovery and content approval model. The application has no dependency on a skill installation.

## Commands and workbench

For automation, start `PixForgeNative.exe serve --workspace W --runtime R` once in the background. When ready, the EXE publishes `R/commands.json`. Send commands to that loopback HTTP endpoint from the calling application; keep the connection details for the session. All requests use the same running EXE. `workbench open` displays its native window; closing the window keeps the project available. [PUBLIC_API.md](PUBLIC_API.md) includes a PowerShell example, command discovery and the response contract.

Running the EXE without a subcommand still opens the desktop. The one-shot CLI remains available for existing scripts; `--version --json` and `project info` do not start a project.

The seven command groups are project, canvas, model, animation, minecraft, workbench and asset. They retain 66 actions, including native window lifecycle, five editors, source-frame operations, independent PNG/animation checks, atomic drafts, shape construction, LabPBR and Minecraft resources.

Use --workspace and --runtime to reuse the same session. Parameters accept command flags, UTF-8 input files or a JSON request file. Commands return JSON with ok/error codes and preview_path/html_path, with nonzero exit codes on failure. Help is on demand and normal use does not require reading implementation files. No global runtime installation, external client or tool registration is required.

## 骨骼玩家模型

在「文件 → 骨骼玩家模型」新建角色，或打开单图集 Bedrock Entity `.bbmodel`。在模型页选择骨骼、添加子骨骼和方块；编辑起止位置、旋转、支点、UV 或关键帧。材质页与模型共用一张图集。播放条可选待机、行走等工程动作。工程可另存为带内嵌图集的 Blockbench 文件，或导出有第三人称主模型、第一人称手臂、动作和贴图的 YSM spec 2 ZIP。该模式与原版 64×64 皮肤独立；当前使用单 PNG、方块骨架和数值线性/阶跃动画。

## Desktop and project data

For Minecraft player skins, choose **文件 → 玩家皮肤** and select Classic (4-pixel arm) or Slim (3-pixel arm) for the 64×64 PNG. **材质 → 面域** identifies each face by body part, base or clothing layer, and the wearer's direction. **模型 → 皮肤外层** toggles each of the six pieces of clothing without erasing any pixels. Use **文件 → 导出 PNG** at the original size and choose the same arm type in the Minecraft Launcher. Saving a .pixforge project retains the editable layers and model. [Minecraft skin guide](https://www.minecraft.net/en-us/article/what-is-minecraft-skin)

The main window is a texture and model viewer. Drag to pan or orbit, scroll to zoom, and use Fit to frame the work. Animated projects have a compact player. Tools, brush controls, the project palette and layers sit beside the canvas. The model panel has independent visibility switches, camera presets and orbit sliders. Model construction, frame authoring, resource exports and specialist editors remain available by command.

workbench open starts or reuses the visible window. workbench wait/present validates an observed document/revision/digest and captures actual discussion images. Closing the window retains the core. Existing .pixforge files, history and recovery remain compatible. Formal exports use current content-bound human consent and fresh resource fingerprints; editable saves and discussion previews require no export approval.

The built-in Minecraft target is Java 1.20.1 / Forge. Resource resolution, render previews, runtime code generation, animation metadata, performance census and LabPBR byte maps belong to the application. Offline results never imply game validation.
