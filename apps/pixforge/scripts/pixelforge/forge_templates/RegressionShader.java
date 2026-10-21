package @PACKAGE@;

import com.google.gson.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.Supplier;
import java.lang.reflect.*;

/** Optional read-only shader-loader observation. Missing APIs remain unknown. */
public final class RegressionShader {
    private RegressionShader(){}
    private static Supplier<JsonObject> projectObserver;
    /** A consuming shader adapter may provide observed enabled/name/loader/loader_version. */
    public static void registerObserver(Supplier<JsonObject> observer){projectObserver=observer;}
    private static Object invoke(Class<?> type,Object owner,String name)throws ReflectiveOperationException{return type.getMethod(name).invoke(owner);}
    private static Object field(Class<?> type,String name)throws ReflectiveOperationException{var f=type.getDeclaredField(name);if(!f.trySetAccessible())throw new IllegalAccessException(name);return f.get(null);}
    private static String text(Object value){if(value instanceof Optional<?> o)return o.map(Object::toString).orElse("");return value==null?"":value.toString();}
    private static String sha(byte[] raw)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}
    private static JsonObject loader(Map<String,String> mods){
        var out=new JsonObject();out.addProperty("known",false);out.addProperty("enabled",false);
        if(projectObserver!=null){try{var observation=projectObserver.get();if(observation!=null&&observation.toString().length()<=8192){out=observation.deepCopy();out.addProperty("source","registered project shader adapter");boolean valid=out.has("enabled")&&out.get("enabled").isJsonPrimitive()&&out.getAsJsonPrimitive("enabled").isBoolean();for(String key:new String[]{"name","loader","loader_version"})valid&=out.has(key)&&out.get(key).isJsonPrimitive()&&out.getAsJsonPrimitive(key).isString()&&!out.get(key).getAsString().isBlank();out.addProperty("known",valid);return out;}}catch(RuntimeException error){out.addProperty("error",error.getClass().getSimpleName());}return out;}
        try{
            var type=Class.forName("net.optifine.shaders.Shaders");Object enabled;
            try{enabled=invoke(type,null,"isShaderPackLoaded");}catch(ReflectiveOperationException error){enabled=field(type,"shaderPackLoaded");}
            String name;try{name=text(invoke(type,null,"getShaderPackName"));}catch(ReflectiveOperationException error){var pack=invoke(type,null,"getShaderPack");var method=pack.getClass().getMethod("getName");method.trySetAccessible();name=text(method.invoke(pack));}
            String version="unknown";for(String config:new String[]{"net.optifine.Config","net.minecraft.src.Config"})try{version=text(invoke(Class.forName(config),null,"getVersion"));break;}catch(ReflectiveOperationException|LinkageError ignored){}
            out.addProperty("known",enabled instanceof Boolean);out.addProperty("enabled",Boolean.TRUE.equals(enabled));out.addProperty("name",name);out.addProperty("loader","optifine");out.addProperty("loader_version",version.replaceFirst("^OptiFine_",""));out.addProperty("source","observed OptiFine shader API");return out;
        }catch(ReflectiveOperationException|LinkageError|RuntimeException ignored){}
        for(String prefix:new String[]{"net.irisshaders.iris","net.coderbot.iris"})try{
            var api=Class.forName(prefix+".api.v0.IrisApi");var instance=invoke(api,null,"getInstance");var enabled=invoke(api,instance,"isShaderPackInUse");var iris=Class.forName(prefix+".Iris");String name;
            try{name=text(invoke(iris,null,"getCurrentPackName"));}catch(ReflectiveOperationException error){var config=invoke(iris,null,"getIrisConfig");name=text(invoke(config.getClass(),config,"getShaderPackName"));}
            String id=mods.containsKey("oculus")?"oculus":"iris";out.addProperty("known",enabled instanceof Boolean);out.addProperty("enabled",Boolean.TRUE.equals(enabled));out.addProperty("name",name);out.addProperty("loader",id);out.addProperty("loader_version",mods.getOrDefault(id,"unknown"));out.addProperty("source","observed Iris-compatible shader API");return out;
        }catch(ReflectiveOperationException|LinkageError|RuntimeException ignored){}
        out.addProperty("source","no supported shader API observed; register an actual project adapter");return out;
    }
    private static String packHash(Path path)throws Exception{
        if(Files.isRegularFile(path)){if(Files.size(path)>512L*1024*1024)throw new IllegalArgumentException("Shader ZIP exceeds 512 MiB");return sha(Files.readAllBytes(path));}
        if(!Files.isDirectory(path))throw new IllegalArgumentException("Active shader source does not exist");
        var root=path.toRealPath();var rows=new ArrayList<Path>();try(var walk=Files.walk(root)){walk.filter(Files::isRegularFile).forEach(rows::add);}
        if(rows.size()>8192)throw new IllegalArgumentException("Shader directory exceeds 8192 files");
        rows.sort((a,b)->Arrays.compareUnsigned(root.relativize(a).toString().replace('\\','/').getBytes(StandardCharsets.UTF_8),root.relativize(b).toString().replace('\\','/').getBytes(StandardCharsets.UTF_8)));
        var hash=MessageDigest.getInstance("SHA-256");long total=0;
        for(var file:rows){if(!file.toRealPath().startsWith(root)||Files.size(file)>32L*1024*1024||(total+=Files.size(file))>128L*1024*1024)throw new IllegalArgumentException("Shader directory budget/path");String name=root.relativize(file).toString().replace('\\','/');hash.update(name.getBytes(StandardCharsets.UTF_8));hash.update((byte)0);hash.update(sha(Files.readAllBytes(file)).getBytes(StandardCharsets.UTF_8));hash.update((byte)'\n');}
        return HexFormat.of().formatHex(hash.digest());
    }
    public static JsonObject observe(Path gameDirectory,JsonObject contract,Map<String,String> mods){
        var out=loader(mods);out.add("expected",contract.deepCopy());out.addProperty("observation_method","shader-loader API plus source and option files");
        try{
            if(!out.get("known").getAsBoolean()||!out.get("enabled").getAsBoolean())return out;
            String name=out.get("name").getAsString();if(name.isBlank()||name.length()>240||name.contains("/")||name.contains("\\")||name.equals(".")||name.equals(".."))throw new IllegalArgumentException("Invalid active shader name");
            var root=gameDirectory.toAbsolutePath().normalize();var packs=root.resolve("shaderpacks").toRealPath();var path=packs.resolve(name).normalize();if(!path.startsWith(packs)||!path.toRealPath().startsWith(packs))throw new IllegalArgumentException("Shader source outside shaderpacks");out.addProperty("sha256",packHash(path));
            var settings=new TreeMap<String,String>();var properties=new Properties();for(String relative:new String[]{"optionsshaders.txt","config/oculus.properties","config/iris.properties","shaderpacks/"+name+".txt"}){var file=root.resolve(relative);if(Files.isRegularFile(file)){if(!file.toRealPath().startsWith(root.toRealPath())||Files.size(file)>65536)throw new IllegalArgumentException("Shader option file budget/path");byte[] raw=Files.readAllBytes(file);settings.put(relative,sha(raw));try(var reader=new java.io.StringReader(new String(raw,StandardCharsets.UTF_8))){properties.load(reader);}}}
            var hashes=new JsonObject();settings.forEach(hashes::addProperty);out.add("settings_files",hashes);
            var actual=new JsonObject();var target=contract.has("target")&&!contract.get("target").isJsonNull()?contract.getAsJsonObject("target"):new JsonObject();var options=target.has("options")?target.getAsJsonObject("options"):new JsonObject();for(var entry:options.entrySet())if(properties.containsKey(entry.getKey()))actual.addProperty(entry.getKey(),properties.getProperty(entry.getKey()));out.add("expected_options_observed",actual);
        }catch(Exception|LinkageError error){out.addProperty("known",false);out.addProperty("error",error.getClass().getSimpleName()+": "+error.getMessage());}
        return out;
    }
}
