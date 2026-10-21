# 部件运动与粒子场景

动画先按用途选择机制。纹理图案流动、闪烁或逐帧换图使用 `texture`；轴、喷口、转子或悬浮部件的空间变化使用 `parts`；离开模型的水滴、火花和能量微粒使用 `particles`。三种机制可组合，不把所有效果压入 PNG 帧条。根据用户要求制作动画，直接配置场景并预览。默认目标为 Minecraft **1.20.1 / Forge**，具体工程另有版本或加载器时以工程为准，并在 `scene.target` 覆盖。

`animation_capabilities` / CLI `session animation-capabilities` 返回当前实现边界。场景本体是 `.pixforge` 的 `pixelforge_desktop.scene_animation`，随工程保存、撤销、恢复，并参与内容摘要与确认失效检查。旧工程不增加空场景字段，其原有内容摘要保持兼容。场景绑定真实模型 element 索引；替换绑定模型前须清除或重设场景，避免轨道静默绑定错误部件。场景只改变预览模型，不推断游戏碰撞或机器状态。

## 设计和准备

读取实际模型后，将以下场景定义交给 `scene-animation` / MCP `configure_scene_animation`。`elements` 和 `anchor_element` 是当前模型的零基索引，必须从当前工程读取。下例要求 element 0 确实存在，不能照抄到未知模型。

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
      "id": "nozzle_turn",
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

仅有空间动画时可保留一张静态贴图。需要材质动画时直接配置材质时序，或使用 `animation-prepare` 增加源帧；场景与材质沿用同一毫秒时钟。新增源帧和场景配置分别进入共享撤销历史。

## 坐标与时间

位置、枢轴、位移幅度和尺寸使用 Java 模型单位，16 单位为一格；速度为模型单位/秒，重力为模型单位/秒²。时间统一使用毫秒。目标版本默认每 tick 50ms，接入游戏时还需将位置和速度转换成方块/tick，并使用客户端渲染时间与 partial tick 插值。

`duration_ms` 为 100..120000；旋转使用有符号整数 `turns`（-64..64，非零），一周期结束回到同一姿态。`translate` / `scale` 使用三维 `amplitude`、整数 `cycles`（1..64）和 `phase_deg`。位移按正弦变化；缩放为 `1 + amplitude × sin(phase)`，各轴幅度限制在 -0.95..0.95，避免零尺度和反转。变换按数组顺序组合；旋转轴和法线正确归一化，非均匀缩放对法线使用逆转置变换。

发射器 `count_per_cycle` 明确一周期的发射数，等效发射率为 `count_per_cycle × 1000 / duration_ms`，避免任意帧率影响数量。方向归一化后按 `spread` 的三个分量加入固定种子的方向扰动，再归一化。`size` 与 `color` 为起止值，随粒子年龄线性插值；颜色为 RGBA 0..255。`blend` 支持 `alpha` 和 `additive`，当前粒子外观是纯色方形 billboard。粒子参与模型深度测试，按视角远近排序，透明粒子不写深度。

`anchor_element` 可省略或为 `null`，表示固定模型空间发射点；指定部件时，发射位置和速度方向按**出生时**的部件姿态计算。已发射粒子随后按初速度和重力飞行，不会被当前喷口拖动。循环场景预热上一周期仍存活的粒子，使用周期出生编号保持同种子重复性。非循环场景不预热，在结束时保留最终姿态和仍存活粒子的最终画面。

至多 64 条部件轨道、16 个发射器、每个发射器每周期至多 1024 粒子，同时存活粒子预算为 2048。寿命不可超过场景周期。相机边界保守覆盖整个运动和粒子包络，不随每帧姿态抖动。

## 预览与验收

C++ 原生工作台的“模型与形状”页使用同一场景描述。在模型面板下部可以载入场景 JSON，或清除场景绑定。底部显示独立的场景毫秒时钟，播放、暂停、恢复和底部时间条可定位连续时间；帧缩略图继续表示材质源帧，单帧不限制场景时长。空间播放由 C++ 本地采样，GPU 复用几何与纹理，软件回退也由 C++ 渲染，不逐帧请求 Python 核心。

```powershell
pixelforge session --runtime <目录> animation-capabilities
pixelforge session --runtime <目录> scene-sample --time-ms 1000
pixelforge session --runtime <目录> animation-preview --output <讨论播放器.html>
pixelforge ui --runtime <目录> set '{"panel":"shapes","time_ms":1000,"playing":false}'
pixelforge ui --runtime <目录> scene-sample --time-ms 1000
```

`scene_sample` / MCP `sample_scene` 与原生场景采样用于查看实际轨道数值，均不改作品。`animation-preview` 生成当前场景的阶段图与可拖动时间的 HTML，实际检查方向、时序、遮挡与循环。部件运动不要求贴图本身变化，用户确认仍绑定当前内容。

## 关键帧与命名状态（v2）

“动画 → 关键帧与状态编辑器…”对任意工程开放，“模型与形状”面板顶部也有入口。编辑器先复制一份独立草稿，可创建、复制、命名和删除状态，调整时长、循环、启动/停机目标以及结束后自动进入的状态。中间面板选择真实模型部件通道或粒子发射器；右侧编辑关键帧时间、值和到下一关键帧的插值，并显示当前模型的 C++ 草稿预览与所选通道曲线。旧周期运动保留原定义，点击“采样为关键帧”后才在草稿中转换。

校验同时检查模型索引、关键帧端点、循环闭合、状态引用、材质帧绑定及粒子预算。校验通过后可播放选中状态，触发启动/停机事件，或播放完整流程；时间定位不改变工程。点击“应用到工程”写入一条可撤销操作，取消则丢弃草稿。若工程在其他接口中已有变化，旧草稿不能覆盖新版本，须重开编辑器。打开旧 v1 场景不会改写文件；只有应用草稿时才写入 v2。

`pixelforge.scene-animation/v2` 可直接描述一个片段，也可用 `states` 描述命名状态机。状态名由用户指定，不内置特定机器或作品。根节点包含 `initial_state`、`states`、`transitions`、`preview_sequence`、`loop`、`seed` 与 `target`。每个状态有独立的 `id`、`label`、`duration_ms`、`loop`、`next`、`transforms`、`emitters` 和 `texture`；`next` 仅供非循环状态使用。`transitions` 的每项为 `{"from":"rest","event":"start","to":"active"}`，事件可用 `start` 或 `stop`。完整流程的每项为 `{"state":"rest","duration_ms":2000}`，从初始状态开始，跨状态时必须有声明的转换或自动 next。

部件通道增加 `keyframes` 和 `entry`。旋转值为角度，平移值为 `[x,y,z]`，缩放值为三个轴的倍率；发射器的 `emission` 使用相同关键帧结构，值在 0..1 之间，0 表示关闭新发射。每条曲线明确包含 0 和片段结束时刻，时间严格递增。以下曲线先加速到 90°，随后保持；它属于非循环旋转通道：

```json
{
  "id":"arm", "type":"rotate", "elements":[0],
  "pivot":[8,8,8], "axis":[0,1,0], "entry":"from_current",
  "keyframes":[
    {"time_ms":0,"value":0,"easing":"ease_in"},
    {"time_ms":800,"value":90,"easing":"hold"},
    {"time_ms":1600,"value":90,"easing":"linear"}
  ]
}
```

插值取左侧关键帧的 `easing`：`hold` 保持，`linear` 线性，`smooth` 平滑，`ease_in` 缓入，`ease_out` 缓出。`entry=absolute` 使用曲线的绝对值；`from_current` 将第一段的起点替换为切换瞬间的真实姿态；仅旋转还可用 `relative`，将角度叠加到当前角度。跨状态保持相同的部件通道 id、类型、部件、支点、轴和顺序，以及相同的发射器 id/顺序；静止状态用保持曲线，关闭发射用 emission=0。切换时已出生的粒子继续沿原来的世界轨迹飞行，关闭发射不使它们瞬间消失，进入短循环状态也不改变其出生姿态。

`texture={"mode":"play","speed":1}` 延续材质时钟；`{"mode":"hold"}` 保持进入状态时的材质帧，也可指定 `frame`，索引须来自当前材质播放步骤。增删其他源帧时，固定引用跟随原来的源帧重排；仍被状态固定引用的源帧不能直接删除，须先修改该状态的材质设置。循环曲线首尾闭合，旋转允许整数圈差；非循环状态可停在任意角度。最多 16 个状态，每条曲线 2..128 个关键帧，状态机合计不超过 4096 个关键帧，切换中的粒子总量不超过 2048。完整流程总时长不超过 120 秒。

```powershell
pixelforge session --runtime <目录> scene-validate <草稿.json>
pixelforge session --runtime <目录> scene-sample --scene-state <状态id> --time-ms 500
pixelforge ui --runtime <目录> set '{"scene_event":"start","playing":true}'
pixelforge ui --runtime <目录> set '{"scene_demo":true,"time_ms":2500,"playing":false}'
pixelforge ui --runtime <目录> scene-context
pixelforge ui --runtime <目录> scene-editor open
```

`scene_validate` / MCP `validate_scene_animation` 只校验草稿，`scene_sample` 可接受状态 id 或原生 `ui_scene_context` 返回的有界播放快照。原生 `ui_scene_editor` 和 CLI `ui scene-editor` 的字段/动作名称可从编辑器 status 读取；`field`、`invoke` 只修改草稿，`apply` 才写入作品。HTML 预览提供同样的状态选择、启动、停机和完整流程控制。

## 游戏接入边界

软件 2.4+ 已提供 Forge 1.20.1 的部件、状态与粒子执行器代码导出，见 [Forge 运行时接入](forge-runtime.md)。通过公开目标配置、只读代码预览和正式导出流程生成接入包或可构建示例模组。SceneRuntime.Player 按 tick 推进，渲染按 partial tick 采样；生产注册、真实运行状态和同步仍接到消费项目。scene_sample 和编辑器播放继续是离线证据，不代表代码已部署到游戏。

预览报告中的 `integration` 记录实际目标、所用部件/发射器和待绑定信息。默认 Forge 1.20.1 中，动态部件通常接入 `BlockEntityRenderer.render` / `PoseStack`；粒子需要客户端 provider、类型与贴图资源，并按项目选择客户端发射或服务器同步。具体注册、namespace、资源 id、工作状态同步必须读取真实模组工程后实现和编译。当前预览不包含游戏安装、世界碰撞、风、Minecraft 光照、骨骼系统或自定义 GLSL；加色混合也需游戏端相应的 RenderType。

参考实际机制：Cyclic 1.20.1 的 [TileSprinkler](https://github.com/Lothrazar/Cyclic/blob/19032f230356f6bc258a2a8b31758134228bd3c8/src/main/java/com/lothrazar/cyclic/block/sprinkler/TileSprinkler.java) 在客户端生成水粒子；Draconic Evolution 的 [RenderTileEnergyCore](https://github.com/Draconic-Inc/Draconic-Evolution/blob/4e7fc310f025a255b685c9e9754d2369f8d7b561/src/main/java/com/brandon3055/draconicevolution/client/render/tile/RenderTileEnergyCore.java) 组合模型旋转与着色器；Create 的 [KineticBlockEntityRenderer](https://github.com/Creators-of-Create/Create/blob/588124239141029c5321afd38d20c2eaf872b32b/src/main/java/com/simibubi/create/content/kinetics/base/KineticBlockEntityRenderer.java) 依渲染时间与转速计算部件旋转。这里实现独立通用场景，不复制这些项目的素材或渲染代码。Forge 接入依据官方 [BER 文档](https://docs.minecraftforge.net/en/1.20.x/blockentities/ber/) 与 [粒子文档](https://docs.minecraftforge.net/en/1.20.1/gameeffects/particles/)。