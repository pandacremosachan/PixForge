# PixForge

[![PixForge 4.2.3](https://img.shields.io/badge/PixForge-4.2.3-2563eb?style=flat-square)](apps/pixforge/README.md)
[![Skill 3.2.3](https://img.shields.io/badge/Skill-3.2.3-0d9488?style=flat-square)](.agents/skills/pixelforge/SKILL.md)
[![Public API 4](https://img.shields.io/badge/Public%20API-4-7c3aed?style=flat-square)](apps/pixforge/PUBLIC_API.md)
[![Windows x64](https://img.shields.io/badge/Platform-Windows%20x64-0078d4?style=flat-square)](https://github.com/pandacremosachan/PixForge/releases/tag/v4.2.3)
[![CLI and HTTP](https://img.shields.io/badge/Interfaces-CLI%20%2B%20HTTP-475569?style=flat-square)](.agents/skills/pixelforge/references/command-line.md)

[English](README.md) | 简体中文

PixForge 是用于像素画、纹理模型和动画的 Windows 工作台。AI 通过命令绘制，工作台实时显示同一份工程。材质页展开画板工具、调色板和图层，模型页展开视角与显示选项。

## 使用技能

下载 [Windows x64 技能包](https://github.com/pandacremosachan/PixForge/releases/download/v4.2.3/PixForge-Skill-3.2.3-Windows-x64.zip)，解压出完整的 **`pixelforge` 文件夹**。其中已经包含工作台、运行环境和模板；技能的可用范围由放置目录决定：

| 可用范围 | 放置后的目录 |
| --- | --- |
| 仅当前项目 | `<项目根目录>/.agents/skills/pixelforge/` |
| 当前用户的所有 Codex 项目 | `~/.codex/skills/pixelforge/`；自定义了 `CODEX_HOME` 时用 `<CODEX_HOME>/skills/pixelforge/` |

打开项目后，用 `$pixelforge` 调用。即使全局共享技能，每个项目也各自保存作品和会话。让代理代为放置时，把[目录说明](INSTALL.md)和所需范围告诉它即可。

## 单独使用桌面程序

下载 [Windows x64 便携工作台](https://github.com/pandacremosachan/PixForge/releases/download/v4.2.3/PixForge-4.2.3-Portable-Windows-x64.zip)，解压完整的 `PixForge` 文件夹，运行其中的 `PixForgeNative.exe`。无需安装技能或系统 Python。

## 模型与预览

可见零件和交互形状分别定义。新建手持模型默认没有方块碰撞箱；可放置物可用 `base_boxes` 指定主要体块。可旋转网页与模型 PNG 使用同一视角和线框开关，绑定物品时还会并排显示其物品栏效果。

工作台支持 RGBA 图层、模型 UV、纹理帧、部件关键帧、命名状态、粒子和 LabPBR 通道。内置 Minecraft 适配面向 Java 1.20.1 / Forge。参见[工作台说明](apps/pixforge/README.md)与[技能工作流](.agents/skills/pixelforge/SKILL.md)。

## 源码与接口

[工作台源码](apps/pixforge)与[配套技能](.agents/skills/pixelforge)分别维护版本。常驻本地 HTTP 接口和分组 CLI 与编辑器共享工程和撤销历史。参见[公开 API](apps/pixforge/PUBLIC_API.md)及[版本下载](https://github.com/pandacremosachan/PixForge/releases/tag/v4.2.3)。

[来源记录](sources.json) · [第三方声明](apps/pixforge/THIRD_PARTY_NOTICES.md)。
