package @PACKAGE@;

import com.google.gson.Gson;
import com.mojang.brigadier.StringReader;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleType;
import net.minecraft.network.FriendlyByteBuf;

/** Dynamic particle payload, usable by the client program or normal Forge particle packets. */
public final class ProgramOptions implements ParticleOptions {
    public final SceneRuntime.Particle particle;
    public ProgramOptions(SceneRuntime.Particle p){
        if(p==null||p.remaining<=0||p.remaining>120000||!Double.isFinite(p.remaining)||!"alpha".equals(p.blend)&&!"additive".equals(p.blend))throw new IllegalArgumentException("particle lifetime/blend");
        check(p.position,3);check(p.velocity,3);check(p.gravity,3);check(p.color,4);check(p.endColor,4);
        if(!Double.isFinite(p.size)||!Double.isFinite(p.endSize)||p.size<0||p.size>16||p.endSize<0||p.endSize>16)throw new IllegalArgumentException("particle size");
        for(double value:p.color)if(value<0||value>255)throw new IllegalArgumentException("particle color");
        for(double value:p.endColor)if(value<0||value>255)throw new IllegalArgumentException("particle end color");
        particle=p.copy();
    }
    private static void check(double[] values,int size){if(values==null||values.length!=size)throw new IllegalArgumentException("particle vector");for(double v:values)if(!Double.isFinite(v)||Math.abs(v)>1e9)throw new IllegalArgumentException("particle finite value");}
    public String encoded(){return new Gson().toJson(particle);}
    public static ProgramOptions decode(String value){if(value.length()>8192)throw new IllegalArgumentException("particle payload too large");return new ProgramOptions(new Gson().fromJson(value,SceneRuntime.Particle.class));}
    public static final Codec<ProgramOptions> CODEC=Codec.STRING.comapFlatMap(text->{try{return DataResult.success(decode(text));}catch(RuntimeException error){return DataResult.error(()->"Invalid PixForge particle: "+error.getMessage());}},ProgramOptions::encoded);
    public static final Deserializer<ProgramOptions> DESERIALIZER=new Deserializer<>(){
        @Override public ProgramOptions fromCommand(ParticleType<ProgramOptions> type,StringReader reader)throws CommandSyntaxException {reader.expect(' ');return decode(reader.readString());}
        @Override public ProgramOptions fromNetwork(ParticleType<ProgramOptions> type,FriendlyByteBuf buffer){return decode(buffer.readUtf(8192));}
    };
    @Override public ParticleType<?> getType(){if(RuntimeModule.PROGRAM_PARTICLE==null)throw new IllegalStateException("No emitters were exported");return RuntimeModule.PROGRAM_PARTICLE.get();}
    @Override public void writeToNetwork(FriendlyByteBuf buffer){buffer.writeUtf(encoded(),8192);}
    @Override public String writeToString(){return RuntimeData.MODID+":"+RuntimeData.DATA.get("module_id").getAsString()+"_program "+new Gson().toJson(encoded());}
}
