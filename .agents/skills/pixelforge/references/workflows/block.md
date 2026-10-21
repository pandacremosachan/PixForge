# 定义一个方块

适用于新建普通静态方块的完整外观；复杂朝向、multipart 或现有机器的换皮使用 [替换已有材质](replace-texture.md)。非立方几何使用 [模型与形状](model-shapes.md)。如果用户要能在游戏中放置的新对象，还要执行下文的注册接入，资源包本身不注册方块。

## 输入和产出

确定实际 namespace/name、原生面尺寸、材质与风格、六面关系、是否透明、是否需要新增注册对象、正式输出目录。未给尺寸时参考该项目相邻同类方块；模板 16 是示例。六面相同时选 block-shared；顶/底/侧面有区别时选 block-faces。已确定用途时直接选，不必要求用户填写流程表。

完成后有可编辑工程、原生纹理、显式模型、blockstate、方块物品模型，以及适用时的注册/语言/数据改动。生产资源由工作台导出，模板只作为制作输入。

## 创建、绘图与模型

先按 [操作约定](../operations.md) 建立 c、s、D。模板写入新的草稿目录：

```text
python <skill-dir>/scripts/scaffold.py block-faces --output <D> --namespace examplemod --name panel
```

把示例 namespace/name 换成项目值。block-shared 用同名配方即可。可通过重复的 `--dependency <真实JAR或资源目录>`、`--project-source <真实资源目录>` 在 target.json 写入已有来源，不复制其内容。

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", p["preset"].replace("_", "-"),
            "--face-size", p["face_size"])
uv = c.read("model-uv")
# 查看 uv["uv_map"]。六面独立示例为 48×32，共用为 16×16。
s = c.write(s, "edit", D / "draw.px", "--label", "方块结构与材质")
c.read("preview", "--output", D / "atlas-preview.png", "--tile")
c.read("shape-preview", "--output", D / "block-preview.html", "--overlays")
s = c.write(s, "save", D / "panel.pixforge")
```

把模板 draw.px 的演示面板替换成用户设计后再执行绘图。六面独立布局的帧内像素为：

| 模型局部面 | 示例原点 | 范围 |
|---|---|---|
| up | (0,0) | 0..15 × 0..15 |
| north | (16,0) | 16..31 × 0..15 |
| east | (32,0) | 32..47 × 0..15 |
| south | (0,16) | 0..15 × 16..31 |
| west | (16,16) | 16..31 × 16..31 |
| down | (32,16) | 32..47 × 16..31 |

表只对应本模板；实际面尺寸为 F 时各原点按 F 计算。共享面会同时改变，不能给同一块 UV 分别画两种外观。模型面 UV 单位为 0..16，图集像素并非同一单位；后续调整布局以 model-uv 的实际结果为准。矩形绘图终点包含在内。新建工程已带正确立方体模型，无需自己重建 UV。

## 配置、检查与交付

```python
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
check = c.read("minecraft-check")
assert check["validation"]["passed"]
s = check["state"]
digest = check["validation"]["validation_digest"]
c.read("minecraft-preview", "--output", D / "target-preview.png")
s = c.write(s, "save", D / "panel.pixforge")
```

查看原尺寸、平铺和模型：明确重复面接缝、上下方向、边缘光影、六面色差和物品栏可读性。六面展开图的平铺只用于检查各块纹理局部，不能将整张图集的 3×3 接缝当作模型接缝通过。透明块查看实际渲染层和背面遮挡；PNG alpha 不自动配置方块渲染行为。

按 [正式导出](../operations.md#资源检查与正式导出) 使用当前 digest 和真实批准导出 mod-assets 或 resource-pack。简单 block 绑定生成：

```text
assets/<namespace>/textures/block/<name>.png
assets/<namespace>/models/block/<name>.json
assets/<namespace>/blockstates/<name>.json
assets/<namespace>/models/item/<name>.json
```

六面图集作为一张原生 PNG 导出，模型 UV 保持各面对应关系，不擅自拆六张图。新增游戏方块按 [Forge 静态对象接入](../forge-static.md) 完成 Block、BlockItem、语言、掉落与获取方式；已有注册对象只接其真实资源入口。项目采用 datagen 时修改 provider 或其纹理输入，不将生成结果与手写状态互相覆盖。

## 分支与完成标准

- 朝向/开关/连接状态：先定义真实状态矩阵与模型引用，再用 texture 绑定；简单 block 绑定只有单个空 variant，不能作为该分支的最终状态定义。
- 自定义碰撞/选中：执行模型与形状流程并接入 Java；资源包不能改变物理形状。
- 动画、发光或 PBR：继续对应专项流程，保留当前模型与像素，不能新建空工程覆盖它。
- 其他 Minecraft 版本/加载器：保留编辑和原生 PNG/模型制作流程，使用该项目适配器接入；不套用 forge-1.20.1 目标打包。

完成时核对原生尺寸、UV、实际资源 ID、引用、检查结果、ZIP 清单、注册与 datagen 边界。未编译或未在游戏内验证的部分如实标出。失败先按 issues 的资源和来源修正；不靠切换版本或删掉复杂状态让检查变绿。
