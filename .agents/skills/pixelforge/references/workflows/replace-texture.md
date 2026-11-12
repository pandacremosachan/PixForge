# 修改已有材质

保留现有模型、朝向、multipart、连接、tint 与渲染机制。确认实际生效的纹理 ID、来源、尺寸/帧时序和授权修改范围。

## 起点与目标

按 [操作约定](../operations.md) 打开或复用工作台。当前工作台已有对应工程时继续；只有 PNG 时先保存原工作，再 project open。打开 PNG 会清除模型关联，后续使用真实目标模型或 model import 导入已解析模型。

目标使用 texture 绑定，按实际来源构造 `minecraft configure` 的 `settings`：

```json
{
  "schema": "pixforge.minecraft-project/v1",
  "profile": "forge-1.20.1",
  "namespace": "examplemod",
  "sources": [
    {
      "name": "mod",
      "path": "<依赖JAR>",
      "role": "dependency"
    },
    {
      "name": "project",
      "path": "<资源目录>",
      "role": "project"
    }
  ],
  "entries": [
    {
      "kind": "blockstate",
      "id": "examplemod:machine"
    }
  ],
  "binding": {
    "kind": "texture",
    "path": "machine",
    "texture": "block/machine"
  }
}
```

来源按低到高排序，当前画布最高；dependency 只解析、不再分发。物品入口用 kind=model，当前 PNG 必须对应目标精灵。

## 修改与检查

minecraft check --use-document false 核对原始来源，model uv 核对采样范围；先 canvas validate --commands 查看预演，再 canvas draw 提交同一修改，透明像素为替换语义。修改限于授权区域，撤销用 project undo 和返回状态。

有工程模型时展示 shapes；否则 `minecraft preview` 的 `options` 指定真实 blockstate/model。批量预览按 next_case_offset 分页，覆盖受影响状态与连接件的孤立/直线/弯角/分支/端盖。原生窗口使用 workbench editor --editor-kind preview。

展示前后、实际模型和资源检查结果后，按 [正式导出](../operations.md#资源检查与正式导出) 交付 resource-pack/mod-assets。保留 alpha、真实时序和源工程，归档只包含需要交付的自身资源。
