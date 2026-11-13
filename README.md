# PixForge

[![PixForge 4.12.1](https://img.shields.io/badge/PixForge-4.12.1-2563eb?style=flat-square)](apps/pixforge/README.md)
[![Skill 3.9.1](https://img.shields.io/badge/Skill-3.9.1-0d9488?style=flat-square)](.agents/skills/pixelforge/SKILL.md)
[![Public API 4](https://img.shields.io/badge/Public%20API-4-7c3aed?style=flat-square)](apps/pixforge/PUBLIC_API.md)
[![Windows x64](https://img.shields.io/badge/Platform-Windows%20x64-0078d4?style=flat-square)](https://github.com/pandacremosachan/PixForge/releases/tag/v4.12.1)
[![CLI and HTTP](https://img.shields.io/badge/Interfaces-CLI%20%2B%20HTTP-475569?style=flat-square)](.agents/skills/pixelforge/references/command-line.md)

English | [简体中文](README.zh-CN.md)

PixForge is a Windows workbench for pixel art, textured 3D models and animation. Choose **Block** to paint faces and assemble a model in the same project; switch between the texture and model views as you work. Choose **Item Texture** for a flat sprite or **Character Modeling** to start with a player skeleton. An agent can edit the open project through commands while you watch.

## Use the skill

Download the [PixForge skill for Windows x64](https://github.com/pandacremosachan/PixForge/releases/download/v4.12.1/PixForge-Skill-3.9.1-Windows-x64.zip). It includes the workbench, its private runtime and the skill templates. Extract the **whole `pixelforge` folder** and choose its location:

| Available in | Put the folder here |
| --- | --- |
| One project | `<project>/.agents/skills/pixelforge/` |
| All Codex projects for this user | `~/.codex/skills/pixelforge/`, or `<CODEX_HOME>/skills/pixelforge/` if configured |

Open the project and invoke `$pixelforge`. Each project keeps its own artwork and session, even with a user-wide installation. If your agent is placing the folder for you, give it the [installation guide](INSTALL.md) and the desired scope.

## Use the desktop on its own

Download the [standalone Windows x64 workbench](https://github.com/pandacremosachan/PixForge/releases/download/v4.12.1/PixForge-4.12.1-Portable-Windows-x64.zip), extract the `PixForge` folder and run `PixForgeNative.exe`. The application works without a skill or a system Python installation.

## Models and previews

Use the Model Display sidebar to see the base shape, collision boxes or selection boxes. For example, a monitor can have separate boxes for its screen, post and foot without making the space under the screen solid. Hiding the textured model leaves the chosen wireframes visible.

For characters, paint a 64 × 64 Classic or Slim player skin, or use an editable rig with per-face UVs, multiple textures and animation curves. Rigs support Bedrock Entity Blockbench projects and YSM export. [Skin workflow](.agents/skills/pixelforge/references/workflows/player-skin.md) · [Rig workflow](.agents/skills/pixelforge/references/workflows/player-rig.md).

The workbench edits RGBA layers, model UVs, texture frames, keyframes, named states, particles and LabPBR channels. The built-in Minecraft target is Java 1.20.1 / Forge. [Application guide](apps/pixforge/README.md) · [Skill workflows](.agents/skills/pixelforge/SKILL.md).

## Source and interfaces

Application source is in [apps/pixforge](apps/pixforge); the independently versioned [skill](.agents/skills/pixelforge) uses the public commands. A resident local HTTP endpoint and the grouped CLI share the editor's project and history. See the [API contract](apps/pixforge/PUBLIC_API.md) and [release downloads](https://github.com/pandacremosachan/PixForge/releases/tag/v4.12.1).

[Source provenance](sources.json) · [Third-party notices](apps/pixforge/THIRD_PARTY_NOTICES.md).
