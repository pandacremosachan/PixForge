# 成组调整方块与逐面 UV

新做方块用 [六面共用](../../assets/templates/block-shared/project.json) 或 [六面独立](../../assets/templates/block-faces/project.json) 创建工程，一开始就有可编辑的立方体和贴图。在同一工程用 `workbench view` 的 `{"settings":{"panel":"shapes","rig_mode":"model"}}` 进入部件视图；用 `model inspect-rig` 读取部件。原有 64×64 的 [component_model 命令模板](../../assets/templates/component-model/project.json) 仍可用于已有流程。

**建模与摆姿势。** 在「模型 → 部件建模」中编辑静止造型。单击方块选中；Shift 或 Ctrl 点选会加入或移出选择集。空白处单击清空。在骨骼列表中选骨骼会选中它直属的所有方块。描边表示选中，金色是当前方块；后续逐面操作默认只作用于它。退出「部件建模」回到动作姿势编辑。

**大小、旋转、支点。** 侧栏选择缩放、旋转或移动支点，再选 X/Y/Z；缩放还可选「等比」。在已选部件上左拖，松手提交；右拖转动视角。默认中心为所有已选方块静止几何中心的平均值；「各自支点」切换为分别围绕本方块支点进行变换。「输入数值」可一次填写三个轴，也可设自定义变换中心或把各支点设到同一位置。单独移动支点保留当前几何所在位置。

**逐面 UV。** 打开「逐面 UV」后，在 3D 视图点一个表面，或点 UV 面板下方的六个方向键。右侧显示该面的绑定贴图：金框是所选面的取样范围，青色角标表示第一个端点。拖框内部平移，拖四个角缩放或越过对角翻转；拖动中所见即为 3D 取样结果。滚轮以鼠标为中心缩放，右拖平移，按 Shift 拖动使用 1/8 UV 单位。「单方块」可切换为「同向面联动」，相同的端点增量同时应用到选中方块的同方向面。只有实际提交的手势进入撤销历史。

**AI 使用同一操作。** 用 `model inspect-rig` 找 UUID，传 `cube_ids` 精读所选方块的 from/to、pivot、rotation 和 faces。每面包含保持原方向的 `uv:[u0,v0,u1,v1]`、旋转和绑定贴图 UUID。坐标相对于那张贴图的 `uv_size`，不是横向拼接画布的绝对像素。用 `workbench view` 向用户展示同一个选择：

```json
{"settings":{"panel":"shapes","rig_mode":"model","rig_cubes":["<方块 A UUID>","<方块 B UUID>"],"rig_transform":"rotate","rig_transform_axis":"z","rig_uv_editor":true,"rig_face":"south","rig_link_faces":true}}
```

`workbench state` 的 `rig_components` 返回有序 UUID、当前方块、面、工具和联动状态。无界面也可直接提交这些 UUID；视图选择不修改文档。将下列操作随当前 `expected_document_id / expected_revision` 传给 `model edit-rig`。一批为一步撤销：

```json
{"operations":[
  {"op":"transform_cubes","cube_ids":["<A>","<B>"],"scale":[1,1.12,1],"rotation":[0,0,8],"anchor":"selection","pivot_delta":[0,0.5,0]},
  {"op":"face_uv","cube_ids":["<A>","<B>"],"face":"south","offset":[1,-1]}
]}
```

`scale` 是原尺寸的倍率；缩放中心间距按静止模型轴，长宽高按方块自身轴，保证方块保持直角。先缩放再旋转，最后移支点。旋转是静止模型空间绕 X、Y、Z 的增量（度）。`anchor` 可为 `selection`、`individual` 或绝对三坐标。`pivot_delta` 是静止模型轴偏移；`pivot` 是希望所有支点到达的绝对坐标。原骨骼、父子关系和动作轨不变。缩放时使用显式面 UV 以锁定原纹理，不依赖盒式 UV 的重新计算。

`face_uv` 可传 `offset:[du,dv]` 平移；`delta:[du0,dv0,du1,dv1]` 相对调整端点；或 `uv:[u0,v0,u1,v1]` 写绝对范围。也可传 `rotation:0|90|180|270`、`flip:"u"|"v"`。逐面编辑将目标方块改为逐面 UV 并保留其它面；原始贴图像素不被改写。导出后以同一动作、时间、视角重新打开，对照渲染以及所选方块的原始面坐标。

