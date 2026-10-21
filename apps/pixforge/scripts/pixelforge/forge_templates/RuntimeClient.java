package @PACKAGE@;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.mojang.math.Axis;
import java.util.*;
import java.util.function.Function;
import java.util.function.ToIntFunction;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.particle.*;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.client.renderer.texture.TextureManager;
import net.minecraft.client.resources.model.*;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.*;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Vector4f;

/** All client classes are isolated behind the physical-client mod-event subscriber. */
@Mod.EventBusSubscriber(modid="@MODID@",bus=Mod.EventBusSubscriber.Bus.MOD,value=Dist.CLIENT)
public final class RuntimeClient {
    private RuntimeClient() {}
    private static volatile BakedModel[][] parts=new BakedModel[0][];
    public static boolean measurePerformance;
    public static long renderedInstances,renderedParts,sceneRenderNanos;
    private static final class BirthCache {long touched;final Map<String,Long> births=new HashMap<>();}
    private static final Map<ClientLevel,Map<BlockPos,BirthCache>> SEEN=new WeakHashMap<>();
    private static final Map<ClientLevel,Long> PRUNED=new WeakHashMap<>();
    private static RenderType entityLayer(String name){return switch(name){case "solid"->RenderType.entitySolid(TextureAtlas.LOCATION_BLOCKS);case "translucent"->RenderType.entityTranslucent(TextureAtlas.LOCATION_BLOCKS);default->RenderType.entityCutoutNoCull(TextureAtlas.LOCATION_BLOCKS);};}
    @SubscribeEvent public static void setup(FMLClientSetupEvent event){event.enqueueWork(()->RuntimeModule.clientTick=RuntimeClient::tickParticles);}
    @SubscribeEvent public static void additional(ModelEvent.RegisterAdditional event){for(var row:RuntimeData.DATA.getAsJsonArray("part_models"))for(var id:row.getAsJsonArray())event.register(new ResourceLocation(id.getAsString()));}
    @SubscribeEvent public static void baked(ModelEvent.BakingCompleted event){
        var rows=RuntimeData.DATA.getAsJsonArray("part_models");var result=new BakedModel[rows.size()][];
        for(int i=0;i<result.length;i++){var row=rows.get(i).getAsJsonArray();result[i]=new BakedModel[row.size()];for(int j=0;j<row.size();j++){var id=new ResourceLocation(row.get(j).getAsString());var model=event.getModels().get(id);if(model==null)throw new IllegalStateException("Unbaked PixForge part "+id);result[i][j]=model;}}
        parts=result;SEEN.clear();
    }
    @SubscribeEvent public static void renderers(EntityRenderersEvent.RegisterRenderers event){
        if(RuntimeModule.examplesRegistered()&&RuntimeModule.hasScene()&&RuntimeModule.EXAMPLE_ENTITY.isPresent())registerRenderer(event,RuntimeModule.EXAMPLE_ENTITY.get(),RuntimeModule.ExampleBlockEntity::pixforgePlayer,RuntimeModule.ExampleBlockEntity::pixforgeRotation);
    }
    public static <T extends BlockEntity> void registerRenderer(EntityRenderersEvent.RegisterRenderers event,BlockEntityType<T> type,Function<T,SceneRuntime.Player> player,ToIntFunction<T> rotation){event.registerBlockEntityRenderer(type,context->new SceneRenderer<>(player,rotation));}
    @SubscribeEvent public static void providers(RegisterParticleProvidersEvent event){
        if(RuntimeModule.PROGRAM_PARTICLE!=null)event.registerSpriteSet(RuntimeModule.PROGRAM_PARTICLE.get(),sprites->(options,level,x,y,z,vx,vy,vz)->new ProgramParticle(level,options,x,y,z,sprites));
    }
    public static final class SceneRenderer<T extends BlockEntity> implements BlockEntityRenderer<T> {
        private final Function<T,SceneRuntime.Player> access;private final ToIntFunction<T> rotation;
        public SceneRenderer(Function<T,SceneRuntime.Player> access,ToIntFunction<T> rotation){this.access=access;this.rotation=rotation;}
        @Override public int getViewDistance(){return RuntimeData.DATA.get("view_distance").getAsInt();}
        @Override public void render(T entity,float partial,PoseStack pose,MultiBufferSource buffers,int light,int overlay){
            var source=access.apply(entity);var models=parts;if(source==null||models.length==0)return;
            long measuredStart=measurePerformance?System.nanoTime():0;
            var player=source.renderCopy();player.simulate(Math.max(0,Math.min(1,partial))*50.0);int frame=player.textureFrame(RuntimeData.DATA.getAsJsonObject("animation"));
            if(frame<0||frame>=models.length)throw new IllegalStateException("Unexported PixForge texture frame");
            var binding=RuntimeModule.CONFIG.getAsJsonObject("scene");RenderType layer=entityLayer(binding.get("render_type").getAsString());
            pose.pushPose();pose.translate(.5,0,.5);pose.mulPose(Axis.YP.rotationDegrees(rotation.applyAsInt(entity)));pose.translate(-.5,0,-.5);
            for(int element=0;element<models[frame].length;element++){
                double[] origin=player.point(element,new double[]{0,0,0},false);double[][] basis={player.point(element,new double[]{1,0,0},false),player.point(element,new double[]{0,1,0},false),player.point(element,new double[]{0,0,1},false)};
                var matrix=new Matrix4f().identity();for(int c=0;c<3;c++)matrix.setColumn(c,new Vector4f((float)(basis[c][0]-origin[0]),(float)(basis[c][1]-origin[1]),(float)(basis[c][2]-origin[2]),0));matrix.setColumn(3,new Vector4f((float)(origin[0]/16),(float)(origin[1]/16),(float)(origin[2]/16),1));
                pose.pushPose();pose.last().pose().mul(matrix);pose.last().normal().mul(new Matrix3f(matrix).invert().transpose());
                var consumer=buffers.getBuffer(layer);for(var quad:models[frame][element].getQuads(entity.getBlockState(),null,RandomSource.create(42))){int color=quad.isTinted()&&entity.getLevel()!=null?Minecraft.getInstance().getBlockColors().getColor(entity.getBlockState(),entity.getLevel(),entity.getBlockPos(),quad.getTintIndex()):0xffffff;consumer.putBulkData(pose.last(),quad,((color>>16)&255)/255F,((color>>8)&255)/255F,(color&255)/255F,light,overlay);}
                pose.popPose();
            }pose.popPose();
            if(measurePerformance){renderedInstances++;renderedParts+=models[frame].length;sceneRenderNanos+=System.nanoTime()-measuredStart;}
        }
    }
    /** Call after a client's 50 ms player advance. Render frames never spawn particles. */
    public static void tickParticles(BlockEntity owner,SceneRuntime.Player player){
        if(RuntimeModule.PROGRAM_PARTICLE==null||!(owner.getLevel() instanceof ClientLevel level))return;
        long now=level.getGameTime();var owners=SEEN.computeIfAbsent(level,key->new HashMap<>());
        if(now%20==0&&!Objects.equals(PRUNED.get(level),now)){owners.entrySet().removeIf(e->e.getValue().touched+2402<now);PRUNED.put(level,now);}
        var cache=owners.computeIfAbsent(owner.getBlockPos().immutable(),key->new BirthCache());cache.touched=now;var seen=cache.births;seen.entrySet().removeIf(e->e.getValue()<now);
        int rotation=owner instanceof RuntimeModule.SceneHost context?context.pixforgeRotation():0;
        double angle=Math.toRadians(rotation),c=Math.cos(angle),s=Math.sin(angle);
        for(var particle:player.particles())if(!seen.containsKey(particle.uid)){
            var p=particle.copy();double x=p.position[0]-8,z=p.position[2]-8;p.position[0]=8+x*c+z*s;p.position[2]=8-x*s+z*c;
            for(double[] vector:new double[][]{p.velocity,p.gravity}){x=vector[0];z=vector[2];vector[0]=x*c+z*s;vector[2]=-x*s+z*c;}
            var origin=owner.getBlockPos();level.addParticle(new ProgramOptions(p),origin.getX()+p.position[0]/16,origin.getY()+p.position[1]/16,origin.getZ()+p.position[2]/16,0,0,0);
            seen.put(p.uid,now+(long)Math.ceil(p.remaining/50)+2);
        }
    }
    private static final ParticleRenderType ADDITIVE=new ParticleRenderType(){
        @Override public void begin(BufferBuilder builder,TextureManager textures){RenderSystem.depthMask(false);RenderSystem.enableBlend();RenderSystem.blendFunc(770,1);RenderSystem.setShader(GameRenderer::getParticleShader);RenderSystem.setShaderTexture(0,TextureAtlas.LOCATION_PARTICLES);builder.begin(VertexFormat.Mode.QUADS,DefaultVertexFormat.PARTICLE);}
        @Override public void end(Tesselator tesselator){tesselator.end();RenderSystem.defaultBlendFunc();RenderSystem.depthMask(true);}
        @Override public String toString(){return "PIXFORGE_ADDITIVE_@MODID@_"+RuntimeData.DATA.get("module_id").getAsString();}
    };
    private static final class ProgramParticle extends TextureSheetParticle {
        private final SceneRuntime.Particle source;private final double startX,startY,startZ;
        ProgramParticle(ClientLevel level,ProgramOptions options,double x,double y,double z,SpriteSet sprites){super(level,x,y,z);source=options.particle.copy();startX=x;startY=y;startZ=z;hasPhysics=false;lifetime=Math.max(1,(int)Math.ceil(source.remaining/50));setSprite(sprites.get(0,1));}
        @Override public void tick(){xo=x;yo=y;zo=z;if(++age*50>=source.remaining){remove();return;}double t=age*.05;x=startX+(source.velocity[0]*t+.5*source.gravity[0]*t*t)/16;y=startY+(source.velocity[1]*t+.5*source.gravity[1]*t*t)/16;z=startZ+(source.velocity[2]*t+.5*source.gravity[2]*t*t)/16;}
        @Override public ParticleRenderType getRenderType(){return source.blend.equals("additive")?ADDITIVE:ParticleRenderType.PARTICLE_SHEET_TRANSLUCENT;}
        @Override public void render(VertexConsumer vertices,Camera camera,float partial){
            double ms=(age+partial)*50;if(ms>=source.remaining)return;double t=ms/1000,ratio=ms/source.remaining;
            var cameraPos=camera.getPosition();double px=startX+(source.velocity[0]*t+.5*source.gravity[0]*t*t)/16-cameraPos.x,py=startY+(source.velocity[1]*t+.5*source.gravity[1]*t*t)/16-cameraPos.y,pz=startZ+(source.velocity[2]*t+.5*source.gravity[2]*t*t)/16-cameraPos.z;
            float half=(float)((source.size+(source.endSize-source.size)*ratio)/32);float[] color=new float[4];for(int i=0;i<4;i++)color[i]=(float)((source.color[i]+(source.endColor[i]-source.color[i])*ratio)/255);
            Vector3f[] corners={new Vector3f(-1,-1,0),new Vector3f(-1,1,0),new Vector3f(1,1,0),new Vector3f(1,-1,0)};float[][] uv={{getU1(),getV1()},{getU1(),getV0()},{getU0(),getV0()},{getU0(),getV1()}};
            int light=getLightColor(partial);for(int i=0;i<4;i++){corners[i].rotate(camera.rotation()).mul(half).add((float)px,(float)py,(float)pz);vertices.vertex(corners[i].x,corners[i].y,corners[i].z).uv(uv[i][0],uv[i][1]).color(color[0],color[1],color[2],color[3]).uv2(light).endVertex();}
        }
    }
}
