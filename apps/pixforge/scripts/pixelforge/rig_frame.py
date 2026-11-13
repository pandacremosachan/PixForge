"""Offscreen frames use the same EXE's skeleton evaluator and rasterizer as the viewport."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from PIL import Image
from .rig_studio import inspect,resolve

def render_rig(document,atlas,options,sample=False):
    model=document.shapes["model"];rig=model["player_rig"];clips=rig["clips"];clip=options.get("scene_state")
    if clip:
        clip=resolve(clips,clip)
    elif clips:clip=next((a for a in clips if a["name"]=="idle"),clips[0])
    tracks=inspect(model,clip["uuid"],native=True)["tracks"] if clip else {}
    texture=options.get("rig_texture")
    index=rig["textures"].index(resolve(rig["textures"],texture)) if texture else -1
    size=options.get("size",400)
    if not 128<=size<=800:raise ValueError("预览尺寸为 128..800")
    # The native sampler only reads bind transforms; the renderer also needs faces and UVs.
    bone_fields=("uuid","name","parent_id","pivot","rotation","visible")
    geometry={"player_rig":{"key_axes":rig.get("key_axes"),"bones":[{k:b[k] for k in bone_fields if k in b} for b in rig["bones"]]}}
    if sample:
        cube_fields=("uuid","name","bone","pivot","turn","visible")
        geometry["elements"]=[{k:e[k] for k in cube_fields if k in e} for e in model["elements"]]
    else:
        geometry.update(elements=model["elements"],texture_size=model["texture_size"])
        geometry["player_rig"]["textures"]=rig["textures"]
    job={"model":geometry,"tracks":tracks,"loop":bool(clip and clip["loop"]=="loop"),
         "time_ms":options.get("time_ms",0),"size":size,"yaw":options.get("yaw",35),"pitch":options.get("pitch",30),
         "texture":index,"show_model":options.get("show_model",True),"clip":clip["name"] if clip else ""}
    if not sample:
        job["shapes"]={k:document.shapes[k] for k in ("base","collision","selection")}
        job["overlays"]=options.get("overlays") or []
        job["atlas"]={"w":atlas.width,"h":atlas.height,"data":base64.b64encode(atlas.tobytes()).decode()}
    with tempfile.TemporaryDirectory(dir=document.runtime) as folder:
        src=Path(folder)/"frame.json";dst=Path(folder)/("pose.json" if sample else "frame.png");src.write_text(json.dumps(job,ensure_ascii=False),encoding="utf-8")
        subprocess.run([os.environ["PIXFORGE_NATIVE_EXE"],"--sample-player-frame" if sample else "--render-player-frame",str(src),str(dst)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if sample:return json.loads(dst.read_bytes())
        with Image.open(dst) as im:return im.convert("RGBA")

