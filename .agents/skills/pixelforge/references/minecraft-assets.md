# Minecraft 目标与资源导出

需要 minecraft-assets/v1；内置目标为 Java 1.20.1 / Forge，资源格式 15。先核对项目版本、namespace、资源源集、datagen 和真实依赖。

## 配置当前工程

```json
{
  "profile": "forge-1.20.1",
  "namespace": "examplemod",
  "sources": [
    {
      "name": "vanilla",
      "path": "<客户端JAR>",
      "role": "dependency"
    },
    {
      "name": "project",
      "path": "src/main/resources",
      "role": "project"
    }
  ],
  "entries": [
    {
      "kind": "blockstate",
      "id": "examplemod:machine"
    }
  ],
  "binding": {
    "kind": "texture",
    "path": "machine",
    "texture": "block/machine"
  }
}
```

来源可为 assets 目录、含 assets 的根目录、ZIP/JAR，按低到高排序，画布绑定最高。相对路径按 workspace 解析。project 的选中引用可导出，dependency 只解析，不分发。

entries 类型为 blockstate/model/texture/atlas，检查其引用闭包。未写 namespace 的引用按 Minecraft 规则指向 minecraft。

| binding | 用途 |
|---|---|
| null | 仅检查来源入口 |
| texture | 覆盖实际纹理，保留原模型与复杂状态 |
| block | 显式模型、单模型空 variant 和方块物品引用 |
| item | 生成物品模型；纯像素需真实 minecraft:item/generated 依赖 |

执行 `minecraft check --request-file <参数.json>`：

```json
{
  "use_document": false
}
```

把上述目标对象作为 `minecraft configure` 的 `settings` 应用，settings=null 清除目标；配置可撤销。minecraft check --settings 对象 只检查草稿，use_document=false 排除画布且需显式来源入口。

## 读取诊断并验收

validation.passed/validation_digest 给出检查结果与指纹。issues 含 severity/code/resource/source；files/edges/overrides/sprites 说明引用、生效来源及生成精灵输入。普通文件按优先级覆盖，atlas 声明合并。

按实际错误修复来源或工程，保留真实父模型、复杂状态和 loader 机制。部件/粒子走 [运行时接入](forge-runtime.md)，普通资源导出不省略其运行行为。纹理动画保持源帧与时长，无法用正整数 50 ms tick 表达时须明确调整/换运行时。

## 正式导出

展示当前结果、检查和依赖后，按 [公共导出](operations.md#资源检查与正式导出) 使用真实用户确认及当前指纹：

执行 `asset export-minecraft --request-file <参数.json>`：

```json
{
  "path": "<资源ZIP>",
  "format": "resource-pack",
  "validation_digest": "<当前指纹>",
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

resource-pack 含 pack.mcmeta、选中 assets 和哈希清单；mod-assets 为供项目合入的 assets 归档。均不注册游戏对象或自动部署。

软件重新检查依赖与确认指纹。RESOURCE_VALIDATION_STALE/RESOURCE_REVIEW_REQUIRED 时核对变化并更新检查/授权。资源检查不覆盖 Java 注册全域或游戏效果。
