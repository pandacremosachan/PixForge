# 通用操作约定

先完成 [连接](connection.md)，再选择一个任务流程。本文件统一参数、返回值、并发、检查和导出；流程不要求阶段登记、计划凭据或额外验收回执。

## 本轮输入

| 代号 | 具体含义 |
|---|---|
| W | 已存在的消费项目工作区绝对路径，决定资源来源相对路径 |
| R | 当前共享 runtime 的绝对路径；继续已有工程时沿用真实 R |
| D | 本任务草稿目录，放脚本、JSON、可编辑工程与预览 |
| namespace/name | 实际小写资源 ID；纹理路径通常为 block/name、item/name 等 |
| native size | 真实源像素尺寸；模板 16×16 仅是可替换示例 |
| target | 实际版本、加载器、模型/状态、渲染层、导出格式及输出位置 |

新建独立作品才使用新的 R。首次连接 status 可启动空核心；不通过这种方式替代已有打开的作品。完成前保存 .pixforge；无需为每轮试改建立备份工程。

## 可复制的 Python 调用前缀

各流程的 Python 代码共用下列前缀。把路径换成实际值后运行；使用与软件同机的已有 Python，不安装库：

```python
import json
import sys
from pathlib import Path

K = Path(r"<skill-dir>").resolve()
W = Path(r"<project-workspace>").resolve()
R = Path(r"<shared-runtime>").resolve()
D = Path(r"<draft-directory>").resolve()
sys.path.insert(0, str(K / "scripts"))
from pixforge_client import Client, SoftwareError

c = Client(workspace=W, runtime=R, app=r"<software-directory-or-exe>")
# 也可去掉 app，使用 config=r"<connection.json>" 或已有环境配置。
s = c.read("status")
def load(name):
    return json.loads((D / name).read_text(encoding="utf-8"))
```

`c.read(action, ...)` 调用公开 session CLI，返回 JSON。`s = c.write(s, action, ...)` 使用 s 或 s.state 中**已观察到的**令牌，返回完整操作结果。每次写入后都保留返回的 s；不要在写入前自动 status 并拿新令牌盲目重试。该客户端不保存作品副本、不实现绘图、不自动批准或重试。

```python
s = c.write(s, "edit", D / "draw.px", "--label", "调整本轮纹理")
c.read("preview", "--output", D / "preview.png")
s = c.write(s, "save", D / "asset.pixforge")
```

上面的文件路径位于同机文件系统。CLI 多参数始终作为独立 argv 传入，路径含空格时无需自己拼 shell 引号。检查失败时抛出 `SoftwareError`，其 `result` 保留软件返回的诊断。MCP 使用相同逻辑但省去临时参数文件，可直接传 JSON 对象或绘图文字。

## CLI 与 MCP 对应表

CLI 前缀均为 `pixelforge session --workspace W --runtime R`。表中“写”操作的 CLI 追加 `--expected-document-id ID --expected-revision REV`；MCP 传同名下划线字段。只读模型 UV 返回顶层令牌，其余大多数操作在 `state` 返回状态；status/info 自身就是状态。

| 用途 | session CLI 动作与主要参数 | MCP 名称与主要字段 | 写 |
|---|---|---|---|
| 状态 | `status` | `info()` | |
| 新建 | `create-project --preset cube-shared --face-size 16` | `create_project(settings={preset:"cube_shared",face_size:16})` | 是 |
| 打开 | `open FILE` | `open_project(path)` | 是 |
| 绘图 | `edit FILE.px` 或 `edit -` stdin | `draw(commands, label)` | 是 |
| 预演 | `validate FILE.px` | `validate(commands)` | 是，仅令牌检查 |
| 像素读回 | 绘图批次内 `read x y w h` | `read(x,y,w,h,raw)` | CLI 批次带令牌 |
| 面域 | `model-uv [--frame N --x X --y Y]` | `model_uv(frame,x,y)` | |
| 图集预览 | `preview --output PNG [--tile]` | `preview(scale,tile,backgrounds)` | |
| 模型预览 | `shape-preview --output PNG或HTML --overlays collision` | `preview_shapes(include_html=True,overlays=["collision"])` | |
| 保存 | `save FILE.pixforge` | `save_project(path)` | 是 |
| 撤销/重做 | `undo` / `redo` | `undo(...)` / `redo(...)` | 是 |
| 增加源帧 | `animation-prepare frames.json` | `prepare_animation_frames(settings)` | 是 |
| 加载时序 | `animation plan.json` | `configure_animation(path)` | 是 |
| 场景草稿校验 | `scene-validate scene.json` | `validate_scene_animation(settings)` | |
| 应用场景 | `scene-animation scene.json` | `configure_scene_animation(settings)` | 是 |
| 场景采样 | `scene-sample --time-ms T [--scene-state ID]` | `sample_scene(time_ms,scene_state)` | |
| 动画播放器 | `animation-preview --output HTML` | `preview_animation(scale)` | |
| 模型导入 | `model-import model.json` | `import_block_model(model)` | 是 |
| 形状修改 | `shape-edit operations.json` | `edit_shapes(operations)` | 是 |
| 从模型建形状 | `shape-build --max-error E --target-boxes N [--dry-run]` | `build_shapes(max_error,target_boxes,dry_run)` | 是 |
| 配置目标 | `minecraft-configure --config target.json` | `configure_minecraft_target(settings)` | 是 |
| 资源检查 | `minecraft-check [--include-generated-code]` | `check_minecraft_resources(include_generated_code)` | |
| Minecraft 预览 | `minecraft-preview --output PNG --options @view.json` | `preview_minecraft_scene(options)` | |
| 数据图配置 | `minecraft-material-configure --settings @material.json` | `configure_minecraft_material(settings)` | 是 |
| 数据字节修改 | `minecraft-material-edit --role specular --channel r --operations @ops.json` | `edit_minecraft_material(role,channel,operations)` | 是 |
| 数据查看 | `minecraft-material --role normal --channel r --output PNG` | `inspect_minecraft_material(role,channel,view,pixel)` | |
| 记录真实批准 | `approve --user-request TEXT` | `approve_export(user_request)` | 是 |
| 导出原生 PNG | `export FILE.png --scale 1` | `export_current(path)` | 是 |
| 导出形状 | `shape-export FILE --format json或forge-1.20.1` | `export_shapes(path,format,...)` | 是 |
| 导出资源 | `minecraft-export ZIP --format mod-assets --validation-digest HASH` | `export_minecraft_resources(path,format,validation_digest)` | 是 |

MCP 表中的对象记法为字段提示，不是可直接复制的 JSON；真实 JSON 的键和值均按标准引号书写。完整参数已由任务流程给出，只有高级选项再查专项参考。

打开桌面用 `pixelforge gui --workspace W --runtime R`。查看设置用 `pixelforge ui --workspace W --runtime R set @view.json`，截图用 `ui … capture FILE.png`；GUI 与核心必须使用同一 R。MCP 图像直接由 image content 返回，HTML 在 JSON 的 html 字段；将其写入草稿后用宿主现有查看工具打开。

MCP 使用模板时，将 project.json 的对象作为 create_project 的 settings；preset=model 的模板还需把 model.json 的**对象**放到 settings.model，不传文件路径。draw.px 的完整文本作为 draw.commands，frames.json/scene.json 分别作为 prepare_animation_frames/configure_scene_animation 的 settings，target.json 作为 configure_minecraft_target 的 settings。每个写请求都加上上一响应 state 中的两个令牌；文件路径类工具使用软件端路径。例如新建共用面方块的参数为：

```json
{"settings":{"preset":"cube_shared","face_size":16},"expected_document_id":"<从info读取>","expected_revision":0}
```

上例 revision=0 仅示意，实际必须使用 info 返回的整数。直接 MCP 模式不运行 Python Client 或 scaffold 也能完成同一流程：读取对应模板、替换 namespace/name、发送对象/文本即可。

## 资源检查与正式导出

Minecraft 流程先应用实际 target，再检查。返回结构中的 `validation.passed` 和 `validation.validation_digest` 是本次资源检查结果，不在顶层。需要真实原版父模型时配置本机合法已有的客户端 JAR 为 dependency；不以自造的同名简化模型替代。

```python
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
check = c.read("minecraft-check")  # 失败抛 SoftwareError，查看 error.result 的 issues。
validation = check["validation"]
assert validation["passed"]
s = check["state"]
digest = validation["validation_digest"]
s = c.write(s, "save", D / "asset.pixforge")
```

向用户展示本轮最终预览、关键资源诊断和交付路径。用户已明确同意当前内容时使用其实际表达；尚未取得时先保存可审查结果，再等待这一最终批准。工作台的 approve 会推进 revision，因此导出必须使用其返回的状态。不得把 skill 自动检查、模板成功或模型自己的决定填成用户同意。

```python
# 仅在当前对话/桌面已有真实批准后执行；approval_text 是该用户的真实表达。
s = c.write(s, "approve", "--user-request", approval_text)
s = c.write(s, "minecraft-export", D / "assets.zip", "--format", "mod-assets",
            "--validation-digest", digest)
s = c.write(s, "save", D / "asset.pixforge")
```

仅需 PNG 的独立任务不必配置 Minecraft 目标，批准后改用 `c.write(s,"export",D/"asset.png","--scale","1")`。资源包把格式改成 `resource-pack`；它不能注册新的游戏对象。目标项目接入前核对 ZIP 文件清单，将授权的自身 assets 合入实际资源或 datagen 规则，不能顺带复制依赖 JAR。已存在的正式文件只有本轮明确替换授权时才加 `--overwrite`。纹理、模型、时序或外部依赖改变后重新检查并核对授权；未变版本的已有授权继续使用。

## 错误与恢复

| 返回 | 下一步 |
|---|---|
| `DOCUMENT_CONFLICT` | 工程已切换；读取新工程并确认本轮修改仍适用 |
| `REVISION_CONFLICT` | 读取用户改动，合并本轮意图后再提交，不自动重试旧脚本 |
| `BUSY` | 人的笔画尚未结束；等待结束，再读取状态 |
| `FILE_EXISTS` | 选新输出名，或在已有替换授权下明确覆盖 |
| 导出缺批准/已过期 | 保存工程和预览，展示当前版本；不要换入口导出 |
| validation 失败 | 按 issues 的 resource/source/code 修正引用、数据或目标，再检查 |
| 缺能力/API 不兼容 | 独立更新软件或使用已支持的流程；不修补私有环境 |
| `.px` 行号错误 | 修正对应命令/坐标；整个 session 批次未提交，可用同一仍有效令牌重试 |
| 声称支持的操作缺失 | 比较 doctor 的软件版本与本文基线，使用该安装 help；不要猜新命令 |

任务结束报告具体文件、原生尺寸、检查范围、游戏接入状态和仍需用户决定的事项。离线预览、资源引用校验、编译和游戏内验证分别记录；不自动启动游戏。
