# 小尺寸图标

先确认原生尺寸、实际显示尺寸和相邻素材。按 [设计验收](design-review.md) 画轮廓、主部件与负形，再补触点、接缝和高光。

- 原尺寸下保持主次与材料可读；装饰碎点过多时合并色簇或删减。
- 成套保持结构尺度、光源、基线和已有类别色，必要时用部件变化区分等级。
- 对称按部件分别确定轴线、中心与变换；定向高光不必与结构同样对称，见 [对称](symmetry.md)。
- 单像素可用于眼睛、灯、尖角或颗粒；四邻接孤立点统计不是噪点判决。
- 透明图在深浅背景和真实控件尺寸下查看；保持约定基线，不按每张包围盒自动居中。

执行 `asset inspect --request-file <参数.json>`：

```json
{
  "path": "<素材PNG>",
  "options": {
    "symmetry": "antidiagonal",
    "symmetry_space": "silhouette",
    "backgrounds": [
      "checker",
      "light",
      "dark"
    ],
    "clusters": true
  },
  "preview_path": "<讨论预览PNG>"
}
```

仅声明实际需要的对称或孤立点约束。`silhouette` 查可见轮廓，`alpha` 查透明度，默认 `rgba` 查成品颜色；内部结构仍须看图。
