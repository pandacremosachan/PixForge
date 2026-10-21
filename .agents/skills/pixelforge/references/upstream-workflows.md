# 三个项目的方法如何用于 PixForge

这份整合基于 2026-10-11 读取的固定源码提交，提取绘制与验收方法。默认使用独立 PixForge 软件的公开 CLI/MCP；skill 不加载图像处理实现。外部编辑器是可选工具，不要求安装、操作桌面或启动游戏。研究版本与消费项目版本分别确认，不能用上游当前默认格式替代项目规则。

| 来源 | 吸收的方法 | PixForge 中的落实 |
|---|---|---|
| Pixelorama | 细线转角处理、选择/alpha 限制、图层、平铺绘制、逐帧时长与洋葱皮 | 笔画检查、局部保护蒙版、结构分层、全部帧检查、声明时序的离线播放器 |
| Blockbench | 从模型面定位 UV、在帧内取样、面/岛绘制边界、Minecraft 格式导出及动画元数据 | UV 与状态矩阵、真实模型适配器优先、导出差异检查、播放顺序/时长核对 |
| Material Maker | 共享结构场、蒙版与颜色映射、可复现参数、像素化/量化/抖动、2D/3D 分开预览 | 角色调色板和结构母版、受结构约束的细节、精确颜色校验、原尺寸与真实模型两层验收 |

## Pixelorama：笔画、范围与动画

**细线转角。** 上游的 pixel-perfect 根据一条笔画中连续位置的关系撤回多余的转角像素，而且只对一像素画笔开启。用于 PixForge 时，检查一像素斜线是否出现无意的 L 形双宽转折、突刺或断点，再按路径意图修正。保留真实直角、铰接、圆弧转折和有意的双宽线；最终 PNG 缺少笔画历史，不能靠遍历所有 2×2 区域自动删除角像素。此方法也不等于取消所有抗锯齿。

**修改范围。** 先确定可编辑的部件/选择区、受保护的区域和允许的 alpha 变化，再写像素。上游的选择区与 alpha lock 是绘制时限制；PixForge 当前没有同名命令，不能声称已经开启。可用准确基底、局部 `patch`、独立结构层降低误改风险，再用 `--compare` 与 `--preserve-mask` 检查最终 PNG。保护蒙版 alpha 255 指定必须保持 RGBA 的像素，alpha 0 允许修改；蒙版必须为原生尺寸和硬边 alpha。只需要保持轮廓时，另检查实际结构层或 alpha，不把“锁定完整 RGBA”与“保持形状”混为一谈。

**平铺绘制与平铺预览。** 上游在平铺模式下把坐标映射回画布，使跨边界笔画可以连续。PixForge 的 `--tile` 只显示重复结果；原生 CLI 的越界写入可能裁切，不会自动 wrap。跨边缘的图案应显式拆到两侧，或在草稿生成步骤按 `(x mod W, y mod H)` 写入，再导出原生 PNG 验收。保护原有非平铺图集区，不能对整个 atlas 做 wrap。像素周期正确仍要看重复大斑、条带和方向。

**图层与调色板。** 结构、类别色、材料明暗、磨损和发光可以按需要拆层，便于隐藏细节后核对大形。层名和语义可自行定义；隐藏层不会进入最终合成。外部编辑器的 indexed palette 可以管理颜色索引，本工具的 `palette` 只是命令字符到 RGBA 的映射；导出 PNG 不据此获得索引约束。若项目或家族有精确配色，使用 `--palette` 检查最终合成，尤其注意半透明叠层产生的新颜色。

**动画。** 保留源帧坐标、每帧时长、播放顺序、重复与标签语义。上游导出把 frame duration 转成实际秒数，洋葱皮显示相邻帧；这些是检查基线和动作接续的方法，不能用默认均速代替项目定义。PixForge 的新播放器接受明确的播放定义、逐步时长和循环模式，显示前蓝/后红洋葱皮、全部源帧和循环变化。具体协议见 [动画验收](animation-review.md)。

## Blockbench：从 UV 和模型状态决定检查范围

**先建立采样记录。** 对需要检查的模型面或动态四边形，记录资源源文件、状态/邻接条件、部件、面朝向、纹理引用链、原始 UV、UV 单位范围、帧尺寸、面旋转、模型/状态旋转、uvlock、tint、渲染层及方向明暗。只记录本次相关状态；简单物品不强行制造整张表。复杂连接件先覆盖孤立、直线、弯角、分支、端盖及各轴，再按实际机制补内角/混合邻接。

**UV 坐标不是 PNG 像素坐标。** 上游绘制用图片尺寸相对 UV 尺度换算位置，并加入当前动画帧偏移；Java 模型导出又把 UV 换算到模型的 16 单位范围。确认项目自己的坐标约定后再换算，例如帧内像素 `x=u×frame_width/uv_width`，`y=v×frame_height/uv_height`。这不是“所有 PNG 都是 16×16”。水平/多列帧图集按实际帧矩形加入两个方向的偏移。

反向 UV、面旋转与模型旋转分别处理。若像素边界为整数，可用 `pixelforge preview PNG --region X Y W H` 检查实际裁片；该裁片仍是图片坐标，不自动展示面向。小数边界的整数包围裁片只是取样范围的辅助图，不能凭四舍五入声称覆盖了精确四边形。共享 UV/岛意味着一次编辑可能影响多个面，预先列出这些引用，避免修复一面后损坏另一面。

**纹理检查和真实烘焙分开落实。** 首先检查 UV 裁片的颜色、alpha 和纹理节奏；随后用目标项目已有的真实模型烘焙/预览适配器验证面顶点顺序、UV 翻转/旋转、元素旋转与 rescale、blockstate rotation/uvlock、culling、tint 和光照。记录适配器支持的状态与输出，查看直线/弯角等真正组合的结果。没有适配器时仍完成裁片及资源引用检查，说明剩余范围；不通过画一个任意立方体就称为目标模型效果。

**外部编辑器导出后核对。** 如使用 Blockbench，选中匹配项目版本的模型格式，在副本中导入真实资源，关注缺失 parent、纹理变量、显示变换及项目扩展字段。逐项核对导出与原模型差异，防止编辑器规范化或新版本字段进入旧项目。当前研究的 Java codec 已包含不同年代格式分支，不能把其最新默认当作全部 Minecraft 版本的规则。动画的 `frametime`、自定义 frame/time、插值与顺序也要核对导出的侧文件，不只看编辑器时间轴。

## Material Maker：结构控制细节，颜色映射控制家族

按需要把材质组织成“结构 → 分区/蒙版 → 明暗与细节 → 颜色映射 → 原生像素导出”。这可以是节点图、草稿生成代码或 PixForge 的几段命令，不要求重建整个节点编辑器。

1. **结构母版**：先确定槽、面、棱、晶面、裂缝及透明窗口。规则结构按自身对称检查；结构层不包含为了光照而不对称的颜色。相同资源家族共享这些形状与尺度，用户认可的母版保留。
2. **蒙版和共同参数**：沿棱放高光，在凹槽放阴影，磨损限制在接触边/易磨部位。相同位置的结构场可以控制多个细节，避免几张独立随机图相互矛盾。参数名称对应实际设计选择，如条纹方向、沟槽宽度、亮部面积；不要用不可解释的大量随机值填空。
3. **颜色角色**：将结构角色映射到底色、阴影、高光和类别色，同一 `grid` 可以换角色调色板生成家族草稿。不同材料需要的面结构与反射可以变化，不能仅靠换色让所有材质相同。若指定精确颜色，将实际 RGBA 写成 JSON 调色板，使用 `--palette` 校验；RGB 通道量化不能保证进入这张调色板。
4. **像素化和量化**：在目标原生网格上采样结构；不要先生成高分辨率照片/PBR，再平滑缩成小 PNG 当成像素画。研究版本的 Pixelize 在像素中心采样，并按 RGB 通道量化，可选抖动；RGB 每通道的等级数与全图调色板颜色数不同。该节点源码的端口是 RGB，与文档中的 RGBA 描述不同，外部节点链必须独立核对 alpha，不能借节点名推断透明度保留。
5. **周期与随机性**：固定种子、参数、版本和输入，空间/时间周期有明确约束。粗糙度和磨损形成适当尺度的色簇；先确认材料需要颗粒，才启用抖动。上游 Make Tileable 通过位移与混合隐藏接缝，可能引入中间色、模糊和重复结构；小尺寸机械纹理优先构造周期形状，任何自动结果都重查原尺寸、alpha、调色板和 3×3。
6. **使用场景**：2D 预览看颜色、平铺和像素；模型预览看方向与材质。普通 Minecraft 资源未必消费 normal/roughness/metallic 贴图，按项目实际材质系统导出，不能交付一套无人引用的 PBR 文件来代替目标 PNG。

制作参数和复现信息保存在项目草稿区，与生产资源分开；已认可资源的修改范围可用保护蒙版检查。没有随机程序的手绘脚本不需要编造 seed；复杂可复现草稿再记录源图哈希、参数、工具版本和导出尺寸。

下面的可执行片段演示共享结构与颜色角色：`B` 是底色，`S` 是槽内阴影，`H` 是上沿高光，`C` 是类别色。同一组行可以替换角色的 RGBA 生成家族草稿；顶光使成品颜色不必上下对称。这是方法示例，不是生产材质模板。

```text
new 8 8
palette B=#526778 S=#263647 H=#b9d6e6 C=#237cc0
grid 0 0
BBBBBBBB
BHHHHHHB
BSSSSSSB
BSCCCCSB
BSCCCCSB
BSSSSSSB
BSSSSSSB
BBBBBBBB

render role-sample.png 1
```

## 可选编辑器接入

先检查项目已有安装与命令帮助，使用实际版本/路径和隔离草稿目录。不要为使用这些方法自动安装全局 Godot/编辑器、打开 GUI 或增加审批流程。

- **Pixelorama CLI**：研究源码有 headless 导出、spritesheet、scale、frames、JSON 和 split-layers 路径。先用一个小的 `.pxo` 样例验证导出尺寸、层合成、帧范围和时长；headless 路径可能依赖保存时含有 blended 图像。导出的 JSON 在该版本来自 project serialization，不能未经转换当作通用 atlas 帧矩形或游戏动画元数据。
- **Blockbench**：可通过已安装编辑器/插件处理模型和纹理，但技能不提供未经验证的“headless CLI”命令。遵循当前用户的 shell-only/桌面授权；离线项目适配器能够解决本次验收时直接使用它。
- **Material Maker CLI**：研究版本的 `parse_args.gd` 将 `--size` 写入 `texture_size`，最终传给 export 的却是 `image_size`。这是源码观察，未据此声称所有发行版都复现同一问题。实际版本必须做小样例导出并读取最终 PNG 尺寸/通道，不把退出码或 `--size` 参数当成功证据；导出还依赖该版本的图形渲染能力，不能凭 `--headless` 推断无 GPU 可用。

这些接入检查是必要时验证具体工具的方法，不是每次画一张 PNG 的前置要求。

## 源码依据与维护

| 项目 / 固定提交 | 主要研究文件 |
|---|---|
| Pixelorama · `e205f47699f424244a7ddc738bac2e0ca42769c1` · MIT | [Drawers.gd](https://github.com/Orama-Interactive/Pixelorama/blob/e205f47699f424244a7ddc738bac2e0ca42769c1/src/Classes/Drawers.gd)、[BaseDraw.gd](https://github.com/Orama-Interactive/Pixelorama/blob/e205f47699f424244a7ddc738bac2e0ca42769c1/src/Tools/BaseDraw.gd)、[Export.gd](https://github.com/Orama-Interactive/Pixelorama/blob/e205f47699f424244a7ddc738bac2e0ca42769c1/src/Autoload/Export.gd)、[OnionSkinning.gd](https://github.com/Orama-Interactive/Pixelorama/blob/e205f47699f424244a7ddc738bac2e0ca42769c1/src/UI/Canvas/OnionSkinning.gd) |
| Blockbench · `7c92e27d237e365110030d73e92c5d1605f0d311` · GPL-3.0 | [painter.js](https://github.com/JannisX11/blockbench/blob/7c92e27d237e365110030d73e92c5d1605f0d311/js/texturing/painter.js)、[java_block.ts](https://github.com/JannisX11/blockbench/blob/7c92e27d237e365110030d73e92c5d1605f0d311/js/formats/java/java_block.ts)、[textures.js](https://github.com/JannisX11/blockbench/blob/7c92e27d237e365110030d73e92c5d1605f0d311/js/texturing/textures.js) |
| Material Maker · `174f15edece663bf10f78588840873fa2fd17bc7` · MIT | [Pixelize](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/addons/material_maker/nodes/pixelize.mmg)、[Quantize](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/addons/material_maker/nodes/quantize.mmg)、[Colorize](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/addons/material_maker/nodes/colorize.mmg)、[Make Tileable](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/addons/material_maker/nodes/make_tileable.mmg)、[gen_graph.gd](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/addons/material_maker/engine/nodes/gen_graph.gd)、[parse_args.gd](https://github.com/RodZill4/material-maker/blob/174f15edece663bf10f78588840873fa2fd17bc7/parse_args.gd) |

本次 helper 为独立实现的方法整合，没有复制三个项目的源码、shader、节点文件或资源进入技能。更新研究版本时重新核对源码/安装版本；如以后引入实际第三方实现，另保留其许可证、版权与版本记录，不能沿用“只参考方法”的说明。
