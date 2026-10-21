# Forge 1.20.1 模组接入

软件 2.4+ 的 `forge-runtime/v1` 能力提供 Forge 部件渲染和粒子执行器。先用公开 `doctor` / `--describe` 和 `session minecraft-capabilities` 发现能力；公开 API 主版本仍为 1。skill 仅使用标准库客户端，不加载软件内部模块或 Java 模板。

先检查消费项目的 Minecraft / Forge 补丁版本、Java 17 工具链、注册方式、资源命名空间、BlockEntityType、客户端事件订阅、真实运行状态。生成示例默认测试基线为 Forge 47.2.0；用配置中的明确 `forge_version` 选择消费项目的 47.x.x。其他 MC / 加载器须对应适配器，不能改一个版本号便宣称支持。

## 配置与检查

目标配置使用 `pixforge.minecraft-project/v2`，在已有目标字段中增加可选 `runtime`；普通绑定设为 null，避免同时覆盖静态模型。通过软件 `minecraft-configure --config target.json` 应用，仍须当前 document_id/revision，配置可一次撤销。

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
    "java_package": "dev.examplemod.visuals",
    "forge_version": "47.2.0",
    "scene": {"block": "examplemod:machine", "render_type": "cutout"}
  }
}
```

绑定当前部件 / 粒子场景。场景方块 id 须属于当前模组命名空间，render_type 可选 solid/cutout/translucent。桌面“资源 → Minecraft 目标、资源与检查…”可按当前工程生成接入草稿，检查后一次应用。

同一模组合并多个导出模块时，为各模块选择不同的 java_package 和方块 id。软件据包名划分粒子、示例实体注册名和运行时定义路径。

`minecraft-check` 返回现有引用图及 `forge_runtime`：生成代码/资源哈希、模板与适配器指纹、部件模型数量，以及消费项目必须提供的状态接口。MCP 继续使用 configure_minecraft_target、check_minecraft_resources、export_minecraft_resources，无需访问私有核心。

## 审查与导出

预览当前作品与生成代码，取得真实用户确认后导出。模型、像素、场景、外部依赖或软件适配代码变化后，重新检查相关资源与当前结果；检查和编译本身不代表用户确认。

```powershell
python scripts/pixforge_client.py --app <EXE> session --workspace <项目> --runtime <会话> minecraft-export integration.zip --format forge-integration --validation-digest <本轮指纹> --expected-document-id <id> --expected-revision <revision>
```

`forge-integration` 包含 src/main/java、src/main/resources 和 FORGE_INTEGRATION.md，不带 @Mod 入口、mods.toml 或构建文件；供现有模组审查合并。`forge-mod` 另外包含示例入口、注册、ForgeGradle 构建与 mods.toml，可用已有 Java 17 / Gradle 8.8 构建并重混淆。两个格式都不直接写入消费项目、不安装模组、不启动游戏。普通 resource-pack/mod-assets 格式不能静默丢弃运行时程序。

## 实际项目接线

部件使用 BlockEntityRenderer、实际 elements/UV、关键帧与状态程序。每张原生纹理帧单独保存，支持状态固定帧、速度、非循环和毫秒时长。每个方块实体独立保存 SceneRuntime.Player，服务端驱动真实 start/stop 事件并同步完整快照及时间戳，客户端按 tick 推进，渲染仅按 partial tick 采样副本。已有模组须合并自身数据包、存档和生命周期；示例注册和右键事件只是可运行的接线例子。没有作者模型的纯粒子工程也可接入：集成包保留消费项目现有方块模型，独立示例提供无可见几何的发射方块和原生纹理图标。

粒子采用普通 Forge ParticleType / Options / 客户端 provider，保留出生姿态、速度、重力、寿命、尺寸与 RGBA 渐变；alpha 和 additive 分批渲染。tick 发射与渲染分离，状态切换保留已飞出的粒子，结束后粒子尾迹继续消亡。common 与物理客户端类分离；不要在专用服务端入口引用 RuntimeClient。若同一效果由客户端程序发射，就不要再由服务端重复发送同一批粒子。

最终须在消费项目验证编译、资源重载、专用服务端加载、跨区块更新、实际工作状态同步、晚加入、状态切换、全部纹理帧、透明排序和粒子寿命。离线报告继续标记 in_game_validated=false；本 skill 不以编译通过代替游戏内验收。

运行时目标工程使用 desktop/v3、包含该历史的会话使用 session/v3；软件 2.4+ 读取旧格式，旧软件明确拒绝新版格式。没有配置运行时的既有工程保持原格式和内容。

审查实际生成代码时，用 `minecraft-check --include-generated-code` 或 MCP include_generated_code=true。它在原指纹之外返回 generated_sources，包含 Java、可读运行时定义和各格式的接线 / 构建文件，不写出正式包、不改变修订号和确认。
