# Forge model and rendering preview

Read `project info` and `minecraft capabilities` to confirm `minecraft-preview/v1`. Use the public API without importing application internals.

Use the project's real target, source precedence, identifiers, item models, tints and light inputs. Begin with `project state` and `minecraft scene`; the latter returns selected models, declared state/weighted cases, source/validation fingerprints, per-face density and scope. Its `include_pixels=true` option includes actual RGBA for clients that require the scene bundle. Ordinary inspection should omit pixels to keep responses compact.

执行 `minecraft preview --request-file <参数.json>`：

```json
{
  "options": {
    "subject": {
      "kind": "model",
      "id": "examplemod:block/machine"
    }
  },
  "batch": true,
  "contexts": [
    "block",
    "gui",
    "ground"
  ],
  "case_offset": 0,
  "case_limit": 8
}
```

These calls are read-only. Optional `settings` checks a target draft without applying it. Output PNGs are discussion previews, never production textures. Use a new output path or explicit overwrite, and retain the application's output/source guards. Previewing does not provide workflow evidence, user approval or formal export authorization.

The application's commands are `minecraft scene` and `minecraft preview`; discover their actual signatures. The command returns preview_path to a PNG file plus its report; inspect that file. In a batch, follow `next_case_offset` until the requested state/context range is covered. Report actual coverage and any errors; do not treat one page as all cases.

Options include:

- `subject:{kind:"document"/"model"/"blockstate"/"texture",id:"namespace:path"}`; document uses `id:"current"`.
- `state`, `property_domains`, `weighted_choices`, `seed`, `item_model` and `item_properties` from the real consuming project. A blockstate in an item context needs its actual item-model resource.
- `context`: `block`, `gui`, `ground`, `fixed`, `head`, `thirdperson_righthand`, `thirdperson_lefthand`, `firstperson_righthand`, `firstperson_lefthand`.
- `render_type`: `auto`, `solid`, `cutout`, `cutout_mipped`, `cutout_mipped_all`, `translucent`, `tripwire`; `mipmap_levels:0..4`, `mip_level:-1..4`, `sort_translucent`, `time_ms`, `camera` and instance arrangements.
- Separate `block_tints` and `item_tints`, keyed by tint index. Climate colors require actual source `biome_tint.colormap` pixels or an explicit water color; screenshots cannot supply them.
- Explicit `environment`, `ao`, full-voxel `occluders`, face `self_light`, and independent `emission_sources`. Face minimum light affects the face; it does not imply world-light emission.

For shared native review, call `workbench editor --editor-kind preview; operation="open"`, inspect `status`, then use the returned field/action identifiers with `configure/field/invoke/camera/capture/cancel`. These public operations change preview settings and capture the application's own window without editing the artwork.

Inspect returned images at relevant distances and contexts. Compare cutout edges and mips, transparent overlap with sorting enabled, declared variants and multipart combinations, GUI/held/ground transforms, per-face texture density, block/item colors and day/night/cave lighting. Use actual source animation time when checking animated edges. Keep all previous pixels and project history unless the user asks to edit them.

The renderer is a controlled offline Forge 1.20.1 preview. Reports explicitly retain `in_game_validated:false`. Resource-declared properties do not establish the complete registered state domain; use explicit domains when known. Custom loaders, partial occlusion callbacks, world light propagation, third-party shaders/PBR/bloom/Fabulous and dynamic custom item renderers require the consuming game project. Never label an offline report as an in-game acceptance result.
