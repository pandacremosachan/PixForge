package @PACKAGE@;

import com.google.gson.*;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.packs.resources.ResourceManagerReloadListener;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterClientCommandsEvent;
import net.minecraftforge.client.event.RegisterClientReloadListenersEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.versions.forge.ForgeVersion;

/** Real frame/event measurements and framebuffer pixels, only after an explicit client command. */
@Mod.EventBusSubscriber(modid="@MODID@",value=Dist.CLIENT)
public final class RegressionClient {
    private RegressionClient(){}
    private static final Gson JSON=new GsonBuilder().setPrettyPrinting().create();
    private static final List<Double> intervals=new ArrayList<>(),renderCpu=new ArrayList<>(),partsCpu=new ArrayList<>();
    private static final List<Long> visible=new ArrayList<>(),parts=new ArrayList<>();
    private static String label;private static int remaining,warmup;private static long previous,start;private static volatile long reloadGeneration;private static volatile String reloadHash="";private static JsonObject initial;
    @Mod.EventBusSubscriber(modid="@MODID@",bus=Mod.EventBusSubscriber.Bus.MOD,value=Dist.CLIENT)
    public static final class Reloads {
        @SubscribeEvent public static void listeners(RegisterClientReloadListenersEvent event){event.registerReloadListener((ResourceManagerReloadListener)manager->{
            try{var hash=MessageDigest.getInstance("SHA-256");var paths=manager.listResources("pixforge",p->p.getNamespace().equals("@MODID@")&&p.getPath().endsWith("runtime.json"));for(var row:new TreeMap<>(paths).entrySet()){hash.update(row.getKey().toString().getBytes(StandardCharsets.UTF_8));try(var stream=row.getValue().open()){hash.update(stream.readNBytes(4*1024*1024));}}reloadHash=HexFormat.of().formatHex(hash.digest());reloadGeneration++;}catch(Exception error){reloadHash="error:"+error.getClass().getSimpleName();}
        });}
    }
    @SubscribeEvent public static void commands(RegisterClientCommandsEvent event){event.getDispatcher().register(Commands.literal("pixforge_capture")
        .then(Commands.argument("label",StringArgumentType.word()).then(Commands.argument("frames",IntegerArgumentType.integer(30,600)).executes(c->{
            String name=StringArgumentType.getString(c,"label");if(!name.matches("[a-z0-9_-]{1,64}")||remaining>0)return 0;
            var mc=Minecraft.getInstance();if(mc.level==null||mc.player==null)return 0;
            label=name;remaining=IntegerArgumentType.getInteger(c,"frames");warmup=60;previous=0;intervals.clear();renderCpu.clear();partsCpu.clear();visible.clear();parts.clear();initial=context();RuntimeClient.measurePerformance=true;
            c.getSource().sendSuccess(()->Component.literal("PixForge: 60 warmup frames, then "+remaining+" measured frames. Keep camera, window and settings fixed."),false);return 1;
        }))));}
    @SubscribeEvent public static void frames(TickEvent.RenderTickEvent event){
        if(remaining<=0)return;
        if(event.phase==TickEvent.Phase.START){start=System.nanoTime();if(previous!=0&&warmup==0)intervals.add((start-previous)/1e6);previous=start;RuntimeClient.renderedInstances=RuntimeClient.renderedParts=RuntimeClient.sceneRenderNanos=0;return;}
        if(warmup>0){warmup--;return;}
        renderCpu.add((System.nanoTime()-start)/1e6);partsCpu.add(RuntimeClient.sceneRenderNanos/1e6);visible.add(RuntimeClient.renderedInstances);parts.add(RuntimeClient.renderedParts);
        if(--remaining==0){RuntimeClient.measurePerformance=false;save();}
    }
    private static JsonObject context(){
        var mc=Minecraft.getInstance();var o=new JsonObject();o.addProperty("dimension",mc.level.dimension().location().toString());var camera=mc.gameRenderer.getMainCamera();var p=camera.getPosition();var pose=new JsonArray();for(double n:new double[]{p.x,p.y,p.z,camera.getYRot(),camera.getXRot()})pose.add(n);o.add("camera",pose);
        o.addProperty("day_time",mc.level.getDayTime());o.addProperty("game_time",mc.level.getGameTime());o.addProperty("rain",mc.level.getRainLevel(0));o.addProperty("window_width",mc.getMainRenderTarget().width);o.addProperty("window_height",mc.getMainRenderTarget().height);o.addProperty("graphics",mc.options.graphicsMode().get().toString());o.addProperty("mipmaps",mc.options.mipmapLevels().get());o.addProperty("render_distance",mc.options.renderDistance().get());o.addProperty("particles",mc.options.particles().get().toString());o.addProperty("gamma",mc.options.gamma().get());o.addProperty("fov",mc.options.fov().get());o.addProperty("vsync",mc.options.enableVsync().get());o.addProperty("fps_limit",mc.options.framerateLimit().get());
        var blocks=new TreeMap<String,String>();int cx=mc.player.chunkPosition().x,cz=mc.player.chunkPosition().z;for(int x=cx-8;x<=cx+8;x++)for(int z=cz-8;z<=cz+8;z++){var chunk=mc.level.getChunkSource().getChunkNow(x,z);if(chunk!=null)for(var entry:chunk.getBlockEntities().entrySet())if(entry.getValue() instanceof RuntimeModule.ExampleBlockEntity be)blocks.put(entry.getKey().toShortString(),be.getBlockState().toString());}
        o.add("loaded_fixture_blocks",JSON.toJsonTree(blocks));o.addProperty("loaded_fixture_count",blocks.size());
        var phases=new TreeMap<String,JsonObject>();var lights=new TreeMap<String,String>();
        for(int x=cx-8;x<=cx+8;x++)for(int z=cz-8;z<=cz+8;z++){var chunk=mc.level.getChunkSource().getChunkNow(x,z);if(chunk!=null)for(var entry:chunk.getBlockEntities().entrySet())if(entry.getValue() instanceof RuntimeModule.ExampleBlockEntity be){var at=entry.getKey();lights.put(at.toShortString(),mc.level.getBrightness(net.minecraft.world.level.LightLayer.SKY,at)+","+mc.level.getBrightness(net.minecraft.world.level.LightLayer.BLOCK,at));if(be.pixforgePlayer()!=null){var snapshot=be.pixforgePlayer().snapshot();var phase=new JsonObject();for(String key:new String[]{"state","time","textureEntry","finished","generation","cycleBase","suspended"})phase.add(key,snapshot.get(key));phase.addProperty("tailTime",be.pixforgePlayer().particles().isEmpty()?0:snapshot.get("tailTime").getAsDouble());phases.put(at.toShortString(),phase);}}}
        o.add("loaded_fixture_phases",JSON.toJsonTree(phases));o.add("fixture_light",JSON.toJsonTree(lights));o.addProperty("sky_darken",mc.level.getSkyDarken());
        if(RuntimeData.DATA.has("material_contract")){var mods=new TreeMap<String,String>();ModList.get().getMods().forEach(mod->mods.put(mod.getModId(),mod.getVersion().toString()));o.add("material_shader",RegressionShader.observe(mc.gameDirectory.toPath(),RuntimeData.DATA.getAsJsonObject("material_contract"),mods));o.addProperty("resource_reload_generation",reloadGeneration);}
        return o;
    }
    private static JsonObject statistics(List<? extends Number> values){
        var sorted=values.stream().mapToDouble(Number::doubleValue).sorted().toArray();var o=new JsonObject();o.addProperty("count",sorted.length);o.addProperty("mean",Arrays.stream(sorted).average().orElse(0));o.addProperty("median",sorted.length==0?0:sorted[(sorted.length-1)/2]);o.addProperty("p95",sorted.length==0?0:sorted[(int)Math.ceil(sorted.length*.95)-1]);o.addProperty("p99",sorted.length==0?0:sorted[(int)Math.ceil(sorted.length*.99)-1]);return o;
    }
    private static String sha(Path path)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));}
    private static void save(){
        var mc=Minecraft.getInstance();try{
            if(mc.level==null||mc.player==null)throw new IllegalStateException("World left during capture");
            var directory=mc.gameDirectory.toPath().resolve("pixforge-regression").resolve(RuntimeData.DATA.get("module_id").getAsString()).resolve(label+"-"+System.currentTimeMillis());Files.createDirectories(directory);var screenshot=directory.resolve("view.png");try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(screenshot.toFile());}
            var o=new JsonObject();o.addProperty("schema","pixforge.game-regression/v1");o.addProperty("case_id",label);o.addProperty("minecraft","1.20.1");o.addProperty("forge",ForgeVersion.getVersion());o.addProperty("module_id",RuntimeData.DATA.get("module_id").getAsString());o.addProperty("runtime_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(RuntimeData.DATA.toString().getBytes(StandardCharsets.UTF_8))));o.addProperty("measured_in_game",true);o.add("start",initial);o.add("end",context());o.addProperty("reload_generation",reloadGeneration);o.addProperty("reload_resource_sha256",reloadHash);o.addProperty("renderer",org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_RENDERER));o.addProperty("vendor",org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_VENDOR));o.addProperty("java",System.getProperty("java.version"));
            o.add("frame_interval_ms",statistics(intervals));o.add("render_event_cpu_ms",statistics(renderCpu));o.add("pixforge_ber_cpu_ms",statistics(partsCpu));o.add("visible_instances",statistics(visible));o.add("part_submissions",statistics(parts));o.addProperty("game_particle_count",mc.particleEngine.countParticles());o.addProperty("gpu_time_ms",(Number)null);o.addProperty("timing_scope","frame intervals include pacing; render-event/BER nanoseconds are CPU observations, not GPU timestamps");
            var mods=new TreeMap<String,String>();ModList.get().getMods().forEach(m->mods.put(m.getModId(),m.getVersion().toString()));o.add("mods",JSON.toJsonTree(mods));o.addProperty("screenshot","view.png");o.addProperty("screenshot_sha256",sha(screenshot));
            var log=mc.gameDirectory.toPath().resolve("logs/latest.log");if(Files.isRegularFile(log)){try(var channel=Files.newByteChannel(log)){long size=channel.size();channel.position(Math.max(0,size-65536));var buffer=java.nio.ByteBuffer.allocate((int)Math.min(size,65536));channel.read(buffer);Files.write(directory.resolve("reload-log-tail.txt"),Arrays.copyOf(buffer.array(),buffer.position()));}o.addProperty("log_tail","reload-log-tail.txt");o.addProperty("log_tail_sha256",sha(directory.resolve("reload-log-tail.txt")));}
            Files.writeString(directory.resolve("capture.json"),JSON.toJson(o)+"\n",StandardCharsets.UTF_8);mc.player.displayClientMessage(Component.literal("PixForge capture: "+directory),false);
        }catch(Exception error){if(mc.player!=null)mc.player.displayClientMessage(Component.literal("PixForge capture failed: "+error),false);}
    }
}
