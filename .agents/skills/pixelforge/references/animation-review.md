# 真实顺序与时长播放器

现有 PNG 的 `asset inspect` 的 `options.frame_height` 仅检查帧像素。真实时序使用本页显式播放定义；.mcmeta 原生检查见 [元数据](runtime-678.md)。

## 播放定义

从实际元数据/代码转换帧矩形、索引顺序、毫秒时长、循环和插值，provenance 记录来源/单位。仅目标 tick 确认为 50 ms 时乘以 50。

```json
{
  "schema": "pixelforge.animation-review/v1",
  "image": "flow.png",
  "frame_size": [
    8,
    8
  ],
  "loop": true,
  "interpolation": "none",
  "provenance": "实际来源、版本和单位",
  "steps": [
    {
      "frame": 2,
      "duration_ms": 100
    },
    {
      "frame": 0,
      "duration_ms": 200
    },
    {
      "frame": 1,
      "duration_ms": 100
    }
  ]
}
```

image 相对 JSON 目录解析。默认按行切分规则网格，PNG 两边须能整除 frame_size；不规则布局增加 rectangles：

```json
{
  "rectangles": [
    [
      3,
      4,
      8,
      8
    ],
    [
      20,
      4,
      8,
      8
    ],
    [
      3,
      19,
      8,
      8
    ]
  ]
}
```

矩形为 [x,y,w,h]，在 PNG 内且同 frame_size，frame 为零基索引。每步 duration_ms 为正有限数，可小数，允许重复/重排。帧坐标与留白保留。

仅支持 interpolation=none；目标插值使用实际渲染适配器。未知字段、无效索引/时长、越界、APNG、输入覆盖会报错。

## 运行与观察

执行 `asset playback --request-file <参数.json>`：

```json
{
  "plan": "<播放定义JSON>",
  "html_path": "<播放器HTML>",
  "report_path": "<时序报告JSON>",
  "scale": 6
}
```

实际打开 HTML，以 1× 观察方向、基线、亮度、停顿和循环，再逐步/洋葱皮定位问题。HTML 内嵌全部原生 RGBA 帧，支持深浅背景、平铺和步进；洋葱皮不用于验收配色。

未播放帧仍展示并报告，不自动判错。单次播放停在末步，循环不追加首帧。短于浏览器刷新间隔的步骤可能看不清。

读取报告中的真实时间轴、矩形/哈希、包围盒和相邻/循环变化；`motion_accepted` 留空不代表动作已验收，实际看图后再描述运动效果并交用户评议。检查退出码、ok 与错误字段。生成成功只表示定义有效；硬约束通过 asset inspect 的 animation_plan 选项检查全部源帧。
