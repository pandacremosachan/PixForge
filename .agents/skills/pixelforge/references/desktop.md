# 共享工作台

通过同一个 EXE 的 `workbench open` 命令启动或复用当前工程窗口，使用 `workbench help` 查询视图字段。窗口与命令共用工程、历史和导出确认；关闭窗口后工程进程继续运行，后续命令仍可继续处理该工程。

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
