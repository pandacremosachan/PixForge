# Minecraft animation and whole-scene regression in PixForge 2.8

The standalone application owns these capabilities. The companion skill uses the
public EXE/CLI/MCP only. Public API major 1 is unchanged; additional capabilities
are `minecraft-animation/v1` and `minecraft-regression/v1`.
The native entry is **资源 → Minecraft 动画与场景回归…**.
Inspection and previews are read only. Applying settings uses the same document
tokens, undo history and save/recovery mechanism as the existing editors.
Formal asset/code export retains its current-version review/approval checks.

## 1. Atlas metadata and actual machine instances

`session minecraft-animation --metadata texture.png.mcmeta --time-ms 50
--output sample.png` reads a draft against the current PNG canvas. Width-only,
height-only, default square sizing, row-major frame indices, default `frametime`,
explicit frame durations, repeated/skipped frames and RGB interpolation use the
Minecraft 1.20.1 rules. A missing/empty `frames` list uses every frame. The source
PNG must be divisible by the declared frame size. Invalid indices/timing are
rejected instead of being silently removed or rounded. Unknown animation fields
are rejected; non-animation metadata of external resource sources is not rewritten.

`session minecraft-animation-apply --metadata texture.png.mcmeta
--expected-document-id ID --expected-revision REV` imports timing and interpolation
in one undo step. Pixel bytes remain unchanged. A configured Minecraft target is
required. Native document timing holds dimensions/rectangles/order/duration;
`texture_animation: {"interpolate": true}` on the Minecraft target selects game
interpolation. `.mcmeta` export repacks declared frames into a vertical strip and
preserves their indices/timing. It requires looping positive whole 50 ms ticks.
The workbench can inspect a draft before applying it, or load an actual `.mcmeta`.
MCP equivalents are `inspect_minecraft_animation` and
`configure_minecraft_animation`.

The renderer samples interpolation on whole game ticks. Only RGB channels are
mixed, and the current source frame's alpha is preserved. The Minecraft preview
uses this same rule. For the BER's independent machine
texture clock, the exporter materializes finite interpolated tick samples as
separate native PNGs and remaps its private runtime plan. A bounded 4096-tick /
16M-pixel expansion and the existing part-model budget prevent accidental huge
exports. This does not make a shared atlas sprite an instance-controlled sprite.

The generated common-side `InstanceState` belongs to exactly one BlockEntity. It
owns that instance's `SceneRuntime.Player`, activation edge, revision and epoch.
Feed the real machine's server state into `setActive(boolean)` after formation /
process evaluation. Repeated true/false values do not restart a state or recreate
particle births. Authored state programs retain their start/stop routes. A single
clip begins stopped, holds its parts/texture on stop, lets existing particles
expire, and resumes its held phase; a completed nonloop clip starts a fresh cycle.

Example integration for an existing BE (retain its inventories, packets and code):

```java
private final InstanceState visual = new InstanceState(SCENE, LIFECYCLE);

// Server onLoad, after the BE has a level:
visual.onLoad(level.getGameTime());
// Each server simulation tick:
if (visual.setActive(actualMachineIsFormedAndProcessing())) sendOwnUpdate();
if (visual.tick(level.getGameTime(), false)) sendOwnUpdate();
// Existing disk save/load:
visual.save(tag, level.getGameTime());
visual.load(tag, false, 0); // defer unload policy until onLoad
// Existing client packet callback/ticker:
visual.load(tag, true, level.getGameTime());
visual.tick(level.getGameTime(), true);
RuntimeClient.tickParticles(this, visual.player());
```

Use `visual.player()` for the registered BER accessor. Render frames sample a
copy, never mutate the stored player or spawn particles. Snapshots retain poses,
texture phase, carried/suspended particles and stable birth identities. Bounded
gzip NBT avoids string limits. Packet revision checks reject duplicate/stale
updates; parsing into a candidate player makes failed packet restores atomic.
The generated example shows the complete save/load, update tag/packet, tick and
onLoad hooks, plus periodic server correction.

Optional `runtime.scene.lifecycle` config:

```json
{"unloaded":"pause","max_catch_up_ticks":2400,"sync_interval_ticks":20}
```

`pause` resumes the saved clock; `catch_up` advances by elapsed server game time,
capped at 0..2400 ticks. Client packets compensate their own transit time. Both
simulation and catch-up use bounded game-time tick durations, independently of render FPS.
No structure formation or machine processing is inferred by the example.

## 2. Whole-scene budget and actual game evidence

`session minecraft-performance --options @budget.json`, or MCP
`inspect_minecraft_performance`, returns source/frame pixel counts, unique RGBA
frames, raw mip-chain bytes, material layers, dynamic parts,
emitters and particles sampled across authored states/times. Instance scenarios
accept 1..4096 machines. Shared textures are counted once; per-instance geometry,
dynamic parts and sampled particles scale separately. Submission counts precede
game culling/batching and are not GPU draw calls. Sampled particle peaks are not
proven continuous maxima. No game FPS is inferred.

Options may include `coverage_view` using the existing Minecraft view schema.
It returns a controlled viewport PNG, depth-passing fragments per layer, blended
screen fraction, mean/max visible blend depth and reference CPU wall time. These
values are labelled as reference observations, separate from game performance.
Source-resolved model views can be used instead of the current document.

Enable `runtime.regression: true` to include buildable game-side fixture/capture
code, `PIXFORGE_REGRESSION.json` and `GAME_REGRESSION.md` in a normal reviewed Forge
export. No game is launched and no world is changed during loading. An operator
may explicitly invoke the bounded empty-volume `pixforge_fixture place` command
and fixed-view presets. The capture command warms 60 frames and measures 30..600
real frames before writing a real framebuffer PNG, JSON metadata and a bounded
latest.log tail under the game's own `pixforge-regression` directory. It records
renderer, versions/mod list, camera/options, loaded fixture states/phases/light,
resource reload generation/hash, frame intervals, CPU render-event/BER timings,
visible instance/part submissions and the game's particle count. GPU timestamps
are unavailable; frame intervals include vsync/FPS caps and background load.

Compare **actual** captured directories with:

```text
session minecraft-regression-compare BASELINE CANDIDATE --budgets "{...}"
```

The default explicit budgets are pixel threshold 0, changed fraction 0, p95 time
ratio 1.1. MCP exposes `compare_minecraft_regression`; the native workbench has
capture directory and budget fields. The comparer verifies PNG/log hashes, fixed
view/options, loaded state/lighting and animation phases, then reports pixel and
timing deltas. Incomparable contexts cannot pass. A bounded log tail is evidence
for that range, not proof that the entire game log is clean. The reload listener
records this module's observed resources; check the actual reload outcome/logs.
Use the fixture `states freeze` command to hold a selected phase (wait for particle tails to expire), and `states resume` to continue. Use matching held/paused phases for reproducible animated screenshots, and repeat
active timing trials separately.

The supplied plan covers many machines, near/far views, four directions,
day/night, light/dark backgrounds, active/stopped instances, chunk boundaries,
unload/reload, late join and activation/tail behavior. The final result must name
the cases actually executed.

## Examples, independent packages, and primary contracts

`examples/forge-runtime-678-1.20.1` contains original machine and metadata
authoring examples, with no game/third-party source assets. New portable launchers
open dedicated example sessions. Existing projects, artwork, history and launchers
are retained. Software 2.8 and companion skill 1.7 are installed/updated/packaged
separately; the software runs without the skill or source checkout.

Primary contracts: the caller-supplied Minecraft 1.20.1 / Forge 47 API sources and
[Forge BER lifecycle](https://docs.minecraftforge.net/en/1.20.1/blockentities/ber/).
Research source and third-party example pixels are never included in the release.
