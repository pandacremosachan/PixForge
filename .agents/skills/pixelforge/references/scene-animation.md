# 部件运动与粒子场景

纹理逐帧见 [材质动画](workflows/texture-animation.md)，场景制作见 [场景流程](workflows/scene-animation.md)。`animation capabilities` 查询当前能力。场景绑定真实 element 零基索引，换模型前清除或重绑。

## v1 周期场景

```json
{
  "schema": "pixelforge.scene-animation/v1",
  "duration_ms": 4000,
  "loop": true,
  "seed": 19,
  "target": {
    "loader": "forge",
    "minecraft": "1.20.1"
  },
  "transforms": [
    {
      "id": "turn",
      "type": "rotate",
      "elements": [
        0
      ],
      "pivot": [
        8,
        8,
        8
      ],
      "axis": [
        0,
        1,
        0
      ],
      "turns": 1,
      "phase_deg": 0
    }
  ],
  "emitters": [
    {
      "id": "water",
      "position": [
        12,
        8,
        8
      ],
      "direction": [
        1,
        0.4,
        0
      ],
      "spread": [
        0.2,
        0.2,
        0.2
      ],
      "speed": 5,
      "gravity": [
        0,
        -8,
        0
      ],
      "lifetime_ms": 1000,
      "count_per_cycle": 80,
      "size": [
        0.65,
        0.15
      ],
      "color": [
        [
          90,
          180,
          255,
          220
        ],
        [
          90,
          180,
          255,
          0
        ]
      ],
      "blend": "alpha",
      "anchor_element": 0
    }
  ]
}
```

示例需 element 0 存在；target 按消费项目设置。单张静态贴图也能驱动部件/粒子，场景和材质共用毫秒时钟。

## 坐标与时间

| 字段 | 约束/语义 |
|---|---|
| 位置、支点、尺寸 | 模型单位，16=一格；速度单位/秒，重力单位/秒² |
| duration_ms | 100..120000 ms |
| rotate | turns 为非零整数 -64..64，支持 phase_deg |
| translate / scale | 三维 amplitude、cycles 1..64、phase_deg；正弦变化 |
| scale | `1+amplitude×sin(phase)`，各轴 amplitude 为 -0.95..0.95 |
| 变换顺序 | 按数组顺序组合 |
| count_per_cycle | 每周期发射数，等效速率为 count×1000/duration_ms |
| direction / spread | 归一化方向加固定种子扰动后再归一化 |
| size / color | 起止值随年龄线性插值，color 为 RGBA 0..255 |
| blend | alpha / additive；纯色方形 billboard，参与深度测试、透明不写深度 |
| anchor_element | 部件出生姿态变换位置/方向；null 为固定模型空间喷口 |

已出生粒子按速度/重力继续运动，不随喷口拖动。循环预热上周期存活粒子；非循环保留结束姿态和最终画面。

限 64 条部件轨道、16 发射器，每发射器每周期 1024 粒子，同时存活 2048；寿命不超过周期。

## 关键帧与命名状态（v2）

`pixelforge.scene-animation/v2` 支持单片段或 states 状态机。根字段：initial_state、states、transitions、preview_sequence、loop、seed、target。

状态字段：id、label、duration_ms、loop、next、transforms、emitters、texture。next 仅用于非循环状态。转换项为 `{"from":"rest","event":"start","to":"active"}`，事件 start/stop；预览步骤为 `{"state":"rest","duration_ms":2000}`，按声明转换或 next 连接。

```json
{
  "id": "arm",
  "type": "rotate",
  "elements": [
    0
  ],
  "pivot": [
    8,
    8,
    8
  ],
  "axis": [
    0,
    1,
    0
  ],
  "entry": "from_current",
  "keyframes": [
    {
      "time_ms": 0,
      "value": 0,
      "easing": "ease_in"
    },
    {
      "time_ms": 800,
      "value": 90,
      "easing": "hold"
    },
    {
      "time_ms": 1600,
      "value": 90,
      "easing": "linear"
    }
  ]
}
```

- rotate 值为角度，translate 为三维位移，scale 为三轴倍率；emission 0..1 控制新粒子发射。
- 曲线时间严格递增，含 0 和片段终点；左关键帧 easing 取 hold/linear/smooth/ease_in/ease_out。
- entry 的 absolute 使用绝对值，from_current 以切换瞬间姿态替换起点；旋转还支持 relative 叠加当前角度。
- 跨状态保持通道 id、类型、部件、支点、轴、顺序，以及发射器 id/顺序；静止用保持曲线，停发用 emission=0，已有尾迹继续。
- 循环曲线首尾闭合，旋转允许整数圈差；非循环可停在任意姿态。
- texture 的 `{"mode":"play","speed":1}` 延续时钟，`{"mode":"hold"}` 固定进入帧，也可给 frame。索引来自材质播放步骤；被固定引用的源帧须先解绑再删除。
- 限 16 状态，每曲线 2..128 关键帧，合计 4096；过渡粒子总量 2048，完整预览总时长不超过 120 秒。

## 预览与编辑

执行 `workbench view --request-file <参数.json>`：

```json
{
  "settings": {
    "panel": "shapes",
    "scene_event": "start",
    "playing": true
  }
}
```

animation scene-validate 只校验，animation scene-configure 才应用。animation sample 可接收状态 id 或原生 scene-context 快照；数值采样与实际播放分别检查。

通过 `workbench editor --editor-kind scene; operation="open"` 打开独立草稿，从 `status` 读取字段/动作标识，以 `field/invoke` 修改；`apply` 校验版本并提交一条历史，`cancel` 丢弃草稿。通过 HTML 播放器或原生视图检查命名状态、启停事件和完整流程。

## 游戏接入

使用 [Forge 运行时](forge-runtime.md) 绑定真实机器状态、同步与客户端渲染。场景不自动改变碰撞；光照、风、骨骼、自定义 shader 等按消费项目实现。编辑器和采样属于离线验证。
