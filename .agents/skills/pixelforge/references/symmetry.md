# 对称范围与变换

先指定完整部件/区域、轴线或中心，以及要比较的轮廓、结构或 RGBA。局部部件可以使用不同规则；定向光照不必随结构对称。

## 变换

| 选项 | 关系 |
|---|---|
| `lr` / `ud` / `both` | `x'=W-1-x` / `y'=H-1-y` / 两者 |
| `diagonal` | 正方形局部坐标 `x=y` 的镜像 |
| `antidiagonal` | `x+y=W-1` 的镜像 |
| `rotate180` | 绕局部中心转 180°，允许长方形 |
| `rotate90` | 绕中心转 90°，要求正方形 |
| `d4` | 90°旋转和正交镜像，要求正方形 |

平移重复和平铺另查接缝。任意角度通常不保像素网格，需按设计核对栅格近似，检查器不支持任意角变换。

## 局部坐标

``asset inspect` 的 `options.region`=[X,Y,W,H]` 先裁片再比较。镜像轴为源图 `x=X+(W-1)/2`、`y=Y+(H-1)/2`；两轴交点是旋转中心。主/反对角线为 `y-x=Y-X`、`x+y=X+Y+W-1`。

执行 `asset inspect --request-file <参数.json>`：

```json
{
  "path": "<素材PNG>",
  "options": {
    "region": [
      5,
      3,
      6,
      6
    ],
    "symmetry": "diagonal"
  }
}
```

symmetry_space 的 rgba/alpha/silhouette 分别比较颜色/透明度/可见轮廓。silhouette 使用 `alpha > alpha_cutoff`，默认 0；该阈值仅用于检查。遮挡或非矩形结构需独立结构层/蒙版。

绘图 `mirror on` 固定围绕整张画布的竖直中线；局部镜像须自行构造坐标或独立母版。完成组合后核对最终结果。
