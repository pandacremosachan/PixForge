"""Whole-scene resource census and separately labelled, observed reference-view costs."""
from collections import Counter
from copy import deepcopy
import base64
import math
import time
from .document import StudioError
from .minecraft_resources import digest, encode
from .minecraft_animation import expanded

CAPABILITY = "minecraft-regression/v1"


def options(raw=None):
    if raw is None:raw={}
    if not isinstance(raw,dict) or set(raw)-{"instance_counts","sample_times_ms","coverage_view","settings"}:raise StudioError("性能选项使用 instance_counts/sample_times_ms/coverage_view/settings")
    counts=raw.get("instance_counts",[1,16,64,256]);times=raw.get("sample_times_ms",[0,250,500,1000,2000,4000])
    if not isinstance(counts,list) or not 1<=len(counts)<=16 or any(type(n) is not int or not 1<=n<=4096 for n in counts):raise StudioError("整场景实例数使用 1..4096 的整数，至多 16 档")
    if not isinstance(times,list) or not 1<=len(times)<=32 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=120000 for n in times):raise StudioError("粒子采样时间使用 0..120000 ms，至多 32 个")
    if raw.get("coverage_view") is not None and not isinstance(raw["coverage_view"],dict):raise StudioError("coverage_view 须为现有 Minecraft 预览选项对象")
    return {"instance_counts":sorted(set(counts)),"sample_times_ms":times,"coverage_view":deepcopy(raw.get("coverage_view")),"settings":raw.get("settings")}


def inspect(document,raw=None):
    opts=options(raw);plan=document.animation;image=document.canvas.composite()
    frames=[image.crop((x,y,x+w,y+h)) for x,y,w,h in plan["rectangles"]]
    frame_hashes={digest(f.tobytes()) for f in frames};pixel_count=sum(f.width*f.height for f in frames)
    alpha=Counter(a for f in frames for a in f.getchannel("A").getdata())
    mip_pixels=0
    for f in frames:
        w,h=f.size
        for _ in range(5):
            mip_pixels+=w*h
            if min(w,h)<2:break
            w//=2;h//=2
    model=document.shapes["model"] or {"elements":[]};elements=model.get("elements",[])
    face_count=sum(len(e.get("faces",{})) for e in elements)
    scene=document.scene_animation;particle_samples=[];dynamic=set();emitters=set()
    if scene:
        from .scene_program import all_entries
        from .scene_animation import sample
        dynamic={element for track in all_entries(scene,"transforms") for element in track["elements"]}
        emitters={e["id"] for e in all_entries(scene,"emitters")}
        states=[s["id"] for s in scene["states"]] if "states" in scene else [None]
        if len(states)*len(opts["sample_times_ms"])>512:raise StudioError("状态 × 时间采样超过 512，请减少采样时间")
        for state in states:
            for moment in opts["sample_times_ms"]:
                result=sample(scene,document.shapes["model"],moment,state=state)
                particle_samples.append({"state":state,"time_ms":moment,"live":len(result["particles"]),"blends":dict(Counter(p["blend"] for p in result["particles"]))})
    peak=max((r["live"] for r in particle_samples),default=0)
    material_layers=Counter()
    config=opts["settings"] if opts["settings"] is not None else document.minecraft_project
    runtime=(config or {}).get("runtime") or {}
    if runtime.get("scene"):material_layers[runtime["scene"]["render_type"]]+=1
    runtime_frames,runtime_animation=expanded(document)
    report={"schema":"pixforge.minecraft-performance/v1","document_id":document.document_id,"revision":document.revision,"content_digest":document.art_digest(),
        "textures":{"source_atlas_pixels":image.width*image.height,"declared_frame_pixels":pixel_count,"frames":len(frames),"unique_rgba_frames":len(frame_hashes),
            "referenced_frames":len({s["frame"] for s in plan["steps"]}),"steps":len(plan["steps"]),"rgba_bytes":pixel_count*4,"mipmap_rgba_bytes_up_to_level4":mip_pixels*4,
            "zero_alpha_pixels":alpha[0],"partial_alpha_pixels":sum(v for k,v in alpha.items() if 0<k<255),"opaque_pixels":alpha[255],
            "instance_texture_frames":len(runtime_frames),"instance_texture_pixels":sum(f.width*f.height for f in runtime_frames)},
        "geometry":{"model_elements":len(elements),"authored_faces":face_count,"authored_triangles":face_count*2,"dynamic_parts":len(dynamic),"emitters":len(emitters),"material_layers":dict(material_layers)},
        "particle_samples":particle_samples,"sampled_peak_particles_per_instance":peak,
        "scenarios":[{"instances":n,"part_submissions_before_game_culling":len(elements)*n,"authored_triangles_before_game_culling":face_count*2*n,
            "dynamic_parts":len(dynamic)*n,"sampled_live_particles":peak*n,
            "texture_memory_shared_between_instances":True,"projected_game_fps":None} for n in opts["instance_counts"]],
        "limits":{"particle_peak":"observed at declared states/times; not a proven continuous upper bound","geometry":"authored submissions, before game visibility/batching; not GPU draw calls",
            "texture_memory":"raw RGBA estimates without game atlas padding/driver compression","costs":"reference renderer timings and game measurements remain separate"},"in_game_validated":False}
    output={"report":report}
    if document.material_data is not None:
        maps=len(document.material_data['maps']);texture=report['textures']
        texture['material_data']={'profile':document.material_data['profile'],'maps':list(document.material_data['maps']),
            'source_atlas_pixels':image.width*image.height*maps,'declared_frame_pixels':pixel_count*maps,'rgba_bytes':pixel_count*4*maps,
            'mipmap_rgba_bytes_up_to_level4':mip_pixels*4*maps,
            'instance_texture_pixels':sum(f.width*f.height for f in runtime_frames)*maps,'alpha_is_opacity':False}
        texture['all_maps_mipmap_rgba_bytes_up_to_level4']=mip_pixels*4*(1+maps)
        texture['all_maps_instance_texture_pixels']=sum(f.width*f.height for f in runtime_frames)*(1+maps)
    if opts["coverage_view"] is not None:
        from .minecraft_view import build_scene
        from .minecraft_raster import render_scene
        from .image_bytes import png
        view={**opts["coverage_view"]};view["size"]=min(512,view.get("size",256))
        start=time.perf_counter();bundle=build_scene(document,settings=opts["settings"],view=view);image,metrics=render_scene(bundle,measure_coverage=True)
        report["reference_view"]={"scene_digest":bundle["scene_digest"],"viewport":[image.width,image.height],"metrics":metrics,"python_wall_ms":(time.perf_counter()-start)*1000,
            "scope":"one reference viewport; this timing is not game-side CPU or GPU performance"}
        output["image"]=base64.b64encode(png(image)).decode("ascii")
    report["report_digest"]=digest(encode(report));return output
