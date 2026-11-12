# 纹理逐帧动画

确认单帧尺寸、实际 UV、源帧布局、播放顺序、逐步时长、循环和插值。几何运动/粒子走 [场景动画](scene-animation.md)，已有工程保留当前像素及时序。

## 制作与调整

按 [操作约定](../operations.md) 打开或复用工作台。新作品读取 texture-animation 模板，替换底图和变化；先 canvas draw 完成底图，再 `animation prepare-frames` 的 `settings` 准备实际源帧。

执行 `animation prepare-frames --request-file <参数.json>`：

```json
{
  "settings": {
    "frame_count": 4,
    "frame_size": [
      16,
      16
    ],
    "steps": [
      {
        "frame": 0,
        "duration_ms": 100
      },
      {
        "frame": 1,
        "duration_ms": 150
      },
      {
        "frame": 2,
        "duration_ms": 100
      },
      {
        "frame": 3,
        "duration_ms": 150
      }
    ],
    "loop": true,
    "interpolation": "none"
  },
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

该工具保留图层和已有帧，新增槽复制首源帧；按返回 rectangles 写坐标。需要插入、复制、删除时使用 animation edit-frames，以 step_index 指定播放位置。纯 GUI 动画跳过模型页。

用 canvas draw 修改各帧。调整完整时序时，直接把 frame_size、rectangles、steps、loop、interpolation 传给 `animation configure` 的 `settings`。已有 .mcmeta 用 animation minecraft-inspect 只读检查，再 animation minecraft-configure 带版本应用，见 [元数据](../runtime-678.md)。

## 播放与交付

调用 animation preview 查看内存中全部帧与真实播放器；独立 PNG 则调用 asset playback。实际播放完整循环，检查方向、相位、亮度、基线和接续；workbench view 的 playing=true 可展示同一窗口。流动沿设计方向推进，不每帧重生噪声。

配置真实 target 后按 [资源检查与导出](../operations.md#资源检查与正式导出) 交付，核对 PNG 与 .png.mcmeta 尺寸、索引及真实时长。Forge 1.20.1 纹理时长须正整数 50 ms tick，不静默取整；单次播放或不支持的插值选实际运行时。独立机器启停走 [运行时接入](../forge-runtime.md)。
