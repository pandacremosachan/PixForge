"""Bounded, explicit keyframes. Segment easing belongs to its left key."""
import math

EASINGS = ("hold", "linear", "smooth", "ease_in", "ease_out")


def normalize_keys(value, duration, *, dimensions=0, low=-4096, high=4096, loop=False, rotation=False):
    from .document import StudioError
    def fail(message):
        raise StudioError(message, "INVALID_SCENE_ANIMATION")
    if not isinstance(value, list) or not 2 <= len(value) <= 128:
        fail("关键帧须为 2..128 个按时间排序的对象")
    output = []
    for key in value:
        if not isinstance(key, dict) or set(key)-{"time_ms", "value", "easing"} or not {"time_ms", "value"} <= set(key):
            fail("关键帧使用 time_ms/value/easing")
        t = key["time_ms"]
        if type(t) not in (int,float) or not math.isfinite(t) or not 0 <= t <= duration or (output and t <= output[-1]["time_ms"]):
            fail("关键帧时间须严格递增且位于当前状态时长内")
        item = key["value"]
        items = item if dimensions else [item]
        if not isinstance(items,list) or len(items) != (dimensions or 1):
            fail("关键帧 value 维度不正确")
        if any(type(n) not in (int,float) or not math.isfinite(n) or not low <= n <= high for n in items):
            fail("关键帧 value 超出有限数值范围")
        easing = key.get("easing", "linear")
        if easing not in EASINGS:
            fail("easing 使用 hold/linear/smooth/ease_in/ease_out")
        output.append({"time_ms": t, "value": list(items) if dimensions else item, "easing": easing})
    if output[0]["time_ms"] != 0 or output[-1]["time_ms"] != duration:
        fail("关键帧须明确包含 0 ms 和当前状态结束时间")
    if loop:
        a,b = output[0]["value"],output[-1]["value"]
        closed = abs((b-a)/360-round((b-a)/360)) < 1e-9 if rotation else a == b
        if not closed:
            fail("循环关键帧首尾须闭合；旋转允许相差整数圈")
    return output


def ease(value, kind):
    if kind == "hold":
        return 0
    if kind == "smooth":
        return value*value*(3-2*value)
    if kind == "ease_in":
        return value*value
    if kind == "ease_out":
        return 1-(1-value)*(1-value)
    return value


def curve(keys, time_ms, first=None):
    if time_ms <= keys[0]["time_ms"]:
        value = keys[0]["value"] if first is None else first
        return list(value) if isinstance(value,list) else value
    if time_ms >= keys[-1]["time_ms"]:
        value = keys[-1]["value"]
        return list(value) if isinstance(value,list) else value
    for index,(a,b) in enumerate(zip(keys,keys[1:])):
        if time_ms < b["time_ms"]:
            p = ease((time_ms-a["time_ms"])/(b["time_ms"]-a["time_ms"]),a["easing"])
            start = first if index == 0 and first is not None else a["value"]
            if isinstance(start,list):
                return [x+(y-x)*p for x,y in zip(start,b["value"])]
            return start+(b["value"]-start)*p
    return keys[-1]["value"]


def track_value(track, duration, time_ms, entry=None, first_cycle=True):
    entry = entry or {}
    inherited = entry.get(track["id"])
    mode = track.get("entry", "absolute")
    if "keyframes" in track:
        value = curve(track["keyframes"],time_ms,inherited if mode == "from_current" and first_cycle else None)
    elif track["type"] == "rotate":
        value = track["phase_deg"]+360*track["turns"]*time_ms/duration
    else:
        wave = math.sin(track["phase_deg"]*math.pi/180+2*math.pi*track["cycles"]*time_ms/duration)
        value = [(1 if track["type"] == "scale" else 0)+a*wave for a in track["amplitude"]]
    if mode == "relative" and inherited is not None:
        value += inherited
    return value


def value_range(track):
    if track["type"] == "rotate":
        return None
    if "keyframes" in track:
        values = [k["value"] for k in track["keyframes"]]
        return [min(v[i] for v in values) for i in range(3)],[max(v[i] for v in values) for i in range(3)]
    base = 1 if track["type"] == "scale" else 0
    return [base-abs(a) for a in track["amplitude"]],[base+abs(a) for a in track["amplitude"]]
