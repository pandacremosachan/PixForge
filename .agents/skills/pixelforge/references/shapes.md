# 模型、碰撞与选中形状

PixForge 1.7.1 将形状及构建算法放在独立核心中，与像素、动画共用工程、历史和内容确认。CLI、MCP 与可选 GUI 使用同一套操作；预览只依赖 Pillow。先发现目标版本、映射、方块朝向与注册方式。需要测试时使用隔离会话，不改写实际物品工程。

## 基础与覆盖

坐标使用 Minecraft 模型单位，16 表示一格。每份形状是最多 256 个轴对齐盒的并集；盒有唯一 `id`、`from` 和 `to`，各轴起点必须小于终点。有限坐标范围为 -1024..1024；允许栅栏等超出单格的形状，报告会提示超出 0..16 的范围。

```json
{
  "schema": "pixelforge.shapes/v1",
  "base": [{"id": "slab", "from": [0, 0, 0], "to": [16, 8, 16]}],
  "collision": null,
  "selection": null,
  "model": null
}
```

`collision` 和 `selection` 为 `null` 时实时继承 `base`；列表表示独立覆盖，`[]` 明确表示空形状。切换 `copy` 复制当前有效形状，此后独立编辑；`inherit` 恢复继承，`empty` 建立空覆盖。新工程及旧版无形状工程默认使用完整方块，不凭视觉猜测原有物理行为。

## CLI 与 MCP

每次写入带刚读取的 `document_id` 和 `revision`。以下命令连接同一独立会话：

```powershell
pixelforge session --runtime <目录> shapes definition.json --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <目录> shape-edit operations.json --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <目录> shape-validate definition.json --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <目录> model-import resolved-model.json --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <目录> shape-preview --output shape-review.html
pixelforge session --runtime <目录> shape-preview --output shape-review.png --overlays collision --yaw 35 --pitch 30
```

`shapes` 替换定义；省略基础时使用完整方块，省略覆盖时恢复继承。`shape-edit` 接受操作数组：

```json
[
  {"op": "update", "target": "base", "id": "slab", "box": {"to": [16, 6, 16]}},
  {"op": "mode", "target": "collision", "mode": "copy"},
  {"op": "add", "target": "collision", "box": {"id": "post", "from": [6, 6, 6], "to": [10, 12, 10]}},
  {"op": "remove", "target": "collision", "id": "post"}
]
```

整组原子提交，末条失败时工程不变；可共享撤销/重做。不能直接编辑仍在继承的覆盖，先改基础或显式切换模式。`shape-validate` 只验证，不修改工程、历史或确认。

MCP 对应工具为 `configure_shapes`、`edit_shapes`、`import_block_model`、`preview_shapes` 和 `export_shapes`，定义可直接传 JSON 对象；`configure_shapes(validate_only=true)` 可预检。无界面与 GUI 打开时使用相同核心。

## 叠加预览与桌面

模型导入将显式 Java `elements` 嵌入工程，原文件之后变化不会暗中改变工程。当前支持单一纹理图集、六向面、显式或默认 UV、UV 的 90 度倍数旋转，以及 x/y/z 轴的 0、±22.5、±45 度元素旋转和 rescale。父模型须事先解析；多纹理模型须先合并图集。导入本身不改写已有形状；新建时默认使用下节的保守重建，旋转表面通过有误差界限的轴对齐盒近似。

模型面数由导入模型决定，纹理画布没有固定的六面或多面布局。替换模型时，旧的几何与 UV 一并被替换，画布像素不会重排；新模型必须与纹理的布局配套。六面模型没有显式 UV 时使用其几何推导的默认 UV，完整立方体可六面共用整张纹理；不会自动把 PNG 切成六格。CLI/MCP 的外部替换也会刷新原生预览，包含首次后台轮询前发生的修改。

预览使用当前内存纹理帧。独立 HTML 包含原生 RGBA、实际播放步骤和时长，支持播放、定位、旋转、顶视/正视及分别开关三份形状。PNG 可指定视角和线框；线框穿透显示隐藏边。显示设置不改变内容摘要或确认。预览采用方向光近似，不含游戏内 AO、状态逻辑、邻接行为、光照或实体测试。

GUI“模型与形状”页使用同一核心渲染器，提供基础/碰撞/选中目标、继承/独立覆盖、盒列表和六个坐标输入。点击“应用当前盒坐标”提交；新增与删除也是共享历史，删除全部盒建立空形状。角度、线框开关和底部时间轴用于查看；载入/清除模型或应用形状会使旧确认失效。

## 构建和减少分箱

新建碰撞或选中形状默认从嵌入的原始模型保守重建，CLI 使用 `shape-build`，MCP 使用 `build_shapes`，GUI 默认选中“保守重建原模型”。核心统一提供初始误差 1 个模型单位（1/16 格）、目标 16 箱，两项都可按用途调整；`status.shape_construction_defaults` 可查询相同策略。这是可调起点，不是所有物品的性能标准。导入模型本身保留已有形状，预检和应用均由用户或调用者明确发起；缺少模型时要求先导入，不以现有近似形状代替原模型。

保守重建只允许在误差上限内外扩，保持源体积被覆盖，并对每个新增网格单元验证它到某个源凸长方体的最大欧氏距离。目标箱数是搜索目标，误差是硬约束；未达到目标时报告 `target_met=false`，不自动放宽误差，也不声称求得全局最少箱数。需要保持现有并集与孔洞时，显式选择可选的无损整理：移除包含/重复盒、合并整面，并在坐标压缩网格内搜索较大的覆盖盒。

```powershell
pixelforge session --runtime <测试目录> shape-build --dry-run --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <测试目录> shape-build --max-error 0.5 --target-boxes 12 --dry-run --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <测试目录> shape-optimize --dry-run --expected-document-id <ID> --expected-revision <整数>
```

删除 `--dry-run` 才写入当前观察到的工程，并产生一次共享撤销记录。`shape-optimize` 默认误差 0，针对当前形状；正误差相对于这份输入形状，连续近似会累积偏差。`shape-build` 从嵌入的原始模型重新构建，默认最大误差为 1 个模型单位（1/16 格）、目标 16 箱；可按用途调整，不把这些数值当作所有物品的性能标准。旋转元素无法用有限轴对齐盒精确表示，因此无损构建旋转模型会拒绝并要求显式正误差。零体积面不会生成实体碰撞。

`--symmetry auto` 默认保留检测到的镜像、轴交换和旋转对称；非对称模型不强制对称。`none` 可关闭。算法有中间切片、压缩网格、距离查询和搜索预算；达到预算时只保留已证明有效的结果或退回无损整面整理，并给出警告，不以未验证的近似代替结果。

MCP 的 `build_shapes` 和 `optimize_shapes` 使用同样参数；预检返回 `proposed_shapes` 与实际箱数、误差、体积、对称和目标状态报告。GUI 默认“保守重建原模型”，可切换“无损整理当前形状”，高级选项保留“按误差精简当前形状”。无损模式停用误差与目标控件，回到保守模式时保留原先输入的参数；“预检构建”只展示候选线框，“应用构建”才提交。预检期间不能从 GUI 确认导出当前工程，须先应用候选或退出预检，避免所见形状与导出对象不一致；工程变化会使旧预检失效。

盒数量不等于 Minecraft 最终的分区数量。报告中的坐标区间和 `source_grid_cells` 只统计源几何端点形成的压缩网格；游戏可能增加边界或分区，这些统计不能代替真实引擎测量。Java 导出自动进行无损分箱整理，并以平衡树调用 `Shapes.joinUnoptimized(..., BooleanOp.OR)`，最后只执行一次 `optimize()`，结果保存到静态字段。可编辑 JSON 保留原始盒与 ID；导出整理不改写工程或批准状态。默认保守构建后仍应查看轮廓，并按物品用途调整误差。

## 导出与游戏接入

可编辑 `.pixforge` 始终可保存。正式导出沿用当前内容绑定的人类确认，绑定范围包括纹理、动画、形状和嵌入模型。测试夹具的确认不能用于实际作品；低层接口不能绕过当前协作工程的定稿约定。

```powershell
pixelforge session --runtime <目录> shape-export shapes.json --expected-document-id <ID> --expected-revision <整数>
pixelforge session --runtime <目录> shape-export BlockShapes.java --format forge-1.20.1 --class-name BlockShapes --package example.generated --expected-document-id <ID> --expected-revision <整数>
```

JSON 保留基础、继承、独立空列表、嵌入模型和解析后的有效形状，可重新导入。它是 PixForge 数据格式，不是原版模型的碰撞字段。Forge 1.20.1 / Mojang mappings 适配器生成 `Block.box`、平衡合并和 `Shapes.empty` Java helper；继承对应 `BASE` 引用，并附有 `getShape`、`getCollisionShape` 接入示例。Java 文件名必须与类名一致；GUI 也可选择 JSON 或此 Java 格式。

Java helper 需要接入已注册方块类，不自动注册物品，也不提供朝向状态变换、动态碰撞、实体情境或其他版本适配。原版资源包无法修改碰撞。导出代码需要在目标项目或隔离夹具中编译验证，这与启动游戏验证是不同证据。

## 维护验证

维护验证通过独立软件源码包执行。skill 先用 `doctor` 核对连接，再在隔离 runtime 使用公开 CLI/MCP 验证状态、实际编辑、预览与恢复；不导入软件测试模块。合成素材不代表用户作品的批准。
