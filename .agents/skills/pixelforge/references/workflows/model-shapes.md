# 单图集模型与形状

模型要求已解析 Java elements 和单一图集；父模型、多贴图及其他 loader 先由项目适配。模型单位 16=一格，UV 单位 0..16，图集尺寸为像素。

## 创建与绘制

按 [操作约定](../operations.md) 打开或复用工作台。读取 custom-model 模板，将底座 element 0 和转子 1 替换成实际几何、UV 和图案。把 model.json 解析成对象，传给 `project create` 的 `settings.model`，并设置 preset=model 和实际 width/height；随后 model uv、canvas draw、workbench wait。

仅替换模型使用 model import，保留像素和形状，不重排图集。核对共享 UV、旋转和受影响面，以 model preview 返回的图像或 HTML 检查。

## 形状

新建模型时，`settings.model.elements` 决定外观，`settings.base_boxes` 决定交互形状。手持或展示模型默认是空列表。可放置物按玩家能碰到的主体分箱：机壳、支座或伸出的主要部件各用一个盒，保留部件之间的通道或空隙。按钮、散热片、线缆等细节留在可见模型里。箱数取决于轮廓。

`base_boxes` 使用模型坐标，例如 `[{"id":"housing","from":[1,0,2],"to":[15,8,14]}]`。碰撞和选中默认都继承它。修改既有工程时，从 `project state` 取出完整 `shapes`，只替换要改的 `base` 或覆盖层，再用 `model shapes` 写回；模型、UV 和图层均可保留。

希望碰撞贴合可见零件时，再用 `model build-shapes` 从几何重建；已有形状的无损整理用 `model optimize-shapes --max-error 0`。

执行 `model edit-shapes --request-file <参数.json>`：

```json
{
  "operations": [
    {
      "op": "update",
      "target": "base",
      "id": "slab",
      "box": {
        "to": [
          16,
          6,
          16
        ]
      }
    }
  ],
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

collision/selection 的 null 继承 base，[] 为空覆盖。展示外观时用 `overlays: []`；讨论碰撞时用 `overlays: ["collision"]`，线框能直接看出保留的开口。见 [形状协议](../shapes.md)。

## 交付

静态资源配置 target 后走 [公共导出](../operations.md#资源检查与正式导出)，动态内容先走 [场景动画](scene-animation.md)。asset export-shapes 输出 JSON 或 format=forge-1.20.1 的 Java helper，文件名与 class_name 一致；接到真实 Block 的 getShape/getCollisionShape，朝向/状态由项目实现。资源包不改变碰撞。
