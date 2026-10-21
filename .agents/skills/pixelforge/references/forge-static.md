# Forge 1.20.1：把外观接成真实方块或物品

这是**目标适配器指导**，仅用于 Minecraft Java 1.20.1 / Forge / Mojang mappings。skill 的连接和资产制作不依赖该版本。消费项目已有 Registrate、材料自动注册、KubeJS 或其他注册框架时沿用其入口，不另建第二套注册。资源包换皮不执行新注册。

## 接入顺序

先确认实际 mod id、包名、注册类、主入口 mod event bus、资源源集、datagen provider、创造模式分类和构建任务。下面是普通 Forge 工程的可复制实现；把 examplemod、包路径、类名和资源名换成项目值，并将 register 接到**已有**主入口构造流程。不要新增第二个 @Mod 主入口。DeferredRegister 应挂到 mod event bus，而非全局游戏事件总线。[Forge 注册文档](https://docs.minecraftforge.net/en/1.20.1/concepts/registries/)

工作台资源 binding.path 必须与这里的注册名对应。若资产导出后尚未取得源树集成授权，先交付接线差异和 ZIP，保留现有源文件；用户已要求定义/新增对象时按其项目范围完成实际接线。

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

自定义形状改为项目 Block 子类，将工作台 shape-export 的 helper 接到 getShape/getCollisionShape；加入朝向或开关属性时，默认状态、允许状态域、state definition、放置/旋转行为、模型引用必须一同实现。简单空 variant 导出不涵盖这些状态。透明块还需实际渲染机制，发光纹理也不等于方块发光等级；按项目既有方块实现选择，不能靠图片伪造游戏行为。

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
  "block.examplemod.panel":"面板",
  "item.examplemod.crystal":"晶体"
}
```

方块希望普通挖掘掉落自身时，在项目 loot provider 或 data/examplemod/loot_tables/blocks/panel.json 声明：

```json
{
  "type":"minecraft:block",
  "pools":[{
    "rolls":1,
    "entries":[{"type":"minecraft:item","name":"examplemod:panel"}],
    "conditions":[{"condition":"minecraft:survives_explosion"}]
  }]
}
```

这个示例没有擅自加正确工具/等级要求。若设计要求特定工具，在 Block 属性、mineable 标签和所需等级标签中保持一致，并按项目掉落规则实现。掉落空、掉其他物品、容器保留数据等行为使用其真实设计；不是所有方块都应 dropSelf。[Forge 掉落数据生成](https://docs.minecraftforge.net/en/1.20.1/datagen/server/loottables/)

获取方式使用已确定的创造模式入口、配方、机器配方或掉落，不臆造加工链。需要 tags/配方时沿用项目 providers 和 namespace。现有 datagen 项目把模型/状态/语言/掉落逻辑接到相应 provider，纹理 PNG 作为源资产；不手写 generated 目录后让下次 runData 覆盖。[Forge datagen](https://docs.minecraftforge.net/en/1.20.1/datagen/)、[模型 provider](https://docs.minecraftforge.net/en/1.20.1/datagen/client/modelproviders/)

## 验证与交付

按项目已有 wrapper 与任务运行所需的编译/资源处理/datagen；普通 Gradle 项目常见为 compileJava、processResources，只有已有 runData 任务时才使用它。不安装全局 JDK、不为验证自动启动游戏。构建后核对成品 JAR 中 assets/data 及实际注册名，避免资源被错误源集排除。

工作台 minecraft-check 检查其选中资源引用闭包，不检查 Java 注册全域、配方、语言完整性或所有游戏状态。Java 编译通过证明接线类型正确；游戏里能放置/使用、透明排序、掉落行为和实际性能仍需对应运行证据。只修改 skill 时无需为文档示例创建或编译真实消费模组；不要把示例未在某项目编译描述成该项目已经通过。

交付至少说明：对象 ID、注册/行为修改、原生资产路径、datagen 改动、形状/显示状态、构建结果及游戏验证范围。当前适配器范围之外的版本/框架，保留资产和意图，使用消费项目自己的注册/资源实现，不能将上述 Java 当跨版本代码。
