# GUI 与独立像素画

确认原生/显示尺寸、atlas/UV、状态、透明边缘和基线。独立像素画使用实际构图尺寸。按 [操作约定](../operations.md) 打开或复用工作台并读取当前状态。

读取 gui 模板，用 `project create` 的 `settings` 的 preset=pixels、width/height 创建实际尺寸画布。已有 atlas 直接 project open，不重建；按控件代码的矩形/UV 修改。用 canvas draw 绘制，再 canvas preview、project save 和 workbench present 展示。

执行 `project create --request-file <参数.json>`：

```json
{
  "settings": {
    "preset": "pixels",
    "width": 32,
    "height": 32
  },
  "expected_document_id": "<ID>",
  "expected_revision": 0
}
```

普通、悬停、按下、禁用等通常是独立区域，只有实际逐帧播放时才用 [动画流程](texture-animation.md)。九宫格保留边角与可拉伸区域，新增状态不超出采样区；按最终控件尺寸检查轮廓、透明边缘、字体/图标基线和状态对比。

不需要 Minecraft 目标配置。按 [正式导出](../operations.md#资源检查与正式导出) 输出原生 PNG，接到真实 resource ID 和 UV，并保留可编辑工程。
