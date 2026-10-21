# LabPBR data materials — PixForge 2.7

The Forge 1.20.1 workflow supports explicit `labpbr-1.3` data maps. The color atlas, `_n.png` and `_s.png` share the same canvas, frame rectangles, UVs and derived frame layouts. Data maps have their own raw RGBA storage and undo history. Alpha in either data map is a material value; it never controls layer opacity.

## Desktop

Open **资源 → LabPBR 数据材质与通道…**, or run `打开LabPBR数据材质示例.cmd`. Enable LabPBR, select normal/specular and a channel, then choose **查看与检查**. The channel image is opaque grayscale, including the alpha channel. Clicking it reports all eight raw bytes and decoded meanings. Packed RGB, reconstructed normal Z and semantic views are diagnostic views. They do not show the final shader's lighting.

The default canvas tool only inspects. The numeric brush replaces the selected byte plane with an integer from 0 to 255. A complete stroke or exact rectangle is one undo entry; the other seven planes and color atlas retain their bytes. The shader/resource page imports a complete PNG or its red plane into the selected channel. Imports require the exact atlas dimensions and 8-bit PNG input; no resizing or color-profile conversion is applied. A new normal map starts at `(128,128,255,255)` and a new specular map at `(0,10,0,255)`.

Source resource inspection resolves `_n`/`_s` through the configured resource priorities and records the winning source. It stays read only. Explicit resource import refuses a source marked `dependency`; import a permitted project asset or supply a separately authorized PNG. Free canvas resizing is blocked while data maps are attached. Frame duplicate/delete/insert remaps all three atlases together, using neutral data for inserted frames.

## Exact LabPBR 1.3 meanings

| Map | Channel | Meaning |
| --- | --- | --- |
| `_n` | R | Tangent normal X, `2R/255 - 1` |
| `_n` | G | DirectX normal Y; increasing green points down |
| `_n` | B | Material AO, `B/255`; 255 is unoccluded |
| `_n` | A | Height, `A/255`; 255 is the surface, 0 is maximum depth |
| `_s` | R | Perceptual smoothness `R/255`; linear roughness is `(1-R/255)^2` |
| `_s` | G | 0..229: dielectric F0 `G/255`; 230..237: named metal; 238..254: reserved; 255: albedo metal fallback |
| `_s` | B | 0..64: porosity `B/64`; 65..255: scattering `(B-65)/190` |
| `_s` | A | 0..254: emission `A/254`; **255 means emission ignored/zero** |

Normal Z is reconstructed as `sqrt(1-dot(XY,XY))`. XY outside the unit disk blocks resource export. Zero height and reserved metal values are reported for target review and retained exactly. Named metals 230..237 are iron, gold, aluminum, chrome, copper, lead, platinum and silver. These encodings follow the [LabPBR material standard](https://shaderlabs.org/index.php?title=LabPBR_Material_Standard&oldid=935); optional features follow its [implementation requirements](https://shaderlabs.org/index.php?title=LabPBR_Implementation_Requirements&oldid=878).

## Shader target and export

The target records `name`, `version`, `loader`, `loader_version`, optional `minecraft`/`forge`, `features`, `options`, and optionally a local ZIP/directory `path` and SHA-256. Features are `normals`, `smoothness`, `f0`, `hardcoded_metals`, `ao`, `height`, `porosity`, `sss`, `emission`; values are true, false or null. A used feature explicitly declared unsupported blocks export. Missing support evidence is reported as unknown. Binding a source hashes its actual bytes and detects replacement; inspecting it does not prove support or load GLSL.

Ordinary texture bindings and Forge runtime exports derive color and data from the same layouts. Data PNGs retain RGB even at alpha zero, contain no sRGB/gamma/ICC profile, and are not alpha-composited. Data sidecars receive the animation section of `.mcmeta`.. Interpolated animations that vary specular G or B across frames are blocked because interpolation could invent another metal or material category. Forge animation expansion keeps distinct data frames even when their color frames are identical.

The pack declares `assets/minecraft/optifine/texture.properties` with `format=lab-pbr/1.3`, following the [OptiFine texture format document](https://github.com/sp614x/optifine/blob/master/OptiFineDoc/doc/texture.properties). An effective source declaring another format blocks export. Formal exports retain current review and user approval requirements. Review evidence includes all eight planes; a data or shader change invalidates earlier evidence. Editable save remains available for invalid drafts.

The included **PixForge LabPBR Probe 1.0.0** is an owned diagnostic shader with normal, AO, smoothness, F0/albedo-metal and emission sampling. It declares height/POM, named-metal tables, porosity and SSS unsupported. Its target pins OptiFine `1.20.1_HD_U_I6` and Forge `47.2.18`, the combination listed by [OptiFine downloads](https://optifine.net/downloads). The pack ZIP hash is portable; its local path is deliberately unset. Bind the actual local copy before use. The application remains a Forge 1.20.1 authoring tool; this example does not claim that OptiFine I6 works with arbitrary Forge builds. No shader or loader is installed automatically.

## Public interface

Discover `minecraft-material/v1` through `--describe`. Existing public API major 1 is retained. CLI examples below use the same absolute runtime as the GUI; mutations also require the current document/revision tokens and the application's AI workflow readiness.

```powershell
PixForgeNative.exe --cli session --runtime D:/project/.runtime/pixforge minecraft-material --role specular --channel a --pixel 2 3 --output D:/review/emission.png
PixForgeNative.exe --cli session --runtime D:/project/.runtime/pixforge minecraft-material-configure --settings '{"profile":"labpbr-1.3"}' --expected-document-id ID --expected-revision REV
PixForgeNative.exe --cli session --runtime D:/project/.runtime/pixforge minecraft-material-import --role normal --path D:/assets/normal.png --expected-document-id ID --expected-revision REV
PixForgeNative.exe --cli session --runtime D:/project/.runtime/pixforge minecraft-material-edit --role specular --channel a --operations '[{"rect":[2,3,1,1],"value":0}]' --expected-document-id ID --expected-revision REV
```

Use `@file` or `-` for JSON settings/operations when shell quoting is inconvenient. Setting material configuration to `null` clears data maps as an undoable operation. MCP provides `inspect_minecraft_material`, `configure_minecraft_material`, `import_minecraft_material`, and `edit_minecraft_material`; inspection returns JSON and a PNG. Native window automation is available through the app-owned `ui minecraft-material-editor` API. No computer-use tool is required.

## Persistence and validation scope

Configured data projects use desktop/session format v4, requiring software 2.7+. Recovery retains v4 while any undo/redo entry contains material data. Older software refuses the format rather than discarding channels. Unconfigured projects retain their prior schemas, and older v1/v2/v3 projects remain readable. Software and skill are separate packages; the standard-library skill client only calls public executable interfaces.

Opt-in Forge game regression exports observe the active OptiFine or Iris/Oculus shader API, actual shader source hash, selected option files, and resource-reload generation at capture start/end. Missing, disabled, changed or mismatched shader evidence prevents comparison. A consuming project can register an observer for its actual loader through `RegressionShader.registerObserver`. An adapter declaration or synthetic fixture is not game evidence.

Perform target acceptance with the generated game fixture/capture guide in the consuming project.
