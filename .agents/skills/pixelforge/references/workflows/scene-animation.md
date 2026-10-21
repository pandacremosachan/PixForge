# 部件、状态与粒子动画

适用于模型部件的旋转/位移/缩放、启停关键帧和离开模型的粒子。单张静态材质即可驱动场景，不为几何运动强行增加纹理源帧。新增素材和只给现有作品加动画属于不同任务；后者保留原模型和像素。

## 准备和选择

确定真实部件索引、支点/轴、运动方向、周期或非循环时长、启停姿态、事件/状态、粒子出生位置/方向/数量/寿命、目标运行时。所有位置与速度使用模型单位，16=一格；时间为 ms。模型索引从 0 起，不凭部件名字猜索引。

新建示例选择 scene-states（idle/active 关键帧）或 particles（转子与跟随出生的粒子）：

```text
python <skill-dir>/scripts/scaffold.py scene-states --output <D> --namespace examplemod --name rotor
```

两模板的 model.json 都明确 element 0=base、1=rotor，scene.json 的 elements=[1] 与其对应。用于实际机器时替换成真实索引、几何和 UV。已有动画任务跳过下面的新建/绘图部分，直接检查当前模型与 scene。

## 建立模型并应用场景

按 [操作约定](../operations.md) 建立 c、s、D：

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "model", "--model", D / "model.json",
            "--width", p["width"], "--height", p["height"])
c.read("model-uv")
s = c.write(s, "edit", D / "draw.px", "--label", "模型静态材质")
draft = c.read("scene-validate", D / "scene.json")
assert draft["report"]["valid"]
s = draft["state"]
s = c.write(s, "scene-animation", D / "scene.json")
c.read("animation-preview", "--output", D / "scene.html")
c.read("shape-preview", "--output", D / "model.html", "--overlays")
s = c.write(s, "save", D / "rotor.pixforge")
```

scene-validate 不应用草稿，scene-animation 才进入一条共享撤销历史。出错先修正被指出的索引、曲线、循环闭合或帧绑定，不删除轨道以获得空场景通过。

## 状态流程

scene-states 模板使用 v2 状态机：idle 保持相对角度、active 每 2000 ms 转一圈；start 从 idle 到 active，stop 返回 idle。两个状态保留同一通道 ID、element、支点、轴与顺序，entry=relative 保持切换时的角度。完整预览为待机 1000 ms、运行 4000 ms、待机 1000 ms，并重复。根据真实需求加入启动/减速片段；它们应是非循环状态并明确 next 或事件，不能假装模板已经包含加减速。

```python
idle = c.read("scene-sample", "--scene-state", "idle", "--time-ms", "500")
active = c.read("scene-sample", "--scene-state", "active", "--time-ms", "500")
```

数值采样核对绑定和姿态，实际打开 scene.html 分别播放状态、触发 start/stop、播放完整流程。单状态静止截图不能证明过渡连续。原生窗口需要时使用相同 R 打开 GUI，并通过 ui set 的 scene_event/scene_demo 查看；它们只改变视图。

更多曲线选择为 rotate 角度、translate 三维位移、scale 三维倍率，关键帧完整包含 0 和片段终点；hold/linear/smooth/ease_in/ease_out 作用于左关键帧后的区间。循环旋转允许整圈差，平移/缩放必须闭合。详细字段见 [场景协议](../scene-animation.md)。

## 粒子流程

particles 模板将 anchor_element=1 绑定转子；出生点和方向按**出生瞬间**姿态转换，已经发出的粒子不跟着当前转子移动。固定空间喷口改为 null 或移除 anchor_element。示例每 2000 ms 发射 24 个、寿命 700 ms、alpha 混合，不代表所有设备预算。

应用上面的同一 scene 命令后，用 `c.read("scene-sample","--time-ms","500")` 检查粒子位置和数量，再在 HTML 中看完整轨迹、方向、重力、遮挡和循环。需要停止发射时在各状态保留相同发射器 ID，用 emission=0 的曲线控制新发射；现存粒子继续飞完。改变种子、频率、寿命和速度时重新查看完整循环，不能仅凭数量统计验收。

## 游戏交付与完成标准

保存 .pixforge 和可审查 HTML 始终可用，不要求先导出生产 PNG。运动场景不是 vanilla model JSON 的可执行动画；仅导出静态方块或 PNG 会丢掉其运行行为。

只需离线工程时交付当前工程和预览即可。要接入 Forge 1.20.1，继续 [Forge 运行时接入](../forge-runtime.md)：配置实际 namespace、包名、BlockEntity/结构、状态同步、runtime 场景/粒子资源，执行 minecraft-check --include-generated-code，查看生成 Java 和定义，使用当前指纹与真实批准导出 forge-integration 或 forge-mod。前者接已有项目，后者是独立示例；不把示例注册替代生产对象，不在 skill 重写执行器。

模板 target.json 仅是显式 texture-only 绑定，用于确实单独需要材质的交付；它不会生成部件/粒子代码，软件会报告未包含的运行时效果。不得把它作为完整动画接入完成。

检查所有绑定元素、轨道/发射器、关键帧端点、状态入口、事件/自动 next、完整播放顺序、材质时钟和暂停恢复。更换模型前清除或重绑旧场景，避免索引指向别的部件。离线播放器和采样分别说明其证据范围，游戏代码还须在消费项目编译，实例行为与性能需要实际游戏证据。
