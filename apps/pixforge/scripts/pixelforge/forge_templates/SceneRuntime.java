package @PACKAGE@;

import com.google.gson.*;
import java.util.*;

/** Deterministic model-unit/millisecond runtime. Contains no client-only classes. */
public final class SceneRuntime {
    private SceneRuntime() {}
    static double n(JsonObject o,String k) { return o.get(k).getAsDouble(); }
    static String s(JsonObject o,String k) { return o.get(k).getAsString(); }
    static boolean b(JsonObject o,String k) { return o.get(k).getAsBoolean(); }
    static double[] v(JsonElement a) { var arr=a.getAsJsonArray();double[] out=new double[arr.size()];for(int i=0;i<out.length;i++)out[i]=arr.get(i).getAsDouble();return out; }
    static JsonArray array(double[] v) {var a=new JsonArray();for(double x:v)a.add(x);return a;}
    static double[] add(double[] a,double[] b) {return new double[]{a[0]+b[0],a[1]+b[1],a[2]+b[2]};}
    static double[] sub(double[] a,double[] b) {return new double[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};}
    static double[] mul(double[] a,double s) {return new double[]{a[0]*s,a[1]*s,a[2]*s};}
    static double length(double[] a) {return Math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);}
    static double mod(double x,double d) {return x-Math.floor(x/d)*d;}
    static double moment(JsonObject clip,double t) {return b(clip,"loop")?mod(t,n(clip,"duration_ms")):Math.min(n(clip,"duration_ms"),Math.max(0,t));}
    static boolean advanced(JsonObject clip) {return s(clip,"schema").equals("pixelforge.scene-animation/v2");}
    public static double random(long seed) {
        seed&=0xffffffffL;seed^=seed>>>16;seed=(seed*0x7feb352dL)&0xffffffffL;
        seed^=seed>>>15;seed=(seed*0x846ca68bL)&0xffffffffL;seed^=seed>>>16;
        return seed/4294967296.0;
    }
    static double ease(double p,String kind) {return switch(kind){case "hold"->0;case "smooth"->p*p*(3-2*p);case "ease_in"->p*p;case "ease_out"->1-(1-p)*(1-p);default->p;};}
    static JsonElement interpolate(JsonElement a,JsonElement b,double p) {
        if(a.isJsonArray()){var out=new JsonArray();for(int i=0;i<a.getAsJsonArray().size();i++)out.add(a.getAsJsonArray().get(i).getAsDouble()+(b.getAsJsonArray().get(i).getAsDouble()-a.getAsJsonArray().get(i).getAsDouble())*p);return out;}
        return new JsonPrimitive(a.getAsDouble()+(b.getAsDouble()-a.getAsDouble())*p);
    }
    static JsonElement curve(JsonArray keys,double time,JsonElement first) {
        JsonObject begin=keys.get(0).getAsJsonObject(),end=keys.get(keys.size()-1).getAsJsonObject();
        if(time<=n(begin,"time_ms"))return(first==null?begin.get("value"):first).deepCopy();
        if(time>=n(end,"time_ms"))return end.get("value").deepCopy();
        for(int i=0;i<keys.size()-1;i++) {
            var a=keys.get(i).getAsJsonObject();var b=keys.get(i+1).getAsJsonObject();
            if(time<n(b,"time_ms"))return interpolate(i==0&&first!=null?first:a.get("value"),b.get("value"),ease((time-n(a,"time_ms"))/(n(b,"time_ms")-n(a,"time_ms")),s(a,"easing")));
        }
        return end.get("value").deepCopy();
    }
    static JsonElement track(JsonObject track,double duration,double time,JsonObject entries,boolean first) {
        JsonElement inherited=entries.get(s(track,"id")),value;String mode=track.has("entry")?s(track,"entry"):"absolute";
        if(track.has("keyframes"))value=curve(track.getAsJsonArray("keyframes"),time,mode.equals("from_current")&&first?inherited:null);
        else if(s(track,"type").equals("rotate"))value=new JsonPrimitive(n(track,"phase_deg")+360*n(track,"turns")*time/duration);
        else {double wave=Math.sin(n(track,"phase_deg")*Math.PI/180+2*Math.PI*n(track,"cycles")*time/duration);double[] amp=v(track.get("amplitude"));for(int i=0;i<3;i++)amp[i]=(s(track,"type").equals("scale")?1:0)+amp[i]*wave;value=array(amp);}
        if(mode.equals("relative")&&inherited!=null)value=new JsonPrimitive(value.getAsDouble()+inherited.getAsDouble());
        return value;
    }
    public static double[] transform(JsonObject clip,int element,double[] point,double time,JsonObject entries,boolean first,boolean normal) {
        double[] p=point.clone();double duration=n(clip,"duration_ms");
        for(var raw:clip.getAsJsonArray("transforms")) {
            var t=raw.getAsJsonObject();if(!t.getAsJsonArray("elements").contains(new JsonPrimitive(element)))continue;
            String kind=s(t,"type");boolean adv=t.has("entry")||t.has("keyframes");
            JsonElement value=adv?track(t,duration,moment(clip,time),entries,first&&time>=0&&time<duration):null;
            double[] pivot=normal?new double[3]:v(t.get("pivot"));double phase=n(t,"phase_deg")*Math.PI/180;
            if(kind.equals("rotate")) {
                double angle=adv?value.getAsDouble()*Math.PI/180:phase+2*Math.PI*n(t,"turns")*time/duration;
                double[] q=sub(p,pivot),axis=v(t.get("axis"));double c=Math.cos(angle),sn=Math.sin(angle),dot=axis[0]*q[0]+axis[1]*q[1]+axis[2]*q[2];
                double[] cross={axis[1]*q[2]-axis[2]*q[1],axis[2]*q[0]-axis[0]*q[2],axis[0]*q[1]-axis[1]*q[0]};
                for(int i=0;i<3;i++)p[i]=pivot[i]+q[i]*c+cross[i]*sn+axis[i]*dot*(1-c);
            } else {
                double[] vals;if(adv)vals=v(value);else {vals=v(t.get("amplitude"));double wave=Math.sin(phase+2*Math.PI*n(t,"cycles")*time/duration);for(int i=0;i<3;i++)vals[i]=(kind.equals("scale")?1:0)+vals[i]*wave;}
                if(kind.equals("translate")){if(!normal)p=add(p,vals);}else for(int i=0;i<3;i++)p[i]=pivot[i]+(p[i]-pivot[i])*(normal?1/vals[i]:vals[i]);
            }
        }
        double len=length(p);return normal&&len>0?mul(p,1/len):p;
    }
    public static final class Particle {
        public String emitter,blend,uid;public long birthId;public double age,size,remaining,endSize;
        public double[] position,velocity,gravity,color,endColor;
        Particle copy(){
            var p=new Particle();p.emitter=emitter;p.blend=blend;p.uid=uid;p.birthId=birthId;p.age=age;p.size=size;p.remaining=remaining;p.endSize=endSize;
            p.position=position.clone();p.velocity=velocity.clone();p.gravity=gravity.clone();p.color=color.clone();p.endColor=endColor.clone();return p;
        }
        public JsonObject json() {
            var p=new JsonObject();p.addProperty("emitter",emitter);p.addProperty("birth_id",birthId);p.addProperty("age_ms",age);
            p.add("position",array(position));p.addProperty("size",size);p.add("color",array(color));p.addProperty("blend",blend);
            p.add("_velocity",array(velocity));p.add("_gravity",array(gravity));p.addProperty("_remaining_ms",remaining);
            p.addProperty("_end_size",endSize);p.add("_end_color",array(endColor));p.addProperty("_uid",uid);return p;
        }
    }
    static List<Particle> carried(List<Particle> carry,double time) {
        var out=new ArrayList<Particle>();
        for(var p:carry)if(time>=0&&time<p.remaining) {
            Particle q=p.copy();double t=time/1000,ratio=time/p.remaining;
            q.age+=time;for(int i=0;i<3;i++){q.position[i]+=p.velocity[i]*t+.5*p.gravity[i]*t*t;q.velocity[i]+=p.gravity[i]*t;}
            q.size+=(p.endSize-p.size)*ratio;for(int i=0;i<4;i++)q.color[i]+=(p.endColor[i]-p.color[i])*ratio;
            q.remaining-=time;out.add(q);
        }
        return out;
    }
    public static final class Player {
        public final JsonObject scene;private final LinkedHashMap<String,JsonObject> states=new LinkedHashMap<>();
        public String state,instance;public double time,textureEntry,tailTime;private double unusedAfterFinish;public JsonObject entry=new JsonObject();
        public List<Particle> carry=new ArrayList<>();public boolean prewarm,firstCycle=true,finished,sequenceMode;
        public int sequenceIndex;public double sequenceElapsed;public long generation,cycleBase;
        public Player(JsonObject definition) {
            instance=UUID.randomUUID().toString();
            scene=definition.deepCopy();
            if(scene.has("states"))for(var s:scene.getAsJsonArray("states"))states.put(s.getAsJsonObject().get("id").getAsString(),s.getAsJsonObject());
            else {var c=scene.deepCopy();c.addProperty("id","default");c.add("next",JsonNull.INSTANCE);if(!c.has("texture")){var tx=new JsonObject();tx.addProperty("mode","play");tx.addProperty("speed",1);c.add("texture",tx);}states.put("default",c);}
            state=scene.has("initial_state")?s(scene,"initial_state"):"default";prewarm=b(clip(),"loop");
        }
        private boolean suspended;
        private boolean renderOnly;
        private List<Particle> suspendedTail=new ArrayList<>();
        private double tailEpoch,emissionStart=-1;
        private double absoluteTime(){return cycleBase*n(clip(),"duration_ms")+time;}
        public boolean suspended(){return suspended;}
        /** Hold parts/texture, stop new births, let already-born particles expire. */
        public void suspend(){suspend(true);}
        public void suspend(boolean keepParticles){if(suspended)return;suspendedTail=keepParticles?particles():new ArrayList<>();carry=new ArrayList<>();tailTime=0;suspended=true;}
        /** Resume the held pose; a completed single clip starts another cycle. */
        public void resume(){if(!suspended)return;var surviving=carried(suspendedTail,tailTime);suspended=false;suspendedTail=new ArrayList<>();if(finished){enter(state,false);carry=surviving;}else{suspendedTail=surviving;tailTime=0;tailEpoch=absoluteTime();emissionStart=tailEpoch;generation++;}}
        public JsonObject clip(){return states.get(state);}
        double textureTime(){return textureEntry+time*(clip().getAsJsonObject("texture").has("speed")?n(clip().getAsJsonObject("texture"),"speed"):0);}
        public double[] point(int element,double[] p,boolean normal){double actual=advanced(clip())?time:moment(clip(),time);return transform(clip(),element,p,actual,entry,firstCycle,normal);}
        public int textureFrame(JsonObject animation) {
            var tx=clip().getAsJsonObject("texture");if(s(tx,"mode").equals("hold")&&tx.has("frame"))return tx.get("frame").getAsInt();
            double at=textureTime(),total=0;for(var step:animation.getAsJsonArray("steps"))total+=n(step.getAsJsonObject(),"duration_ms");
            if(b(animation,"loop"))at=mod(at,total);else at=Math.max(0,Math.min(at,total));
            for(var step:animation.getAsJsonArray("steps")){var row=step.getAsJsonObject();if(at<n(row,"duration_ms"))return row.get("frame").getAsInt();at-=n(row,"duration_ms");}
            var steps=animation.getAsJsonArray("steps");return steps.get(steps.size()-1).getAsJsonObject().get("frame").getAsInt();
        }
        public List<Particle> particles() {
            if(suspended)return carried(suspendedTail,tailTime);
            JsonObject clip=clip();double duration=n(clip,"duration_ms");boolean adv=advanced(clip),loop=b(clip,"loop");
            double t=adv&&loop?time:loop?mod(time,duration):Math.min(duration,Math.max(0,time))+tailTime;var out=new ArrayList<Particle>();int ei=0;
            for(var raw:clip.getAsJsonArray("emitters")) {
                var e=raw.getAsJsonObject();int count=e.get("count_per_cycle").getAsInt();double spacing=duration/count,life=n(e,"lifetime_ms");
                long last=(long)Math.floor(t/spacing+1e-10),first=(long)Math.floor((t-life)/spacing)+1;
                for(long birth=first;birth<=last;birth++) {
                    if(!loop&&(birth<0||birth>=count)||adv&&birth<0&&!prewarm)continue;
                    double born=cycleBase*duration+birth*spacing+(loop&&!adv?Math.floor(time/duration)*duration:0);if(emissionStart>=0&&born+1e-8<emissionStart)continue;
                    double age=t-birth*spacing;if(age<0||age>=life)continue;long identity=Math.floorMod(birth,count);
                    long seed=(clip.get("seed").getAsLong()+ei*1000003L+identity*9176L)&0xffffffffL;
                    if(adv){double intensity=curve(e.getAsJsonArray("emission"),loop?mod(birth*spacing,duration):birth*spacing,null).getAsDouble();if(intensity<=0||intensity<1&&random(seed^0x9e3779b9L)>=intensity)continue;}
                    double[] direction=v(e.get("direction")),spread=v(e.get("spread"));for(int i=0;i<3;i++)direction[i]+=(2*random(seed+i*374761393L)-1)*spread[i];
                    double len=length(direction);direction=len>1e-9?mul(direction,1/len):v(e.get("direction"));double[] origin=v(e.get("position"));
                    if(e.has("anchor_element")&&!e.get("anchor_element").isJsonNull()){
                        int element=e.get("anchor_element").getAsInt();double[] end=transform(clip,element,add(origin,direction),birth*spacing,entry,firstCycle,false);
                        origin=transform(clip,element,origin,birth*spacing,entry,firstCycle,false);direction=sub(end,origin);direction=mul(direction,1/length(direction));
                    }
                    Particle p=new Particle();p.emitter=s(e,"id");p.blend=s(e,"blend");p.birthId=identity;p.age=age;p.remaining=life-age;
                    p.uid=instance+":"+generation+":"+ei+":"+(cycleBase*count+birth+(adv?0:(long)Math.floor(time/duration)*count));
                    p.position=new double[3];p.velocity=new double[3];p.gravity=v(e.get("gravity"));double secs=age/1000;
                    for(int i=0;i<3;i++){p.position[i]=origin[i]+direction[i]*n(e,"speed")*secs+.5*p.gravity[i]*secs*secs;p.velocity[i]=direction[i]*n(e,"speed")+p.gravity[i]*secs;}
                    double[] sizes=v(e.get("size"));p.size=sizes[0]+(sizes[1]-sizes[0])*age/life;p.endSize=sizes[1];
                    p.color=v(e.getAsJsonArray("color").get(0));p.endColor=v(e.getAsJsonArray("color").get(1));for(int i=0;i<4;i++)p.color[i]+=(p.endColor[i]-p.color[i])*age/life;
                    out.add(p);
                }
                ei++;
            }
            out.addAll(carried(carry,time+tailTime));out.addAll(carried(suspendedTail,Math.max(0,absoluteTime()-tailEpoch)+tailTime));return out.size()>2048?new ArrayList<>(out.subList(0,2048)):out;
        }
        private void enter(String identity,boolean preserve) {
            if(!states.containsKey(identity))throw new IllegalArgumentException("Unknown scene state: "+identity);
            JsonObject values=new JsonObject();List<Particle> flying=new ArrayList<>();double texture=0;
            if(preserve){double t=moment(clip(),time);for(var raw:clip().getAsJsonArray("transforms")){var track=raw.getAsJsonObject();values.add(s(track,"id"),track(track,n(clip(),"duration_ms"),t,entry,firstCycle&&time<n(clip(),"duration_ms")));}flying=renderOnly?new ArrayList<>():particles();texture=textureTime();}
            state=identity;time=0;tailTime=0;entry=values;carry=flying;textureEntry=texture;prewarm=!preserve&&b(clip(),"loop");firstCycle=true;finished=false;generation++;cycleBase=0;suspended=false;suspendedTail=new ArrayList<>();tailEpoch=0;emissionStart=-1;
        }
        public void select(String identity,boolean preserve){enter(identity,preserve);sequenceMode=false;}
        public boolean event(String event){
            if(!scene.has("transitions"))return false;
            for(var raw:scene.getAsJsonArray("transitions")){var route=raw.getAsJsonObject();if(s(route,"from").equals(state)&&s(route,"event").equals(event)){enter(s(route,"to"),true);sequenceMode=false;return true;}}
            return false;
        }
        public void beginSequence(){if(!scene.has("preview_sequence"))return;sequenceIndex=0;sequenceElapsed=0;enter(s(scene.getAsJsonArray("preview_sequence").get(0).getAsJsonObject(),"state"),false);sequenceMode=true;}
        private void tick(double delta){
            time+=delta;
            double max=carry.stream().mapToDouble(p->p.remaining).max().orElse(0),duration=n(clip(),"duration_ms");
            if(b(clip(),"loop")&&time>=Math.max(duration*(firstCycle?2:1),max)){
                double wrapped=time-mod(time,duration);textureEntry+=wrapped*(clip().getAsJsonObject("texture").has("speed")?n(clip().getAsJsonObject("texture"),"speed"):0);
                cycleBase+=(long)Math.floor(wrapped/duration);time-=wrapped;carry=new ArrayList<>();prewarm=true;firstCycle=false;
            }
        }
        public void advance(double delta){
            if(!Double.isFinite(delta)||delta<0||delta>120000)throw new IllegalArgumentException("delta 0..120000 ms");
            double remaining=delta;int guard=0;unusedAfterFinish=0;
            while(!finished){if(++guard>4096)throw new IllegalStateException("transition budget");
                if(sequenceMode){var sequence=scene.getAsJsonArray("preview_sequence");double limit=n(sequence.get(sequenceIndex).getAsJsonObject(),"duration_ms");double step=Math.min(remaining,Math.max(0,limit-sequenceElapsed));tick(step);sequenceElapsed+=step;remaining-=step;if(sequenceElapsed+1e-9<limit)break;
                    if(sequenceIndex+1<sequence.size())sequenceIndex++;else if(b(scene,"loop"))sequenceIndex=0;else{finished=true;break;}sequenceElapsed=0;enter(s(sequence.get(sequenceIndex).getAsJsonObject(),"state"),true);
                }else if(b(clip(),"loop")){tick(remaining);break;}
                else{double limit=n(clip(),"duration_ms"),step=Math.min(remaining,Math.max(0,limit-time));tick(step);remaining-=step;if(time+1e-9<limit)break;var next=clip().get("next");if(next==null||next.isJsonNull()){finished=true;break;}enter(next.getAsString(),true);}
                if(remaining<=1e-9)break;
            }
            unusedAfterFinish=finished?remaining:0;
        }
        /** Game simulation continues the finite particle tail after the final pose stops. */
        public void simulate(double delta){
            if(!Double.isFinite(delta)||delta<0||delta>120000)throw new IllegalArgumentException("delta 0..120000 ms");
            if(finished||suspended)tailTime=Math.min(120000,tailTime+delta);else{advance(delta);if(finished)tailTime=Math.min(120000,unusedAfterFinish);}
        }
        public JsonObject snapshot(){
            var o=new JsonObject();o.addProperty("state",state);o.addProperty("instance",instance);o.addProperty("time",time);o.addProperty("textureEntry",textureEntry);o.addProperty("tailTime",tailTime);o.add("entry",entry.deepCopy());
            o.add("carry",new Gson().toJsonTree(carry));o.addProperty("prewarm",prewarm);o.addProperty("firstCycle",firstCycle);o.addProperty("finished",finished);
            o.addProperty("sequenceMode",sequenceMode);o.addProperty("sequenceIndex",sequenceIndex);o.addProperty("sequenceElapsed",sequenceElapsed);o.addProperty("generation",generation);o.addProperty("cycleBase",cycleBase);
            o.addProperty("suspended",suspended);o.add("suspendedTail",new Gson().toJsonTree(suspendedTail));o.addProperty("tailEpoch",tailEpoch);o.addProperty("emissionStart",emissionStart);return o;
        }
        public void restore(JsonObject o){
            String st=s(o,"state");if(!states.containsKey(st)||!Double.isFinite(n(o,"time"))||n(o,"time")<0||n(o,"time")>240000||o.getAsJsonArray("carry").size()>2048)throw new IllegalArgumentException("Invalid scene snapshot");
            state=st;instance=s(o,"instance");time=n(o,"time");textureEntry=n(o,"textureEntry");tailTime=n(o,"tailTime");entry=o.getAsJsonObject("entry").deepCopy();carry=new ArrayList<>();
            if(instance.length()>80||!Double.isFinite(tailTime)||tailTime<0||tailTime>120000)throw new IllegalArgumentException("Invalid scene identity/tail");
            for(var p:o.getAsJsonArray("carry"))carry.add(new Gson().fromJson(p,Particle.class));
            prewarm=b(o,"prewarm");firstCycle=b(o,"firstCycle");finished=b(o,"finished");sequenceMode=b(o,"sequenceMode");sequenceIndex=o.get("sequenceIndex").getAsInt();sequenceElapsed=n(o,"sequenceElapsed");generation=o.get("generation").getAsLong();cycleBase=o.get("cycleBase").getAsLong();
            suspended=o.has("suspended")&&b(o,"suspended");suspendedTail=new ArrayList<>();tailEpoch=o.has("tailEpoch")?n(o,"tailEpoch"):0;emissionStart=o.has("emissionStart")?n(o,"emissionStart"):-1;
            if(!Double.isFinite(tailEpoch)||tailEpoch<0||!Double.isFinite(emissionStart)||emissionStart< -1||o.has("suspendedTail")&&o.getAsJsonArray("suspendedTail").size()>2048)throw new IllegalArgumentException("Invalid suspended snapshot");
            if(o.has("suspendedTail"))for(var p:o.getAsJsonArray("suspendedTail"))suspendedTail.add(new Gson().fromJson(p,Particle.class));
        }
        private Player(Player source){this(source,false);}
        private Player(Player source,boolean render){
            scene=source.scene;states.putAll(source.states);state=source.state;instance=source.instance;time=source.time;textureEntry=source.textureEntry;tailTime=source.tailTime;entry=source.entry.deepCopy();
            if(!render)for(var p:source.carry)carry.add(p.copy());prewarm=source.prewarm;firstCycle=source.firstCycle;finished=source.finished;
            sequenceMode=source.sequenceMode;sequenceIndex=source.sequenceIndex;sequenceElapsed=source.sequenceElapsed;generation=source.generation;cycleBase=source.cycleBase;
            suspended=source.suspended;if(!render)for(var p:source.suspendedTail)suspendedTail.add(p.copy());tailEpoch=source.tailEpoch;emissionStart=source.emissionStart;renderOnly=render;
        }
        public Player copy(){return new Player(this);}
        public Player renderCopy(){return new Player(this,true);}
    }
}
