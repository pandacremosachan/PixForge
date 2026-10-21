package @PACKAGE@;

import com.google.gson.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleType;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.Connection;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityTicker;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/** Common-side integration hooks. This class never references Minecraft client classes. */
public final class RuntimeModule {
    private RuntimeModule() {}
    public static final JsonObject CONFIG=RuntimeData.DATA.getAsJsonObject("configuration");
    public static final BooleanProperty ACTIVE=BooleanProperty.create("active");
    public static final IntegerProperty ROTATION=IntegerProperty.create("rotation",0,3);
    public interface SceneHost {
        SceneRuntime.Player pixforgePlayer();
        default int pixforgeRotation(){return 0;}
    }
    @FunctionalInterface public interface ClientTick { void tick(BlockEntity owner,SceneRuntime.Player player); }
    public static ClientTick clientTick=(owner,player)->{};
    private static final DeferredRegister<Block> BLOCKS=DeferredRegister.create(ForgeRegistries.BLOCKS,RuntimeData.MODID);
    private static final DeferredRegister<Item> ITEMS=DeferredRegister.create(ForgeRegistries.ITEMS,RuntimeData.MODID);
    private static final DeferredRegister<BlockEntityType<?>> ENTITIES=DeferredRegister.create(ForgeRegistries.BLOCK_ENTITY_TYPES,RuntimeData.MODID);
    private static final DeferredRegister<ParticleType<?>> PARTICLES=DeferredRegister.create(ForgeRegistries.PARTICLE_TYPES,RuntimeData.MODID);
    public static final Map<String,RegistryObject<? extends Block>> EXAMPLE_BLOCKS=new LinkedHashMap<>();
    public static final RegistryObject<BlockEntityType<ExampleBlockEntity>> EXAMPLE_ENTITY;
    public static final RegistryObject<ParticleType<ProgramOptions>> PROGRAM_PARTICLE;
    private static boolean examplesRegistered;
    static {
        if(hasScene())addExample(CONFIG.getAsJsonObject("scene").get("block").getAsString());
        EXAMPLE_ENTITY=ENTITIES.register(RuntimeData.DATA.get("module_id").getAsString()+"_example",()->BlockEntityType.Builder.of(ExampleBlockEntity::new,EXAMPLE_BLOCKS.values().stream().map(RegistryObject::get).toArray(Block[]::new)).build(null));
        PROGRAM_PARTICLE=hasParticles()?PARTICLES.register(RuntimeData.DATA.get("module_id").getAsString()+"_program",()->new ParticleType<ProgramOptions>(false,ProgramOptions.DESERIALIZER){
            @Override public com.mojang.serialization.Codec<ProgramOptions> codec(){return ProgramOptions.CODEC;}
        }):null;
    }
    public static boolean hasScene(){return CONFIG.has("scene")&&!CONFIG.get("scene").isJsonNull();}
    public static boolean hasParticles(){
        if(!hasScene())return false;var scene=RuntimeData.DATA.getAsJsonObject("scene");
        if(scene.has("states")){for(var s:scene.getAsJsonArray("states"))if(!s.getAsJsonObject().getAsJsonArray("emitters").isEmpty())return true;return false;}
        return !scene.getAsJsonArray("emitters").isEmpty();
    }
    private static void addExample(String id){
        String path=new ResourceLocation(id).getPath();var block=BLOCKS.register(path,()->new ExampleBlock());EXAMPLE_BLOCKS.put(id,block);
        ITEMS.register(path,()->new BlockItem(block.get(),new Item.Properties()));
    }
    /** Standalone example only. Existing mods use registerParticles and their own registries. */
    public static void register(IEventBus bus){examplesRegistered=true;BLOCKS.register(bus);ITEMS.register(bus);ENTITIES.register(bus);registerParticles(bus);}
    public static boolean examplesRegistered(){return examplesRegistered;}
    public static void registerParticles(IEventBus bus){PARTICLES.register(bus);}
    public static final class ExampleBlock extends Block implements EntityBlock {
        ExampleBlock(){super(BlockBehaviour.Properties.of().strength(1.5F).noOcclusion());registerDefaultState(stateDefinition.any().setValue(ACTIVE,false).setValue(ROTATION,0));}
        @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(ACTIVE,ROTATION);}
        @Override public BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new ExampleBlockEntity(pos,state);}
        @Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level,BlockState state,BlockEntityType<T> type){return type==EXAMPLE_ENTITY.get()?(world,pos,s,be)->((ExampleBlockEntity)be).tick():null;}
        @Override public InteractionResult use(BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
            if(hand!=InteractionHand.MAIN_HAND)return InteractionResult.PASS;
            if(!level.isClientSide){var be=level.getBlockEntity(pos);if(be instanceof ExampleBlockEntity own){
                if(player.isShiftKeyDown())level.setBlock(pos,state.setValue(ROTATION,(state.getValue(ROTATION)+1)%4),Block.UPDATE_ALL);
                else{boolean active=!state.getValue(ACTIVE);level.setBlock(pos,state.setValue(ACTIVE,active),Block.UPDATE_ALL);own.setActive(active);}
                own.changed();
            }}return InteractionResult.sidedSuccess(level.isClientSide);
        }
    }
    public static final class ExampleBlockEntity extends BlockEntity implements SceneHost {
        private final InstanceState instance;
        ExampleBlockEntity(BlockPos pos,BlockState state){super(EXAMPLE_ENTITY.get(),pos,state);instance=new InstanceState(RuntimeData.DATA.getAsJsonObject("scene"),CONFIG.getAsJsonObject("scene").getAsJsonObject("lifecycle"));}
        @Override public SceneRuntime.Player pixforgePlayer(){return instance==null?null:instance.player();}
        public InstanceState pixforgeInstance(){return instance;}
        @Override public int pixforgeRotation(){return getBlockState().getValue(ROTATION)*90;}
        public boolean event(String event){boolean result=instance!=null&&instance.event(event);if(result)changed();return result;}
        public void setActive(boolean active){if(instance!=null&&instance.setActive(active))changed();}
        public void changed(){setChanged();if(level!=null)level.sendBlockUpdated(worldPosition,getBlockState(),getBlockState(),Block.UPDATE_CLIENTS);}
        void tick(){if(instance==null||level==null)return;boolean sync=instance.tick(level.getGameTime(),level.isClientSide);if(level.isClientSide){if(instance.ready())clientTick.tick(this,instance.player());}else{setChanged();if(sync)level.sendBlockUpdated(worldPosition,getBlockState(),getBlockState(),Block.UPDATE_CLIENTS);}}
        @Override public void onLoad(){super.onLoad();if(level!=null&&!level.isClientSide){if(instance!=null){instance.onLoad(level.getGameTime());instance.setActive(getBlockState().getValue(ACTIVE));}changed();}}
        @Override protected void saveAdditional(CompoundTag tag){super.saveAdditional(tag);if(instance!=null)instance.save(tag,level==null?0:level.getGameTime());}
        @Override public void load(CompoundTag tag){super.load(tag);if(instance!=null)instance.load(tag,false,0);}
        @Override public CompoundTag getUpdateTag(){return saveWithoutMetadata();}
        @Override public ClientboundBlockEntityDataPacket getUpdatePacket(){return ClientboundBlockEntityDataPacket.create(this);}
        @Override public void onDataPacket(Connection connection,ClientboundBlockEntityDataPacket packet){if(packet.getTag()!=null)handleUpdateTag(packet.getTag());}
        @Override public void handleUpdateTag(CompoundTag tag){if(level!=null&&instance!=null)instance.load(tag,true,level.getGameTime());}
        @Override public AABB getRenderBoundingBox(){var a=RuntimeData.DATA.getAsJsonArray("model_bounds");return new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble()).move(worldPosition);}
    }
}
