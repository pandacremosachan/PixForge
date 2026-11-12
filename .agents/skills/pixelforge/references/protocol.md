# PixForge 像素协议 v1

共享工程用 `canvas draw`，批次仅含绘图命令；新建、打开、保存、导出和撤销使用对应命令。完整流程见 [操作约定](operations.md)。

## 命令一览


| 命令 | 说明 |
|---|---|
| `new W H` | 仅离线批次：新建画布（≤4096²），重置为单层 `main`，清空调色板/撤销 |
| `layer add\|use\|show\|hide\|remove NAME` / `layer list` | 图层（≤16），`add` 后自动激活；`list` 标 `*` 为当前层 |
| `mirror on\|off` | 对称模式：每次绘制额外贴一份水平镜像副本（轴=画布垂直中线） |
| `palette A=#rrggbbaa B=#rrggbb` | 字符→颜色。支持 `#rgb/#rgba/#rrggbb/#rrggbbaa`；alpha `ff`=不透明 `00`=全透明。`.` 恒为全透明，不可定义；**数字不能作调色板字符**（RLE 冲突） |
| `grid X Y` + 行负载 | 每字符=1 像素。负载行宽必须一致 |
| `rle X Y` + 行负载 | 游程编码：`4H2.6H` = `HHHH..HHHHHH`。计数可省略（默认 1）。行解码长度必须一致 |
| `patch X Y W H` + 行负载 | 原生 RGBA 网格：每行 W 个空格分隔的 `rrggbbaa` 单元，`.`=全透明。不经调色板，直接决定每点 RGB+α |
| `set X Y #rrggbbaa` | 单像素 |
| `rect X0 Y0 X1 Y1 #rrggbbaa` | 实心矩形（含端点，自动裁剪） |
| `clear X0 Y0 X1 Y1` | 擦除为全透明 |
| `read X Y W H [raw]` | **读回**（见下） |
| `render PATH [SCALE]` | 仅离线批次：请求合成输出；由工具延后发布 |
| `save PATH` / `load PATH` | 仅离线批次：读取或请求保存画布 JSON；保存输出延后 |
| `undo` / `redo` | 快照式撤销（≤50 步），覆盖所有绘制与图层操作 |
| `info` | 画布尺寸/镜像/图层/调色板 |
| `stats [X Y W H]` | 区域颜色直方图 top16 |

## 负载与替换

grid/rle/patch 从下一行读取负载，直到空行、# 注释或下一条命令。各行宽度须一致，RLE 按解码宽度比较。

```text
palette G=#2ecc71ff D=#27ae60ff
grid 4 4
GGGG
GDDG
GGGG

rle 4 8
8G
2G4D2G
```

所有负载像素都替换目标，`.` 会打透明孔；局部叠画裁剪负载或使用独立层。行首 # 或恰好等于命令名会被解析为注释/命令，换字符或 patch。

## 镜像语义

mirror on 围绕整张画布竖直中线。grid/rle/patch 先贴原块，再水平翻转贴到 `(W-X-w,Y)`；set/rect 使用 `x'=W-1-x`。越界裁切，重叠处后写覆盖，不保证结果对称。

偶数宽轴线在像素间，如宽 16 为 x=7.5；局部/旋转变换见 [对称](symmetry.md)。

## 读回

`read X Y W H` 返回可执行 palette+grid；`read ... raw` 返回精确 RGBA patch。读的是可见层合成结果，透明像素为 00000000，不能直接回贴到原半透明层冒充无损。

普通 read 会为新颜色增加稳定调色板字符；字符不足或负载有语法歧义时自动回退 patch。

## 错误与离线兼容

错误带行号/坐标。共享批次为原子操作，validate 仅预演；检查退出码及 ok/error/code。

用户明确选择离线批处理时调用 `asset batch`，详见 [事务](transactions-review.md)。它使用独立画布，整批成功后才返回候选草稿；不更新共享工程。

离线绘图文本中的 render/save 请求保持延后，不发布生产文件；使用命令参数 project_path 保存可编辑草稿，再通过正常工程确认与导出。绘图文本中的输入路径按协议空白分词；含空格的工程路径通过命令参数传入。
