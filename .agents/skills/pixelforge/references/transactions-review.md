# 事务、统一预览与当前素材验收

此页描述保留的 CLI/离线检查能力。1.5 的制作入口是 [独立会话](session.md)：CLI/MCP 与可选桌面共享工程，讨论确认当前版本后导出；AI 自检记录不替代用户确认，离线输出不用于绕过这一流程。

保留现有 `.px` 语法与 `pixelforge run`。新制作优先使用 `--atomic`，不确定的批次先用 `--dry-run` 查看候选结果。继续采用任务项目的资源路径、尺寸、风格、动画与输出约定。

## 批次提交和预演

```powershell
# 整批成功后才写生产 PNG 和会话；预览另外保存。
python <skill-base-dir>/scripts/pixforge_client.py run material.px --atomic -o material.png -s material-session.json --preview material-preview.png

# 只演练：脚本中的 render/save 和 -o/-s 都不落盘；显式 --preview 可以输出候选证据。
python <skill-base-dir>/scripts/pixforge_client.py run material.px --dry-run -o material.png --preview proposed.png
```

`--atomic` 在副本上运行整份脚本，成功后作为一次撤销步骤提交。副本包含尺寸、像素、图层及当前层、调色板和镜像状态。新会话的第一批绘制可撤销为同尺寸空画布。脚本内部仍能使用 `render`、`save` 和 `load`；输出先暂存，同批 `load` 能读取前面暂存的会话。文件发布失败时恢复已替换的文件，内存画布不提交。这是普通执行异常下的回退，不承诺断电或进程崩溃时跨多个文件的事务恢复。

`--dry-run` 不改变当前画布、撤销/重做或生产输出，返回候选图、变化区域、变化像素和计划输出。显式指定的 `--preview` 是本轮证据，可以写入独立路径；不能覆盖输入、生产 PNG 或会话。不带这些选项的旧 CLI 保持逐命令执行和撤销，失败前的命令可能已经生效。

`run --preview` 自动采用事务执行。`--preview-scale 1..16` 只影响证据，`-S` 仍控制 `-o` 的导出倍率。生产资源保持原生尺寸。编辑预览可按需增加 `--tile`、`--backgrounds checker light dark`、静态 `--compare before.png`，或垂直帧条的 `--frame-height H`。帧表不推断时长。

外部集成通过软件公开 CLI/MCP 调用事务，不导入内部执行器。MCP 的 `draw` 默认整批事务并返回实际图像；`validate` 只预演，`preview` 只查看。`include_preview=False` 可省略明确可预测的中间图像；共享 MCP 始终为原子批次，旧逐命令行为仅保留在显式低层 CLI。接收到图像仍需实际查看，不能仅凭返回成功宣称看过。

## 同一个入口生成证据

```powershell
# 静态材质：按实际要求选择约束和背景。
python <skill-base-dir>/scripts/pixforge_client.py preview material.png --output material-review.png --expect-size 16 16 --opaque --tile --report material-checks.json

# 动画：沿用按真实资源元数据建立的播放定义，同时检查全部源帧并生成无损播放器。
python <skill-base-dir>/scripts/pixforge_client.py preview flow.png --output flow-review.png --animation-plan flow-playback.json --expect-size 16 16 --report flow-checks.json
```

`preview` 复用原 `texture_review.py` 的尺寸、alpha、调色板、保护蒙版、区域与平铺检查。`--output` 与 `--preview` 同义，`--scale` 是证据倍率。指定动画计划后，按其真实帧矩形检查全部源帧，包括未播放帧；另外生成 `*-frames.png` 和默认 `*-player.html`，也可用 `--player` 指定 HTML 路径。不要同时传 `--animation-plan` 与 `--frame-height`。计划必须引用正在检查的 PNG，实际时长、插值边界和来源规则见 [动画验收](animation-review.md)。

静态检查与动画播放器分别通过软件公开 `preview`、`animation-preview` 命令调用，不导入内部 Python 实现。动画与静态证据使用同一组原尺寸、最近邻、背景和平铺方法。静态修改可加入前后对照。过大的 PNG 证据会要求降低展示倍率/背景数量或选择相关区域，不缩小生产像素、不减少应检查的源帧。
