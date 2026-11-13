# Minecraft 玩家皮肤

需要能从侧面看见厚度、能弯曲摆动的尾巴或自定义身体比例时，使用[骨骼玩家模型](player-rig.md)；若用户指定只穿原版 PNG，继续下文。

这里制作 **Java 原版现代 64×64 PNG**。[Minecraft 官方说明](https://www.minecraft.net/en-us/article/what-is-minecraft-skin)将皮肤定义为包在人体上的展开贴图；Classic/Wide 的手臂宽 4 像素，Slim 宽 3 像素，导入启动器时要选相同的臂型。两者的画布尺寸相同，尺寸本身不能识别臂型。新设计未指定时用 Classic，已有皮肤沿用原设定。

标准样本可从 [Mojang 的 Java 1.20.1 版本清单](https://piston-meta.mojang.com/v1/packages/d9ad5f3ab4523f9311a4e67d92a51f5a93d67333/1.20.1.json) 的 `downloads.client` 取得，在包内取 `assets/minecraft/textures/entity/player/wide/steve.png`。[宽臂与细臂的中文展开图](../../assets/templates/player-skin/atlas-guide.png)取自 PixForge 的两种实际模型；其中的标色和字不属于游戏贴图。

## 新建或改图

工作台入口是 **文件 → 玩家皮肤**，可按臂型新建或打开 PNG。通过命令操作时，按[操作约定](../operations.md)连接同一工程，并携带当前文档 ID 和 revision。

- **从头设计**：将 [Classic](../../assets/templates/player-skin/classic/project.json) 或 [Slim](../../assets/templates/player-skin/slim/project.json) 的内容作为 `project create` 的 `settings`。画布的 `base` 层已铺好人体六面的底色，`outer` 层为空。按人物设定画脸、头发和服装。
- **修改已有皮肤**：`project open` 传 `path` 和 `arm_model:"classic"` 或 `"slim"`。工作台把原图中的外层像素放到 `outer` 图层，保留其余原画；在已有 `.pixforge` 上继续时直接打开工程。64×32 老皮肤的布局不同，不能纵向拉伸套用这个模板。
- **试画**：每个臂型目录的 `draw.px` 都是一圈右袖金边。文本作为 `canvas draw` 的 `commands`；两份示例的环绕长度不同。[山地邮差 Slim 示例](../../assets/templates/player-skin/courier-slim.png)可直接作为已有皮肤打开，切换 `outer` 可看清帽檐、斜挎带和背包各在哪一层。

## 在人体上定位

以下是每个部位展开图左上角的像素坐标，原点在 PNG 左上。左右按**穿着者自己**的方向；面对人物时，右臂在画面左边。

| 部位 | 宽×高×深 | 基础层原点 | 外层原点 |
|---|---|---|---|
| 头 | 8×8×8 | (0, 0) | (32, 0) |
| 躯干 | 8×12×4 | (16, 16) | (16, 32) |
| 右臂 | 4 或 3×12×4 | (40, 16) | (40, 32) |
| 左臂 | 4 或 3×12×4 | (32, 48) | (48, 48) |
| 右腿 | 4×12×4 | (0, 16) | (0, 32) |
| 左腿 | 4×12×4 | (16, 48) | (0, 48) |

每组上排是顶、底，下排从左到右是人物的右、前、左、后。起点是整组矩形的左上角，可能正好是未映射的留白。用 `model uv` 读取 `uv_map.player_skin.parts[部位][base|outer].faces[面]`：面名为 `top/bottom/right/front/left/back`，值为 `[x,y,宽,高]`，右、下边界不含。尚未建工程时，`project plan` 传皮肤模板也返回同样的图集。

- `body.base.faces.front` 是 `[20,20,8,12]`；`body.outer.faces.back` 是 `[32,36,8,12]`。外层的透明像素露出基础层；未映射的留白不会显示在人体上。
- `right_arm.base.faces.back` 在 Classic 为 `[52,20,4,12]`，在 Slim 为 `[51,20,3,12]`。左右肢体分别画，不对整张图镜像。
- 反查时，`model uv` 传 `{"x":32,"y":36}`，读 `uv_map.point.faces[0].skin`；命中躯干外套背面。未映射处返回 `point.unmapped:true`。工作台「材质 → 面域」提供相同的名称、位置和尺寸。

将相连的头发、衣领、袖口沿棱边画到侧面和后面。基础层覆盖六面；在另一块外层 UV 上画帽檐、衣摆、袖章等凸起细节，其余留透明。仅切换画布图层不会改变同一坐标贴到人体上的位置。

做低噪点皮肤时，先连成发束、衣片和肌肉的主要明暗面，再给眼睛、徽记等识别点留小色块；不要在每个面上铺同样的碎高光。原图中的轮廓可以用服装外层暗示，单张原版 PNG 不能添加尾巴骨骼。需要单独切换的背饰时，让它独占外套区域，把完整衣背保留在基础层。

## 预览与交付

用 `model preview` 传 `overlays:[]`；`yaw:0, pitch:0` 查看正面，`yaw:180, pitch:0` 查看背面，再稍作旋转看接缝。`hidden_skin_overlays:["jacket"]` 只隐藏外套；`[]` 显示全部。支持 `hat/jacket/right_sleeve/left_sleeve/right_pants/left_pants`。工作台「模型 → 皮肤外层」也能逐件切换，或用 `workbench view` 的 `settings.hidden_skin_overlays`。这些预览开关不改 PNG；材质页的画布图层可见性则影响导出。

交付前恢复要穿戴的图层。用 `project save` 保存可编辑工程，按[PNG 导出约定](../operations.md#资源检查与正式导出)执行 `asset export-png`（`scale:1`），并注明 Classic 或 Slim。玩家直接用这张展开 PNG，不需要 Forge 目标、物品模型或资源包。

用户要求四栏图时，从同一份导出的皮肤制作「参考原图｜正面｜背面｜实际展开 PNG」，另附可直接导入的 64×64 原尺寸文件。要看得更清楚就提高展示图分辨率，保留原版游戏贴图的尺寸和透明通道。
