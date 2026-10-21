# Forge 1.20.1 runtime export in PixForge 2.4

The additional `forge-runtime/v1` capability belongs to the standalone application. The skill only calls the public EXE/CLI/MCP.
Target configuration adds an optional runtime object; no existing project is assigned one automatically.

```json
{
  "schema": "pixforge.minecraft-project/v2",
  "profile": "forge-1.20.1",
  "namespace": "examplemod",
  "sources": [],
  "entries": [],
  "binding": null,
  "runtime": {
    "schema": "pixforge.forge-runtime/v1",
    "java_package": "dev.pixforge.examplemod",
    "forge_version": "47.2.0",
    "scene": {
      "block": "examplemod:machine",
      "render_type": "cutout"
    }
  }
}
```

Use the existing `session minecraft-configure --config target.json` and guarded document/revision tokens.
The native **资源 → Minecraft 目标、资源与检查…** dialog can derive a draft from the current scene. In 2.4.1, use the **Forge 接入** page for structured package/version and scene block/render-layer fields; **编辑完整 JSON…** opens the full configuration in a separate editor. The **检查结果** page separates diagnostics, files, overrides and required project hooks, and opens generated code in a read-only file viewer. These views retain the same draft, validation fingerprint and undo behavior.
`minecraft-check --include-generated-code` (MCP `check_minecraft_resources(include_generated_code=True)`) exposes the generated Java, build entry points and runtime definition before approval.
It is read only and does not write an export. The native **查看生成代码与接线说明（只读）** action provides the same draft preview.
`workflow-review` includes this code in its `minecraft.json` evidence; code/template and source dependency changes invalidate the reviewed fingerprint.

After real user acceptance, `minecraft-export result.zip --format forge-integration|forge-mod --validation-digest <digest>` publishes atomically.
The menu contains matching physical confirmation/export actions. Public draft UI commands never approve or export.
Configured runtime projects use desktop/v3; sessions with current or undo/redo runtime data use session/v3. PixForge 2.4 reads v1/v2/v3.
Older applications reject v3. Existing unconfigured and resource-only projects retain their prior formats, art digests and history.

The original combined example is in [examples/forge-runtime-1.20.1](examples/forge-runtime-1.20.1/README.md); the portable launcher is **打开Forge模组接入示例.cmd**.
It contains no source paths or game assets and is saved without export approval.

# Generated integration contract


This archive contains application-generated Java 17 source and original authored resources.
It does not install a mod, run Minecraft, change a source tree, or prove in-game behavior.
Target: Minecraft 1.20.1 / Forge 47.2.0. Package: `dev.pixforge.demo`.

## Contents and build

Mode: `forge-integration: mergeable source and resources; no mod entry point or registries are attached automatically`.
The source lives under `src/main/java`; resources live under `src/main/resources`.
The export manifest records all file hashes, dependency requirements and the approved validation fingerprint.
Do not overwrite an existing mod entry point, blockstates or resource namespace without reviewing the diff.

Use your existing Forge 1.20.1 project and its Java 17 build. Copy the generated helpers and selected resources into a review branch. Call RuntimeModule.registerParticles(modEventBus) from your common mod constructor if using the scene emitters. Do not call RuntimeModule.register, which registers the example blocks and block entity.

The standalone example registers these block/item IDs: `pixforge_demo:animated_machine`.
Obtain them with `/give @p <id>`. Right-click toggles `active` and dispatches the server-side `start`/`stop` scene event; sneak-right-click rotates by 90 degrees.
These demonstration properties and events must be connected to the consuming machine logic.

## Parts, textures and activation

The scene keeps the actual element indices, UVs, keyframes, easing, periodic tracks, named states, start/stop routes,
automatic next states, entry pose inheritance and in-flight particle carry.
Every native texture frame is a separate PNG so scene playback can hold frames, change speed, use non-looping clips,
and retain millisecond durations without relying on the global atlas clock.
The empty world model prevents a second static copy beneath the animated parts; the inventory model shows the full authored model.
If the document has particles but no authored geometry, the integration format preserves the existing block's base models;
the standalone example adds an invisible emitter block and a flat icon using the actual native texture.

Store one `SceneRuntime.Player` per block entity, created from `RuntimeData.DATA.getAsJsonObject("scene")`.
Call player.simulate(50) in each simulation tick. It advances the state and lets the finite particle tail expire after the final pose stops.
It is intentionally independent of render frame count. player.advance is also available for editor-style stopped-clock probes.
Dispatch real machine activation events on the server through player.event("start") / player.event("stop");
the boolean result indicates whether a route exists. A single clip simply follows its authored loop/non-loop definition.
Persist and synchronize `player.snapshot()` together with a server game-time epoch; restore it for late joiners and advance by the elapsed ticks.
The snapshot includes entry poses, carry particles, automatic-next progress and texture time.
SnapshotCodec stores bounded gzip JSON in an NBT byte array (4 MiB decoded / 1.5 MB compressed),
avoiding the 64 KiB NBT string limit. Player instance identities survive save/sync, and particle births are not repeated on a short chunk unload/reload.
The generated ExampleBlockEntity provides save/load, update-tag, update-packet, event and client/server ticking examples.
For an existing BE, retain its own packets, inventory, processing and lifecycle; merge only these fields and hooks.
Register a BER on the client mod bus:

```java
RuntimeClient.registerRenderer(event, MY_BE_TYPE.get(), MyBlockEntity::pixforgePlayer, MyBlockEntity::pixforgeRotation);
```

Implement SceneHost access to the player and rotation, or provide equivalent functions.
The renderer samples a copy at partial-tick time and applies each part's affine matrix and inverse-transpose normal matrix.
It does not advance the stored player, spawn particles or modify world state while rendering.
The export contains conservative bounds across all states and four block rotations. The example BE uses those bounds;
the renderer chooses a finite view distance between 64 and 256 blocks. Preserve equivalent bounds in an existing BE.

## Particles and sidedness

The common-side ProgramOptions/ParticleType and the physical-client provider are separate classes.
The provider uses a generated white sprite and the actual RGBA/size curves, velocity, gravity and remaining lifetime.
Alpha and additive particles use separate particle render batches. No custom GLSL or world collision is implied.
In a client's ticker, call RuntimeClient.tickParticles(owner, player) after its 50 ms advance.
Birth identities are per owner/state generation/cycle, so two renders do not duplicate emission and switching states retains existing particles.
Only birth position and velocity use the moving emitter pose; particles already in flight do not follow the emitter.
Already-spawned particles live in the normal particle engine and expire independently of their emitter's render visibility.
Particle settings, distance limits, lighting, depth and transparent ordering follow the running game and still need visual acceptance.
For explicit server-authored particle spawns, ProgramOptions also implements the normal codec and network contract.
Avoid both per-client program emission and server-send emission for the same effect, which would duplicate particles.

RuntimeModule, SceneRuntime, ProgramOptions and RuntimeData contain no client-class imports.
RuntimeClient is isolated by Dist.CLIENT. Keep client imports and renderer/provider calls out of dedicated-server entry points.

## Acceptance in the consuming mod

Compile with your actual Forge patch and dependencies, inspect resource/model reload, dedicated-server loading,
real state packets, join/reload behavior, all source frames,
start/stop/automatic transitions, rotated emitters, alpha/additive blending and particle expiry.
Offline parity and compilation evidence do not replace these game-side checks.
Authoritative API references: https://docs.minecraftforge.net/en/1.20.1/rendering/modelloaders/bakedmodel/ ,
https://docs.minecraftforge.net/en/1.20.1/blockentities/ber/ ,
https://docs.minecraftforge.net/en/1.20.1/gameeffects/particles/ .
