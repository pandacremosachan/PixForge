---
name: pixelforge
description: 使用独立 PixForge 工作台制作或修改像素画、Minecraft 方块与物品材质、单图集模型、碰撞/选中形状、GUI 图标、材质帧动画、部件状态/粒子和 LabPBR 数据材质。提供完整任务流程、可复制模板及 CLI/MCP 接口；适用于能运行命令或连接 MCP 的任意代理，不依赖 Codex。
---

# PixForge

本 skill 是独立工作台的操作指导和外部客户端。工作台负责像素、模型、动画、工程、撤销、恢复与导出；skill 不包含其实现。先读 [连接与 harness 接入](references/connection.md)，再读 [操作约定](references/operations.md) 和下表中与任务对应的一套流程。完整流程已包含准备、参数、操作、预览、交付和失败处理，无需先研究源码、遍历工具或阅读全部参考。

## 按任务选择流程

| 任务 | 完整流程 | 起步模板 |
|---|---|---|
| 新方块：共用贴图、六面独立、简单静态方块 | [定义方块](references/workflows/block.md) | `block-shared` / `block-faces` |
| 材料物品、工具外观、平面或三维物品 | [定义物品](references/workflows/item.md) | `item` |
| 只修改已有资源，保留朝向、multipart、连接和 tint | [替换已有材质](references/workflows/replace-texture.md) | 使用真实源文件 |
| 自定义几何、UV、碰撞箱与选中框 | [模型和形状](references/workflows/model-shapes.md) | `custom-model` |
| 流动、闪烁等逐帧材质 | [材质动画](references/workflows/texture-animation.md) | `texture-animation` |
| 部件旋转/位移/缩放、启停状态、发射粒子 | [场景动画](references/workflows/scene-animation.md) | `scene-states` / `particles` |
| GUI 按钮、状态图标、槽位、独立像素画 | [GUI 与独立图片](references/workflows/gui.md) | `gui` |
| 法线、AO、高度、粗糙/金属、发光等数据通道 | [LabPBR 材质](references/workflows/labpbr.md) | `labpbr` |

模板目录和所需能力也列在 [机器可读流程目录](assets/workflows.json)。用 `python <skill-dir>/scripts/scaffold.py --list` 查看；例如：

```text
python <skill-dir>/scripts/scaffold.py block-faces --output <新的草稿目录> --namespace <实际namespace> --name <资源名>
```

scaffold 只复制文本模板，不启动软件、不修改已有作品、不批准导出。模板采用明确的 16 像素示例尺寸和演示图案；实际项目的尺寸、模型、风格和像素密度优先。改变尺寸时同步修改布局和绘图坐标，不能直接复用示例坐标。

## 接入与兼容性

能执行进程的 harness 使用公开 CLI；支持 MCP 的 harness 可直接启动软件的 stdio MCP；也可把本目录作为普通指导文件加载。无需特定工具名称、系统提示、Codex 目录、目录联接或 `$pixelforge` 语法。`agents/openai.yaml` 仅为可选宿主元数据，工作流和客户端不读取它。

本版流程以 **PixForge 2.9.0 / public API 1** 为基线。新建、绘制、模型、形状、帧/场景动画是通用能力；内置 Minecraft 资源/Java 导出适配器目前只承诺 **Java 1.20.1 / Forge**。其他版本和加载器沿用本流程制作资产，接入与资源布局由目标项目自己的适配器处理，不将它们声明为已支持。harness 通用性不等于软件发行包能在所有操作系统运行；当前现成桌面包是 Windows x64。连接方式和远端边界见连接文档。

## 共同操作原则

- 读取任务项目的规则和既有资源，确定真实 namespace、版本/加载器、注册/datagen 方式、原生尺寸、图集/UV、状态、渲染层和输出位置。已有工程直接继续，不重新创建空工程。
- 所有写入携带已观察到的 `document_id`、`revision`；用操作返回的 `state` 继续。冲突或用户笔画进行中时停止当前写入，重读并合并意图，不自动用新令牌覆盖。
- AI 与桌面连接同一 `workspace/runtime`。需要共同查看时打开窗口；编辑、预览和可编辑工程保存不依赖 GUI。
- 共享绘图批次只放绘图命令；创建、打开、保存、撤销、动画与导出调用专用操作。不得导入软件模块、调用私有 Python、编辑会话文件或直接改写活动工程。
- 新作品先定义布局，再画大形与材料层次，再补细节。按真实 UV 定位，明确局部对称范围；`mirror on` 只围绕整个画布的竖直中线。
- `grid/rle/patch` 的透明字符 `.` 会替换原像素。叠画时裁剪负载或使用独立图层；`read` 读的是可见层合成结果，不能回贴到半透明前景层冒充无损编辑。
- 实际查看原尺寸和最近邻预览。可平铺纹理检查 3×3，透明图查看深浅背景，模型检查所用朝向/状态，动画按真实顺序和时长播放。检查器成功不代表视觉通过或游戏内验证。
- 可编辑工程和讨论预览可以直接保存。正式图片、形状和资源包导出受工作台现有的内容确认约束；展示具体版本后记录真实用户同意，已有有效授权不重复询问。内容或资源依赖改变后按实际变化重新确认。
- 原生 PNG 保持实际生产分辨率；预览、脚本、制作资料与正式资源分开。遵循任务项目的 datagen 边界，不把模板、预览或依赖 JAR 放入资源包。默认不启动游戏、安装运行时或改存档。

## 按需深入

| 当前问题 | 参考 |
|---|---|
| 精确绘图语法、替换与读回 | [像素协议](references/protocol.md) |
| 视觉设计、参考转化、局部修改 | [设计验收](references/design-review.md)、[材质](references/textures.md)、[图标](references/icons.md)、[对称](references/symmetry.md) |
| 资源来源、引用闭包、指纹与版本导出 | [Minecraft 资源](references/minecraft-assets.md) |
| 新注册对象、语言、掉落、标签和构建 | [Forge 静态对象接入](references/forge-static.md) |
| 复杂状态、mipmap、透明与光照 | [Minecraft 预览](references/minecraft-preview.md) |
| 关键帧、事件和状态曲线 | [场景协议](references/scene-animation.md) |
| 动画文件、真实时长、游戏实例和捕获 | [动画播放器](references/animation-review.md)、[元数据与回归](references/runtime-678.md) |
| 动态部件/粒子的 Java 接入 | [Forge 运行时导出](references/forge-runtime.md) |
| 数据通道字节和着色器契约 | [数据材质](references/material-data.md) |
| 桌面操作、恢复与预演 | [桌面](references/desktop.md)、[会话](references/session.md)、[事务](references/transactions-review.md) |
| 成套素材与迭代效率 | [方法整合](references/upstream-workflows.md)、[效率](references/performance.md) |
