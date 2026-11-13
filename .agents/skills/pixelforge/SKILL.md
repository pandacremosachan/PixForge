---
name: pixelforge
description: 用 PixForge 制作 Minecraft 原版 PNG 皮肤、支持部件多选、逐面 UV、多贴图和动画曲线的 Blockbench / YSM 骨骼模型、方块与物品材质、GUI、像素画、可放置模型与碰撞形状，以及像素和部件动画。
---

# PixForge

[放置目录](INSTALL.md)决定此技能仅对当前项目可用，还是对当前用户的所有 Codex 项目可用。

AI 通过命令绘制材质，用户在工作台查看同一份作品。材质页直接显示画板、绘图工具、调色板和图层；模型页直接显示视角和各形状的开关。有动画时出现播放条。

工作台和命令由同一个常驻 `PixForgeNative.exe` 提供。优先通过目标工程的 `R/commands.json` 复用用户正在用的会话。继续桌面作品时，以该桌面的 workspace/runtime 为准；无参数打开便携版的工作区位于 EXE 旁的 `workspace`。尚无目标会话时，用项目指定的固定安装或技能自带的 `runtime/windows-x64/PixForgeNative.exe` 启动一次 `serve`。后续通过宿主的 HTTP 客户端向同一实例发送命令。

启动时指定消费项目 `--workspace W` 和已有会话 `--runtime R`。下文的 `project state` 等命令名表示发给该会话的 `group` 和 `command`。按需用 `project info` 核对平台与能力，或读取对应动作的 HTTP 帮助查询参数。

将草稿 JSON 或绘图文本读入请求的 `params`，检查返回的 `ok` 并通过返回的文件路径实际看图。连接、帮助和参数示例见 [命令入口](references/command-line.md)，实际流程见 [操作约定](references/operations.md)。

## 默认流程

1. 确认消费项目的尺寸、风格、资源 ID、模型/UV 和输出位置；已有作品沿用原 workspace/runtime。
2. 用 `workbench open` 打开或复用同一窗口，随后读取 `project state`；已有工程不重新创建。
3. 读取真实素材和 UV，先画主体与材料层次，再补细节；新设计先自查代表样。模板图案仅作示例。
4. 将相关笔画合为一个 `canvas draw` 原子批次，后续操作沿用响应的 `state`。只需确认窗口同步时用 `workbench wait`；进入展示时直接用下一步的 `workbench present`。
5. 用 `workbench present` 提交 observed、path 和 panel，由程序完成同步与截图。实际查看返回的 PNG，核对原尺寸、放大图及适用的真实模型，修正问题后交用户评议。
6. 在同一工程中按意见修改并重新展示；沿用对当前内容有效的用户授权，通过对应导出命令交付原生资源。

保存工程和讨论预览无需批准。窗口空白、旧版、缺模型或无法看图时，检查实际状态并处理问题。只读检查可省略窗口；用户明确要求无界面时跳过窗口步骤。环境不能显示窗口时说明限制并保留草稿，不自行改成后台制作流程。

## 操作边界

- 写入携带已观察到的 `expected_document_id/expected_revision`，继续使用响应的 `state`；冲突后理解新改动，不刷新令牌盲目重试。
- `canvas draw` 只放绘图命令。PNG 通过 `project open` 或数据材质导入命令处理，不经剪贴板传图。
- `grid/rle/patch` 的 `.` 覆盖为透明；`canvas read` 返回可见层合成结果。叠画、半透明和镜像见 [像素协议](references/protocol.md)。
- 正式输出保持原生尺寸，遵循消费项目的资源/datagen 边界。默认不启动游戏、安装运行时或修改存档。

## 选择流程

新建时按作品选择工程预设，直接调用 `project plan` 或 `project create`。方块在同一工程中绘制贴图、添加和修改三维部件；三维建模入口专用于骨骼角色。[启动页与预设对照](references/desktop.md#启动页与工程预设)

| 任务 | 流程 | 模板 |
|---|---|---|
| 方块（画材质、改外形、搭部件） | [方块](references/workflows/block.md) · [部件建模与逐面 UV](references/workflows/rig-components.md) | block-shared / block-faces |
| 平面物品、工具 | [物品](references/workflows/item.md) | item |
| Java 原版玩家皮肤（新绘、改装 PNG、定位六面或预览服装开关） | [官方格式与工作流](references/workflows/player-skin.md) | player-skin/classic 或 player-skin/slim |
| 骨骼玩家模型（多选变换、逐面 UV、多贴图、姿势与曲线、Blockbench、YSM） | [骨骼建模与导出](references/workflows/player-rig.md) | player-rig |
| 3D 物品（手持、物品栏） | [三维物品](references/workflows/item.md#三维物品) | item/project-3d.json + item/target.json |
| 修改已有材质 | [替换材质](references/workflows/replace-texture.md) | 真实源文件 |
| 可放置模型、碰撞、选中框 | [模型与形状](references/workflows/model-shapes.md) | custom-model |
| 纹理逐帧动画 | [材质动画](references/workflows/texture-animation.md) | texture-animation |
| 部件运动、状态、粒子 | [场景动画](references/workflows/scene-animation.md) | scene-states / particles |
| GUI、独立像素画 | [GUI](references/workflows/gui.md) | gui |
| LabPBR 数据通道 | [LabPBR](references/workflows/labpbr.md) | labpbr |

读取 `assets/workflows.json` 和对应模板，将项目尺寸、资源 ID、模型及图案替换为实际值，再通过命令的文件参数传入。模板文件本身不构成软件依赖。

## 按需参考

- 设计：[视觉验收](references/design-review.md)、[平铺材质](references/textures.md)、[图标](references/icons.md)、[对称](references/symmetry.md)、[成套制作](references/upstream-workflows.md)。
- 命令：[分组与输入](references/session.md)、[工作台](references/desktop.md)、[离线事务](references/transactions-review.md)、[效率](references/performance.md)。
- Minecraft：[资源与导出](references/minecraft-assets.md)、[资源机制](references/game-assets.md)、[模型预览](references/minecraft-preview.md)、[静态注册](references/forge-static.md)、[运行时接入](references/forge-runtime.md)。
- 动态与数据：[播放定义](references/animation-review.md)、[场景协议](references/scene-animation.md)、[游戏回归](references/runtime-678.md)、[数据材质](references/material-data.md)。

基线为 **PixForge 4.12.1 / 命令版本 4**。随包程序面向 **Windows x64**，内置 Minecraft 导出适配 **Java 1.20.1 / Forge**；其他平台或游戏版本先核对可用程序与项目适配器。
