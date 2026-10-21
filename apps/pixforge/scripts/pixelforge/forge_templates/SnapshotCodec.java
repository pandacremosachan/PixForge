package @PACKAGE@;

import com.google.gson.JsonParser;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.zip.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;

/** Bounded NBT byte-array snapshots avoid NBT's 64 KiB modified-UTF string limit. */
public final class SnapshotCodec {
    private SnapshotCodec() {}
    private static final int MAX_DECODED=4*1024*1024,MAX_COMPRESSED=1500000;
    public static boolean has(CompoundTag tag){return tag.contains("PixForgeScene",Tag.TAG_BYTE_ARRAY);}
    public static void write(CompoundTag tag,SceneRuntime.Player player,long gameTick){
        byte[] raw=player.snapshot().toString().getBytes(StandardCharsets.UTF_8);
        if(raw.length>MAX_DECODED)throw new IllegalStateException("PixForge snapshot exceeds 4 MiB");
        try{var bytes=new ByteArrayOutputStream();try(var zip=new GZIPOutputStream(bytes)){zip.write(raw);}byte[] compressed=bytes.toByteArray();if(compressed.length>MAX_COMPRESSED)throw new IllegalStateException("PixForge compressed snapshot exceeds 1.5 MB");tag.putByteArray("PixForgeScene",compressed);tag.putLong("PixForgeGameTick",gameTick);}
        catch(IOException error){throw new IllegalStateException("Cannot encode PixForge snapshot",error);}
    }
    public static long read(CompoundTag tag,SceneRuntime.Player player){
        byte[] compressed=tag.getByteArray("PixForgeScene");if(compressed.length>MAX_COMPRESSED)throw new IllegalArgumentException("PixForge snapshot compressed limit");
        try(var zip=new GZIPInputStream(new ByteArrayInputStream(compressed))){byte[] raw=zip.readNBytes(MAX_DECODED+1);if(raw.length>MAX_DECODED)throw new IllegalArgumentException("PixForge snapshot decoded limit");player.restore(JsonParser.parseString(new String(raw,StandardCharsets.UTF_8)).getAsJsonObject());return tag.getLong("PixForgeGameTick");}
        catch(IOException error){throw new IllegalArgumentException("Invalid PixForge snapshot",error);}
    }
}
