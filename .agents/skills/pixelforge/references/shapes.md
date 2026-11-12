# 模型、碰撞与选中形状

制作流程见 [模型和形状](workflows/model-shapes.md)。坐标为模型单位，16=一格。每份形状最多 256 个轴对齐盒，id 唯一，from<to，有限坐标范围 -1024..1024。

## 基础与覆盖

`project create` 的 `settings.base_boxes` 直接写入 base。省略时，新建 model/pixels 工程不带方块形状，cube_faces/cube_shared 保留一个完整方块。已有工程继续使用自己保存的形状。

```json
{
  "schema": "pixelforge.shapes/v1",
  "base": [
    {
      "id": "slab",
      "from": [
        0,
        0,
        0
      ],
      "to": [
        16,
        8,
        16
      ]
    }
  ],
  "collision": null,
  "selection": null,
  "model": null
}
```

collision/selection 的 null 实时继承 base，列表为独立覆盖，[] 明确为空。mode 的 copy/inherit/empty 分别复制当前有效形状/恢复继承/空覆盖。旧无形状工程默认为完整方块。

## 操作

通过以下命令操作，写入使用已观察到的 expected_document_id/expected_revision。

| 动作 | 用途 |
|---|---|
| `model shapes --settings` | 替换定义；省略 base 用完整方块，省略覆盖则继承 |
| `model edit-shapes --operations` | 原子操作数组 |
| `model shapes --settings,validate-only true` | 只验证，带版本令牌 |
| `model import --model` | 嵌入已解析模型，保留已有像素和形状 |
| `model preview --overlays ["collision"],include-html true` | 当前纹理帧与指定线框，视图角度可用 yaw/pitch |

```json
[
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
  },
  {
    "op": "mode",
    "target": "collision",
    "mode": "copy"
  },
  {
    "op": "add",
    "target": "collision",
    "box": {
      "id": "post",
      "from": [
        6,
        6,
        6
      ],
      "to": [
        10,
        12,
        10
      ]
    }
  },
  {
    "op": "remove",
    "target": "collision",
    "id": "post"
  }
]
```

继承中的覆盖不可直接编辑。对应命令 model shapes、model edit-shapes、model import、model preview；model shapes --validate-only true 预检。

## 模型与预览

支持单图集 Java elements、六向面、默认/显式 UV、90°倍数面旋转，以及轴向 0、±22.5、±45°元素旋转和 rescale。父模型须先解析。替换模型替换几何与 UV，不重排像素。

HTML 保留真实纹理帧、播放时序和形状开关；PNG 可指定视角和线框。基础预览为方向光近似，目标状态/tint 等走 [Minecraft 预览](minecraft-preview.md)。

## 构建和减少分箱

- `model build-shapes` 从嵌入原模型保守重建；默认误差 1 模型单位、目标 16 箱，可按用途调整。
- `model optimize-shapes` 针对现有并集，默认误差 0；正误差连续处理会累积偏差。
- 误差是硬约束，target_boxes 是搜索目标。未达目标返回 target_met=false，不放宽误差。
- 旋转实体不能用有限轴对齐盒精确表示，需要正误差；零体积面不生成碰撞。
- symmetry="auto" 保留检测到的镜像/轴交换/旋转，none 关闭。预算不足时返回已验证结果或无损回退并警告。

执行 `model build-shapes --request-file <参数.json>`：

```json
{
  "max_error": 0.5,
  "target_boxes": 12,
  "dry_run": true,
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

设置 dry_run=false 才写入，命令为 model build-shapes/model optimize-shapes。预检报告含 proposed_shapes、箱数、误差、体积和目标状态；工程变化后旧预检失效。检查实际孔洞、轮廓和外扩，不仅看箱数。

## 导出与游戏接入

当前内容确认后执行 asset export-shapes：

执行 `asset export-shapes --request-file <参数.json>`：

```json
{
  "path": "<形状JSON>",
  "format": "json",
  "expected_document_id": "<ID>",
  "expected_revision": 12
}
```

JSON 保留原盒/id、继承、空覆盖和模型。Java helper 无损整理并平衡合并，最后一次 optimize；接到真实 Block 的 getShape/getCollisionShape。文件名与类名一致，朝向、动态/情境形状由项目实现。盒统计不等于游戏最终分区数，资源包不能改变碰撞。
