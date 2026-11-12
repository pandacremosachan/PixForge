# Forge 1.20.1 运行时接入

需要 forge-runtime/v1。核对消费项目 Forge 47.x.x、Java 17、namespace、注册和实际 BlockEntity 状态；使用项目明确的 forge_version。

## 配置与检查

目标为 pixforge.minecraft-project/v2，普通 binding 设 null，runtime 绑定当前场景：

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
    "scene": {
      "block": "examplemod:machine",
      "render_type": "cutout"
    }
  }
}
```

block 属于本模组 namespace；render_type 为 solid/cutout/translucent。多个模块合入同一模组时使用不同 java_package 和 block ID。

通过 minecraft configure 应用，`minecraft check --include-generated-code true` 返回 forge_runtime 指纹与 generated_sources，供只读审查 Java、定义和接线文件。

## 导出

当前作品与生成代码确认后，按 [公共导出](operations.md#资源检查与正式导出) 选择：

| 格式 | 内容 |
|---|---|
| forge-integration | src/main/java、src/main/resources、FORGE_INTEGRATION.md，无主入口/构建文件 |
| forge-mod | 额外含示例入口、注册、ForgeGradle 和 mods.toml；示例用已有 Java 17 / Gradle 8.8 构建 |

导出包供审阅合入；普通 resource-pack/mod-assets 不交付部件执行器。

## 项目接线

- 每个真实 BlockEntity 独立持有 SceneRuntime.Player，服务端用真实工作状态触发 start/stop，接存档、更新包和生命周期。客户端按 tick 推进，BER 只按 partial tick 采样副本。
- 使用真实 elements/UV 和纹理帧；纯粒子集成保留消费项目原模型。
- 粒子接 Forge ParticleType/Options/provider，保留出生姿态、速度、重力、寿命、尺寸和 RGBA；alpha/additive 分批。tick 发射与渲染分离，避免客户端/服务端重复发射。
- common 不引用物理客户端类。示例注册/右键事件仅供接线，不替代真实机器逻辑。

按项目检查编译、资源重载、专用服务端、晚加入/区块重载、状态同步、全部帧、透明排序和粒子尾迹。离线报告保留 in_game_validated=false。
