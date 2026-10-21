# 运行效率与分阶段检查

让检查服务本轮设计问题。常见小尺寸绘制与 PNG 检查的计算量很小，反复启动 Python、同步运行环境、输出大报告或生成大量放大预览反而容易占掉更多时间。使用已有运行时和按问题选项，不靠抽掉帧或放宽约束加速。

## 运行环境与批量操作

- 复用已经安装并通过 `doctor` 检查的软件。skill 不准备图像处理环境，不同步软件私有依赖；同一项目复用同一 runtime，避免反复重建工程或启动核心。
- 一套资源可在同一个 `.px` 文件里依次 `new`、绘制、`render` 多张原生 PNG，重用角色与结构方案，减少进程启动。每次 `new` 会重置画布与调色板，必须明确重新定义本张素材的颜色。
- 新修改用 `run --atomic`，不确定时先 `--dry-run`；`--preview` 可在同次调用生成独立证据。事务预演不写脚本内的生产输出。交付记录绑定当前像素与依赖，仅在内容和要求仍一致时复用，详见 [事务和验收](transactions-review.md)。
- 大量同类型 PNG 可在一个外部脚本中依次调用公开命令，按真实尺寸、区域和语义传参；不能导入软件检查器以减少启动次数。下面只使用 Python 标准库：

```python
from pathlib import Path
import subprocess
import sys

client = Path("<skill-base-dir>/scripts/pixforge_client.py")
images = [Path("draft/part-a.png"), Path("draft/part-b.png")]
codes = []
for index, image in enumerate(images):
    codes.append(subprocess.run([
        sys.executable, str(client), "preview", str(image),
        "--expect-size", "32", "32", "--report",
        str(Path("draft/reports") / f"{index:03d}-{image.stem}.json"),
    ]).returncode)
raise SystemExit(max(codes, default=0))
```

示例只声明共同的原生尺寸；alpha、对称、调色板等按本组素材的真实要求增加。报告名含序号，避免不同目录同名图片覆盖报告。非零退出码仍须处理；批量运行不把失败吞成成功。没有新改动或新问题时复用已验证证据，不反复跑整套工具测试。

## 按阶段选检查

| 阶段 | 本轮需要完成的检查 | 合适的输出 |
|---|---|---|
| 调整大形/一个部件 | 原尺寸轮廓、留白、相关局部轴线与必要像素约束 | 原生 PNG，加一张最近邻预览或局部裁片 |
| 调整材料/家族配色 | 主次、颜色角色、改动范围；影响材料的背景/平铺或模型面 | 代表样或受影响成员的对照图，必要约束报告 |
| 调整动画 | 变动相关的帧与时序问题，保持真实位置和时长 | 重用播放定义，生成原生帧播放器；修改后最终看全部帧及循环 |
| 扩展家族/交付 | 所有受影响成员、完整帧和相关连接/模型状态，以及实际资源引用 | 完整适用验收与必要视觉证据 |

PNG 检查器没有 `--preview` 时不会生成预览图；`--clusters`、`--tile`、调色板及保护蒙版按需要启用。局部修改可以用 `--region` 减少像素分析范围，但保护蒙版仍检查完整源图，不能为加速隐藏误改。最终验收不省掉必要的全帧/状态检查。

长动画避免每次生成“每一帧 × 三种背景 × 大倍数 × 3×3”的巨幅 PNG。按当前问题使用较小 `--scale` 和相关背景，或用 软件公开 `animation-preview` 命令 在浏览器里切换背景/平铺；所有源帧依然保留。PNG 原尺寸始终不变，降低展示倍数不改变硬约束检查。模型规则/UV 没有变化时复用已验证的项目适配器，不重复研究上游或建立新的渲染环境。

## 完整证据与简短输出

两个检查 helper 都支持 `--report full.json`：完整 JSON 落盘，stdout 返回摘要。所有帧、像素约束和播放步骤仍会计算；失败帧摘要最多列八帧并给出省略数，完整失败信息留在报告中。未传该参数时保持原来的完整 stdout JSON。

```powershell
python <skill-base-dir>/scripts/pixforge_client.py preview asset.png --expect-size 32 32 --report asset-review.json
python <skill-base-dir>/scripts/pixforge_client.py animation-preview flow-review.json --html flow-review.html --report flow-review-report.json
```

先读摘要和失败项，只有需要定位时再读取相应报告区域。一次工具调用完成相关的多张图，避免把大量完整 JSON、逐像素数据或 base64 放进对话；视觉验收仍查看实际输出图。

## 当前实现的性能边界

对称、alpha/轮廓、像素差异和平铺差值使用 Pillow 原生图像运算；精确色簇按请求分析。动画按源帧准备比较数据，相同帧对重复播放时复用统计结果，但每个播放步骤、时长与转换关系完整保留。HTML 画布保存原生像素并由 CSS 最近邻放大，全部源帧仍可见；暂停/后台不做播放步骤扫描。

耗时取决于原生总像素、帧数、色簇和预览输出面积。新尺寸或大型任务出现明显等待时，测真实输入并区分启动、像素分析与导出，按瓶颈调整展示或复用计算。不得把减少帧、平滑缩小生产 PNG、关闭必要约束或仅返回“成功”当性能优化。
