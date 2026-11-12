# Place the PixForge skill folder

[中文目录说明](.agents/skills/pixelforge/INSTALL.md)

Download the [Windows x64 skill ZIP](https://github.com/pandacremosachan/PixForge/releases/download/v4.1.1/PixForge-Skill-3.1.2-Windows-x64.zip) and extract it. The ready-to-use payload is the `pixelforge` folder containing `SKILL.md`, `assets/`, `references/` and `runtime/windows-x64/PixForgeNative.exe`.

Move or copy that folder to **one** of these locations:

| Scope | Final location of the entry file |
| --- | --- |
| This project | `<project root>/.agents/skills/pixelforge/SKILL.md` |
| All Codex projects for the current user | `~/.codex/skills/pixelforge/SKILL.md` |

If you set `CODEX_HOME`, use `<CODEX_HOME>/skills/pixelforge/` for the user-wide location. A directory junction to a maintained copy of the complete skill folder works in either location.

Open the project and invoke `$pixelforge`. The same folder works in both scopes; each project uses its own workspace and session. The Git checkout contains the sources. The [release](https://github.com/pandacremosachan/PixForge/releases/tag/v4.1.1) includes the built runtime.
