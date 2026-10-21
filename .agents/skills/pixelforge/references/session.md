# 共享工程与直接操作

CLI、MCP 与 Windows C++ 桌面使用同一独立核心。本文中的 `pixelforge` 指标准库客户端 `python <skill-base-dir>/scripts/pixforge_client.py [--app <软件目录>]`，所有编辑经软件公开接口执行。

## 会话

用 `session --workspace <项目> --runtime <目录> status` 或 MCP `info` 读取实际工程 ID、revision、图层、帧矩形和确认状态。首次调用可自动启动核心；`gui` 打开或复用原生窗口，关闭窗口后核心继续运行。`--runtime` 或 `PIXFORGE_RUNTIME` 指定共享会话，默认位于项目下 `.runtime/pixelforge-desktop`。不同 runtime 相互隔离。

软件自行维护 `state.json` 中的工程与撤销历史、`approvals.json` 中的真实确认以及会话发现文件。不得编辑这些内部文件。服务重启恢复内容并推进 revision，旧版本令牌不能复用。

## 编辑

每次修改提交当前 `expected_document_id` 和 `expected_revision`，冲突后重读。手动笔画期间核心会阻止竞争写入。`edit` / MCP `draw` 执行当前工程的绘图批次，失败不提交、成功进入一条共享历史；`validate` 可预演。`undo`、`redo`、`save`、`open` 和 `create-project` 各自直接执行，不要求登记阶段或获取计划回执。

`create-project` 支持 `cube-faces`、`cube-shared`、`model` 和 `pixels`；导入模型保留其真实 UV。`project-plan` 是可选的只读布局预演。创建使用设置与当前版本令牌，旧未保存工程保留恢复稿。编辑模型面前用 `model-uv` 查询实际面域和共用关系。

材质时序用 `animation` 配置；增加源帧用 `animation-prepare definition.json`，定义包含 `frame_count` 和可选的 `frame_size`、`steps`、`loop`、`interpolation`，可一次撤销。部件运动、粒子、关键帧与命名状态用 `scene-animation` 或 MCP `configure_scene_animation`，参照 [场景定义](scene-animation.md)。原生编辑器、手动分帧、添加/复制/删除帧继续使用同一核心数据。

## 预览、保存与导出

`preview` 查看图集，`shape-preview` 查看模型与形状，`animation-preview --output preview.html` 生成按真实时序播放的 HTML；均不要求先导出正式 PNG。`save` 保存可编辑工程，不需要用户批准。

向用户展示当前结果，取得针对该版本的真实同意后，调用 `approve` / MCP `approve_export`，再使用对应导出操作。用户也可自行点击桌面“确认并导出”。两种入口使用同一内容绑定；像素、模型、动画或依赖变化会使旧确认失效。没有额外的视觉验收凭据或阶段登记要求。

## 桌面接口

`ui help`、MCP `desktop_help` 返回当前原生界面的操作。`ui set` / `desktop_view` 可设置像素或模型面板、缩放、视角、时间和播放；截图用 `ui capture` / `desktop_capture`。这些查看操作不改作品、不产生撤销记录，也不批准导出。
