# PixForge

PixForge is a standalone pixel, model and animation workbench, with a separately versioned companion skill for AI agents. The application and skill communicate through public CLI/MCP interfaces and can be used independently.

| Component | Version | Source and documentation |
|---|---|---|
| Windows desktop and independent core | 2.9.0 | [Application](apps/pixforge/README.md) |
| Harness-independent companion skill | 1.8.0 | [Skill entry](.agents/skills/pixelforge/SKILL.md) |
| Public API | 1 | [Interface contract](apps/pixforge/PUBLIC_API.md) |

## Downloads

Download the three packages from [Releases](https://github.com/pandacremosachan/PixForge/releases):

- **PixForge-Cpp-Windows-x64.zip**: ready-to-run Windows application. Extract the complete folder and keep its private backend beside the executable. No global Python or C++ installation is required.
- **PixForge-Cpp-Source.zip**: application source without runtimes or session data.
- **PixForge-Skill.zip**: portable instructions, standard-library client and task templates. The skill does not contain the application or its runtime.

[RELEASE_SHA256.txt](RELEASE_SHA256.txt) records the package checksums for this release.

## Application

The workbench edits RGBA pixels and layers, model UVs, collision and selection shapes, texture frames, part keyframes and named states, particles and independent LabPBR data channels. Desktop, CLI and MCP share the project, history, recovery and content-bound export approval. See the [application guide](apps/pixforge/README.md) and [public API](apps/pixforge/PUBLIC_API.md).

The native distribution targets Windows x64. Minecraft resource and Java export adapters currently target Java 1.20.1 / Forge; offline checks and previews do not establish in-game validation.

## Companion skill

Load [SKILL.md](.agents/skills/pixelforge/SKILL.md) in a harness that can read instructions and run a process or connect standard MCP stdio. The folder can be installed elsewhere: this repository layout and optional OpenAI metadata are not execution dependencies.

Eight complete workflows and nine starter templates cover blocks, items, existing texture replacement, model/shapes, texture animation, scene states/particles, GUI images and LabPBR channels. Follow the relevant workflow; `scripts/scaffold.py --list` lists the template catalog. The application and skill keep separate versions and packages.

## Source and provenance

Application implementation lives in `apps/pixforge/`; skill instructions and its external clients live in `.agents/skills/pixelforge/`. Build instructions are in the [application README](apps/pixforge/README.md). Runtime environments, private artwork, sessions and temporary verification data are excluded.

Preserve the existing [third-party notices](apps/pixforge/THIRD_PARTY_NOTICES.md) and [provenance](sources.json). This repository does not assign a new license to pre-existing source or third-party dependencies.
