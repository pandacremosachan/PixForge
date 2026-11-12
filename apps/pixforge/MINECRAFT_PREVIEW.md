# Forge 1.20.1 model and rendering preview

The command contract exposes `minecraft-preview/v1`. The application owns resource resolution, geometry, texture sampling and rendering. The companion skill calls application commands. Previewing does not edit pixels, target configuration, project history, approval or game files.

Call workbench editor --editor-kind preview with operation=open, then read status and configure the actual model, blockstate or texture identifier. The current document can also be previewed, including its model, part poses and particle samples. Load the original example with project open using examples/forge-preview-1.20.1/preview-demo.pixforge.

The window provides these controls:

- Resource, blockstate properties, nine block/item display contexts, instance arrangement, and current/all-context comparison scope.
- Declared or explicit render layer, generated mipmap count, automatic or manual mip selection, camera distance, source animation time and translucent sorting.
- Sky/block light, day/night/cave presets, brightness, AO, separate block/item tints, actual source grass/foliage colormaps or explicit water color, face minimum light and separate local light probes.
- Per-face texture density, selected models, actual texture sources and validation diagnostics. Full JSON options expose weighted alternatives, item predicates, additional instances, occluders and probes.

Drag to orbit and use the wheel to zoom. These operations stay in the native renderer; they do not call the core or upload unchanged textures. Native OpenGL uses application-owned standard sampling shaders and cached mip chains. If unavailable, a C++ CPU renderer provides the same scene semantics. Batch comparison images use the independent headless reference renderer, with pagination.

## Public requests

Discover `minecraft capabilities` first; `minecraft capabilities` describes contexts, layers, features and scope. Commands accept an options object. Optional settings supplies a read-only target draft; omitting it uses the document's existing target.

执行 `minecraft preview --request-file <参数.json>`：

```json
{
  "batch": true,
  "contexts": [
    "block",
    "gui",
    "ground"
  ]
}
```

minecraft scene --include-pixels true returns a self-contained `pixforge.minecraft-scene/v1` bundle with actual RGBA pixels, baked faces, vertex colors, render rules, source/validation fingerprints and density reports. Pixels are omitted by default for compact inspection. minecraft preview returns a PNG and `pixforge.minecraft-preview/v1` report, including `total_cases` and `next_case_offset`. Limit each comparison page to 1–16 cases. A case is a declared property combination × weighted model alternative × requested display context.

application commands are `minecraft scene` and `minecraft preview`. The latter returns the PNG file as preview_path. Their request fields include options, settings, include_pixels, batch, contexts, case_offset and case_limit as applicable. All are reads. Neither operation grants workflow evidence or export approval.

Native window inspection uses workbench editor --editor-kind preview. Operations are `open`, `status`, `configure`, `field`, `invoke`, `camera`, `capture`, and `cancel`. operation=configure with a value object changes preview options only. The desktop API exposes field/action identifiers and GPU counters in `status`. Captures are discussion PNGs of this application's own window, subject to the normal source-overwrite guard.

Example options:

```json
{
  "subject": {
    "kind": "blockstate",
    "id": "examplemod:machine"
  },
  "state": {
    "facing": "east",
    "active": "true"
  },
  "context": "block",
  "mipmap_levels": 4,
  "mip_level": -1,
  "sort_translucent": true,
  "camera": {
    "yaw": 35,
    "pitch": 22,
    "distance": 56
  },
  "block_tints": {
    "0": "#70b94b"
  },
  "item_tints": {
    "0": "#d6ad66"
  },
  "environment": {
    "sky_light": 15,
    "block_light": 0,
    "gamma": 0
  },
  "ao": true,
  "self_light": 0,
  "size": 512
}
```

Subjects are `document/current`, `model/namespace:path`, `blockstate/namespace:path`, or `texture/namespace:path`. Contexts are `block`, `gui`, `ground`, `fixed`, `head`, `thirdperson_righthand`, `thirdperson_lefthand`, `firstperson_righthand`, and `firstperson_lefthand`. A blockstate in an item context requires its actual `models/item/<block>` resource or an explicit `item_model`; world blockstate geometry is not substituted for a missing item model.

Additional options:

| Field | Meaning |
| --- | --- |
| `render_type` | `auto`, `solid`, `cutout`, `cutout_mipped`, `cutout_mipped_all`, `translucent`, `tripwire` |
| `time_ms` | Source `.mcmeta` frame/interpolation and document scene sampling, 0–120000 ms |
| `item_properties` | Actual supplied item predicate values; last matching override wins |
| `property_domains` | Explicit property value lists for known registered-state domains |
| `weighted_choices` | Explicit alternative indices from the returned catalog; otherwise seeded target-compatible selection |
| `arrangement` | `single`, `grid`, `glass_layers`, `corner` |
| `instances` | Up to 64 `{pos:[x,y,z], subject?, state?, x?, y?}` instances; rotations in quarter turns |
| `biome_tint` | `{mode:"grass"/"foliage"/"water", index:0, temperature:0.8, downfall:0.4, colormap?:"namespace:colormap/grass", water_color?:"#3f76e4", item:false}` |
| `occluders` | Explicit full-voxel samples `{pos, shade_brightness, light_block, sky_light, block_light}` |
| `emission_sources` | Explicit unoccluded local probes `{pos:[x,y,z], level:15}`; separate from face minimum light |
| `environment` | Sky/block level 0–15; `sky_darken`, `gamma`, `ambient`, `flicker`, `night_vision`, `force_bright` |
| `use_document` | Include the current document's configured resource binding overlay, default true |

## Implemented semantics and verification scope

The source resolver reuses the application's directory/ZIP/JAR priority and fingerprint checks. Models resolve parents, texture aliases and distinct textures per face. Blockstates evaluate variants, multipart AND/OR conditions, weighted alternatives, quarter-turn rotations and UV locking. Display transforms inherit per context and preserve left-hand mirroring, translation, scale and `right_rotation`. Generated item layers include thickness edges merged over all used animation frames. Texture animation follows source frame dimensions, integer 50 ms ticks and current-alpha RGB interpolation.

Mipmaps use the target gamma 2.2 reduction and transparent-chain alpha handling. The standard terrain and item layers have distinct sampling and alpha-test behavior, including item cutout testing sprite alpha before vertex color. Transparent terrain retains depth writes and sorts faces by camera distance. Per-face density measures actual UV span against model-space edge length without changing source resolution.

Block and item tint providers are explicit inputs. Climate lookup samples actual 256×256 source colormap pixels. Controlled lightmap calculation combines sky/block values, brightness and the supplied preview environment. AO interpolates explicitly supplied full-voxel shade samples. `forge_data` supports ARGB color, minimum block/sky light, AO and normal flags, at element or face scope. A face's minimum light brightens that face; it does not change surrounding world light. Local light probes are separately placed preview inputs.

This is an offline controlled scene, with `in_game_validated:false` in results. Resource-declared state conditions do not prove the complete registered block-state domain. Custom model loaders, custom partial occlusion callbacks, actual world light propagation, third-party shader packs, PBR, bloom, Fabulous postprocessing, held-item use/bob animations and runtime custom item renderers require their consuming project. Independent sprites include the standard face-corner UV inset. Actual atlas packing, atlas-size shrink and neighboring-sprite bleed are not inferred.
