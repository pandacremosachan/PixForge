# Animation metadata and game regression

Discover `minecraft-animation/v1` and
`minecraft-regression/v1` through the independent application's `--describe`.
These additions use public API major 1. The skill remains a standard-library
client: parsing, drawing, code generation, measurements, and packaging belong to
the application. Older compatible software still handles its existing commands;
missing capabilities require an independent software update.

For Minecraft 1.20.1 `.mcmeta`, call `session minecraft-animation --metadata
file.png.mcmeta --time-ms 50 --output sample.png`, or MCP
`inspect_minecraft_animation`. The software reads the actual current PNG grid,
frame dimensions/order, default/per-frame tick durations and RGB interpolation.
Read-only inspection does not import pixels or retime the document. Apply using
`minecraft-animation-apply` / `configure_minecraft_animation` with current document
tokens after reviewing the proposed timing; it is one undo step. The normal
document timing and `texture_animation.interpolate` are exported together.
Minecraft texture steps must be positive whole 50 ms ticks; do not round timing.

The atlas clock is shared across blocks. Machine start/stop must call one
`InstanceState` owned by the real BlockEntity, on the server. Feed actual machine
activation into `setActive(boolean)`; repeated values do not restart a state.
Authored programs use their event routes; a single clip holds parts/texture on
stop, lets existing particles expire and resumes its held phase. Bind save/load,
update tags/packets and ticking to that same owner. Select pause or bounded
catch-up after unload, and a synchronization interval, through the application.
The BER samples a copy and never emits particles or advances the stored clock.
Do not replace real formation/process state with the example block's switches.

Use `minecraft-performance` / `inspect_minecraft_performance` for whole-scene
counts of source/frame pixels, raw mip memory, material layers, dynamic parts,
sampled particles and multiple instance counts. Texture storage is shared between
instances. Optional `coverage_view` is a controlled viewport's depth-passing alpha
coverage. Reference renderer time, estimated submissions and sampled peaks do not
establish game FPS, GPU time or a continuous particle maximum.

For game evidence, enable `runtime.regression` in a reviewed Forge export. The
application generates an opt-in operator fixture command, fixed-view presets,
client frame/CPU capture, actual framebuffer PNGs and bounded log tails. It does
not start a game or modify a world. Execute game/world commands only within the
consumer project's authorization. Follow the generated `GAME_REGRESSION.md` and
`PIXFORGE_REGRESSION.json`, including many machines, distance/directions,
lighting/background, state and orientation cases, chunk reload/late join,
start/stop tails and F3+T resource reload logs.

Compare supplied captures with `minecraft-regression-compare BASELINE CANDIDATE
--budgets '{"pixel_threshold":0,"changed_fraction":0,"p95_ratio":1.1}'` or MCP
`compare_minecraft_regression`. The software checks hashed attachments and matching
camera, options, loaded block states, lighting and animation phases before a
visual pass. Set budgets for the project. CPU event/BER measurements are separate
from paced frame intervals; GPU timestamps are unavailable. Report exactly which
cases were actually captured. A numerical probe, source compilation or editor
preview does not constitute completed game-side acceptance.
