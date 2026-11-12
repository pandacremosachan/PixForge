# 通用操作约定

W 为消费项目绝对路径，R 为共享会话，D 为该项目的草稿目录。下文用“分组 动作”标记发送给同一常驻实例的命令。JSON 示例是请求的 `params`；文件参数和结果传递按[命令入口](command-line.md)映射。工程 ID、revision、文件路径和内容取自本轮实际响应。

## 程序与工程状态

调用 `workbench open`，核对返回窗口已加载、非 pending 且 W/R 正确，再读取 `project state`。复用时不附源文件路径，不替换用户当前工程。

直接执行 `project state`，需要留存状态时使用 `--result-file <D>/observed.json`。

`project state` 自身就是状态，多数写入响应在 `state` 返回状态。每次写入携带该状态的 `document_id/revision`：

执行 `canvas draw --request-file <本次参数.json>`，参数文件内容：

```json
{
  "commands": "rect 2 2 5 5 #397a99ff",
  "label": "调整纹理",
  "expected_document_id": "<已观察到的ID>",
  "expected_revision": 12
}
```

参数按 `领域 子命令 --help --json` 返回的 params_schema 传入。模板 JSON 用对应文件选项传入，绘图文件用 --commands-file。检查退出码、ok 与 code/details。冲突、BUSY 或写入超时后先重读并理解状态，不自动重发。

成功响应已返回 state 时，沿用它继续操作；不为每个笔画重复查询工程。切换工程、用户修改、状态不明确或发生冲突时，再读取当前状态。

## 绘制后的同步与实际展示

需要单独确认窗口同步时调用 `workbench wait`；需要展示时直接调用 `workbench present`，其内部已完成版本同步、视图设置和截图。observed 使用最近操作的完整响应或其 state，必须包含 `document_id/revision/content_digest`；等待中内容变化会停止。

执行 `workbench present --request-file <本次参数.json>`，参数文件内容：

```json
{
  "observed": {
    "document_id": "<ID>",
    "revision": 12,
    "content_digest": "<摘要>"
  },
  "path": "<D>/round-01-pixels.png",
  "panel": "pixels"
}
```

每轮使用新截图路径。实际查看 PNG，检查非空、完整和像素/UV；`visual_review_required=true` 或 `scene_ready=true` 只说明同步条件，不能替代看图。真实工程模型存在时再以 `panel="shapes"` 展示。`model uv` 返回的 `uv_map.model_present=false` 时，使用真实目标的 `minecraft preview`，不假造模型。

无界面任务跳过窗口操作，仍检查预览与当前内容。`workbench view` 设置视图，`workbench capture` 返回原生窗口截图；编辑器字段和动作从对应 status 读取，见 [工作台](desktop.md)。

## PNG 与剪贴板

经 `canvas draw` 绘制，不用剪贴板传 PNG。`project open --path` 打开 PNG 会替换工程并清除旧模型关联，操作前用 `project save` 保存原工作；已有对应工程直接继续。

保留模型的局部叠加先无损解码 RGBA，再使用受限 patch 或独立层，注意透明覆盖。缺解码/导入能力时说明限制。独立 PNG 检查使用 `asset inspect`，无需替换当前工程。窗口卡住时停止投递并保留可保存工程；未重测不得声称已修复。

## 资源检查与正式导出

先用 `minecraft configure --settings` 应用真实目标，再用 `minecraft check` 检查。读取 `validation.passed`、issues 和 `validation_digest`；检查通过后保留当前 state 与摘要，并保存工程。

展示当前结果并接受修订；保存工程和讨论预览不需批准。正式导出使用用户对当前内容的实际有效确认，修改意见不等于批准修订稿。已有有效授权继续使用。

执行 `asset approve --request-file <本次参数.json>`，参数文件内容：

```json
{
  "user_request": "<用户对当前内容的实际批准原话>",
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

批准推进 revision。用批准响应的 state 调用 `asset export-png`、`asset export-shapes` 或 `asset export-minecraft`；Minecraft 导出同时提交当前 validation_digest。PNG 保持原生尺寸；资源格式为 resource-pack/mod-assets/forge-integration/forge-mod。内容或依赖变化后重查相关结果与授权；覆盖正式文件遵循用户的替换授权。

## 错误与恢复

| 情况 | 处理 |
|---|---|
| DOCUMENT_CONFLICT / REVISION_CONFLICT | 读取新工程或用户改动，理解后继续 |
| BUSY | 等笔画/同步结束，再读取状态 |
| FILE_EXISTS | 换新路径，或在替换授权内设置 overwrite |
| 缺批准/检查过期 | 保存草稿，展示并检查当前版本 |
| validation 失败 | 按 issues 的 resource/source/code 修复 |
| 语法错误 | 修正行号/坐标；原子批次失败未提交 |
| 缺能力或命令 | 核对 project info 和命令帮助，报告缺失操作 |

按需用 `project recover` 保留未保存内容；恢复实际文件用 `project open`。关闭窗口用 `workbench close`，仅在任务确需结束会话时再调用 `project shutdown`。交付说明尺寸、实际文件和检查范围，分别据实报告离线、编译与游戏验证。
