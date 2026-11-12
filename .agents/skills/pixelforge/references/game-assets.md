# Minecraft 资源机制

目标和引用配置见 [Minecraft 资源](minecraft-assets.md)。先查项目现有资源、datagen、渲染层与颜色来源。

| 类型 | 关键约束 |
|---|---|
| 方块/地表 | 实际面方向、纹理尺度及平铺 |
| 物品/工具 | 原生轮廓、显示变换；优先复用已有材料图标体系 |
| GUI | 实际绘制尺寸、atlas/UV、九宫格和控件状态 |
| 玻璃/流体 | 透明区域、渲染层、背面和透明排序 |
| 发光/tint | 贴图颜色、表面发光、世界照明和代码着色分别接入 |
| 连接/复合模型 | 孤立、直线、弯角、分支、端盖及实际朝向组合 |

颜色由 tint、shader 或世界坐标提供时，沿用该来源。连接纹理检查真实中心件、连接臂和端盖的组合，单张 PNG 平铺不覆盖模型连续性。

## 动画

区分纹理图案、模型部件和离开模型的粒子，分别走 [材质动画](workflows/texture-animation.md) 或 [场景动画](workflows/scene-animation.md)。确认流向、周期、速度/亮度变化及启停语义。

读取实际元数据/代码，保留帧矩形、顺序、时长和插值。流动沿设计方向推进相位，检查相邻帧与末步到首步接续；不要每帧重生成噪声或强加首尾重复帧。

执行 `asset inspect --request-file <参数.json>`：

```json
{
  "path": "<动画PNG>",
  "options": {
    "frame_height": 32,
    "expect_size": [
      32,
      32
    ],
    "tile": true
  },
  "preview_path": "<讨论预览PNG>"
}
```

仅适用于已确认的垂直帧条，尺寸约束作用于每帧/所选区域。contact sheet 无时长，真实播放使用 [动画播放器](animation-review.md)。

UV 换算见 [UV 方法](upstream-workflows.md#blockbench从-uv-和模型状态决定检查范围)。项目扩展 loader、动态 UV 或渲染回调按消费项目验证，离线图像不作为游戏内证据。
