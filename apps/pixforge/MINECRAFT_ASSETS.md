# Minecraft targets and asset exports

PixForge 2.3 adds the optional `minecraft-assets/v1` capability to public API v1. The first target is **Forge / Minecraft Java 1.20.1**, using resource-pack format **15**. Parsing, validation, source precedence, asset generation and publication belong to the application. No skill files or modules are needed.

The native desktop exposes **资源 → Minecraft 目标、资源与检查…**. The dialog edits an independent draft: validate it, inspect issues and sources, then apply one undoable operation. Cancelling leaves the project untouched. The same core operations are available through CLI/MCP. Formal exports remain gated by current evidence, real user approval and current dependency fingerprints.

PixForge 2.4.1 organizes this dialog into **目标配置**, **资源来源**, **Forge 接入**, and **检查结果** pages. Package/version/block/render-layer settings are edited directly; complete runtime JSON and entry arrays have separate resizable editors. Reports switch between issues, effective files, overrides and project hooks, while generated source opens in a dedicated read-only file browser. Check/apply/cancel remain in a persistent footer. Compact windows scroll only the active page and reveal keyboard-focused controls automatically.

## Configuration

Use `session minecraft-capabilities` to discover the exact supported profiles. Applying a configuration is explicit; older projects are never assigned or converted to a Minecraft target automatically.

```json
{
  "schema": "pixforge.minecraft-project/v1",
  "profile": "forge-1.20.1",
  "namespace": "examplemod",
  "description": "Example Forge 1.20.1 resources",
  "sources": [
    {"name": "vanilla", "path": "D:/reference/client-1.20.1.jar", "role": "dependency"},
    {"name": "project", "path": "src/main/resources", "role": "project"},
    {"name": "generated", "path": "src/generated/resources", "role": "project"}
  ],
  "entries": [
    {"kind": "blockstate", "id": "examplemod:existing_machine"}
  ],
  "binding": {
    "kind": "texture",
    "path": "existing_machine",
    "texture": "block/existing_machine"
  }
}
```

Sources are resource directories containing `assets`, the `assets` directory itself, resource-pack ZIPs, or mod/client JARs. Their order is **low to high**. Relative paths are resolved against the session workspace when configured and saved as absolute locations; relocating a resource project requires updating these locations. A missing source is a diagnostic, never a reason to invent its contents or download a dependency implicitly.

`project` sources can contribute their selected reference closure to the export; `dependency` sources are resolved and hashed but **not copied**. Supply the actual target client/mod JARs when models depend on them. A resource source is not a game instance: PixForge does not launch Minecraft, modify saves or install the exported pack.

`entries` contains `blockstate`, `model`, `texture`, or `atlas` resource IDs. Unqualified IDs use Minecraft's actual default namespace `minecraft`, not the configuration's namespace. Only the selected closure is checked/exported. Inspecting every registered state, datagen completeness or a running client's active pack order requires project/game evidence outside this adapter.

`binding` is optional. When present, the current document is the final overlay:

| Binding | Generated assets |
|---|---|
| `texture` | Current native pixels and, when needed, `.png.mcmeta`. Existing model/state files remain governed by their real source references. |
| `block` | Texture, current explicit model, a single-model empty-variant blockstate, and the legacy `models/item` block-item reference. It supplies appearance for a registered block; it does not register new blocks or export physical behavior. |
| `item` | Texture and `models/item` model. A model-free item references the real `minecraft:item/generated` template and therefore needs that dependency source. |

Use `texture` when replacing an existing mod's texture without flattening its facing, variants, multipart or custom rendering. `block` deliberately represents a simple single-model state. Embedded model UVs and RGBA pixels are preserved; production textures are not silently resized or quantized. Atlas frames may be repacked vertically for Minecraft without changing their pixels.

## Public operations

```powershell
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge minecraft-capabilities
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge minecraft-configure --config target.json --expected-document-id <id> --expected-revision <revision>
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge minecraft-check
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge minecraft-check --sources-only
.\PixForgeNative.exe --cli session --workspace D:\Project --runtime D:\Project\.runtime\pixforge minecraft-export resources.zip --format resource-pack --validation-digest <digest> --expected-document-id <id> --expected-revision <revision>
```

`minecraft-configure --clear` removes the target in one undoable operation. `minecraft-check --config draft.json` checks a draft without applying it. `--sources-only` excludes the current document overlay and needs explicit source entries. Checks return `validation.passed`, issues with severity/code/resource/source, graph edges, source winners/overrides, exact file hashes, generated-sprite inputs and `validation_digest`. A failed CLI check returns exit code 1 with its report; MCP marks that result as an error and still supplies diagnostics.

MCP equivalents are `minecraft_capabilities`, `configure_minecraft_target`, `check_minecraft_resources`, and `export_minecraft_resources`. The authenticated JSON operations are `minecraft_capabilities`, `minecraft_configure`, `minecraft_check`, and `minecraft_export`; mutating operations require the observed document ID/revision. CLI checks return the report in `validation`, including `validation.passed` and `validation.validation_digest`; the same result includes the observed project in `state`. Apply targets and edit directly, then inspect resources and previews. Formal export binds real user approval to current content and the validation fingerprint. A changed dependency invalidates resource approval/export even when no artwork pixel changed.

The native editor's public `ui minecraft-editor` commands operate on drafts, inspection and apply/cancel only. They expose no approval or export action. Real native export gestures live under the **资源** menu.

## Forge 1.20.1 checks

The checker follows parent models, child-context texture aliases, model faces, item overrides, blockstate variants/multipart, texture metadata and selected atlas inputs. It distinguishes parent cycles, alias cycles, missing/case-mismatched resources, invalid JSON/PNG, stale dependencies and unsupported target features. Child item overrides are not inherited; empty child geometry uses parent elements, matching the target implementation.

Ordinary resource files use the highest source. PNG metadata can come from the PNG's source or a higher metadata-only source; metadata below a replacement PNG is not inherited. Atlas declarations combine across their source stack. Default `block`/`item` directories, single sprites, filters and paletted-permutation inputs are resolved; generated sprite names are traced back to real source PNGs and palettes rather than imaginary generated PNG files. Unsupported source/model loaders and pack filters are explicit errors. This checks asset inputs, not shader execution or the rendered appearance of generated sprites.

Metadata checks include actual frame dimensions/order/index/duration and target format. Exported animation durations must be positive integer multiples of 50 ms. Non-looping texture timelines and nonrepresentable durations are rejected without rounding. Source interpolation is checked structurally; the application's current editable playback/export remains explicit `none` interpolation. Newer `mipmap_strategy`, `alpha_cutoff_bias` and GUI sprite scaling metadata are not accepted as Forge 1.20.1 behavior.

NPOT dimensions and unknown cull-direction strings are reported as warnings rather than automatically changing valid native pixels. Unrecognized third-party model loaders, custom shaders and physical behavior require separate adapters. PixForge 2.4 provides its own Forge part/state and particle code adapter through the optional `forge-runtime/v1` capability; see [FORGE_RUNTIME.md](FORGE_RUNTIME.md). A static block/item export is blocked when it would silently discard a current scene program. An explicitly selected texture-only export reports those runtime omissions.

One check is bounded to 16 sources, 256 explicit entries, 4096 resolved files, 32 MiB per input and 128 MiB in the reference closure. Split a large project audit into entry batches. Directory/JAR sources are read in place; archives are not extracted. Dependency/runtime/skill files are never added to an asset ZIP implicitly.

## Publication and project compatibility

`resource-pack` produces a ZIP with root `pack.mcmeta` (`pack_format: 15`), selected `assets/`, and `pixforge-export.json`. `mod-assets` produces the selected `assets/` and export manifest for review before integrating into a mod's source/datagen layout. Neither installs into a game, runs datagen or modifies a source resource tree. A ZIP is prepared and validated in memory before the existing atomic file publisher replaces the chosen output.

The export manifest contains target/adapter version, asset SHA-256 values, dependency requirements, content/validation fingerprints and warnings. It excludes connection credentials and absolute local source paths. Export rechecks the source graph and requires the caller's `validation_digest` to match both the current graph and the user's approved resource fingerprint.

Unconfigured old projects keep `pixelforge.desktop/v1`, unchanged content digests and existing history. Applying a target saves configured projects as `pixelforge.desktop/v2`; a session carrying target history uses `pixelforge.session/v2`. The new app reads both versions. Old software rejects the newer schema instead of silently discarding target settings/history. Clearing the target permits a v1 project file again; the session still protects any newer undo/redo entries. The skill can update independently, and public API v1 integrations remain compatible with the newer app.

Forge runtime configuration uses an optional `runtime` object and target schema `pixforge.minecraft-project/v2`; it is explicit and uses desktop/v3 / session/v3 protection. `forge-integration` and `forge-mod` are code/resource formats, while the formats above retain their asset-only behavior. `minecraft-check --include-generated-code` provides read-only code/build previews before approval. Runtime and ordinary bindings cannot overlap silently. Full configuration, synchronization and integration contracts are in [FORGE_RUNTIME.md](FORGE_RUNTIME.md).

All results set `in_game_validated: false`. Format/reference checks do not establish registry coverage, actual rendering, game performance or visual acceptance.

Target references: [Forge resources](https://docs.minecraftforge.net/en/1.20.1/concepts/resources/), [model providers](https://docs.minecraftforge.net/en/1.20.1/datagen/client/modelproviders/), and [Mojang's resource-pack format 15 release notes](https://www.minecraft.net/en-us/article/trails-tales-update-out-today-java).
