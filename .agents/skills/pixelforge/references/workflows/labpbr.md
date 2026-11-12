# LabPBR 数据材质

需要 minecraft-material/v1。确认 albedo、帧布局/UV、LabPBR 版本与真实 shader/loader。数据使用独立字节平面，alpha 也是数据。

## 编辑

按 [操作约定](../operations.md) 打开或复用工作台。新作品读取 labpbr 模板，先完成真实 albedo；已有工程跳过新建。`minecraft material-configure` 的 `settings` 使用实际配置：

执行 `minecraft material-configure --request-file <参数.json>`：

```json
{
  "settings": {
    "profile": "labpbr-1.3"
  },
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

minecraft material-edit 的 operations 使用 rect=[x,y,width,height]、value=0..255。已有 _n/_s 通过 minecraft material-import 导入，须与完整 albedo 图集等尺寸。以 minecraft material-inspect 分别查看 normal/specular 的 RGBA 八通道和 decoded 值。

| 图 | R | G | B | A |
|---|---|---|---|---|
| normal | DirectX 法线 X | 法线 Y | AO | 高度 |
| specular | 感知平滑度 | F0/金属分类 | 孔隙/SSS | 发光，255 为忽略/零 |

避免颜色合成、sRGB 校正或缩放。模型页只证明 albedo 上模；精确语义见 [数据材质](../material-data.md)。需要原生字节编辑器时使用 workbench editor --editor-kind material。

## 目标与交付

target 记录 shader 名称/版本、loader/version、options 和真实 features；未知为 null，可绑定已有 shader 包及 sha256。通过 [资源检查与导出](../operations.md#资源检查与正式导出) 配对 _n/_s、帧布局与元数据。核对归档侧文件、尺寸和字节；声明或离线解码不能证明 shader 已生效。
