# 来源与第三方内容

- **Impeccable**：上游 [pbakaus/impeccable](https://github.com/pbakaus/impeccable)。从当前 CTNH 项目安装提取，技能元数据版本 4.5.0，启动器固定的引擎版本 0.1.11，两者分别记录，不视为同一版本号。原始指令保存在 `.agents/skills/impeccable/UPSTREAM_SKILL.md`；上游参考文档与脚本保留原文。LICENSE 和 NOTICE.md 从 `engine-v0.1.11` 获取，置于该技能目录。Minecraft 入口属于本集合的适配内容。
- **mc-worldgen-preview**：来自当前 CTNH 开发工作区的项目级自定义技能。读取消费项目的 MC 资源及现有生产类，没有把 CTNH/MC 的 Java 游戏源码或 Gradle 缓存复制进集合。
- **PixForge**：来自本机已有的用户级 `pixelforge` 技能，包含其自带 Python 工具及后来完善的材质规范。原安装未附独立许可证，不据此补造授权；保留来源和原安装哈希。Pillow 等依赖不作为自有源码发布。
- **PixForge 方法研究（2026-10-11）**：研究 [Pixelorama](https://github.com/Orama-Interactive/Pixelorama)（MIT）、[Blockbench](https://github.com/JannisX11/blockbench)（GPL-3.0）与 [Material Maker](https://github.com/RodZill4/material-maker)（MIT）的绘制、UV、节点和导出实现。固定提交记录在 `sources.json`，具体源码依据在 `.agents/skills/pixelforge/references/upstream-workflows.md`。本次只整合方法并独立编写检查/播放 helper，没有将三个项目的源码、shader、节点或资源复制进技能；研究下载保存在本机运行缓存，不作为技能源码发布。若后续引入实际上游实现，需要重新处理其许可证、版权和版本记录。
- **PixForge 事务与验收方法研究（2026-10-17）**：参考 [Pixel Loom](https://github.com/yangsir2077/pixel-loom)（MIT，固定提交见 `sources.json`）的批次事务、预演图像和内容绑定验收方法，独立实现适用于现有 CLI、`.px` 和 Minecraft 资源流程的扩展，以及共享画布、用户确认后导出的 Python 桌面工作台；未复制其源码或应用资源。没有改变 PixForge 原安装内容的许可状态。

旧安装路径、原始文件哈希与本机迁移结果记录在 `.runtime/migration/`，不进入对外源码。原安装快照只作本机恢复使用，不作为第二份维护源码。

- **PixForge 桌面界面参考（2026-10-18）**：以 [PixiEditor](https://github.com/PixiEditor/PixiEditor)（LGPL-3.0）为主要工作区布局范本，借鉴 [Pixelorama](https://github.com/Orama-Interactive/Pixelorama)（MIT）的像素和动画交互；参考提交记录见 `sources.json`。Qt 界面、图标和帧操作独立实现，未复制上述项目的源码、品牌、字体或素材。PySide6-Essentials 为可选运行依赖，保留其随包许可证，不作为自有源码发布。

- **PixForge C++ 桌面（2026-10-18）**：新增 Win32/GDI/GDI+/OpenGL 前端和独立绘制图标，未复制外部 GUI 源码或素材。使用系统 API 和本机 MSVC 工具链；便携包不含 Qt，自带的 CPython、Pillow 和 MCP 及其依赖保留运行库、元数据和许可证，核心继续独立运行。以上新增实现不改变原有 PixForge 的许可状态。
