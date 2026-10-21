# 修改已有材质并保留资源机制

适用于已有方块、物品、连接纹理或复杂机器的局部修改。起点是真实项目或当前工作台工程，不能用新方块模板覆盖既有状态体系。

## 准备

确定当前作品的 runtime、目标纹理完整 ID、真实资源来源/生效覆盖、PNG/原生工程、帧尺寸和时序、实际模型与 UV、blockstate/item 入口、tint、渲染层及本轮允许修改的范围。先查看目标与相邻材质；用户已认可的形状和颜色作为本轮基线。不要把项目事实缺失理解成需要研究软件源码。

如果工作台已打开对应工程，直接使用 [操作约定](../operations.md) 的 status；如果只有实际 PNG，先保存当前工作，再通过专用 open 导入。open PNG 会清除旧模型关联；PNG 本身不能推断面域。此时模型/状态检查由配置的实际资源来源完成，或显式导入已解析的模型，不能猜六面布局。

```python
# 仅在确实需要打开外部源文件时执行：
s = c.write(s, "open", actual_png_or_project)
```

## 保留状态的 target

示例绑定一张既有机器纹理，所有值改为真实项目值：

```json
{
  "schema":"pixforge.minecraft-project/v1",
  "profile":"forge-1.20.1",
  "namespace":"examplemod",
  "sources":[
    {"name":"vanilla","path":"<实际客户端JAR>","role":"dependency"},
    {"name":"mod","path":"<实际依赖模组JAR>","role":"dependency"},
    {"name":"project","path":"<实际资源目录>","role":"project"}
  ],
  "entries":[{"kind":"blockstate","id":"examplemod:machine"}],
  "binding":{"kind":"texture","path":"machine","texture":"block/machine"}
}
```

不需要的来源删除，保留的来源必须真实存在。sources 按低到高排序，当前画布绑定最高。物品入口改为 kind=model、id=examplemod:item/name。只制作局部覆盖资源包、不重发原模组状态时，将原模组来源标为 dependency；需随交付包含的自身资源才标 project。当前 PNG 的画布应与目标精灵匹配，不能把一整张外部多精灵 atlas 当作单精灵替换。

## 原子修改与预览

```python
s = c.write(s, "minecraft-configure", "--config", D / "target.json")
before = c.read("minecraft-check", "--sources-only")
# 检查 before["validation"] 的来源和引用，确认编辑的是实际生效纹理。
# 若嵌入了模型，读取其实际 UV。未嵌入时查询会明确没有模型，不能猜面域。
uv = c.read("model-uv")
trial = c.write(s, "validate", D / "change.px", "--preview", D / "trial.png")
# 查看预演。validate 不推进内容，继续使用其返回 state。
s = trial
s = c.write(s, "edit", D / "change.px", "--label", "本轮局部材质修改")
check = c.read("minecraft-check")
s = check["state"]
digest = check["validation"]["validation_digest"]
c.read("preview", "--output", D / "after.png")
s = c.write(s, "save", D / "updated.pixforge")
```

change.px 只放本轮绘图，沿用图层、帧与真实坐标。小元素叠画不用透明字符占位整片旧图；透明覆盖会打孔。改错时用返回的 s 调用 undo，确认恢复；不通过打开原 PNG 来丢弃其他人的修改。

在 view.json 声明实际检查主体：

```json
{"subject":{"kind":"blockstate","id":"examplemod:machine"}}
```

```python
c.read("minecraft-preview", "--output", D / "states.png", "--options", "@" + str(D / "view.json"), "--batch")
```

读取返回报告的 next_case_offset，存在下一页时按其值设置 --case-offset，直到覆盖任务所需状态。连接件按孤立/直线/弯角/分支/端盖和朝向检查，不能以整 PNG 平铺替代。动画继续用实际元数据播放；tint 等由项目代码决定的效果保留其真实机制。

## 交付

展示前后对照和当前检查，再按 [正式导出](../operations.md#资源检查与正式导出) 导出 resource-pack 或 mod-assets。批准绑定当前像素与依赖；此后改像素或来源须重查。检查 ZIP 只包含本轮需要的资源，dependency 不重新分发。原对象注册、复杂状态、机器实例逻辑和生产代码都以实际项目为准，纹理替换不承担修改它们的授权。

完成标准是目标引用真实生效、本轮范围清晰、原生尺寸/alpha/帧时序保持、所需模型状态已预览、源工程可继续编辑。离线不支持的 loader 或连接渲染机制明确列出，保留源资源，不扁平化为简单方块消除问题。
