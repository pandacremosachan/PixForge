# 命令分组与按需参数

程序提供以下七组命令，合计 66 个动作。下文省略 EXE 路径及 W/R 参数；定位与输入规则见 [命令入口](command-line.md)。

| 分组 | 用途 |
|---|---|
| project | 软件信息、当前工程、新建/打开/保存、历史、恢复与会话结束 |
| canvas | 原子绘制、预演、像素读取和画布预览 |
| model | 模型、UV、基础/碰撞/选中形状与模型预览 |
| animation | 源帧、纹理时序、部件/粒子、状态、采样及播放 |
| minecraft | 资源目标与检查、渲染、LabPBR、性能和回归 |
| workbench | 窗口生命周期、同步、展示、视图及原生编辑器 |
| asset | 独立 PNG/动画检查、离线草稿、真实内容确认与正式导出 |

`--help` 只列分组；`canvas --help` 只列绘图动作；`canvas draw --help --json` 返回该动作的 params_schema。按需查询并复用说明，正常使用不读取实现。

内容写入的 expected_document_id/expected_revision 必须来自已观察到的当前状态；请求文件使用这些原名，命令参数为 `--expected-document-id` 与 `--expected-revision`。多数响应的 state 为后续状态。冲突后理解改动，不刷新令牌重发。

## 任务文件映射

| 文件内容 | 命令参数 |
|---|---|
| project.json | `project create --settings-file` |
| draw.px | `canvas draw --commands-file` |
| frames.json | `animation prepare-frames --settings-file` |
| scene.json | `animation scene-configure --settings-file` |
| target.json | `minecraft configure --settings-file` |
| 完整操作响应或 state | `workbench wait --observed-file` 或 `workbench present --observed-file` |

使用 `--settings-file project.json` 时，文件根对象就是 settings，模型对象放在其中的 model 字段。使用 `--request-file` 时，完整参数对象才包含 settings.model。options、observed 同样遵循此规则：单个参数文件直接存对象，完整请求文件用参数名包裹对象。

原生编辑器使用 `workbench editor --editor-kind scene --operation status` 等命令；editor_kind 选择 scene、target、preview、regression 或 material 中的一项。先读取 status 的 actions 与 editable_fields，再设置 name/value。窗口命令与工程共用历史，关闭窗口后工程进程继续运行。

独立检查通过 `asset inspect`，离线草稿通过 `asset batch`；它们不替换共享工程。正式输出遵循 [操作约定](operations.md#资源检查与正式导出)。
