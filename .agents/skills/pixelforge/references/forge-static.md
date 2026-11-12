# Forge 1.20.1：把外观接成真实方块或物品

仅用于 Java 1.20.1 / Forge / Mojang mappings。沿用项目已有注册框架；仅替换资源时不新增注册。

## 接入顺序

确认实际 mod id、注册类、mod event bus、资源源集和 datagen。下例替换包名/ID 后合入已有主入口；DeferredRegister 挂 mod event bus，不另建 @Mod。[Forge 注册文档](https://docs.minecraftforge.net/en/1.20.1/concepts/registries/)

binding.path 对应真实注册名。仅制作资源时交付 assets；要求新增游戏对象时完成项目接线。

## 普通静态方块

以下 PanelContent.java 同时注册 Block 和可放置的 BlockItem；强度只是示例设计参数。完整块外观按 [方块流程](workflows/block.md) 导出。

```java
package examplemod.content;

import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class PanelContent {
    private static final String MODID = "examplemod";
    public static final DeferredRegister<Block> BLOCKS =
        DeferredRegister.create(ForgeRegistries.BLOCKS, MODID);
    public static final DeferredRegister<Item> ITEMS =
        DeferredRegister.create(ForgeRegistries.ITEMS, MODID);
    public static final RegistryObject<Block> PANEL = BLOCKS.register(
        "panel", () -> new Block(BlockBehaviour.Properties.of().strength(2.0F)));
    public static final RegistryObject<Item> PANEL_ITEM = ITEMS.register(
        "panel", () -> new BlockItem(PANEL.get(), new Item.Properties()));

    private PanelContent() {}

    public static void register(IEventBus bus) {
        BLOCKS.register(bus);
        ITEMS.register(bus);
        bus.addListener(PanelContent::creative);
    }

    private static void creative(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.BUILDING_BLOCKS) {
            event.accept(PANEL_ITEM.get());
        }
    }
}
```

在项目已有主入口的 mod event bus 初始化后调用 `PanelContent.register(modEventBus);`。若该项目已经有 BLOCKS/ITEMS，把对应的两项注册放入原类，不重复注册相同 ID。BlockItem 决定物品栏/放置入口，模型资源不能代替这项注册。

自定义形状改为项目 Block 子类，将工作台 asset export-shapes 的 helper 接到 getShape/getCollisionShape；加入朝向或开关属性时，默认状态、允许状态域、state definition、放置/旋转行为、模型引用必须一同实现。简单空 variant 导出不涵盖这些状态。透明块还需实际渲染机制，发光纹理也不等于方块发光等级；按项目既有方块实现选择，不能靠图片伪造游戏行为。

## 普通材料物品

以下 CrystalContent.java 注册一个无额外行为的材料；配套资源按 [物品流程](workflows/item.md) 导出。

```java
package examplemod.content;

import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class CrystalContent {
    public static final DeferredRegister<Item> ITEMS =
        DeferredRegister.create(ForgeRegistries.ITEMS, "examplemod");
    public static final RegistryObject<Item> CRYSTAL =
        ITEMS.register("crystal", () -> new Item(new Item.Properties().stacksTo(64)));

    private CrystalContent() {}

    public static void register(IEventBus bus) {
        ITEMS.register(bus);
        bus.addListener(CrystalContent::creative);
    }

    private static void creative(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.INGREDIENTS) {
            event.accept(CRYSTAL.get());
        }
    }
}
```

同样调用 `CrystalContent.register(modEventBus);`，或合并进项目已有 ITEMS。堆叠和耐久按真实用途设置；复杂使用行为应由对应 Item 子类或项目框架承担。创造模式内容通过 BuildCreativeModeTabContentsEvent 接到 mod event bus；已有自定义分类时使用项目的分类键。[Forge 物品与分类文档](https://docs.minecraftforge.net/en/1.20.1/items/)

## 语言、掉落与获取

合并语言键到实际 assets/<namespace>/lang/zh_cn.json 或语言 provider，不能覆盖整份语言文件：

```json
{
  "block.examplemod.panel": "面板",
  "item.examplemod.crystal": "晶体"
}
```

方块希望普通挖掘掉落自身时，在项目 loot provider 或 data/examplemod/loot_tables/blocks/panel.json 声明：

```json
{
  "type": "minecraft:block",
  "pools": [
    {
      "rolls": 1,
      "entries": [
        {
          "type": "minecraft:item",
          "name": "examplemod:panel"
        }
      ],
      "conditions": [
        {
          "condition": "minecraft:survives_explosion"
        }
      ]
    }
  ]
}
```

这个示例没有擅自加正确工具/等级要求。若设计要求特定工具，在 Block 属性、mineable 标签和所需等级标签中保持一致，并按项目掉落规则实现。掉落空、掉其他物品、容器保留数据等行为使用其真实设计；不是所有方块都应 dropSelf。[Forge 掉落数据生成](https://docs.minecraftforge.net/en/1.20.1/datagen/server/loottables/)

获取方式使用已确定的创造模式入口、配方、机器配方或掉落，不臆造加工链。需要 tags/配方时沿用项目 providers 和 namespace。现有 datagen 项目把模型/状态/语言/掉落逻辑接到相应 provider，纹理 PNG 作为源资产；不手写 generated 目录后让下次 runData 覆盖。[Forge datagen](https://docs.minecraftforge.net/en/1.20.1/datagen/)、[模型 provider](https://docs.minecraftforge.net/en/1.20.1/datagen/client/modelproviders/)

## 验证与交付

按项目 wrapper 和既有任务编译、处理资源及必要的 datagen，再核对 JAR 中 assets/data 与注册名。

minecraft check 只覆盖选中资源引用，Java 编译不覆盖游戏行为。按本次改动分别报告资源、编译和实际运行检查；技能维护不为示例另建消费模组。

交付对象 ID、源资产与接线改动、构建结果及未验证范围。其他版本/框架使用项目自己的适配。
