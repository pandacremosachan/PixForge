# GUI 图标与独立像素图片

适用于按钮、状态图标、槽位、HUD 与不需要 Minecraft 模型的像素画。GUI 的 atlas、UV、九宫格、文字和实际显示尺寸来自消费项目；不是所有 GUI 都是 16×16 或由方块资源接口导出。

## 输入和产出

确定源像素尺寸、实际显示尺寸/缩放、所在 atlas 与 UV、状态（正常/悬停/按下/禁用/激活）、透明边缘和基线、相邻图标风格与实际资源路径。独立像素画改为其画布/构图要求。产出包含可编辑工程、原生 PNG 和适用时的状态/UV 接线；预览放在草稿目录。

## 从模板到可编辑图

```text
python <skill-dir>/scripts/scaffold.py gui --output <D> --name status
```

按 [操作约定](../operations.md) 建立 c、s、D，先把 project.json 和 draw.px 改为实际尺寸/设计。16 像素演示图标不代表最终 UI 风格：

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "pixels", "--width", p["width"], "--height", p["height"])
s = c.write(s, "edit", D / "draw.px", "--label", "GUI图标")
c.read("preview", "--output", D / "gui-preview.png", "--scale", "8")
s = c.write(s, "save", D / "status.pixforge")
```

在原尺寸和实际 UI 显示尺寸查看：轮廓/负形、透明外缘、图标与字体基线、缩放下的像素密度、禁用状态对比和同组状态的辨识。文字不明时沿用项目字体渲染，不把小字硬画成不可读噪点。需要深浅背景用 MCP preview 的 backgrounds 或宿主图像工具显示相同原生 RGBA。

## 状态与图集分支

同一个静态 GUI atlas 的不同状态是不同区域，不自动等于播放动画。先从实际控件代码得到每个状态的矩形、UV 和绘制尺寸，再在一个 pixels 工程按该布局组织；给每个状态保留同样的基线/点击轮廓。新增状态不能超出项目实际读取的图集区域。

向已有 atlas 叠加图标时，打开真实 atlas，按既有 UV 编辑；不新建小图后用未知逻辑覆盖整 atlas。九宫格保留边角、可拉伸边和中心范围，检查拉伸后的真实控件；一个正方形原图预览不能替代长按钮验证。

仅在项目控件确实逐帧播放时执行 [材质动画](texture-animation.md) 的帧/时序操作，使用其真实时钟和元数据；普通 GUI PNG 不自动生成 .mcmeta。

## 交付和完成标准

展示原图、实际使用尺寸和必要状态对照，按 [正式导出](../operations.md#资源检查与正式导出) 记录/沿用当前用户授权，执行：

```python
s = c.write(s, "approve", "--user-request", approval_text)
s = c.write(s, "export", D / "status.png", "--scale", "1")
s = c.write(s, "save", D / "status.pixforge")
```

不需要 Minecraft 目标配置；将 PNG 接到项目实际 GUI resource ID 和 UV，不将其放进 block/item 模型目录。代码/配置修改遵循项目现有控件实现，构建能检查引用但不能证明布局看起来正确。完成时列出源尺寸、显示尺寸、图集矩形/状态、实际接线和已查看的效果。导出生产图不能使用放大预览；重绘后旧确认过期。
