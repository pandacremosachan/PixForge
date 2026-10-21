"""Named animation states and a deterministic, view-only playback controller.

State changes inherit channel values and retain particles already in flight.
The project owns the definition; a player owns only preview time and switches.
"""
from copy import deepcopy
import math

from .scene_curves import track_value, value_range


def is_program(scene):
    return scene is not None and "states" in scene


def clips(scene):
    return scene["states"] if is_program(scene) else [scene] if scene is not None else []


def all_entries(scene, kind):
    result = {}
    for clip in clips(scene):
        for item in clip[kind]:
            result.setdefault(item["id"],item)
    return list(result.values())


def normalize_program(value, model):
    from .document import StudioError
    from .scene_animation import ADVANCED_SCHEMA, DEFAULT_TARGET, normalize
    def fail(message):
        raise StudioError(message,"INVALID_SCENE_ANIMATION")
    allowed = {"schema","seed","target","initial_state","states","transitions","preview_sequence","duration_ms","loop"}
    if set(value)-allowed:
        fail("状态动画包含未知字段")
    states = value.get("states")
    if not isinstance(states,list) or not 1 <= len(states) <= 16:
        fail("状态动画须包含 1..16 个状态")
    seed = value.get("seed",1)
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        fail("seed 须为 0..2147483647 整数")
    target = deepcopy(value.get("target",DEFAULT_TARGET))
    normalized,ids = [],set()
    for index,state in enumerate(states):
        if not isinstance(state,dict) or not {"id","label","duration_ms"} <= set(state):
            fail("每个状态须包含 id/label/duration_ms")
        identity,label = state["id"],state["label"]
        if not isinstance(identity,str) or not identity.strip() or len(identity)>80 or identity in ids:
            fail("状态 id 须为唯一的 1..80 字文字")
        if not isinstance(label,str) or not label.strip() or len(label)>80:
            fail("状态 label 须为 1..80 字文字")
        ids.add(identity)
        raw = {k:deepcopy(v) for k,v in state.items() if k not in ("id","label","next")}
        raw.setdefault("schema",ADVANCED_SCHEMA)
        if raw["schema"] != ADVANCED_SCHEMA or "states" in raw:
            fail("状态片段须使用 v2 关键帧格式，不嵌套状态机")
        raw.setdefault("seed",(seed+index*100003)%2147483648)
        raw.setdefault("target",target)
        if raw["target"] != target:
            fail("所有状态须使用同一游戏目标")
        clip = normalize(raw,model)
        nxt = state.get("next")
        if nxt is not None and (not isinstance(nxt,str) or clip["loop"]):
            fail("自动 next 仅用于非循环片段，值须为状态 id 或 null")
        normalized.append({"id":identity,"label":label,"next":nxt,**clip})
    for state in normalized:
        if state["next"] is not None and state["next"] not in ids:
            fail("next 引用了不存在的状态")
    initial = value.get("initial_state",normalized[0]["id"])
    if initial not in ids:
        fail("initial_state 不存在")
    # A channel keeps its geometry and ordering across states. Only its motion
    # changes, so entry values remain meaningful and never bind another part.
    topology = lambda s:[{k:t[k] for k in ("id","type","elements","pivot","axis") if k in t} for t in s["transforms"]]
    basis = topology(normalized[0])
    emitter_ids = [e["id"] for e in normalized[0]["emitters"]]
    key_count = 0
    budgets = []
    for state in normalized:
        if topology(state) != basis or [e["id"] for e in state["emitters"]] != emitter_ids:
            fail("各状态须保留相同部件通道及发射器 id/顺序；静止用保持关键帧，关闭发射用 emission=0")
        key_count += sum(len(t.get("keyframes",[])) for t in state["transforms"])+sum(len(e["emission"]) for e in state["emitters"])
        budgets.append(sum(math.ceil(e["count_per_cycle"]*e["lifetime_ms"]/state["duration_ms"])+1 for e in state["emitters"]))
    if not basis and not emitter_ids:
        fail("状态动画至少需要一个部件通道或发射器")
    if key_count > 4096:
        fail("状态动画关键帧总数超过 4096")
    if sum(sorted(budgets,reverse=True)[:2]) > 2048:
        fail("状态切换的粒子预算超过 2048，请减少发射量或寿命")
    transitions = value.get("transitions",[])
    if not isinstance(transitions,list) or len(transitions)>64:
        fail("transitions 须为至多 64 项的数组")
    routes,seen = [],set()
    for route in transitions:
        if not isinstance(route,dict) or set(route) != {"from","event","to"}:
            fail("状态转换使用 from/event/to")
        if route["from"] not in ids or route["to"] not in ids or route["event"] not in ("start","stop"):
            fail("状态转换须引用真实状态，event 使用 start/stop")
        key = route["from"],route["event"]
        if key in seen:
            fail("同一状态和事件不可存在两条转换")
        seen.add(key);routes.append(deepcopy(route))
    sequence = value.get("preview_sequence")
    if not isinstance(sequence,list) or not 1 <= len(sequence) <= 32:
        fail("preview_sequence 须为 1..32 个状态时段")
    by_id = {s["id"]:s for s in normalized}
    preview = []
    for item in sequence:
        if not isinstance(item,dict) or set(item) != {"state","duration_ms"} or item["state"] not in ids:
            fail("预览时段使用真实 state 与 duration_ms")
        duration = item["duration_ms"]
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 100 <= duration <= 120000:
            fail("预览时段须为 100..120000 毫秒")
        clip = by_id[item["state"]]
        if not clip["loop"] and duration != clip["duration_ms"]:
            fail("非循环状态的预览时段须覆盖完整片段")
        preview.append(deepcopy(item))
    if preview[0]["state"] != initial:
        fail("完整流程须从 initial_state 开始")
    repeat = value.get("loop",False)
    if type(repeat) is not bool:
        fail("loop 须为布尔值")
    joins = list(zip(preview,preview[1:]))+([(preview[-1],preview[0])] if repeat else [])
    for a,b in joins:
        source,dest = a["state"],b["state"]
        if source != dest and by_id[source]["next"] != dest and not any(r["from"]==source and r["to"]==dest for r in routes):
            fail("完整流程包含未声明的状态转换："+source+" → "+dest)
    duration = sum(s["duration_ms"] for s in preview)
    if duration>120000 or ("duration_ms" in value and value["duration_ms"] != duration):
        fail("完整流程总时长须不超过 120000 毫秒，并与 duration_ms 一致")
    return {"schema":ADVANCED_SCHEMA,"seed":seed,"target":target,"initial_state":initial,
            "states":normalized,"transitions":routes,"preview_sequence":preview,"duration_ms":duration,"loop":repeat}


def clip_moment(clip,time_ms):
    return time_ms%clip["duration_ms"] if clip["loop"] else min(clip["duration_ms"],max(0,time_ms))


def carry_particles(carry,time_ms):
    result = []
    for particle in carry:
        remaining = particle["_remaining_ms"]
        if not 0 <= time_ms < remaining:
            continue
        t,ratio = time_ms/1000,time_ms/remaining
        p = deepcopy(particle)
        p["age_ms"] += time_ms
        p["position"] = [x+v*t+.5*g*t*t for x,v,g in zip(particle["position"],particle["_velocity"],particle["_gravity"])]
        p["_velocity"] = [v+g*t for v,g in zip(particle["_velocity"],particle["_gravity"])]
        p["size"] += (p["_end_size"]-p["size"])*ratio
        p["color"] = [a+(b-a)*ratio for a,b in zip(p["color"],p["_end_color"])]
        p["_remaining_ms"] -= time_ms
        result.append(p)
    return result


class ScenePlayer:
    def __init__(self,scene):
        if not is_program(scene):
            raise ValueError("ScenePlayer requires named states")
        self.scene = scene
        self.by_id = {s["id"]:s for s in scene["states"]}
        self.state = scene["initial_state"]
        self.time = 0
        self.entry,self.carry = {},[]
        self.prewarm = self.clip["loop"]
        self.first_cycle = True
        self.texture_entry = 0
        self.sequence_mode = False
        self.sequence_index = 0
        self.sequence_elapsed = 0
        self.finished = False
        self.repeat = scene["loop"]

    @property
    def clip(self):
        return self.by_id[self.state]

    def texture_time(self):
        return self.texture_entry+self.time*self.clip["texture"].get("speed",0)

    def view(self):
        return {"state":self.state,"time_ms":self.time,"entry_values":deepcopy(self.entry),
                "carry":deepcopy(self.carry),"prewarm":self.prewarm,"first_cycle":self.first_cycle,
                "texture_entry_time_ms":self.texture_entry}

    def summary(self):
        return {"state":self.state,"label":self.clip["label"],"time_ms":clip_moment(self.clip,self.time),
                "duration_ms":self.clip["duration_ms"],"sequence_mode":self.sequence_mode,"sequence_time_ms":self.clock(),
                "sequence_duration_ms":self.scene["duration_ms"],"finished":self.finished,"repeat_sequence":self.repeat,"repeat_sequence":self.repeat,
                "available_events":[r["event"] for r in self.scene["transitions"] if r["from"]==self.state]}

    def clock(self):
        if not self.sequence_mode:
            return clip_moment(self.clip,self.time)
        return sum(s["duration_ms"] for s in self.scene["preview_sequence"][:self.sequence_index])+self.sequence_elapsed

    def _capture(self):
        from .scene_animation import _clip_particles
        at = clip_moment(self.clip,self.time)
        values = {t["id"]:track_value(t,self.clip["duration_ms"],at,self.entry,self.first_cycle and self.time < self.clip["duration_ms"]) for t in self.clip["transforms"]}
        flying = _clip_particles(self.clip,self.time,self.view())+carry_particles(self.carry,self.time)
        return values,flying[:2048],self.texture_time()

    def _enter(self,identity,preserve=True):
        if identity not in self.by_id:
            from .document import StudioError
            raise StudioError("未知动画状态："+str(identity),"INVALID_SCENE_STATE")
        values,flying,texture = self._capture() if preserve else ({},[],0)
        self.state,self.time,self.entry,self.carry = identity,0,values,flying
        self.texture_entry = texture
        self.prewarm = False if preserve else self.clip["loop"]
        self.first_cycle,self.finished = True,False

    def select(self,identity,*,preserve=False):
        self._enter(identity,preserve)
        self.sequence_mode = False

    def event(self,event):
        target = next((r["to"] for r in self.scene["transitions"] if r["from"]==self.state and r["event"]==event),None)
        if target is None:
            from .document import StudioError
            raise StudioError("当前状态不接受事件："+str(event),"INVALID_SCENE_TRANSITION")
        self._enter(target,True)
        self.sequence_mode = False

    def begin_sequence(self,*,preserve=False):
        self._enter(self.scene["preview_sequence"][0]["state"],preserve)
        self.sequence_mode,self.sequence_index,self.sequence_elapsed = True,0,0
        self.finished = False

    def _tick(self,delta):
        self.time += delta
        if self.clip["loop"] and self.time >= max(self.clip["duration_ms"]*(2 if self.first_cycle else 1),max((p["_remaining_ms"] for p in self.carry),default=0)):
            wrapped = self.time-self.time%self.clip["duration_ms"]
            self.texture_entry += wrapped*self.clip["texture"].get("speed",0)
            self.time -= wrapped
            self.carry = []
            self.prewarm,self.first_cycle = True,False

    def advance(self,delta):
        if type(delta) not in (int,float) or not math.isfinite(delta) or not 0 <= delta <= 120000:
            raise ValueError("Playback delta must be finite 0..120000 ms")
        remaining = delta
        while not self.finished:
            if self.sequence_mode:
                limit = self.scene["preview_sequence"][self.sequence_index]["duration_ms"]
                step = min(remaining,max(0,limit-self.sequence_elapsed))
                self._tick(step);self.sequence_elapsed += step;remaining -= step
                if self.sequence_elapsed+1e-9 < limit:
                    break
                if self.sequence_index+1 < len(self.scene["preview_sequence"]):
                    self.sequence_index += 1
                elif self.repeat:
                    self.sequence_index = 0
                else:
                    self.finished = True
                    break
                self.sequence_elapsed = 0
                self._enter(self.scene["preview_sequence"][self.sequence_index]["state"],True)
            elif self.clip["loop"]:
                self._tick(remaining)
                break
            else:
                step = min(remaining,max(0,self.clip["duration_ms"]-self.time))
                self._tick(step);remaining -= step
                if self.time+1e-9 < self.clip["duration_ms"]:
                    break
                target = self.clip["next"]
                if target is None:
                    self.finished = True
                    break
                self._enter(target,True)
            if remaining <= 1e-9:
                break

    def seek(self,time_ms):
        if self.sequence_mode:
            self.begin_sequence(preserve=False)
            self.advance(time_ms)
        else:
            self.time = time_ms
            self.finished = False


def resolve(scene,time_ms=0,view=None,state=None):
    if not is_program(scene):
        return scene,view or {"time_ms":time_ms,"entry_values":{},"carry":[],"prewarm":scene["loop"],"first_cycle":True,"texture_entry_time_ms":0}
    if view is None:
        player = ScenePlayer(scene)
        if state is None:
            player.begin_sequence()
            player.advance(time_ms)
        else:
            player.select(state)
            player.time = time_ms
        view = player.view()
    clip = next((s for s in scene["states"] if s["id"]==view["state"]),None)
    if clip is None:
        from .document import StudioError
        raise StudioError("未知动画状态","INVALID_SCENE_STATE")
    return clip,view


def texture_control(scene,time_ms=0,view=None,state=None):
    if not is_program(scene) and "texture" not in scene:
        return {"mode":"play","time_ms":time_ms}
    clip,actual = resolve(scene,time_ms,view,state)
    texture = clip["texture"]
    return {**texture,"time_ms":actual.get("texture_entry_time_ms",0)+actual["time_ms"]*texture.get("speed",0)}


def channel_ranges(scene):
    result = {}
    for clip in clips(scene):
        for track in clip["transforms"]:
            bounds = value_range(track)
            if bounds is None:
                continue
            if track["id"] not in result:
                result[track["id"]] = deepcopy(bounds)
            else:
                a,b = result[track["id"]]
                for i in range(3):
                    a[i],b[i] = min(a[i],bounds[0][i]),max(b[i],bounds[1][i])
    return result


def validate_binding(scene,animation):
    from .document import StudioError
    referenced = {s["frame"] for s in animation["steps"]}
    for clip in clips(scene):
        texture = clip.get("texture",{})
        if texture.get("mode") == "hold" and "frame" in texture and texture["frame"] not in referenced:
            raise StudioError("状态固定帧须来自当前材质播放步骤","INVALID_SCENE_ANIMATION")


def remap_texture_frames(scene,mapping):
    """Keep state holds attached to their original source cel after atlas edits."""
    from .document import StudioError
    if scene is None:
        return None
    result = deepcopy(scene)
    for clip in clips(result):
        texture = clip.get("texture",{})
        if texture.get("mode") == "hold" and "frame" in texture:
            source = texture["frame"]
            if source not in mapping:
                raise StudioError("该源帧仍被动画状态固定引用；请先修改相应状态的材质设置","SCENE_FRAME_IN_USE")
            texture["frame"] = mapping[source]
    return result


def validate_view(scene,view):
    """Accept only a bounded snapshot produced by a state playback controller."""
    from .document import StudioError
    def fail():
        raise StudioError("scene_view 不是当前状态机的有限播放快照","INVALID_SCENE_VIEW")
    def finite(value,low=-1e9,high=1e9):
        return type(value) in (int,float) and math.isfinite(value) and low <= value <= high
    def vector(value,count,low=-1e9,high=1e9):
        return isinstance(value,list) and len(value)==count and all(finite(n,low,high) for n in value)
    if not is_program(scene) or not isinstance(view,dict) or set(view)!={"state","time_ms","entry_values","carry","prewarm","first_cycle","texture_entry_time_ms"}:
        fail()
    clip = next((s for s in scene["states"] if s["id"]==view["state"]),None)
    if clip is None or not finite(view["time_ms"],0,240000) or not finite(view["texture_entry_time_ms"],-1e12,1e12) or type(view["prewarm"]) is not bool or type(view["first_cycle"]) is not bool:
        fail()
    entry = view["entry_values"]
    channels = {t["id"]:t for t in clip["transforms"]}
    if not isinstance(entry,dict) or set(entry)-set(channels):
        fail()
    for identity,value in entry.items():
        kind = channels[identity]["type"]
        if kind=="rotate":ok=finite(value)
        else:ok=vector(value,3,.05 if kind=="scale" else -256,8 if kind=="scale" else 256)
        if not ok:fail()
    if not isinstance(view["carry"],list) or len(view["carry"])>2048:
        fail()
    emitters = {e["id"] for e in clip["emitters"]}
    fields = {"emitter","birth_id","age_ms","position","size","color","blend","_velocity","_gravity","_remaining_ms","_end_size","_end_color"}
    for p in view["carry"]:
        if not isinstance(p,dict) or set(p)!=fields or p["emitter"] not in emitters or type(p["birth_id"]) is not int or not 0 <= p["birth_id"]<1024 or p["blend"] not in ("alpha","additive"):
            fail()
        if not all(vector(p[k],3) for k in ("position","_velocity","_gravity")) or not all(vector(p[k],4,-1e-8,255+1e-8) for k in ("color","_end_color")):
            fail()
        if not finite(p["age_ms"],0,120000) or not finite(p["_remaining_ms"],0,120000) or p["_remaining_ms"]<=0 or not all(finite(p[k],0,16) for k in ("size","_end_size")):
            fail()
    return deepcopy(view)
