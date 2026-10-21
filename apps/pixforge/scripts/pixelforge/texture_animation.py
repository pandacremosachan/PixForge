"""Read-only, lossless timed animation review from an explicit project-derived plan.

Does not parse .mcmeta, .pxo, .bbmodel or engine metadata; never invents runtime timing.
"""

import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import sys

from PIL import Image

from .texture_review import comparison_image, emit_report, image_comparison, image_geometry, load_png


SCHEMA = "pixelforge.animation-review/v1"


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def duration(value):
    # Pixelorama-style FPS/multipliers can produce fractional milliseconds.
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("duration_ms must be a positive finite number")
    return value


def load_plan(path):
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError(f"plan schema must be {SCHEMA}")
    allowed = {"schema", "image", "frame_size", "rectangles", "steps", "loop", "interpolation", "provenance"}
    if set(plan) - allowed:
        raise ValueError(f"unknown plan fields: {sorted(set(plan) - allowed)}")
    if not isinstance(plan.get("image"), str) or not plan["image"]:
        raise ValueError("plan image must be a PNG path relative to the plan, or an absolute path")
    size = plan.get("frame_size")
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError("frame_size must be [width, height]")
    width, height = [integer(value, "frame_size", 1) for value in size]
    if type(plan.get("loop")) is not bool:
        raise ValueError("loop must be explicitly true or false")
    if plan.get("interpolation") != "none":
        raise ValueError("only explicit interpolation 'none' is supported; interpolated engine playback needs a project renderer")
    if "provenance" in plan and not isinstance(plan["provenance"], str):
        raise ValueError("provenance must be text identifying the project metadata/adapter")
    image_path = (path.parent / plan["image"]).resolve()
    image = load_png(image_path)
    rectangles = plan.get("rectangles")
    if rectangles is None:
        if image.width % width or image.height % height:
            raise ValueError("frame_size must divide both source dimensions for a row-major grid; provide explicit rectangles for an atlas")
        rectangles = [[x, y, width, height] for y in range(0, image.height, height) for x in range(0, image.width, width)]
    if not isinstance(rectangles, list) or not rectangles:
        raise ValueError("rectangles must be a nonempty list of [x, y, width, height]")
    frames = []
    for rect in rectangles:
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError("each rectangle must be [x, y, width, height]")
        x, y, rw, rh = [integer(value, "rectangle") for value in rect]
        if [rw, rh] != size or x + rw > image.width or y + rh > image.height:
            raise ValueError(f"rectangle {rect} must match frame_size and fit the source PNG")
        frames.append(image.crop((x, y, x + rw, y + rh)))
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a nonempty array of {frame, duration_ms}")
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"frame", "duration_ms"}:
            raise ValueError("each step must contain exactly frame and duration_ms")
        if integer(step["frame"], "frame") >= len(frames):
            raise ValueError(f"frame {step['frame']} does not exist")
        duration(step["duration_ms"])
    if not math.isfinite(sum(step["duration_ms"] for step in steps)):
        raise ValueError("total duration must be finite")
    return plan, image_path, rectangles, frames


def frame_at(steps, elapsed_ms, loop):
    """Timing contract also used in the standalone player: durations are half-open."""
    total = sum(step["duration_ms"] for step in steps)
    if not loop and elapsed_ms >= total:
        return len(steps) - 1
    elapsed_ms = elapsed_ms % total if loop else max(0, elapsed_ms)
    for index, step in enumerate(steps):
        if elapsed_ms < step["duration_ms"]:
            return index
        elapsed_ms -= step["duration_ms"]
    return len(steps) - 1


def build_report(plan, image_path, rectangles, frames):
    starts, cursor = [], 0
    for step in plan["steps"]:
        starts.append(cursor)
        cursor += step["duration_ms"]
    transitions = []
    prepared_frames = [comparison_image(frame) for frame in frames]
    comparisons = {}
    count = len(plan["steps"])
    for i in range(count if plan["loop"] else count - 1):
        a, b = plan["steps"][i]["frame"], plan["steps"][(i + 1) % count]["frame"]
        pair = (min(a, b), max(a, b))
        if pair not in comparisons:
            comparisons[pair] = image_comparison(prepared_frames[a], prepared_frames[b])
        transitions.append({"from_step": i, "to_step": (i + 1) % count, "from_frame": a, "to_frame": b,
                            "loop_boundary": i == count - 1,
                            "pixels": comparisons[pair].copy()})
    return {"schema": SCHEMA, "input": str(image_path), "provenance": plan.get("provenance"),
            "frame_size": plan["frame_size"], "rectangles": rectangles,
            "frames": [{"frame": i, "rgba_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                        "geometry": image_geometry(frame, 0)}
                       for i, frame in enumerate(frames)],
            "steps": [{**step, "start_ms": start, "end_ms": start + step["duration_ms"]}
                      for step, start in zip(plan["steps"], starts)],
            "total_duration_ms": cursor, "loop": plan["loop"], "interpolation": "none",
            "unused_frames": sorted(set(range(len(frames))) - {step["frame"] for step in plan["steps"]}),
            "transitions": transitions, "plan_valid": True, "motion_accepted": None,
            "note": "Validates and plays the declared plan only. Direction, rhythm, baseline, brightness and loop intent require visual review. No runtime metadata or in-game validation is inferred."}


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PixForge 动画验收</title>
<style>
body{font:16px system-ui;margin:24px;background:#131c28;color:#e0e9f4;max-width:1100px}
button,select,input{font:inherit;margin:0;padding:6px}button{cursor:pointer}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.controls label{display:inline-flex;align-items:center;gap:6px}
.panels{display:flex;gap:24px;flex-wrap:wrap;margin:20px 0}figure{margin:0}
canvas{display:block;image-rendering:pixelated;margin-top:8px;background:#283244}
pre{white-space:pre-wrap}.gallery{display:flex;gap:16px;flex-wrap:wrap;margin-top:20px}
.checker{background:repeating-conic-gradient(#283244 0 25%,#354154 0 50%) 0/16px 16px}
.dark{background:#10151b}.light{background:#f1f3f5}
</style>
<h1>PixForge 动画验收</h1>
<p>按声明顺序和毫秒时长播放。逐帧 PNG 保留 RGBA；洋葱皮和 3×3 是辅助观察。请核对流向、节奏、结构和循环衔接。</p>
<div class="controls"><button id="play">暂停</button><button id="prev">上一播放步</button><button id="next">下一播放步</button><button id="reset">重播</button>
<label>背景 <select id="bg"><option value="checker">棋盘</option><option value="light">浅色</option><option value="dark">深色</option></select></label>
<label><input id="onion" type="checkbox">洋葱皮（前蓝 / 后红）</label>
<label><input id="tile" type="checkbox">3×3</label><label>速度 <select id="speed"><option value="1">1×</option><option value="0.25">0.25×</option><option value="2">2×</option></select></label></div>
<p id="status"></p><div class="panels"><figure>原尺寸<canvas id="native"></canvas></figure><figure>最近邻放大<canvas id="zoom"></canvas></figure></div>
<details><summary>播放定义与检查范围</summary><pre id="info"></pre></details>
<h2>全部源帧</h2><p>包括播放定义未引用的帧；帧坐标保持原样。</p><div id="gallery" class="gallery"></div>
<script id="plan" type="application/json">__PAYLOAD__</script>
<script>
'use strict';
const p=JSON.parse(document.getElementById('plan').textContent);
const $=id=>document.getElementById(id), steps=p.steps, total=p.total_duration_ms;
let elapsed=0, running=true, last=null, current=0, frames=[];const ghostCache=new WeakMap();
function stepAt(ms){if(!p.loop&&ms>=total)return steps.length-1;let t=p.loop?((ms%total)+total)%total:Math.max(0,ms);for(let i=0;i<steps.length;i++){if(t<steps[i].duration_ms)return i;t-=steps[i].duration_ms;}return steps.length-1;}
function neighbor(i,d){const j=i+d;return p.loop?((j%steps.length)+steps.length)%steps.length:(j<0||j>=steps.length?null:j);}
function ghost(image,color){let cache=ghostCache.get(image);if(!cache){cache=new Map();ghostCache.set(image,cache);}if(cache.has(color))return cache.get(color);const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const ctx=c.getContext('2d');ctx.drawImage(image,0,0);ctx.globalCompositeOperation='source-in';ctx.fillStyle=color;ctx.fillRect(0,0,c.width,c.height);cache.set(color,c);return c;}
function paint(canvas,scale,index){const mult=$('tile').checked?3:1,w=p.frame_size[0],h=p.frame_size[1];if(canvas.width!==w*mult)canvas.width=w*mult;if(canvas.height!==h*mult)canvas.height=h*mult;canvas.style.width=`${w*scale*mult}px`;canvas.style.height=`${h*scale*mult}px`;canvas.className=$('bg').value;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=false;
for(let y=0;y<mult;y++)for(let x=0;x<mult;x++){const dx=x*w,dy=y*h;if($('onion').checked){for(const [d,c] of [[-1,'#4488ff'],[1,'#ff5555']]){const n=neighbor(index,d);if(n!==null){ctx.globalAlpha=0.35;ctx.drawImage(ghost(frames[steps[n].frame],c),dx,dy,w,h);}}}ctx.globalAlpha=1;ctx.drawImage(frames[steps[index].frame],dx,dy,w,h);}}
function render(){if(!frames.length)return;current=stepAt(elapsed);paint($('native'),1,current);paint($('zoom'),p.scale,current);$('status').textContent=`播放步 ${current+1}/${steps.length} · 源帧 ${steps[current].frame} · 本步 ${steps[current].duration_ms} ms · 周期 ${total} ms · ${p.loop?'循环':'单次'}`;}
function jump(i){running=false;last=null;$('play').textContent='播放';elapsed=steps[i].start_ms;render();}
$('play').onclick=()=>{if(!p.loop&&elapsed>=total)elapsed=0;running=!running;last=performance.now();$('play').textContent=running?'暂停':'播放';};
$('reset').onclick=()=>{elapsed=0;running=true;last=performance.now();$('play').textContent='暂停';render();};
$('prev').onclick=()=>jump(neighbor(current,-1)??0);$('next').onclick=()=>jump(neighbor(current,1)??(steps.length-1));
for(const id of ['bg','onion','tile'])$(id).onchange=render;$('speed').onchange=()=>{last=performance.now();};
document.addEventListener('visibilitychange',()=>{last=performance.now();});
function tick(now){if(last!==null&&running&&document.visibilityState!=='hidden'){elapsed+=(now-last)*Number($('speed').value);if(p.loop)elapsed%=total;else if(elapsed>=total){elapsed=total;running=false;$('play').textContent='播放';}if(current!==stepAt(elapsed))render();}last=now;requestAnimationFrame(tick);}
Promise.all(p.images.map(url=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;im.src=url;}))).then(images=>{frames=images;for(let i=0;i<frames.length;i++){const figure=document.createElement('figure'),c=document.createElement('canvas');figure.textContent=`源帧 ${i}${p.unused_frames.includes(i)?'（未播放）':''}`;c.width=p.frame_size[0];c.height=p.frame_size[1];c.style.width=`${c.width*p.scale}px`;c.style.height=`${c.height*p.scale}px`;c.className='checker';const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(frames[i],0,0,c.width,c.height);figure.append(c);$('gallery').append(figure);}const info={...p};delete info.images;$('info').textContent=JSON.stringify(info,null,2);last=performance.now();render();requestAnimationFrame(tick);}).catch(()=>{$('status').textContent='帧解码失败，不能进行播放验收。';});
</script></html>
'''


def player_html(report, frames, scale=6):
    if type(scale) is not int or not 1 <= scale <= 16:
        raise ValueError("player scale must be an integer in 1..16")
    urls = []
    for frame in frames:
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        urls.append("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"))
    payload = json.dumps({**report, "images": urls, "scale": scale}, ensure_ascii=False).replace("<", "\\u003c")
    return HTML.replace("__PAYLOAD__", payload)


def save_player(report, frames, path, scale):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(player_html(report, frames, scale), encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--html", type=Path, required=True, help="standalone, lossless PNG player; never the production texture")
    parser.add_argument("--scale", type=int, choices=range(1, 17), default=6, metavar="1..16")
    parser.add_argument("--report", type=Path, help="save full JSON and print compact playback metadata; all frames/steps remain checked")
    args = parser.parse_args(argv)
    try:
        plan, image_path, rectangles, frames = load_plan(args.plan)
        if args.html.resolve() in (args.plan.resolve(), image_path):
            raise ValueError("HTML output must not overwrite the plan or source PNG")
        if args.html.suffix.lower() != ".html":
            raise ValueError("player output must use .html")
        if args.report and (args.report.suffix.lower() != ".json" or args.report.resolve() in (args.plan.resolve(), image_path, args.html.resolve())):
            raise ValueError("report must use .json and not overwrite any input or player output")
        report = build_report(plan, image_path, rectangles, frames)
        save_player(report, frames, args.html, args.scale)
        report["html"] = str(args.html.resolve())
        emit_report(report, args.report, {"input": report["input"], "plan_valid": True, "motion_accepted": None,
                    "frame_count": len(frames), "playback_steps": len(plan["steps"]), "total_duration_ms": report["total_duration_ms"],
                    "loop": report["loop"], "unused_frame_count": len(report["unused_frames"]), "html": report["html"]})
        return 0
    except (OSError, ValueError, OverflowError) as error:
        print(f"texture_animation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
