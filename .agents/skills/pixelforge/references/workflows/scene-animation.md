# 部件、状态与粒子动画

用于部件旋转/位移/缩放、启停状态和粒子。读取真实 element 零基索引、支点、轴、周期和事件；位置单位 16=一格，时间 ms。只加动画时保留模型与贴图。

## 应用与预览

按 [操作约定](../operations.md) 打开或复用工作台。读取 scene-states / particles 模板，用实际几何、索引和 UV 替换底座 0、转子 1；新作品通过 project create 创建单图集模型，再 model uv、canvas draw。

把 scene.json 解析成对象，先 animation scene-validate --settings，通过后 animation scene-configure --settings 提交。用 animation sample 检查数值，再 animation preview 和同一工作台播放；保存 .pixforge 并展示像素和真实模型。

执行 `animation sample --request-file <参数.json>`：

```json
{
  "scene_state": "active",
  "time_ms": 500
}
```

scene-states 示范 idle/active、start/stop 与完整 preview_sequence，不提供通用加减速。跨状态保持通道 ID、部件、支点/轴和顺序，relative 旋转可延续当前角度；见 [场景协议](../scene-animation.md)。通过 workbench view 的 scene_event/scene_demo 播放启停及完整流程，静态截图不能覆盖过渡。

粒子 anchor_element 使用出生时的部件姿态，已出生粒子继续飞行；null 为固定喷口。emission=0 只停新发射，保留尾迹。检查方向、重力、遮挡、数量预算和循环。原生草稿编辑使用 workbench editor --editor-kind scene，先读 status 的字段/动作 ID。

## 交付

离线交付 .pixforge 和真实播放器。游戏执行走 [Forge 运行时接入](../forge-runtime.md)，读取真实机器状态并编译接线。模板 target 仅做 texture-only 导出；完整部件/粒子程序使用 forge-integration/forge-mod。换模型前清除或重绑索引。
