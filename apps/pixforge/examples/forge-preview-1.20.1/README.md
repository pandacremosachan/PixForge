# Original Forge 1.20.1 preview example

This resource set was authored for PixForge. It contains no Minecraft/Mojang pixels or dependency code. Use the executable commands with this example directory as --workspace and a separate --runtime. Load preview-demo.pixforge through project open, then pass the preview.json object to workbench editor --editor-kind preview; operation=configure,value=object or minecraft preview --options object.

The machine blockstate combines a frame, translucent glass, alpha-cutout leaves, and a minimum-light strip. It declares four directions and two active states. `asymmetric` adds UV-lock and weighted alternatives. Actual item models provide GUI, ground, fixed and hand display transforms; `item/diagnostic` demonstrates generated thickness and an item predicate override. The grass colormap is an original synthetic 256×256 image.

Select resources from the preview catalog. Compare sampling levels and camera distances, three overlapping instances, sky/block light, AO and separate tint tables. For climate lookup choose the grass mode and set the colormap to `pixforge_preview_demo:colormap/grass`. Local light probes and face minimum light are separate controls. Use state comparison with block/GUI/ground scope to inspect all pages.

The example is an offline controlled scene, not a playable mod or an in-game acceptance test. Original projects and source pixels are not changed by previewing. `target.json` uses the current workspace as its source root; changing the workspace requires a corresponding source configuration.
