"""Generate opt-in game fixtures and compare actual capture directories, never launch a game."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from .document import StudioError
from .minecraft_resources import encode, digest


def fixture_files(data):
    runtime=data["configuration"]
    blocks=[runtime["scene"]["block"]] if runtime["scene"] else []
    plan={"schema":"pixforge.game-regression-plan/v1","minecraft":"1.20.1","forge":runtime["forge_version"],
        "module_id":data["module_id"],"block_ids":blocks,"instance_counts":[1,16,64,256],
        "views":["near","far","north","east","south","west","night"],
        "warmup_frames":60,"sample_frames":120,"commands":{"place":"/pixforge_fixture place <block-id> <x y z> <count>","states":"/pixforge_fixture states <x y z> <count> <match|state_split|rotations|stopped|active|freeze|resume>","view":"/pixforge_fixture view <x y z> <count> <case>","capture":"/pixforge_capture <case-label> 120"},
        "required_manual_cases":["light and dark neutral background","chunk-edge unload/reload","join after activation","start/stop and particle tail","F3+T resource reload, inspect latest.log"],
        "auto_launch":False,"auto_place":False,"in_game_validated":False}
    guide="""# Forge 1.20.1 game regression fixture

Build and load this explicit example with your existing Java 17 / Forge environment.
No game has been launched by PixForge. Loading the mod registers commands only.
The operator's `place` command requires a loaded empty volume: it checks every cell
before placing a neutral floor and 1..256 generated blocks. Use a disposable test
world. `view` teleports the issuing player and selects day/night; it changes that
world only when explicitly invoked. The command does not erase fixtures afterward.

Run separate 1, 16, 64 and 256 instance fixtures at nonoverlapping origins. Repeat
near/far and the four compass views, day/night, light/dark neutral backgrounds,
chunk boundary views. The fixture assigns alternating active states and four
rotations. Use its `states` command for matching / split state / rotation cases. `freeze` holds all
fixture visual clocks at their current phase; wait for flying particles to expire
before fixed-image acceptance, and `resume` restores playback. Use active trials
separately for frame/CPU timing. Use the project's real server state for production acceptance. Test start/stop, particle
tail, unload/reload and late join independently.

After the view has settled, run `/pixforge_capture <case-label> 120`. Keep camera,
window, render distance, FPS limit/vsync, graphics, particles, mips and gamma fixed.
The client warms 60 frames, records real frame intervals and CPU event/BER time,
visible instances and submitted parts, then writes a real framebuffer PNG,
capture.json and a bounded latest.log tail under gameDirectory/pixforge-regression.
GPU timestamps are not measured. Frame intervals include pacing and background
load; repeat trials. Never compare editor CPU/GPU timing with these measurements.

F3+T reloads resources. Inspect reload errors and the recorded generation/hash.
Use the software's `minecraft-regression-compare` with baseline/candidate capture
directories for fixed-camera pixel and timing deltas. Camera/options, modules,
loaded block states and animation phases must match before a visual pass can be
reported. Animated phases/particles can differ between frame-count trials; capture
matching held states or a paused deterministic phase for image acceptance.
Set explicit pixel/timing budgets for the project. A successful source build or an
offline reference preview does not complete these game-side acceptance cases.
"""
    if data.get('material_contract'):
        plan['material_contract']=data['material_contract']
        guide+='''\n## LabPBR target acceptance\n\nThis example has separate LabPBR data textures. Select the exact shader ZIP and\nloader version recorded in its material contract. The capture observes supported\nOptiFine or Iris-compatible APIs, active shader-pack bytes and option-file hashes.\nMissing APIs, a disabled pack, a different pack hash/version or unknown expected\noptions block a PBR comparison. Other loaders may register an actual observer with\n`RegressionShader.registerObserver`; return enabled, name, loader and loader_version\nfrom that loader's real runtime API. A declaration is never an observed shader.\n\nCheck normal direction, roughness/F0, AO and emission in held views independently.\nTest height/POM, porosity, SSS or predefined metals only when the selected pack\nexplicitly supports them. Compare the exact same pack/settings between captures.\nResource/PBR bytes may change between baseline and candidate; pack identity and\nsettings may not change. Pack hashing happens outside the measured frame window.\nNo shader loader or shader pack is automatically installed or enabled.\n'''
    return {"PIXFORGE_REGRESSION.json":encode(plan),"GAME_REGRESSION.md":guide.encode("utf-8")}


def _capture(path):
    root=Path(path).resolve();file=root/"capture.json" if root.is_dir() else root;root=file.parent
    if file.stat().st_size>8*1024*1024:raise StudioError("游戏回归记录超过 8 MiB")
    value=json.loads(file.read_text(encoding="utf-8-sig"))
    if not isinstance(value,dict) or value.get("schema")!="pixforge.game-regression/v1" or value.get("measured_in_game") is not True or value.get("minecraft")!="1.20.1":raise StudioError("需要实际 Forge 1.20.1 游戏捕获记录")
    def attachment(key,hash_key):
        name=value.get(key)
        if not isinstance(name,str) or Path(name).name!=name or name in (".",".."):raise StudioError("捕获附件须为同目录文件名")
        result=(root/name).resolve()
        if not result.is_relative_to(root) or not result.is_file() or result.stat().st_size>32*1024*1024:raise StudioError("捕获附件缺失 / 越界 / 过大")
        if digest(result.read_bytes())!=value.get(hash_key):raise StudioError("捕获附件哈希不一致")
        return result
    image=attachment("screenshot","screenshot_sha256")
    logs=attachment("log_tail","log_tail_sha256") if "log_tail" in value else None
    with Image.open(image) as source:
        if source.width*source.height>16_777_216:raise StudioError("捕获截图超过 16M 像素")
        picture=source.convert("RGB")
    for key in ("frame_interval_ms","render_event_cpu_ms","pixforge_ber_cpu_ms","visible_instances","part_submissions"):
        row=value.get(key)
        if not isinstance(row,dict) or type(row.get("count")) is not int or not 1<=row["count"]<=600 or any(type(row.get(k)) not in (int,float) or not math.isfinite(row[k]) or row[k]<0 for k in ("mean","median","p95","p99")):raise StudioError("实际测量统计无效: "+key)
    return value,picture,logs


def compare(baseline,candidate,budgets=None,*,require_material=False):
    if budgets is None:budgets={}
    if not isinstance(budgets,dict) or set(budgets)-{"pixel_threshold","changed_fraction","p95_ratio"}:raise StudioError("比较预算使用 pixel_threshold/changed_fraction/p95_ratio")
    limits={"pixel_threshold":budgets.get("pixel_threshold",0),"changed_fraction":budgets.get("changed_fraction",0.),"p95_ratio":budgets.get("p95_ratio",1.1)}
    for key,lo,hi in (("pixel_threshold",0,255),("changed_fraction",0,1),("p95_ratio",1,100)):
        n=limits[key]
        if type(n) not in (int,float) or not math.isfinite(n) or not lo<=n<=hi:raise StudioError("比较预算范围无效: "+key)
    a,ia,la=_capture(baseline);b,ib,lb=_capture(candidate);mismatches=[]
    # Runtime bytes may intentionally change across a candidate; record that change separately.
    for key in ("case_id","minecraft","forge","module_id","renderer","vendor","java","mods"):
        if a.get(key)!=b.get(key):mismatches.append(key)
    keys=("dimension","camera","rain","window_width","window_height","graphics","mipmaps","render_distance","particles","gamma","fov","vsync","fps_limit","loaded_fixture_blocks","loaded_fixture_phases","fixture_light","sky_darken")
    for side,value in (("baseline",a),("candidate",b)):
        if type(value.get("reload_generation")) is not int or value["reload_generation"]<1 or not isinstance(value.get("reload_resource_sha256"),str) or len(value["reload_resource_sha256"])!=64:mismatches.append(side+"/resource_reload")
        if not isinstance(value.get("start"),dict) or not isinstance(value.get("end"),dict):raise StudioError("捕获缺少视图 / 环境记录")
        for key in keys:
            if key not in value["end"]:mismatches.append(side+"/missing/"+key)
        for key in ("camera","window_width","window_height","graphics","mipmaps","render_distance","particles","gamma","fov","vsync","fps_limit","loaded_fixture_blocks"):
            if value["start"].get(key)!=value["end"].get(key):mismatches.append(side+"/changed_during_capture/"+key)
    for key in keys:
        if a["end"].get(key)!=b["end"].get(key):mismatches.append("context/"+key)
    # PBR acceptance additionally identifies the active loader, actual pack bytes
    # and settings. A matching user-declared feature list cannot establish this.
    shader_context=any('material_shader' in value.get(side,{}) for value in (a,b) for side in ('start','end'))
    if require_material and not shader_context:mismatches.append('material_shader_context_required')
    if shader_context:
        for label,value in (('baseline',a),('candidate',b)):
            for side in ('start','end'):
                observed=value[side].get('material_shader')
                prefix=label+'/'+side+'/material_shader'
                if not isinstance(observed,dict) or observed.get('known') is not True or observed.get('enabled') is not True:
                    mismatches.append(prefix+'/active_shader_unknown');continue
                contract=observed.get('expected');target=contract.get('target') if isinstance(contract,dict) else None
                if not isinstance(target,dict):mismatches.append(prefix+'/target_unbound');continue
                for name in ('name','loader','loader_version','sha256'):
                    if not target.get(name) or target[name]!=observed.get(name):mismatches.append(prefix+'/'+name)
                if not isinstance(observed.get('sha256'),str) or len(observed['sha256'])!=64:mismatches.append(prefix+'/source_fingerprint')
                if not isinstance(observed.get('settings_files'),dict):mismatches.append(prefix+'/settings_unknown')
                for option,expected in target.get('options',{}).items():
                    actual=observed.get('expected_options_observed',{}).get(option)
                    desired=str(expected).lower() if type(expected) is bool else str(expected)
                    if actual!=desired:mismatches.append(prefix+'/option/'+option)
            for name in ('material_shader','resource_reload_generation'):
                if value['start'].get(name)!=value['end'].get(name):mismatches.append(label+'/changed_during_capture/'+name)
        identity=lambda observed:{k:v for k,v in observed.items() if k!='expected'} if isinstance(observed,dict) else observed
        if identity(a['end'].get('material_shader'))!=identity(b['end'].get('material_shader')):mismatches.append('context/material_shader')
    if ia.size!=ib.size:mismatches.append("screenshot_size");pixels=None
    else:
        diff=ImageChops.difference(ia,ib);maximum=max(max(p) for p in diff.getdata());changed=sum(max(p)>limits["pixel_threshold"] for p in diff.getdata());fraction=changed/(ia.width*ia.height)
        pixels={"size":list(ia.size),"max_channel_delta":maximum,"mean_channel_delta":sum(ImageStat.Stat(diff).mean)/3,"changed_pixels":changed,"changed_fraction":fraction,"within_budget":fraction<=limits["changed_fraction"]}
    times={}
    for key in ("frame_interval_ms","render_event_cpu_ms","pixforge_ber_cpu_ms"):
        before,after=a[key]["p95"],b[key]["p95"];ratio=after/before if before else (1 if not after else None)
        times[key]={"baseline_p95_ms":before,"candidate_p95_ms":after,"ratio":ratio,"within_budget":ratio is not None and ratio<=limits["p95_ratio"]}
    errors={}
    for name,path in (("baseline",la),("candidate",lb)):
        errors[name]=[line for line in path.read_text(encoding="utf-8",errors="replace").splitlines() if any(token in line.lower() for token in ("[error]","/error]"," error ","failed to load","unable to load","missing texture","unresolved texture"))][-40:] if path else ["No captured reload log tail"]
    comparable=not mismatches
    return {"schema":"pixforge.game-regression-comparison/v1","comparable":comparable,"context_mismatches":mismatches,"budgets":limits,"pixels":pixels,"timings":times,
        "reload_log_findings":errors,"runtime_changed":a.get("runtime_sha256")!=b.get("runtime_sha256"),"resource_changed":a.get("reload_resource_sha256")!=b.get("reload_resource_sha256"),
        'material_shader_context_checked':shader_context,'material_contract_changed':a['end'].get('material_shader',{}).get('expected')!=b['end'].get('material_shader',{}).get('expected'),
        "passed":comparable and pixels is not None and pixels["within_budget"] and all(v["within_budget"] for v in times.values()) and not any(errors.values()),
        "evidence_scope":"supplied actual game captures only; not a claim that all regression-plan cases were performed"}
