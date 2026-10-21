# 材质逐帧动画

适用于纹理上的流动、闪烁和图案变化。部件空间运动与离开模型的粒子使用 [场景动画](scene-animation.md)，可与本流程组合。已经有动画工程时保留实际帧矩形和时序，不重新创建。

## 输入与产出

确定原生单帧尺寸、模型/UV、需要变化的区域、源帧数、播放顺序、逐步时长、循环、插值以及消费端元数据。图集物理排列不等于播放顺序。只在目标确为 Forge 1.20.1 纹理动画时采用 50 ms tick；最终时长须为正整数 tick，不能静默四舍五入。

产出 .pixforge、全部源帧、真实时长 HTML、PNG 和 .png.mcmeta；只导出 PNG 不能交付完整 Minecraft 动画。

## 从静态工程开始

新作品可用模板；已有作品跳过新建和 seed 绘图，直接使用其 status：

```text
python <skill-dir>/scripts/scaffold.py texture-animation --output <D> --namespace examplemod --name indicator
```

按 [操作约定](../operations.md) 建立 c、s、D 后：

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "cube-shared", "--face-size", p["face_size"])
s = c.write(s, "edit", D / "draw.px", "--label", "动画静态底图")
s = c.write(s, "animation-prepare", D / "frames.json")
state = s["state"]
print(state["animation"]["rectangles"])
# 模板的 4 个 16×16 源帧为 (0,0)、(0,16)、(0,32)、(0,48)。
s = c.write(s, "edit", D / "animate.px", "--label", "逐帧变化")
c.read("preview", "--output", D / "all-frames.png")
c.read("animation-preview", "--output", D / "timed-preview.html")
s = c.write(s, "save", D / "indicator.pixforge")
```

animation-prepare 保留所有现有层和源帧，用第一源帧复制新增位置，并给出实际 rectangles；模板 animate.px 只适用于上面的示例布局。改帧尺寸/已有帧数量时按返回矩形编写坐标，不能将每帧 y 固定为 n×16。它只增加源帧，不能用较小 frame_count 删除已有帧。

frames.json 是明确可改的播放定义：示例 4 帧时长为 100、150、100、150 ms；允许重复/重排源帧和不等时长，不把“平均帧率”作为生产定义。场景状态固定引用的帧仍须存在。涉及法线/材质数据时，软件同步搬运各通道，修改应保持各帧语义一致。

## 查看与调整

实际打开 HTML，按 1× 速度看完整循环，再逐步看源帧、方向、相位、亮度变化和末步到首步接续。闪烁示例是亮度变化，不代表流动模板；流动应沿纹理设计方向推进相位，不每帧重新随机噪声。不自动复制首帧到最后造成额外停顿。

需要调整时序时，将当前 animation 对象整理为 frame_size、rectangles、steps、loop、interpolation 写入 plan.json，再用 `c.write(s,"animation",D/"plan.json")` 加载；该文件不是另存一张 PNG。只读 preview 或播放定位不改变内容。实际像素变化后重新生成预览。

已有 .mcmeta 时，先用 `minecraft-animation --metadata FILE` 只读检查；确认当前图集匹配后用 `minecraft-animation-apply --metadata FILE` 加令牌应用。不能把 .mcmeta 直接传给 animation 或将默认 100 ms 当游戏时长。具体见 [动画元数据](../runtime-678.md)。

## Minecraft 交付

```python
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
check = c.read("minecraft-check")
s = check["state"]
digest = check["validation"]["validation_digest"]
s = c.write(s, "save", D / "indicator.pixforge")
```

展示全部原生帧和真实时长播放器，再按 [正式导出](../operations.md#资源检查与正式导出) 使用真实批准、当前 digest 导出资源。软件会按目标需要无损重排为垂直帧条，保留像素、索引与时长；核对 .png.mcmeta 的 frame dimensions、frametime/frames 与已展示定义一致。单次播放、不能用整 tick 表达的时长、当前未支持的插值需明确调整或选择项目运行时，不能改了语义却声称等价。

纹理图集时钟是共享材质行为，不能表示每台机器独立启动或停止；独立实例走 [Forge 运行时接入](../forge-runtime.md)。未接入游戏时报告已验证源像素、声明时序和资源引用，不宣称真实加载与性能已经验证。
