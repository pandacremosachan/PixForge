# Forge 1.20.1 模组接入示例

这是软件自带的原创合成工程，包含三个模型部件、启动/运行/停止状态和 alpha / additive 粒子。打开 `runtime-demo.pixforge`，在“模型与形状”页播放完整流程或切换状态。

“资源 → Minecraft 目标、资源与检查…”提供场景接入草稿及只读生成代码预览。示例绑定 `pixforge_demo:animated_machine`，右键切换 active 并触发 start/stop，潜行右键改变朝向。真实工作状态和同步由消费项目接入。

接入包包含 Java 17 源码及资源；独立示例模组还包含注册与 ForgeGradle 构建。工程未批准正式导出，未自动安装模组或启动游戏。具体接口和验证范围见 `FORGE_RUNTIME.md`。
