# 普通方块

适用于普通静态方块；复杂状态走 [替换材质](replace-texture.md)，非立方几何走 [模型与形状](model-shapes.md)。按 [操作约定](../operations.md) 打开或复用工作台并读取当前状态。

## 创建与绘制

读取 block-shared 或 block-faces 模板，按真实面尺寸调用 project create。六面相同使用 cube_shared，有区别使用 cube_faces：

执行 `project create --request-file <参数.json>`：

```json
{
  "settings": {
    "preset": "cube_faces",
    "face_size": 16
  },
  "expected_document_id": "<ID>",
  "expected_revision": 0
}
```

调用 model uv 核对实际布局，以 `canvas draw` 的 `commands` 提交修改后的 draw.px 文本。六面独立在面尺寸 F 时为 3F×2F 图集：up/north/east 原点为 (0,0)/(F,0)/(2F,0)，south/west/down 为 (0,F)/(F,F)/(2F,F)。共用面为 F×F；以返回 uv_map 为准。模型 UV 单位 0..16，绘图为像素，共享区域影响所有引用面。

## 检查与交付

把 target.json 解析成对象传给 minecraft configure，再 minecraft check。用 canvas preview 检查图集，用 minecraft preview 检查目标，保存 .pixforge，并通过 workbench present 展示像素及真实模型。

按实际 UV 裁面检查平铺、方向、接缝和六面明暗；整张图集的平铺不能代替模型接缝检查。透明块另查渲染层与遮挡。

按 [正式导出](../operations.md#资源检查与正式导出) 输出 mod-assets/resource-pack。通常含 textures/block/name.png、models/block/name.json、blockstates/name.json、models/item/name.json；图集保持一张原生 PNG。新对象完成 [静态接入](../forge-static.md)，已有朝向、multipart、连接和 datagen 规则按项目保留。
