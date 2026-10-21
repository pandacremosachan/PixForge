"""Application-owned Forge 1.20.1 code/resource adapter. Never deploys to a mod."""
from copy import deepcopy
import base64
import io
import json
import math
from pathlib import Path
import re
import zipfile

from PIL import Image

from .document import StudioError
from .minecraft_resources import encode, digest
from .minecraft_target import namespace, resource_id, location
from .image_bytes import png

SCHEMA = "pixforge.forge-runtime/v1"
CAPABILITY = "forge-runtime/v1"
RENDER_TYPES = ("solid", "cutout", "translucent")
FORGE_VERSION = "47.2.0"
TEMPLATES = Path(__file__).with_name("forge_templates")
JAVA_RESERVED = set("abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null record sealed permits var yield".split())


def fail(message, code="INVALID_FORGE_RUNTIME"):
    raise StudioError(message, code)


def normalize(value, domain):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"schema", "java_package", "forge_version", "scene", "regression"} or value.get("schema", SCHEMA) != SCHEMA:
        fail("Forge 接入配置仅包含 schema/java_package/forge_version/scene/regression")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", domain):
        fail("Forge 模组 id 须为 2..64 位小写字母、数字或下划线，且以字母开头")
    package = value.get("java_package", "dev.pixforge." + domain)
    if not isinstance(package, str) or len(package) > 160 or any(not re.fullmatch(r"[a-z][a-z0-9_]*", part) or part in JAVA_RESERVED for part in package.split(".")):
        fail("java_package 使用合法的小写 Java 包名，不使用关键字")
    version = value.get("forge_version", FORGE_VERSION)
    if not isinstance(version, str) or not re.fullmatch(r"47\.[0-9]{1,3}\.[0-9]{1,3}", version):
        fail("Forge 1.20.1 接入只接受明确的 47.x.x 版本")
    def binding(raw, label):
        if not isinstance(raw, dict) or set(raw) - {"block", "render_type", "lifecycle"}:
            fail(label + " 仅包含 block/render_type")
        block = resource_id(raw.get("block"))
        if block.split(":", 1)[0] != domain:
            fail("生成的方块接入须属于当前模组命名空间；外部模组需在其自身项目配置接入")
        render_type = raw.get("render_type", "cutout")
        if render_type not in RENDER_TYPES:
            fail("render_type 使用 solid/cutout/translucent")
        result = {"block": block, "render_type": render_type}
        if "lifecycle" in raw:
            option = raw["lifecycle"]
            if not isinstance(option, dict) or set(option)-{"unloaded", "max_catch_up_ticks", "sync_interval_ticks"}:
                fail("lifecycle 使用 unloaded/max_catch_up_ticks/sync_interval_ticks")
            policy, limit, interval = option.get("unloaded", "pause"), option.get("max_catch_up_ticks", 2400), option.get("sync_interval_ticks", 20)
            if policy not in ("pause", "catch_up") or type(limit) is not int or not 0 <= limit <= 2400 or type(interval) is not int or not 1 <= interval <= 1200:
                fail("卸载策略 pause/catch_up，补时 0..2400 tick，同步间隔 1..1200 tick")
            result["lifecycle"] = {"unloaded": policy, "max_catch_up_ticks": limit, "sync_interval_ticks": interval}
        return result

    scene = value.get("scene")
    scene = binding(scene, "场景") if scene is not None else None
    if scene is None:
        fail("Forge 接入需要绑定部件 / 粒子场景")
    result = {"schema": SCHEMA, "java_package": package, "forge_version": version,
              "scene": scene}
    if "regression" in value:
        if type(value["regression"]) is not bool: fail("regression 须为布尔值")
        result["regression"] = value["regression"]
    return result


def _remap_model(model, texture):
    result = deepcopy(model)
    result.pop("parent", None)
    result.pop("overrides", None)
    result["textures"] = {key: value if value.startswith("#") else texture for key, value in result.get("textures", {}).items()}
    result["textures"]["particle"] = texture
    for element in result.get("elements", []):
        for face in element.get("faces", {}).values():
            # Part rendering has no static neighbor culling. Bake every authored face.
            face.pop("cullface", None)
            if not face["texture"].startswith("#"):
                face["texture"] = texture
    return result


def build(document, config):
    """Return asset overlay, graph entries, generated integration files and diagnostics."""
    runtime = config["runtime"]
    domain = config["namespace"]
    module_id = "pf_"+digest(runtime["java_package"].encode("utf-8"))[:16]
    files, entries, code, issues = {}, [], {}, []

    def issue(name, message, severity="error"):
        issues.append((name, message, severity))

    if runtime["scene"] is None and document.scene_animation is not None:
        issue("FORGE_SCENE_NOT_BOUND", "当前工程包含场景程序，须显式绑定场景方块，不能静默省略动画或粒子")
    if runtime["scene"] is not None and document.scene_animation is None:
        issue("FORGE_SCENE_REQUIRED", "场景接入需要当前工程的实际场景程序")
    if document.scene_animation is not None and document.scene_animation["target"] != {"loader": "forge", "minecraft": "1.20.1"}:
        issue("FORGE_SCENE_TARGET", "场景目标与 Forge / Minecraft 1.20.1 不一致，不自动转换")
    if config["binding"] is not None:
        issue("FORGE_RUNTIME_STATIC_BINDING", "运行时接入使用显式的场景方块绑定；请清除普通纹理 / 方块 / 物品绑定，避免双重覆盖")
    if issues:
        return files, entries, code, issues, {}
    animation = document.animation
    atlas = document.canvas.composite()
    frames = [atlas.crop((x, y, x+w, y+h)) for x, y, w, h in animation["rectangles"]]
    part_models = []
    model_bounds = [0, 0, 0, 1, 1, 1]
    scene_geometry = False
    if runtime["scene"] is not None:
        from .minecraft_animation import expanded
        try:
            frames, animation = expanded(document)
        except StudioError as error:
            issue("FORGE_INSTANCE_TEXTURE_ANIMATION", str(error))
            return files, entries, code, issues, {}
        model = document.shapes["model"] or {"textures": {}, "elements": []}
        scene_geometry = bool(model.get("elements"))
        if not scene_geometry and any(clip["transforms"] for clip in _clips(document.scene_animation)):
            issue("FORGE_MODEL_REQUIRED", "场景接入需要带实际 elements 和 UV 的当前模型")
            return files, entries, code, issues, {}
        if len(model["elements"])*len(frames) > 1024:
            issue("FORGE_PART_MODEL_BUDGET", "场景部件 × 原生帧数量超过 1024，请拆分工程")
            return files, entries, code, issues, {}
        from .shape_preview import mesh
        from .scene_animation import point_bounds
        geometry = mesh(model)
        low, high = [0, 0, 0], [16, 16, 16]
        for element_index in range(len(model["elements"])):
            points = [point for face in geometry if face["element"] == element_index for point in face["vertices"]]
            if not points:
                continue
            lo, hi = point_bounds(document.scene_animation, element_index,
                [min(point[i] for point in points) for i in range(3)], [max(point[i] for point in points) for i in range(3)])
            low = [min(a, b) for a, b in zip(low, lo)]
            high = [max(a, b) for a, b in zip(high, hi)]
        if any(not math.isfinite(v) or abs(v) > 1e30 for v in low+high):
            issue("FORGE_POSE_FLOAT_RANGE", "组合部件变换的保守边界超出目标浮点范围；请减少连续缩放 / 大幅变换")
            return files, entries, code, issues, {}
        corners = [(x, z) for x in (low[0], high[0]) for z in (low[2], high[2])]
        rotated = []
        for x, z in corners:
            x, z = x-8, z-8
            rotated.extend([(x+8, z+8), (z+8, 8-x), (8-x, 8-z), (8-z, x+8)])
        model_bounds = [(min(x for x, z in rotated)-1)/16, (low[1]-1)/16, (min(z for x, z in rotated)-1)/16,
                        (max(x for x, z in rotated)+1)/16, (high[1]+1)/16, (max(z for x, z in rotated)+1)/16]
        path = runtime["scene"]["block"].split(":", 1)[1]
        for index, frame in enumerate(frames):
            texture = f"{domain}:block/pixforge_scene/{path}/frame_{index}"
            files[location("texture", texture)] = png(frame)
            entries.append({"kind": "texture", "id": texture})
            row = []
            for element_index, element in enumerate(model["elements"]):
                identifier = f"{domain}:block/pixforge_scene/{path}/frame_{index}_part_{element_index}"
                part = _remap_model(model, texture)
                part["elements"] = [part["elements"][element_index]]
                files[location("model", identifier)] = encode(part)
                entries.append({"kind": "model", "id": identifier})
                row.append(identifier)
            part_models.append(row)
        # Empty world model prevents a static copy beneath the animated parts.
        # The separate item model shows the complete authored model at its first frame.
        block_id = runtime["scene"]["block"]
        model_id = domain + ":block/" + path
        texture = f"{domain}:block/pixforge_scene/{path}/frame_0"
        if scene_geometry:
            files[location("model", model_id)] = encode({"textures": {"particle": texture}, "elements": []})
            files[location("blockstate", block_id)] = encode({"variants": {"": {"model": model_id}}})
            item_id = domain + ":item/" + path
            files[location("model", item_id)] = encode(_remap_model(model, texture))
            entries += [{"kind": "blockstate", "id": block_id}, {"kind": "model", "id": item_id}]
        else:
            issue("FORGE_PARTICLE_ONLY_SCENE", "当前场景仅有粒子，没有作者模型。接入包保留消费项目现有外观；独立示例使用无可见几何的发射方块和原生纹理物品图标。", "warning")
    if document.scene_animation is not None and any(clip["emitters"] for clip in _clips(document.scene_animation)):
        files[f"assets/{domain}/textures/particle/pixforge_white.png"] = png(Image.new("RGBA", (1, 1), (255, 255, 255, 255)))
        files[f"assets/{domain}/particles/{module_id}_program.json"] = encode({"textures": [domain+":pixforge_white"]})
        entries.append({"kind": "texture", "id": domain+":particle/pixforge_white"})
    definition_path = f"assets/{domain}/pixforge/{module_id}/runtime.json"
    runtime_data = {"schema": SCHEMA, "mod_id": domain, "module_id": module_id, "configuration": runtime,
        "scene": deepcopy(document.scene_animation), "animation": deepcopy(animation),
        "part_models": part_models,
        "element_count": len((document.shapes["model"] or {}).get("elements", [])), "scene_geometry": scene_geometry, "model_bounds": model_bounds,
        "view_distance": max(64, min(256, math.ceil(max(abs(v) for v in model_bounds)+16)))}
    if getattr(document,'material_data',None) is not None:
        from .material_data import summary,shader_probe
        runtime_data['material_contract']=summary(document.material_data)
        shader=runtime_data['material_contract'].get('target')
        if shader:
            if shader.get('path') and not shader.get('sha256'):
                try:shader['sha256']=shader_probe(shader).get('sha256')
                except (OSError,ValueError,zipfile.BadZipFile):pass
            shader.pop('path',None)
    files[definition_path] = encode(runtime_data)
    if runtime.get("regression"):
        from .minecraft_regression import fixture_files
        files.update(fixture_files(runtime_data))
    code = _sources(runtime_data)
    # Include all non-reference resource inputs and code in the reviewed fingerprint.
    all_generated = {**files, **code}
    if len(all_generated) > 4096 or sum(map(len, all_generated.values())) > 128*1024*1024:
        issue("FORGE_EXPORT_BUDGET", "Forge 接入超过 4096 个文件或 128 MiB，请拆分工程")
    requirements = []
    issue("FORGE_PROJECT_BINDING", "接入包包含真实 Forge 代码和示例注册；现有模组须按接入接口提供真实服务端状态。当前未执行游戏内验收。", "warning")
    metadata = {"schema": SCHEMA, "capability": CAPABILITY, "adapter_version": 3,
        "module_id": module_id, "runtime_definition_path": definition_path,
        "forge_version": runtime["forge_version"], "java_release": 17,
        "formats": ["forge-integration", "forge-mod"], "part_models": sum(map(len, part_models)),
        "states": len(document.scene_animation.get("states", [])) if document.scene_animation else 0,
        "scene_geometry": scene_geometry,
        "required_project_hooks": requirements, "generated_files": {name: digest(raw) for name, raw in sorted(all_generated.items())},
        "runtime_template_sha256": {p.name: digest(p.read_bytes()) for p in sorted(TEMPLATES.glob("*.java"))},
        "adapter_source_sha256": digest(Path(__file__).read_bytes()),
        "format_files": {mode: {name: digest(raw) for name, raw in sorted(project_files(config, standalone=mode == "forge-mod", scene_geometry=scene_geometry).items())}
                         for mode in ("forge-integration", "forge-mod")},
        "in_game_validated": False}
    return files, entries, code, issues, metadata


def _clips(scene):
    return scene["states"] if "states" in scene else [scene]


def _sources(data):
    package = data["configuration"]["java_package"]
    folder = "src/main/java/"+package.replace(".", "/")+"/"
    files = {}
    for path in sorted(TEMPLATES.glob("*.java")):
        if path.stem.startswith("Regression") and not data["configuration"].get("regression"):
            continue
        files[folder+path.name] = path.read_text(encoding="utf-8").replace("@PACKAGE@", package).replace("@MODID@", data["mod_id"]).encode("utf-8")
    raw = base64.b64encode(encode(data)).decode("ascii")
    pieces = ",\n        ".join(json.dumps(raw[i:i+4000]) for i in range(0, len(raw), 4000))
    files[folder+"RuntimeData.java"] = ("package "+package+";\nimport com.google.gson.*;\nimport java.nio.charset.StandardCharsets;\nimport java.util.Base64;\n"
        "public final class RuntimeData {\n    private RuntimeData() {}\n    public static final String MODID = "+json.dumps(data["mod_id"])+";\n"
        "    public static final JsonObject DATA = JsonParser.parseString(new String(Base64.getDecoder().decode(String.join(\"\", new String[]{\n        "+pieces+"\n    })), StandardCharsets.UTF_8)).getAsJsonObject();\n}\n").encode()
    return files


def project_files(config, *, standalone, scene_geometry=True):
    """Format-specific entry point/build files; never alter a consumer source tree."""
    runtime, domain = config["runtime"], config["namespace"]
    package = runtime["java_package"]
    files = {}
    if standalone:
        folder = "src/main/java/"+package.replace(".", "/")+"/"
        files[folder+"PixForgeExampleMod.java"] = ("package "+package+";\nimport net.minecraftforge.fml.common.Mod;\nimport net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;\n"
            "@Mod(RuntimeData.MODID)\npublic final class PixForgeExampleMod {\n    public PixForgeExampleMod() { RuntimeModule.register(FMLJavaModLoadingContext.get().getModEventBus()); }\n}\n").encode()
        files["settings.gradle"] = b"pluginManagement { repositories { gradlePluginPortal(); maven { url = 'https://maven.minecraftforge.net/' } } }\nrootProject.name = 'pixforge-forge-1.20.1'\n"
        files["build.gradle"] = ("plugins { id 'java'; id 'net.minecraftforge.gradle' version '6.0.36' }\n"
            "version = '1.0.0'\ngroup = '"+package+"'\njava.toolchain.languageVersion = JavaLanguageVersion.of(17)\n"
            "minecraft { mappings channel: 'official', version: '1.20.1' }\nrepositories { mavenCentral() }\n"
            "dependencies { minecraft 'net.minecraftforge:forge:1.20.1-"+runtime["forge_version"]+"' }\n"
            "tasks.withType(JavaCompile).configureEach { options.encoding = 'UTF-8'; options.release = 17 }\n"
            "jar.finalizedBy('reobfJar')\n").encode()
        files["gradle.properties"] = b"org.gradle.jvmargs=-Xmx3G\norg.gradle.daemon=false\norg.gradle.java.installations.auto-download=false\n"
        files["src/main/resources/META-INF/mods.toml"] = ("modLoader=\"javafml\"\nloaderVersion=\"[47,)\"\nlicense=\"All Rights Reserved\"\n"
            "[[mods]]\nmodId=\""+domain+"\"\nversion=\"1.0.0\"\ndisplayName=\"PixForge generated example\"\n"
            "description='''Generated Forge integration example; no game validation claimed.'''\n"
            "[[dependencies."+domain+"]]\nmodId=\"forge\"\nmandatory=true\nversionRange=\"[47.2.0,48)\"\nordering=\"NONE\"\nside=\"BOTH\"\n"
            "[[dependencies."+domain+"]]\nmodId=\"minecraft\"\nmandatory=true\nversionRange=\"[1.20.1,1.20.2)\"\nordering=\"NONE\"\nside=\"BOTH\"\n").encode()
        if runtime["scene"] and not scene_geometry:
            path = runtime["scene"]["block"].split(":", 1)[1]
            model_id = domain+":block/"+path
            texture = f"{domain}:block/pixforge_scene/{path}/frame_0"
            prefix = "src/main/resources/"
            files[prefix+location("model", model_id)] = encode({"textures": {"particle": texture}, "elements": []})
            files[prefix+location("blockstate", runtime["scene"]["block"])] = encode({"variants": {"": {"model": model_id}}})
            icon = {"textures": {"image": texture}, "elements": [{"from": [0, 0, 8], "to": [16, 16, 8],
                "faces": {side: {"texture": "#image", "uv": [0, 0, 16, 16]} for side in ("north", "south")}}]}
            files[prefix+location("model", domain+":item/"+path)] = encode(icon)
    files["FORGE_INTEGRATION.md"] = integration_guide(config, standalone=standalone).encode("utf-8")
    return files


def integration_guide(config, *, standalone):
    runtime, domain = config["runtime"], config["namespace"]
    package = runtime["java_package"]
    blocks = []
    if runtime["scene"]:
        blocks.append(runtime["scene"]["block"])
    return f"""# PixForge Forge 1.20.1 integration

This archive contains application-generated Java 17 source and original authored resources.
It does not install a mod, run Minecraft, change a source tree, or prove in-game behavior.
Target: Minecraft 1.20.1 / Forge {runtime['forge_version']}. Package: `{package}`.

## Contents and build

Mode: `{'forge-mod: standalone example mod' if standalone else 'forge-integration: mergeable source and resources; no mod entry point or registries are attached automatically'}`.
The source lives under `src/main/java`; resources live under `src/main/resources`.
The export manifest records all file hashes, dependency requirements and the approved validation fingerprint.
Do not overwrite an existing mod entry point, blockstates or resource namespace without reviewing the diff.

{'Use an existing JDK 17 and Gradle 8.8: `gradle --no-daemon build`. The pinned ForgeGradle 6.0.36 resolves official mappings and target dependencies. No JDK, Gradle, Minecraft JAR or dependency libraries are redistributed here. Only the build task is required; no runClient/runServer task is invoked. The reobfuscated mod JAR is produced under build/libs.' if standalone else 'Use your existing Forge 1.20.1 project and its Java 17 build. Copy the generated helpers and selected resources into a review branch. Call RuntimeModule.registerParticles(modEventBus) from your common mod constructor if using the scene emitters. Do not call RuntimeModule.register, which registers the example blocks and block entity.'}

The standalone example registers these block/item IDs: {', '.join('`'+b+'`' for b in blocks)}.
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

Store one `SceneRuntime.Player` per block entity, created from `RuntimeData.DATA.getAsJsonObject(\"scene\")`.
Call player.simulate(50) in each simulation tick. It advances the state and lets the finite particle tail expire after the final pose stops.
It is intentionally independent of render frame count. player.advance is also available for editor-style stopped-clock probes.
Dispatch real machine activation events on the server through player.event(\"start\") / player.event(\"stop\");
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
"""
