package @PACKAGE@;

import com.google.gson.JsonObject;
import net.minecraft.nbt.CompoundTag;

/** One owner per BlockEntity. Server events, simulation, disk and packet restore share one clock. */
public final class InstanceState {
    private SceneRuntime.Player player;
    private final String unloaded;
    private final int maxCatchUpTicks,syncInterval;
    private final boolean singleClip;
    private boolean active,ready;
    private long lastTick,revision,receivedRevision=-1;

    public InstanceState(JsonObject scene,JsonObject lifecycle){
        player=new SceneRuntime.Player(scene);
        singleClip=!scene.has("states");
        if(singleClip)player.suspend(false);
        unloaded=lifecycle==null?"pause":lifecycle.get("unloaded").getAsString();
        maxCatchUpTicks=lifecycle==null?2400:lifecycle.get("max_catch_up_ticks").getAsInt();
        syncInterval=lifecycle==null?20:lifecycle.get("sync_interval_ticks").getAsInt();
        if(!unloaded.equals("pause")&&!unloaded.equals("catch_up")||maxCatchUpTicks<0||maxCatchUpTicks>2400||syncInterval<1||syncInterval>1200)throw new IllegalArgumentException("Instance lifecycle");
    }
    public SceneRuntime.Player player(){return player;}
    public boolean active(){return active;}
    public boolean ready(){return ready;}
    public long revision(){return revision;}
    /** Return true for an actual edge, even when a single clip has no named event route. */
    public boolean setActive(boolean value){if(active==value)return false;active=value;if(singleClip){if(value)player.resume();else player.suspend();}else player.event(value?"start":"stop");revision++;return true;}
    public boolean event(String name){boolean changed=player.event(name);if(changed)revision++;return changed;}
    public void suspendVisual(){if(!player.suspended()){player.suspend();revision++;}}
    public void resumeVisual(){if(player.suspended()){player.resume();revision++;}}
    public void onLoad(long now){if(ready&&unloaded.equals("catch_up"))catchUp(now);lastTick=now;ready=true;revision++;}
    private void catchUp(long now){long elapsed=now<=lastTick?0:Math.min(maxCatchUpTicks,now-lastTick);if(elapsed>0)player.simulate(elapsed*50.0);}
    /** No rendering side effects. Returns whether a server synchronization is due. */
    public boolean tick(long now,boolean client){
        if(!ready||now<=lastTick)return false;
        long delta=Math.min(2400,now-lastTick);player.simulate(delta*50.0);lastTick=now;
        if(client)return false;revision++;return now%syncInterval==0;
    }
    public void save(CompoundTag tag,long now){SnapshotCodec.write(tag,player,now);tag.putBoolean("PixForgeActive",active);tag.putLong("PixForgeRevision",revision);}
    /** Disk restore remains paused until onLoad; packets catch up only their transit time. */
    public boolean load(CompoundTag tag,boolean packet,long now){
        if(!SnapshotCodec.has(tag))return false;
        long incoming=tag.getLong("PixForgeRevision");if(incoming<0)throw new IllegalArgumentException("Instance revision");
        if(packet&&receivedRevision>=incoming)return false;
        SceneRuntime.Player candidate=player.copy();long epoch=SnapshotCodec.read(tag,candidate);if(epoch<0)throw new IllegalArgumentException("Instance epoch");
        player=candidate;active=tag.contains("PixForgeActive")?tag.getBoolean("PixForgeActive"):!candidate.suspended();revision=incoming;lastTick=epoch;ready=true;
        if(packet){receivedRevision=incoming;catchUp(now);lastTick=now;}
        return true;
    }
}
