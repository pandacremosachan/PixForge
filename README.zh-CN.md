# PixForge

[![PixForge 2.9.0](https://img.shields.io/badge/PixForge-2.9.0-2563eb?style=flat-square)](https://github.com/pandacremosachan/PixForge/releases/tag/v2.9.0)
[![Skill 1.8.0](https://img.shields.io/badge/Skill-1.8.0-0d9488?style=flat-square)](.agents/skills/pixelforge/SKILL.md)
[![Public API 1](https://img.shields.io/badge/Public%20API-1-7c3aed?style=flat-square)](apps/pixforge/PUBLIC_API.md)
[![Windows x64](https://img.shields.io/badge/Platform-Windows%20x64-0078d4?style=flat-square)](https://github.com/pandacremosachan/PixForge/releases/tag/v2.9.0)
[![CLI and MCP](https://img.shields.io/badge/Interfaces-CLI%20%2B%20MCP-475569?style=flat-square)](.agents/skills/pixelforge/references/connection.md)

[English](README.md) | 简体中文

PixForge 是独立的像素画、模型与动画工作台，并提供供 AI 代理使用的配套 skill。软件与 skill 分别维护版本，通过公开的命令行接口（CLI）和模型上下文协议（MCP）通信，也可以独立使用。

| 组件 | 版本 | 源码与文档 |
|---|---|---|
| Windows 桌面程序与独立核心 | 2.9.0 | [软件说明](apps/pixforge/README.md) |
| 适用于不同代理宿主环境的配套 skill | 1.8.0 | [Skill 入口](.agents/skills/pixelforge/SKILL.md) |
| 公开 API | 1 | [接口约定](apps/pixforge/PUBLIC_API.md) |

## 让 AI 代理安装和配置

将下面这段指令复制给你的编程代理。代理会按照[安装说明](INSTALL.md)，选择当前宿主环境（harness）支持的 skill 安装位置，连接独立工作台，并验证连接。

```text
请读取并遵循 https://github.com/pandacremosachan/PixForge/blob/main/INSTALL.md（必要时通过已有授权的 Git 克隆读取），为当前代理环境安装并配置 PixForge skill，并验证连接。
```

英文指令：

```text
Read and follow https://github.com/pandacremosachan/PixForge/blob/main/INSTALL.md (using an authenticated Git clone if needed) to install and configure the PixForge skill for this agent environment, then verify the connection.
```

本仓库目前为私有仓库。代理需要通过已有的 GitHub 授权访问仓库，或读取本地克隆的文件；浏览器已登录不一定意味着代理使用的 Git 或网页读取工具也已获得授权。如果已有本地克隆，可以让代理读取仓库根目录的 `INSTALL.md`，在本地完成同样的安装步骤。

只要宿主环境能够加载 skill 指令，并且能够执行进程或连接 MCP，就可以使用这套 skill。当前可直接运行的软件包面向 Windows x64；其他系统需要已有的兼容软件连接。缺少仓库访问权限或软件时，代理应说明尚待完成的配置步骤。

## 下载

在[发布页](https://github.com/pandacremosachan/PixForge/releases)下载所需的软件包：

- **PixForge-Cpp-Windows-x64.zip**：可直接运行的 Windows 软件包。解压完整目录，保留可执行文件及其配套后端，无需在系统中另外安装 Python 或 C++ 开发环境。
- **PixForge-Cpp-Source.zip**：软件源码包，不包含运行环境或会话数据。
- **PixForge-Skill.zip**：可移植的操作说明、仅依赖 Python 标准库的客户端和任务模板。Skill 包不包含独立软件及其运行环境。

本次发布的软件包校验值记录在 [RELEASE_SHA256.txt](RELEASE_SHA256.txt) 中。

## 软件功能与兼容范围

工作台支持编辑 RGBA 像素与图层、模型 UV、碰撞与选中形状、材质帧动画、部件关键帧和命名状态、粒子，以及相互独立的 LabPBR 数据通道。桌面程序、CLI 和 MCP 共享工程、历史记录、恢复功能与绑定具体内容版本的导出确认机制。具体操作见[软件使用说明](apps/pixforge/README.md)和[公开 API](apps/pixforge/PUBLIC_API.md)。

原生发行包面向 Windows x64。内置的 Minecraft 资源与 Java 代码导出适配器目前支持 Minecraft Java 版 1.20.1 / Forge；离线检查与预览的结果不能代替游戏内验证。

## 配套 skill

在能够读取指令并执行进程，或连接标准 MCP stdio 服务的宿主环境中，加载 [SKILL.md](.agents/skills/pixelforge/SKILL.md)。Skill 目录可以安装在其他位置，执行时不依赖本仓库的目录布局，也不依赖可选的 OpenAI 宿主元数据。

Skill 提供八套完整流程和九套起步模板，覆盖方块、物品、已有材质替换、模型与形状、材质帧动画、场景状态与粒子、GUI 图片和 LabPBR 数据通道。使用时按任务选择相应流程；`scripts/scaffold.py --list` 可以列出模板目录。软件与 skill 分别维护版本和发布包。

## 源码与来源

软件实现位于 `apps/pixforge/`，skill 操作说明及其外部客户端位于 `.agents/skills/pixelforge/`。构建方法见[软件 README](apps/pixforge/README.md)。仓库不包含运行环境、私人画稿、会话数据和临时验证数据。

使用或分发时，请保留已有的[第三方声明](apps/pixforge/THIRD_PARTY_NOTICES.md)和[来源记录](sources.json)。本仓库未对已有源码或第三方依赖另行指定新的许可证。
