# 目标版本、资源引用与版本化导出

在准备 Minecraft 生产资源、检查资源引用或生成资源包时使用本流程。解析器和导出器属于独立软件；skill 通过公开接口选择配置、读取诊断并组织验收，不读取软件私有模块或直接修改工程文件。

先通过 `doctor` 检查软件的 `capabilities`，再调用 `session minecraft-capabilities` 或 MCP `minecraft_capabilities`。本流程需要 `minecraft-assets/v1`，目前可导出目标为 **Forge / Minecraft Java 1.20.1，资源格式 15**。旧软件缺少该能力时独立更新软件，不在 skill 中复制解析器补齐。客户端的 `--app`、连接用 `--config` 放在命令前；命令后的 `--config` 原样交给软件，表示目标配置文件。

## 配置当前工程

按当前项目的版本、namespace、源资源、datagen 输出和依赖确定设置。来源按低到高排序，当前画布绑定最后生效；`project` 来源的选中引用可以导出，`dependency` 来源只供解析、校验及记录，不重新分发。真实客户端或模组 JAR 可作为依赖，不编造原版父模型、显示变换或图集内容。

```json
{
  "profile": "forge-1.20.1",
  "namespace": "examplemod",
  "sources": [
    {"name": "vanilla", "path": "D:/reference/client-1.20.1.jar", "role": "dependency"},
    {"name": "project", "path": "src/main/resources", "role": "project"},
    {"name": "generated", "path": "src/generated/resources", "role": "project"}
  ],
  "entries": [{"kind": "blockstate", "id": "examplemod:machine"}],
  "binding": {"kind": "texture", "path": "machine", "texture": "block/machine"},
  "description": "Example resources for Forge 1.20.1"
}
```

来源可以是包含 `assets` 的目录、`assets` 本身、ZIP 或 JAR。相对路径由软件按当前 workspace 解析后保存为绝对位置；移动项目时通过接口更新来源。未限定 namespace 的引用按 Minecraft 规则指向 `minecraft`。入口类型为 `blockstate`、`model`、`texture`、`atlas`；检查范围是选中入口的引用闭包，不等于检查全部已注册状态。

`binding` 可为空，表示只检查来源入口。`texture` 适用于保留既有模型、朝向、multipart 和渲染逻辑的纹理替换；`block` 为当前显式模型生成单模型方块状态及旧版 `models/item` 引用；`item` 生成物品模型，纯像素物品需要真实的 `minecraft:item/generated` 依赖。资源包不能注册方块或修改物理行为。不要用简单 `block` 绑定覆盖已有复杂状态。

```powershell
pixelforge session --workspace <项目> --runtime <会话> minecraft-configure --config target.json --expected-document-id <id> --expected-revision <revision>
pixelforge session --workspace <项目> --runtime <会话> minecraft-check
pixelforge session --workspace <项目> --runtime <会话> minecraft-check --sources-only
```

MCP 分别使用 `configure_minecraft_target` 和 `check_minecraft_resources`。配置作为一次可撤销改动随工程保存；`minecraft-configure --clear` 清除目标。检查可传草稿 `--config`，不会应用它。`--sources-only` 排除当前画布，需要显式来源入口，适合核对当前项目实际资源和覆盖关系。

## 读取诊断并验收

检查父模型、子模型上下文中的纹理别名、方块状态和物品变体、PNG、动画元数据及图集输入。返回的 `issues` 给出 severity/code/resource/source；`files`、`edges`、`overrides` 和 `sprites` 说明引用、真实生效来源及生成精灵的输入。普通文件按来源优先级覆盖，atlas 声明合并。不能将“文件存在”“统计通过”或 `passed: true` 当作游戏内效果。

发现错误后通过软件接口修正工程，或按消费项目授权修改其资源文件，再重新检查。不通过更改目标版本、关闭检查或伪造依赖来消除错误。尚未适配的第三方模型加载器会明确报错；部件 / 粒子程序可显式配置 [Forge 运行时接入](forge-runtime.md)，普通资源导出仍拒绝静默省略这些程序；仅纹理导出可保留其独立用途，并报告未包含的运行时效果。非 2 的幂等提示需要按实际用途判断，软件不会自动缩放原图。

纹理动画导出保留帧像素、索引与时长；无法用正整数 50 ms tick 表达的时长、单次播放等情况须显式调整或选择运行时适配器，不静默取整。Minecraft 中的图集生成精灵应追踪真实 PNG 和调色板输入，不把精灵名误当作必须存在的生成后 PNG。

向用户展示当前素材与必要的资源诊断。确认绑定当前配置、像素及资源指纹，依赖文件变化后重新检查相关结果。用户已对未变版本授权时不重复询问，旧报告或 AI 自查不代替真实用户确认。

## 正式导出

```powershell
pixelforge session --workspace <项目> --runtime <会话> minecraft-export resources.zip --format resource-pack --validation-digest <本轮检查返回值> --expected-document-id <id> --expected-revision <revision>
```

MCP 使用 `export_minecraft_resources`。`resource-pack` 生成根目录 `pack.mcmeta`（格式 15）、选中 `assets` 和哈希清单；`mod-assets` 生成供项目集成前审阅的 assets 归档，不冒充可直接使用的资源包。不会自动安装、启动游戏、运行 datagen 或写入生产资源目录。

正式导出前软件重新读取依赖，并同时校验当前检查指纹和用户确认指纹。遇到 `RESOURCE_VALIDATION_STALE` 或 `RESOURCE_REVIEW_REQUIRED`，先核对变化并生成当前证据；重复提交旧令牌没有作用。失败的检查返回退出码 1，并保留结构化诊断。

旧工程未配置目标时保持原格式和内容。配置目标的工程使用新的 v2 元数据，需 PixForge 2.3+；旧软件会拒绝，避免重新保存时丢掉设置。独立更新 skill 不改变软件、工程或历史。桌面的“资源”菜单提供同一套配置、检查和导出；`ui minecraft-editor` 只操作草稿、查看和应用，不提供自动批准或导出入口。
