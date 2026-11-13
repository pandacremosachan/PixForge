# 共享工作台

通过同一个 EXE 的 `workbench open` 命令启动或复用当前工程窗口，使用 `workbench help` 查询视图字段。窗口与命令共用工程、历史和导出确认；关闭窗口后工程进程继续运行，后续命令仍可继续处理该工程。

## 启动页与工程预设

双击 EXE 或在编辑器按 Ctrl+N 打开任务选择页。`workbench state` 的 `panel: "start"` 表示正在选择，`start_task` 是高亮的 `block`、`item` 或 `model`，选择尚未改动工程。已有作品直接继续当前工程。新建时读取 `project state`，向 `project create` 提交下表的 `settings` 和观察到的 `expected_document_id`、`expected_revision`。同一份 `settings` 可以先用 `project plan` 只读查看图集和 UV。

| 启动页选择 | `settings` 示例 | 起点 |
|---|---|---|
| 方块 · 六面共用 | `{"preset":"cube_shared","face_size":16}` | 一个可编辑方块，六面共用 16×16 贴图 |
| 方块 · 六面分别绘制 | `{"preset":"cube_faces","face_size":16}` | 一个可编辑方块，每面 16×16，展开为 48×32 图集 |
| 物品贴图 | `{"preset":"pixels","width":16,"height":16}` | 透明二维画布 |
| 三维建模 · 角色建模 | `{"preset":"player_rig"}` | 玩家骨架，默认 128×128 图集 |

方块在同一工程里切换「材质」和「模型」。两种贴图布局都支持添加部件和逐面 UV。旧命令模板 `component_model` 仍可创建 64×64 图集的部件工程。

让用户接手贴图时，将 `workbench view` 的 `settings` 设为 `{"panel":"pixels","tool":"pen"}`；六面分别绘制时可加 `"uv_guides":true`。接手部件建模时用 `{"panel":"shapes","rig_mode":"model"}`。这些视图设置只切换显示，不创建工程。

## 材质与模型

材质页默认展开工具、调色板和图层。从启动页创建贴图会选中画笔。笔宽上限为当前帧的短边，不透明度为 0–100%；可单击数值输入，或左右拖动。用 `workbench state` 读取 `brush_size_range`；改变实际像素尺寸用 `canvas resize` 的 `width/height`，按帧最近邻缩放，可撤销。原版玩家皮肤固定为 64×64。画板上方可切换适应、原尺寸、网格、平铺、模型 UV 和动画洋葱皮。

点工程色块取色，或用色相条和色域调色；没有工程色时显示常用色。点图层行切换绘制层，「可见」控制当前层的显示。右键临时取色，空格拖动平移。手改与命令绘制共用同一份工程及撤销历史。

方块的「模型」页右侧「模型显示」可分别开关材质模型、基础形状、碰撞框和选中框。碰撞框以粉红色线框叠加在模型上，未设覆盖时使用基础形状。用预设视角、水平/俯仰滑块或拖动旋转模型，滚轮缩放。侧栏默认展开，线框按需打开；关闭材质模型可以单看线框。

有动画才显示播放条：可播放、暂停、拖动进度，逐帧材质可前后切帧；有命名状态时可选择状态或完整流程。文件菜单提供打开、保存、另存和导出 PNG。模型构建、动画编排和资源导出用对应命令处理。

## 同步与截图

模型面板用 `workbench view` 设置 `yaw/pitch/overlays/show_model`，`workbench present` 截图时保留这些设置。交付可旋转网页时，把同一组设置传给 `model preview`。

用 `workbench state` 核对 workspace/runtime、loaded、pending 和工程版本。编辑后需要截图展示时直接用 `workbench present`，它会同步本轮已观察状态、设置像素或真实模型视图，并返回 PNG 路径；只需确认同步时使用 `workbench wait`。视图操作不修改素材，实际查看截图后判断质量。

`workbench view` 可设置面板、工具、缩放、平移、网格、平铺、洋葱皮、UV、模型角度及播放状态。`workbench focus` 聚焦窗口，`workbench controls` 读取控件状态，`workbench metrics` 读取原生计数，`workbench sample` 采样当前原生播放。字段按 workbench help，避免猜测控件或视图状态。

## 工程内容与编辑器

从 `project state` 读取图层和帧布局，从 `model uv` 读取真实面域。图层最多 16 层、至少一层；共享 UV 修改影响所有引用面。用户编辑会改变共享版本或暂时占用工程，冲突后不自动刷新令牌重发。

| --editor-kind | --operation |
|---|---|
| scene | open/status/field/invoke/apply/cancel/capture |
| target | open/status/field/invoke/apply/cancel/capture |
| preview | open/status/configure/field/invoke/camera/capture/cancel |
| regression | open/status/field/invoke/capture/cancel |
| material | open/status/field/invoke/paint/capture/cancel |

统一调用 workbench editor，以 editor_kind 选择上表编辑器。先 open，再从 status 读取字段/动作 ID；通过 name/value 修改草稿，path 指定截图。场景和目标的 apply 校验草稿版本并提交一条历史，cancel 丢弃草稿。配置编辑与窗口展示不批准导出。

源帧通过 `animation edit-frames` 的 operation/step_index 参数插入、复制或删除；作用于所有图层并维护时序引用，要求完整规则图集。`animation prepare-frames` 可一次增加多帧；`animation configure` 的 `settings` 接收完整内联时序。

## 保存与结束

用 `project save` 保存 .pixforge。`project recover` 为未保存内容创建恢复副本；恢复时通过 project open 打开真实副本。关闭时调用带当前版本令牌的 `workbench close`；需要终止核心时，在窗口关闭后调用 `project shutdown`。
