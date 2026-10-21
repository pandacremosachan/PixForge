# 单图集模型、碰撞与选中形状

适用于新几何、UV 和物理/选择形状。模型决定外观，形状决定实体碰撞/选中；两者可不同。当前编辑模型要求已解析 Java elements 和单一纹理图集，不能直接导入未解析父模型、Blockbench 工程文件或多纹理模型。

## 输入和模板

确定几何各部件的功能、模型单位（16=一格）、原生图集尺寸、面与 UV、旋转、共享区域、碰撞/选中用途及误差范围。已有模型先保留真实结构；多贴图应按项目授权准备单图集适配版本，或保留原模型并走 [纹理替换](replace-texture.md)。

```text
python <skill-dir>/scripts/scaffold.py custom-model --output <D> --namespace examplemod --name mechanism
```

模板是两个元素：0 为底座、1 为转子；上半图集供底座，下半供转子。它只示范结构，不代表目标机器的设计。project.json 的 width/height 是纹理像素；model.json 的 from/to 是模型单位、uv 是 0..16 纹理单位。按需替换模型再执行，不把演示元素索引套到未知模型。

## 创建与绘图

建立 [公共调用前缀](../operations.md#可复制的-python-调用前缀)：

```python
p = load("project.json")
s = c.write(s, "create-project", "--preset", "model", "--model", D / "model.json",
            "--width", p["width"], "--height", p["height"])
uv = c.read("model-uv")
# 根据 uv_map 的面和 shared_regions 核对哪些区域共用，保留旋转/镜像。
s = c.write(s, "edit", D / "draw.px", "--label", "模型图集")
c.read("shape-preview", "--output", D / "model.html", "--overlays")
```

只替换当前模型时改用 `c.write(s,"model-import",D/"model.json")`；它保留现有像素和形状，不重排旧图集。布局不配套时须明确重新映射或配套纹理，不把成功导入当作贴图正确。按真实部件与全部受影响面检查纹理方向。

## 形状构建和覆盖

新建工程会从模型准备基础形状；需要调精度时再次从**原模型**预检。已有形状需要保留原并集时选择 shape-optimize 的误差 0，而不是反复近似已有结果。

```python
trial = c.write(s, "shape-build", "--max-error", "0.5", "--target-boxes", "12", "--dry-run")
# 查看实际误差、箱数和 target_met。0.5 模型单位是本示例参数，可按用途调整。
s = c.write(s, "shape-build", "--max-error", "0.5", "--target-boxes", "12")
s = c.write(s, "shape-edit", D / "shape-edit.json")
c.read("shape-preview", "--output", D / "collision.png", "--overlays", "collision")
c.read("shape-preview", "--output", D / "selection.png", "--overlays", "selection")
s = c.write(s, "save", D / "mechanism.pixforge")
```

模板 shape-edit.json 将 selection 切换为基础形状的独立副本；后续可通过 edit_shapes 操作盒。默认 collision/selection=null 继承 base，独立 [] 表示空形状，不能混用。旋转几何的轴对齐盒近似需正误差；target_boxes 是搜索目标，达不到时不自行放宽误差。按开口、可通过区域、可点选部件和外扩范围检查，不能只数盒子。

## 资源与物理接入

静态新方块可配置模板 target.json、检查引用并用 [正式导出](../operations.md#资源检查与正式导出) 导出 mod-assets；动态场景先走 [场景动画](scene-animation.md)，不能用静态方块包静默丢掉运动。

取得当前版本真实批准后，可分别导出通用定义和 Forge Java helper：

```python
s = c.write(s, "shape-export", D / "shapes.json")
s = c.write(s, "shape-export", D / "MechanismShapes.java",
            "--format", "forge-1.20.1", "--class-name", "MechanismShapes",
            "--package", "examplemod.generated")
```

Java 文件接入已注册 Block 的 getShape/getCollisionShape；类名与文件名一致。朝向变换、状态组合、动态形状和其他加载器由消费项目实际实现。资源包只有模型外观，不能改变碰撞；Java helper 未接线/未编译时不能称为物理功能完成。新增对象接线见 [静态对象接入](../forge-static.md)。

完成时保存原模型、原生 UV/像素和可编辑形状，记录实际箱数、误差、继承/覆盖关系、目标状态。查看模型、碰撞和选中分别显示的预览；导出 JSON 保留定义，Java 的无损整理不改工程。完整数据和操作见 [形状协议](../shapes.md)。
