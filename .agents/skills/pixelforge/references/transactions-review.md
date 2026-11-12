# 离线事务与独立 PNG 检查

仅用于用户明确选择的离线制作或旧绘图文本维护。共享窗口任务按 [操作约定](operations.md)；asset batch 不更新共享工程。

## 原子草稿

执行 `asset batch --request-file <参数.json>`：

```json
{
  "commands": "new 16 16\nrect 0 0 15 15 #336699ff",
  "dry_run": true
}
```

整批在候选画布执行，失败不提交。dry_run=true 只返回讨论预览；dry_run=false 时指定新的 .pixforge project_path，成功后保存独立可编辑草稿。已有文件需明确 overwrite。普通异常可回滚，不承诺跨文件断电恢复。

绘图文本中的 render/save 请求保持延后，返回 deferred_outputs；生产文件通过 project open 打开草稿，再按正常内容确认和导出执行。预览倍率、tile、backgrounds 只影响讨论图。

## 独立检查

asset inspect --path,options 读取实际 PNG，无需替换当前工程。静态对照、保护蒙版和约束见 [材质检查](textures.md)。frame_height 检查已确认的垂直帧条，animation_plan 检查真实矩形与全部源帧；两者互斥。时序定义见 [动画播放器](animation-review.md)。

preview_path、html_path、report_path 分别保存讨论图、播放器和报告，不能覆盖输入或彼此；已有文件需明确 overwrite。独立检查不构成正式输出确认。
