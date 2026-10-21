# 定义一个物品

适用于材料、零件、图标式物品以及工具外观。完整游戏物品包括注册和行为；改一张 PNG 或把模型 parent 改成 handheld 都不能实现工具功能。

## 输入和产出

确定实际 namespace/name、目标版本/加载器、已有注册或新注册、材料图标/手持工具/三维模型、原生尺寸、透明轮廓、风格、tint/物品属性/自定义渲染机制、堆叠或耐久行为。修改现有物品时先保留其模型覆盖、属性和颜色来源。

产出为 .pixforge、原生透明 PNG、真实物品模型，以及任务要求的注册、语言和获取方式。无需物理碰撞定义。

## 平面物品的完整操作

按 [操作约定](../operations.md) 建立 c、s、D。新起步模板使用真实原版客户端依赖；示例路径须替换为已有文件，不自行下载或伪造 minecraft:item/generated。

```text
python <skill-dir>/scripts/scaffold.py item --output <D> --namespace examplemod --name crystal --dependency <真实1.20.1客户端JAR>
```

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "pixels", "--width", p["width"], "--height", p["height"])
s = c.write(s, "edit", D / "draw.px", "--label", "物品轮廓与材质")
c.read("preview", "--output", D / "item-preview.png", "--scale", "8")
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
check = c.read("minecraft-check")
assert check["validation"]["passed"]
s = check["state"]
digest = check["validation"]["validation_digest"]
s = c.write(s, "save", D / "crystal.pixforge")
```

实际查看原尺寸和透明背景，先保证轮廓、负形和方向可读，再补高光。模板图案只是一片演示晶体，不把它作为所有材料默认形状。若相邻资源依赖自动材料图标系统，优先接入该系统的形状/调色板入口。

需要检查物品实际持握和显示时，使用 Minecraft 预览并指定 view.json：

```json
{"subject":{"kind":"model","id":"examplemod:item/crystal"},"context":"gui"}
```

```python
c.read("minecraft-preview", "--output", D / "gui-preview.png", "--options", "@" + str(D / "view.json"))
```

把 context 改为 ground、fixed、firstperson_righthand 或 thirdperson_righthand 检查所需视图。深浅背景检查和颜色对照可用宿主图像查看工具或 MCP preview 的 backgrounds 参数；保持透明 PNG 的实际 alpha。预览成功仍不代表游戏颜色处理、属性覆盖或自定义渲染已经生效。

## 手持工具与属性分支

工作台 item 绑定的纯像素默认模型使用 generated。需要 handheld、自定义 display、overrides 或 tint 时，将真实 item 模型保留在项目来源，改用 texture 绑定。以下 JSON 是单纯手持外观的模型输入；依赖中必须能解析 minecraft:item/handheld：

```json
{
  "parent":"minecraft:item/handheld",
  "textures":{"layer0":"examplemod:item/crystal"}
}
```

将它放在一个 project 来源的 `assets/examplemod/models/item/crystal.json`；target 的 sources 加入该来源，entries 增加 `{"kind":"model","id":"examplemod:item/crystal"}`，binding 改为 `{"kind":"texture","path":"crystal","texture":"item/crystal"}`。重新应用 target、检查并预览。已有复杂模型直接沿用实际文件，不用上面的简化 JSON 覆盖。

真实工具行为用消费项目已有的工具类、tier/组件和注册体系实现；不要把演示晶体注册为普通 Item 后宣称它拥有挖掘或攻击语义。Forge 1.20.1 的基础接线见 [静态对象接入](../forge-static.md)；其他版本沿用其项目 API。

## 三维物品分支

按 [模型与形状](model-shapes.md) 创建或导入真实单图集模型；不执行无关的碰撞导出。target binding 选择 item，texture 使用 item/name，模型 display 按物品使用场景配置。多贴图、未解析父模型、自定义 loader 或骨骼机制不能直接塞进当前单图集编辑器；保留来源，用 texture 绑定或项目适配器处理。

## 交付和完成标准

展示当前 PNG、物品模型视图、资源检查和预期文件清单，再按 [正式导出](../operations.md#资源检查与正式导出) 取得/沿用真实批准，导出 mod-assets。通常输出：

```text
assets/<namespace>/textures/item/<name>.png
assets/<namespace>/models/item/<name>.json
```

新注册对象另完成 [静态对象接入](../forge-static.md)，合并语言、标签/配方或创造模式入口，按实际项目构建；不自动启动游戏。检查物品 ID、纹理引用、原尺寸、透明留白、展示变换、工具行为范围，以及 datagen 是否会覆盖输出。缺父模型时补真实依赖，不能建同名空模型让引用检查通过。
