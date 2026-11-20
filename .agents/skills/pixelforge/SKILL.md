---
name: pixelforge
description: 用 PixForge 设计和导出 Minecraft GUI，包括熔炉、工作台等容器界面、配置页和手册，支持组件布局，使用 SVG 和逐像素绘制制作九宫格主题与加工动画。也可制作原版 PNG 皮肤、支持多选、逐面 UV、多贴图和动画曲线的 Blockbench / YSM 骨骼模型、方块与物品材质、可放置模型与碰撞形状、像素画和部件动画。
---

# PixForge

[放置目录](INSTALL.md)决定此技能仅对当前项目可用，还是对当前用户的所有 Codex 项目可用。

## 能制作什么

| 成品 | 常见例子和交付内容 | 工作流与模板 |
|---|---|---|
| 平面物品与工具 | 矿料、零件、食物、工具等物品图标，交付透明 PNG 和物品模型 JSON | [物品](references/workflows/item.md) · `item` |
| 三维手持物品 | 扳手、手持仪器、展示品等，制作立体模型和贴图，可分别设置手持与物品栏视图 | [三维物品](references/workflows/item.md#三维物品) · `item/project-3d.json` + `item/target.json` |
| 普通方块 | 石材、砖块、面板等，制作六面共用或分面贴图、方块模型和方块状态资源 | [方块](references/workflows/block.md) · `block-shared` / `block-faces` |
| 单格自定义放置物 | 盆栽、路灯底座、小型机器等，制作部件、逐面 UV、贴图、碰撞和选中形状 | [模型与形状](references/workflows/model-shapes.md) · [部件建模与逐面 UV](references/workflows/rig-components.md) · `custom-model` |
| 跨格放置物 | 双格工作台、长桌、大型机器等，可制作跨格外观、碰撞和选中形状。一个物品放下后实际占用多格，由模组实现 | [跨格外观与多格占位](references/workflows/model-shapes.md#跨格外观与多格占位) · `custom-model` |
| Java 原版玩家皮肤 | 宽臂或细臂皮肤、服装外层，交付 64×64 PNG | [玩家皮肤](references/workflows/player-skin.md) · `player-skin/classic` / `player-skin/slim` |
| 骨骼玩家模型 | 自定义角色、发饰、可动部件等，支持多选变换、逐面 UV、多贴图和动画曲线，可导出 Blockbench `.bbmodel` 或 YSM 模型包 | [骨骼建模与导出](references/workflows/player-rig.md) · `player-rig` |
| Minecraft GUI 界面 | 熔炉烧炼、工作台合成、配置页和手册，设置逻辑布局与贴图像素密度，使用 SVG 和逐像素绘制制作九宫格主题，预览翻译与动画并导出 GUI 资源 ZIP | [GUI 设计](references/workflows/gui-design.md) · `gui_layout` |
| 独立像素画 | 像素插画、头像、风景等，交付原尺寸 PNG | [像素画工作流](references/workflows/gui.md) · `gui` |

新建时按成品选择工作流，使用 `project plan` 或 `project create`。方块在同一工程中绘制贴图、添加和修改三维部件。工作台的「角色建模」入口用于骨骼角色。[启动页与预设对照](references/desktop.md#启动页与工程预设)

读取 `assets/workflows.json` 和工作流引用的模板，将项目尺寸、资源 ID、模型及图案替换为实际值，再通过命令的文件参数传入。模板文件本身不构成软件依赖。

### 动画、材质与已有资源

| 需求 | 常见例子 | 工作流与模板 |
|---|---|---|
| 逐帧纹理动画 | 流动纹理、闪烁灯带 | [材质动画](references/workflows/texture-animation.md) · `texture-animation` |
| 部件、状态与粒子 | 转子转动、机器启停和喷口粒子 | [场景动画](references/workflows/scene-animation.md) · `scene-states` / `particles` |
| LabPBR 数据材质 | 法线、粗糙感或金属质感、发光等数据通道 | [LabPBR](references/workflows/labpbr.md) · `labpbr` |
| 替换已有贴图 | 给已有方块或物品换配色、重绘材质 | [替换材质](references/workflows/replace-texture.md) · 真实源文件 |

## 工作台与命令

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

## 按需参考

- 设计：[视觉验收](references/design-review.md)、[平铺材质](references/textures.md)、[图标](references/icons.md)、[对称](references/symmetry.md)、[成套制作](references/upstream-workflows.md)。
- 命令：[分组与输入](references/session.md)、[工作台](references/desktop.md)、[离线事务](references/transactions-review.md)、[效率](references/performance.md)。
- Minecraft：[资源与导出](references/minecraft-assets.md)、[资源机制](references/game-assets.md)、[模型预览](references/minecraft-preview.md)、[静态注册](references/forge-static.md)、[运行时接入](references/forge-runtime.md)。
- 动态与数据：[播放定义](references/animation-review.md)、[场景协议](references/scene-animation.md)、[游戏回归](references/runtime-678.md)、[数据材质](references/material-data.md)。

基线为 **PixForge 4.14.3 / 命令版本 4**。随包程序面向 **Windows x64**，内置 Minecraft 导出适配 **Java 1.20.1 / Forge**；其他平台或游戏版本先核对可用程序与项目适配器。
