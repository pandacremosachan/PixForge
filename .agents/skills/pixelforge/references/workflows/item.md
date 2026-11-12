# 物品与工具

先确定平面精灵或三维模型、真实 item 模型、tint/overrides、原生尺寸和注册入口。工具行为使用项目已有体系。

## 平面物品

按 [操作约定](../operations.md) 打开或复用工作台。读取 item 模板，使用实际客户端 JAR 作为 dependency；把真实 sources 和资源 ID 填入 target.json。以 `project create` 的 `settings` 的 preset=pixels 和实际 width/height 新建，用 canvas draw 绘制。

配置目标后 minecraft check，canvas preview 检查原尺寸轮廓、负形、材料和透明边缘，保存并用 workbench present 展示。已有自动材料图标系统时优先接其入口。

## 三维物品

手持、背包或纯展示物品用 `item/project-3d.json`：将实际单图集模型放入 `settings.model`，图集尺寸与该模型一致。`base_boxes: []` 表示没有方块碰撞或选中箱；键帽、按钮、线缆等仍是完整的可见部件。可放置物另按[主要体块定义接触面](model-shapes.md#形状)。

用 `item/target.json` 绑定实际物品 ID。运行 `model preview`，传入选定的 `yaw/pitch`、`overlays: []` 和 `include_html: true`：PNG 和网页使用同一视角和模型开关，网页旁边同时显示该物品按 `display.gui` 渲染的物品栏图。若物品超出边界，调整模型的 `display.gui.scale/translation`，用 `model import` 更新同一工程。

## 物品栏和手持视图

通过 `minecraft preview` 的 `options` 指定真实物品模型：

执行 `minecraft preview --request-file <参数.json>`：

```json
{
  "options": {
    "subject": {
      "kind": "model",
      "id": "examplemod:item/name"
    },
    "context": "gui"
  }
}
```

按用途检查 ground/fixed/firstperson_righthand/thirdperson_righthand。需要 handheld、display、overrides 或 tint 时，在 project 来源保留真实 item 模型，entries 引用它，binding 使用 texture；纯像素 item 绑定默认 generated。

已有资源用 texture 绑定时，通过上面的真实物品模型 ID 显式预览 GUI。未解析父模型、多贴图或自定义 loader 保留原机制，使用项目适配器。

按 [正式导出](../operations.md#资源检查与正式导出) 输出当前确认的 mod-assets，通常为 textures/item/name.png 与 models/item/name.json。新对象另完成 [注册与数据](../forge-static.md)。
