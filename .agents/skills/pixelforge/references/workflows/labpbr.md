# LabPBR 数据材质

适用于法线、AO、高度、平滑度、F0/金属、孔隙/散射和发光数据。依赖 minecraft-material/v1；工作台以独立原始字节平面保存，不通过颜色图层透明合成。

## 输入和模板

确定现有 albedo 工程与真实帧/UV、LabPBR 版本、需要的通道、消费端着色器名称/精确版本、加载器/版本、选项及已知支持能力。未知能力保持 null；未绑定着色器仍可制作/交付数据，但必须说明实际着色器效果未验证。

```text
python <skill-dir>/scripts/scaffold.py labpbr --output <D> --namespace examplemod --name panel
```

模板包含普通 albedo、material.json 与原始字节 smoothness.json。已有工程跳过新建/绘图，沿用 s；动画工程使用完整图集尺寸，各通道随帧布局一起处理。

## 配置与字节编辑

按 [操作约定](../operations.md) 建立 c、s、D：

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "cube-shared", "--face-size", p["face_size"])
s = c.write(s, "edit", D / "draw.px", "--label", "Albedo")
s = c.write(s, "minecraft-material-configure", "--settings", "@" + str(D / "material.json"))
s = c.write(s, "minecraft-material-edit", "--role", "specular", "--channel", "r",
            "--operations", "@" + str(D / "smoothness.json"))
for role in ("normal", "specular"):
    for channel in ("r", "g", "b", "a"):
        c.read("minecraft-material", "--role", role, "--channel", channel,
               "--output", D / (role + "-" + channel + ".png"))
decoded = c.read("minecraft-material", "--role", "specular", "--view", "decoded", "--pixel", "3", "3")
s = c.write(s, "save", D / "panel-data.pixforge")
```

每个 operations 矩形为 [x,y,width,height]，与 .px rect 的含端点坐标不同。value 是原始 0..255，不是颜色字符串。示例只修改 specular R，其他通道保持初始化或原来的字节。导入已有 _n/_s 使用 minecraft-material-import --role normal|specular --path FILE；必须与完整 albedo 图集等尺寸，不自动缩放。

| 图 | R | G | B | A |
|---|---|---|---|---|
| normal | 法线 X | DirectX 法线 Y | 材质 AO | 高度 |
| specular | 感知平滑度 | F0 或金属分类 | 孔隙或 SSS | 发光，255 为忽略/零 |

数据 alpha 不是透明度。specular A 254 与 255 的意义不同，不能用“255 最亮”直觉。检查解码含义、法线有效范围和全部八通道，不只看合成外观。具体编码见 [数据材质](../material-data.md)。

## 着色器目标

在 material.json 添加 target 后重新配置：

```json
{
  "profile":"labpbr-1.3",
  "maps":["normal","specular"],
  "target":{
    "name":"<实际着色器名称>",
    "version":"<实际精确版本>",
    "loader":"<实际加载器>",
    "loader_version":"<实际加载器版本>",
    "features":{"normals":null,"smoothness":null,"f0":null,"hardcoded_metals":null,"ao":null,"height":null,"porosity":null,"sss":null,"emission":null},
    "options":{}
  }
}
```

根据真实项目证据把适用特性改为 true/false；支持证据未知时保持 null，不照抄全 true。可加 path 指向授权已有着色器包和实际 sha256，软件据此绑定来源指纹。Probe 示例的能力不代表任意着色器。声明、源码检查和离线解码都不能替代游戏加载证据。

## 资源和交付

```python
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
check = c.read("minecraft-check")
s = check["state"]
digest = check["validation"]["validation_digest"]
s = c.write(s, "save", D / "panel-data.pixforge")
```

查看 albedo、八平面和关键原始值，确认动画帧/分类边界及着色器能力问题，再按 [正式导出](../operations.md#资源检查与正式导出) 取得/沿用当前真实批准。软件将同一绑定的 albedo、_n、_s 与动画元数据一起打包，不用普通 export 或颜色合成自行生成数据 PNG。检查 ZIP 侧文件名、尺寸、原始字节和时序配对。

完成时列出使用特性、目标/未知支持项、实际数据和引用检查范围；离线检查失败时按具体通道/feature 修正，不修改 alpha 或关闭通道检查绕过。数据工程使用软件 v4 格式，需要 PixForge 2.7+，本流程基线为 2.9.0。未运行游戏时明确保留未验证状态，不自动安装 shader loader 或启动游戏。
