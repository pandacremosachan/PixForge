# 成套制作方法

按需要采用以下方法，不额外安装外部编辑器。

## Pixelorama：笔画、范围与动画

- 检查一像素线的多余转角、突刺和断点，按路径意图修正；保留真实直角。
- 用局部批次或独立层控制范围，`asset inspect` 的 `options` 的 preserve_mask/compare 复核保护区。检查蒙版不是绘制时 alpha lock。
- `asset inspect` 的 `options.tile` 只预览重复，不自动 wrap 越界笔画；跨边图案显式写到两侧。
- `palette` 是字符到 RGBA 的映射，不锁定最终色数；精确配色用 `asset inspect` 的 `options.palette` 检查合成结果。
- 动画保留源帧位置、播放顺序和逐步时长，见 [播放器](animation-review.md)。

## Blockbench：从 UV 和模型状态决定检查范围

读取实际模型面、引用纹理、UV 单位、旋转及状态。UV 到帧内像素换算为 `x=u×frame_width/uv_width`、`y=v×frame_height/uv_height`，再加当前帧矩形偏移。

共享 UV 会影响多个面；面旋转、模型旋转与 uvlock 分别处理。整数裁片只能检查采样区域，面向、tint、culling 和连接组合使用真实模型预览。使用外部编辑器时核对导出差异和项目扩展字段。

## Material Maker：结构控制细节，颜色映射控制家族

按“结构 → 分区/蒙版 → 明暗细节 → 颜色角色”组织命令：

1. 保留已认可的槽、面、棱和透明窗口母版。
2. 沿结构安排高光、阴影与磨损，用共同参数控制位置和尺度。
3. 映射底色、阴影、高光和类别色；不同材料需要时同时改变结构与反射。
4. 在原生像素网格制作；程序化草稿固定实际使用的种子、参数和输入，复核 alpha、调色板及平铺。

普通 Minecraft 材质按消费端实际机制交付。LabPBR 数据走 [专用流程](workflows/labpbr.md)。

## 来源

方法参考以下固定源码版本，未复制其实现或素材：

| 项目 | 固定版本 | 许可 |
|---|---|---|
| [Pixelorama](https://github.com/Orama-Interactive/Pixelorama/tree/e205f47699f424244a7ddc738bac2e0ca42769c1) | `e205f47699f424244a7ddc738bac2e0ca42769c1` | MIT |
| [Blockbench](https://github.com/JannisX11/blockbench/tree/7c92e27d237e365110030d73e92c5d1605f0d311) | `7c92e27d237e365110030d73e92c5d1605f0d311` | GPL-3.0 |
| [Material Maker](https://github.com/RodZill4/material-maker/tree/174f15edece663bf10f78588840873fa2fd17bc7) | `174f15edece663bf10f78588840873fa2fd17bc7` | MIT |
