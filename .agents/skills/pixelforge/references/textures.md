# 方块与可平铺材质

按真实面尺寸、UV、重复方向和相邻素材设计。一般规则见 [设计验收](design-review.md)，局部对称见 [对称](symmetry.md)。晶体先画晶面与棱，金属先画面、接缝和连续反射，砂石控制颗粒尺度与反差；沿用项目类别色。

## 平铺检查

查看原尺寸、最近邻放大、实际使用面裁片的 3×3；检查模型旋转对应方向、边角、接缝、重复大斑、条带和双宽边框。相对边逐像素相同不是自然纹理无缝的必要条件，端面与侧面只在设计需要处连续。

## PNG 检查参数

调用 asset inspect，path 为真实 PNG，options 为下表对象：

执行 `asset inspect --request-file <参数.json>`：

```json
{
  "path": "<材质PNG>",
  "options": {
    "expect_size": [
      16,
      16
    ],
    "tile": true
  },
  "preview_path": "<预览PNG>",
  "report_path": "<报告JSON>"
}
```

| options 字段 | 语义 |
|---|---|
| expect_size=[W,H] | 检查源图、每帧或所选区域的真实尺寸 |
| opaque / binary_alpha | 要求全不透明 / alpha 仅 0 或 255；按实际目标启用 |
| region=[X,Y,W,H] | 裁片检查；动画先分帧，再取同一区域 |
| symmetry | none/lr/ud/both/diagonal/antidiagonal/rotate90/rotate180/d4，默认 none |
| symmetry_space | rgba/alpha/silhouette，默认 rgba |
| alpha_cutoff | 可见范围采用 alpha>N；默认 0，范围 0..254，不改 PNG |
| clusters | 四邻接同色可见 RGBA 色簇及孤立点，斜线也可能出现孤立点 |
| max_isolated_pixels | 显式孤立点上限，默认无上限 |
| tile | 两向接缝统计和 3×3 预览 |
| match_edges | 显式要求相对边完全相同；tile 不自动启用此约束 |
| compare | 同尺寸静态 PNG 对照；不与动画分帧组合 |
| palette | 非空 RGBA 数组或其 JSON 文件路径，精确检查可见颜色，不量化 |
| preserve_mask + compare | 同原生尺寸二值 alpha 蒙版；255 区域保持 RGBA，0 可改，至少保护一像素，检查完整源图 |
| scale | 1..16 的展示倍率，生产图不变 |
| backgrounds | checker/light/dark 数组，默认 checker |
| display_size=[W,H] | 增加实际绘制尺寸的最近邻预览 |
| frame_height | 已确认垂直帧条的源帧高度 |
| animation_plan | 真实播放定义对象或文件，与 frame_height 互斥，见 [播放器](animation-review.md) |

preview_path/html_path/report_path 为工具顶层输出参数，分别保存讨论 PNG、播放器和完整 JSON；路径彼此不同，不能覆盖输入、对照、蒙版、定义或当前工程。已有文件通过有效替换授权设置 overwrite。

包围盒为区域局部坐标，右/下边界不含；透明隐藏 RGB 不参与视觉比较。拒绝 APNG。约束失败通过非零退出码、ok=false 与 report.constraints_passed 返回；没有声明约束时，成功仅表示分析完成。保护蒙版不是 alpha lock，统计也不是美观评分。
