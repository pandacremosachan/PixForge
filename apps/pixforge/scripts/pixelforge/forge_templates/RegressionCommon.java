package @PACKAGE@;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.exceptions.SimpleCommandExceptionType;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.coordinates.BlockPosArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.registries.ForgeRegistries;

/** Explicit operator commands; no fixture is placed and no world is changed during mod loading. */
@Mod.EventBusSubscriber(modid="@MODID@")
public final class RegressionCommon {
    private RegressionCommon(){}
    private static final SimpleCommandExceptionType ERROR=new SimpleCommandExceptionType(Component.literal("Choose a loaded, empty fixture volume and a configured block id."));
    @SubscribeEvent public static void commands(RegisterCommandsEvent event){
        event.getDispatcher().register(Commands.literal("pixforge_fixture").requires(s->s.hasPermission(2))
            .then(Commands.literal("place").then(Commands.argument("block",StringArgumentType.word()).then(Commands.argument("origin",BlockPosArgument.blockPos()).then(Commands.argument("count",IntegerArgumentType.integer(1,256)).executes(c->{
                var level=c.getSource().getLevel();var origin=BlockPosArgument.getLoadedBlockPos(c,"origin");int count=IntegerArgumentType.getInteger(c,"count");String id=StringArgumentType.getString(c,"block");
                boolean allowed=RuntimeModule.hasScene()&&RuntimeModule.CONFIG.getAsJsonObject("scene").get("block").getAsString().equals(id);
                Block block=ForgeRegistries.BLOCKS.getValue(new ResourceLocation(id));if(!allowed||block==null)throw ERROR.create();int side=(int)Math.ceil(Math.sqrt(count));
                // Check the complete finite box before any mutation. Existing terrain is never replaced.
                for(int x=-1;x<=side;x++)for(int z=-1;z<=side;z++)for(int y=-1;y<=5;y++){var p=origin.offset(x,y,z);if(!level.hasChunkAt(p)||!level.isInWorldBounds(p)||!level.isEmptyBlock(p))throw ERROR.create();}
                for(int x=-1;x<=side;x++)for(int z=-1;z<=side;z++)level.setBlock(origin.offset(x,-1,z),Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState(),Block.UPDATE_ALL);
                for(int i=0;i<count;i++){var p=origin.offset(i%side,0,i/side);BlockState state=block.defaultBlockState();if(state.hasProperty(RuntimeModule.ROTATION))state=state.setValue(RuntimeModule.ROTATION,i%4);if(state.hasProperty(RuntimeModule.ACTIVE))state=state.setValue(RuntimeModule.ACTIVE,i%2==0);level.setBlock(p,state,Block.UPDATE_ALL);if(level.getBlockEntity(p) instanceof RuntimeModule.ExampleBlockEntity be)be.setActive(i%2==0);}
                c.getSource().sendSuccess(()->Component.literal("PixForge fixture: "+count+" blocks; origin "+origin.toShortString()+". No cleanup is performed automatically."),false);return count;
            })))))
            .then(Commands.literal("states").then(Commands.argument("origin",BlockPosArgument.blockPos()).then(Commands.argument("count",IntegerArgumentType.integer(1,256)).then(Commands.argument("pattern",StringArgumentType.word()).suggests((c,b)->net.minecraft.commands.SharedSuggestionProvider.suggest(new String[]{"match","state_split","rotations","stopped","active","freeze","resume"},b)).executes(c->{
                var level=c.getSource().getLevel();var origin=BlockPosArgument.getLoadedBlockPos(c,"origin");int count=IntegerArgumentType.getInteger(c,"count"),side=(int)Math.ceil(Math.sqrt(count));String pattern=StringArgumentType.getString(c,"pattern");if(!java.util.Set.of("match","state_split","rotations","stopped","active","freeze","resume").contains(pattern))throw ERROR.create();
                for(int i=0;i<count;i++)if(!level.hasChunkAt(origin.offset(i%side,0,i/side))||!(level.getBlockEntity(origin.offset(i%side,0,i/side)) instanceof RuntimeModule.ExampleBlockEntity))throw ERROR.create();
                for(int i=0;i<count;i++){var pos=origin.offset(i%side,0,i/side);var be=(RuntimeModule.ExampleBlockEntity)level.getBlockEntity(pos);if(pattern.equals("freeze")||pattern.equals("resume")){if(be.pixforgeInstance()!=null){if(pattern.equals("freeze"))be.pixforgeInstance().suspendVisual();else be.pixforgeInstance().resumeVisual();be.changed();}continue;}
                    boolean active=!pattern.equals("stopped")&&(!pattern.equals("state_split")||i%2==0);var state=be.getBlockState().setValue(RuntimeModule.ROTATION,pattern.equals("rotations")?i%4:0).setValue(RuntimeModule.ACTIVE,active);level.setBlock(pos,state,Block.UPDATE_ALL);be.setActive(active);be.changed();}
                c.getSource().sendSuccess(()->Component.literal("Fixture state pattern: "+pattern),false);return count;
            })))))
            .then(Commands.literal("view").then(Commands.argument("origin",BlockPosArgument.blockPos()).then(Commands.argument("count",IntegerArgumentType.integer(1,256)).then(Commands.argument("case",StringArgumentType.word()).suggests((c,b)->net.minecraft.commands.SharedSuggestionProvider.suggest(new String[]{"near","far","north","east","south","west","night"},b)).executes(c->{
                var p=BlockPosArgument.getLoadedBlockPos(c,"origin");int side=(int)Math.ceil(Math.sqrt(IntegerArgumentType.getInteger(c,"count")));String label=StringArgumentType.getString(c,"case");double distance=label.equals("far")?48:Math.max(10,side*1.5),angle=switch(label){case "east"->90;case "south"->180;case "west"->270;default->0;};if(!java.util.Set.of("near","far","north","east","south","west","night").contains(label))throw ERROR.create();
                var player=c.getSource().getPlayerOrException();double radians=Math.toRadians(angle),cx=p.getX()+side*.5,cy=p.getY()+.5,cz=p.getZ()+side*.5;player.connection.teleport(cx+Math.sin(radians)*distance,cy+Math.tan(Math.toRadians(20))*distance-player.getEyeHeight(),cz+Math.cos(radians)*distance,(float)(180-angle),20);
                c.getSource().getLevel().setDayTime(label.equals("night")?18000:6000);c.getSource().sendSuccess(()->Component.literal("View ready: "+label+". Wait for chunks/light, then /pixforge_capture "+label+" 120"),false);return Command.SINGLE_SUCCESS;
            }))))));
    }
}
