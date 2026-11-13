# 骨骼玩家模型 · Blockbench / YSM

已有角色用 `project open` 打开 Bedrock Entity 方块工程 `.bbmodel` 或 PixForge 工程。新角色用 `project create` 的 [player_rig 预设](../../assets/templates/player-rig/project.json)。坐标沿用 Blockbench：静止骨骼支点、方块起止点是绝对模型单位，+Y 向上，−Z 向前；三个旋转量均为度。4.x 文件的动作关键帧使用 Bedrock 动画面板坐标；5.x 使用新版模型坐标。API 读写源文件的原始数值；预览和 YSM 导出按版本换算。

成组调整发束、衣摆或机械零件，以及直接拖动纹理取样范围，见[多选建模与逐面 UV](rig-components.md)。

**先定位对象。** `model inspect-rig` 返回骨骼、下属方块、全部动作、贴图名称与 UUID。传入 `clip` 只读该动作，再传 `bone` 只读其 animator 和原始关键帧。重名方块使用 `cube_id`，现有关键帧使用 `uuid`。作品可含多套皮肤、逐面绑定、独立支点、表情、待机和大量动作；不需要烘焙成单张图集或删减动作。

**在工作台编辑。** 模型页左键点选可见方块，面板同步显示该方块和所属骨骼。先在播放条选动作、停到目标时刻，再选旋转 / 位移 / 缩放和 X / Y / Z 轴；直接左拖部件或关节圈可预览并在松开时记录关键帧。右拖转动视角，滚轮缩放。要改静止姿势，选择「编辑骨骼」修改静止旋转。下方曲线显示所选通道：点击节点定位，横拖改时间，纵拖改数值。选中节点后在侧栏切换线性、阶跃、Catmull–Rom 或贝塞尔；「更多」可输入贝塞尔左右手柄。播放条里的时间标签是秒，API 使用毫秒。

**用相同命令编辑。** `model edit-rig` 接收一个 `operations` 数组和当前文档令牌，整批为一次撤销。创建骨骼和方块的例子见 [articulation.json](../../assets/templates/player-rig/articulation.json)。骨骼可用 `bone` 操作修改 `pivot/rotation/parent`；关键帧用 `key` 新建或修改，`delete_key` 移除。以下为改已有关键帧的操作形状，替换成实际查询到的名称、UUID 和时间：

```json
{"op":"key","clip":"run","bone":"Tail","channel":"rotation","uuid":"<关键帧 UUID>","time_ms":125,"axis":"x","axis_value":28,"interpolation":"catmullrom"}
```

`axis_value` 只改一个分量；`value:[x,y,z]` 改三轴。双值帧用 `point` 指定前值或后值，`data_points` 设置整个值序列。时间手柄是 `bezier_left_time`、`bezier_right_time`（三轴秒偏移）；另两个字段是 `bezier_left_value`、`bezier_right_value`。用 `workbench view` 的 `scene_state/time_ms/rig_bone/rig_cube/rig_channel/rig_axis` 定位并展示。用 `model preview` 的 `scene_state/time_ms/yaw/pitch/rig_texture` 输出同姿势的 PNG，或用 `animation sample` 读世界空间支点与姿势。

**贴图和面绑定。** 默认「按模型面绑定」采样每个面的原贴图。侧栏选别的 PNG 只预览另一套皮肤；要提交逐面修改，用「更多 → 将预览贴图绑定到所选面」或 `face_texture {bone,cube_id,faces:["north"],texture}`。贴图新增用 `add_texture {name,source}`；替换用 `texture {texture,source}`，source 是 PNG data URL。材质页保留每张图的原始像素；`inspect-rig` 的 `textures[].rect=[x,y,w,h]` 是它在共用画布中的区域，`canvas draw` 可直接在该区域绘制。保存时每张图分别写回。

**往返交付。** `project save` 保存 `.pixforge`；`asset export-rig` 用 `format:"bbmodel"` 写可继续编辑的源工程。用 `project open` 重新打开导出的文件，在同一动作、时间、视角和贴图下对照。原项目的 UUID、隐藏部件、未改的动画通道、表达式、事件和扩展字段随工程保留。内置姿势预览重现数值曲线和常用数学表达式；游戏变量使用静态预览值，时间线脚本、声音及粒子留给 YSM 运行。

`format:"ysm"` 写 spec 2 ZIP：主模型、第一人称双臂子树、材质及 Bedrock 动作；`metadata` 可记录作品署名和许可。多套外观分开存储；若同一模型各面引用不同贴图，YSM 几何与纹理会共同换算到一张图集。YSM 的动作可引用模型工程之外的声音等资源，按消费项目补齐。包放入 `config/yes_steve_model/custom`，原版 PNG 皮肤使用另一套工作流。

参考：[Blockbench 格式](https://www.blockbench.net/wiki/blockbench/formats/) · [YSM 模型目录](https://ysm.cfpa.team/wiki/struct/) · [YSM 动作名称](https://ysm.cfpa.team/wiki/animation/main/)。
