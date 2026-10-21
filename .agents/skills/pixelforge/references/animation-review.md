# 按真实顺序与时长验收动画

软件公开 `preview --frame-height` 命令 检查垂直帧条的全部像素并生成 contact sheet；它不解释时序。软件公开 `animation-preview` 命令 补充**显式播放定义**的无损离线播放器，不改变生产 PNG，也不自动解释 `.mcmeta`、Pixelorama 项目 JSON、Blockbench 项目或其他游戏元数据。

## 建立项目派生的播放定义

先读目标版本的实际元数据/运行代码，确定帧矩形、索引顺序、逐帧时长、是否循环及插值。按真实单位换算为毫秒，再生成草稿 JSON；例如仅在项目确认一个动画 tick 为 50 ms 时，才把 time/frametime 乘以 50。Pixelorama 的 duration multiplier / FPS 可产生小数毫秒，保留这类时长，不为了整数或 GIF 时间粒度强行取整。导出默认值、缺省帧宽高、索引排列和插值规则由项目适配器负责核对，不能凭通用示例推断。

```json
{
  "schema": "pixelforge.animation-review/v1",
  "image": "flow.png",
  "frame_size": [8, 8],
  "loop": true,
  "interpolation": "none",
  "provenance": "填写实际元数据源文件、版本、单位与转换依据",
  "steps": [
    {"frame": 2, "duration_ms": 100},
    {"frame": 0, "duration_ms": 200},
    {"frame": 1, "duration_ms": 100}
  ]
}
```

例子只展示重排和不等时长，不是默认流体速度。`image` 相对播放定义所在目录解析，也允许绝对路径。`frame_size` 是原生帧宽高；默认按行从左到右、从上到下切分，尺寸须整除 PNG 的两个方向，因此支持水平、垂直与多列网格。

非规则 atlas 可以显式增加 `rectangles`，用 `[x,y,width,height]` 列出全部相关源帧，并用该列表的零基索引引用它们；矩形须在图片内、宽高与 `frame_size` 相同。帧坐标保留，播放器不裁掉透明留白、移动基线或逐帧居中。

```json
"rectangles": [[3, 4, 8, 8], [20, 4, 8, 8], [3, 19, 8, 8]]
```

每个播放步明确给出整数 `frame` 和正有限数值 `duration_ms`，时长可以为小数；允许重排、重复帧、回退和停顿。循环模式必须显式为 true/false。目前只支持 `interpolation: "none"`；目标定义启用插值时要使用项目真实渲染适配器，不能关掉插值后声称预览等价。错误索引、零/负/非数值/无穷时长、越界矩形、未知字段、APNG 和输入覆盖都会报错。

## 运行与观察

```powershell
python <skill-base-dir>/scripts/pixforge_client.py animation-preview flow-review.json --html flow-review.html --scale 6
```

使用已有浏览器或 HTML 预览查看生成的独立文件；文件内嵌逐帧 PNG，无外部网络依赖，不经过 GIF 调色或透明色转换。文件较大时仍保留完整源帧，按任务选择适当预览尺度。

可加 `--report flow-review-report.json` 将完整逐步 JSON 留在草稿目录，终端只返回帧数、播放步数、时长等摘要。原生画布通过 CSS 最近邻放大，避免为每帧保存放大后的画布；真实顺序、时长、全部源帧与 PNG RGBA 不因此改变。迭代中按 [运行效率](performance.md) 复用已有环境与必要预览。

播放器同时展示原尺寸和最近邻放大，提供播放/暂停、前后播放步、重播、深浅/棋盘背景、3×3 和前蓝/后红洋葱皮。默认 1× 使用声明时长；0.25×/2× 只用于检查。后台标签页暂停累计时间，返回时继续；浏览器刷新率影响可见采样，短于刷新间隔的步骤可能无法肉眼分辨，不能据此断言源帧缺失。单次播放停在最后一步；循环播放不自动复制首帧到尾部。

按真实 1× 速度看足够的循环，再逐步检查基线、负形、方向、亮度闪烁和循环边界；洋葱皮用于定位相邻播放步的轮廓，开启后有意改变展示颜色，不能用它验收材料配色。全部源帧展示区包含未播放帧，报告同时列出它们，便于发现漏引用或有意保留的素材；unused 不自动判错。

JSON 报告给出逐步起止时刻、总时长、帧矩形/哈希、包围盒、按真实顺序计算的相邻变化及循环边界。变化统计没有美观或流向通过阈值，连续播放同一帧也可能是有意停顿。退出码 `0` 表示播放定义验证和 HTML 导出成功，`2` 表示输入/参数问题；`motion_accepted` 始终为空，保留给人工视觉结论。

每帧的尺寸、alpha、调色板、局部结构等硬约束可继续使用 `preview`，也可用 `pixelforge preview PNG --animation-plan PLAN --output preview.png` 按计划的真实矩形一次检查全部源帧并生成播放器。此播放器证明声明计划可被播放；元数据转换正确、加载引用正确和最终游戏渲染仍需要对应证据。
