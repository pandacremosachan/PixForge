# Forge 1.20.1 / LabPBR 1.3 diagnostic example

`material-demo.pixforge` contains an original 64×64 color atlas and two independent data atlases. Open it with PixForge 2.7, then use 资源 → LabPBR 数据材质与通道. `channels.png` shows all eight data planes. The source PNGs, project and shader pack are owned examples; this folder contains no game, loader or third-party shader binaries. The project has no export approval.

`shader-target.json` pins `PixForge-LabPBR-Probe-1.0.0.zip`, OptiFine `1.20.1_HD_U_I6`, Forge `47.2.18`, and the actual ZIP SHA. The shader is a small diagnostic implementation, with no height/POM, named-metal table, porosity, SSS or SSR. A local shader path is intentionally omitted. Configure the actual local copy and consuming project's versions/options before target testing. Nothing is installed and no game is launched by opening the project.

The shader source is under `shader-pack/shaders`; canonical sources and its generator live in the software's `scripts/material_probe_shaders` and `scripts/material_demo.py`. GPU program compilation and raw-byte decoding are offline checks. Use the opt-in Forge regression export and its capture guide for actual game acceptance. See the application's `MINECRAFT_MATERIAL_DATA.md` for semantics and public commands.
