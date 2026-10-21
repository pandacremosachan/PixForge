"""Current-content scene evidence with a real geometric/particle player."""
from PIL import Image, ImageDraw
from .shape_preview import render, html
from .scene_animation import analyze


def texture_at(document, time_ms, scene_view=None, scene_state=None):
    plan = document.animation
    control = None
    if document.scene_animation is not None:
        from .scene_program import texture_control
        control = texture_control(document.scene_animation,time_ms,scene_view,scene_state)
        time_ms = control["time_ms"]
    total = sum(s["duration_ms"] for s in plan["steps"])
    t = time_ms % total if plan["loop"] else min(time_ms,total-1e-7)
    frame = plan["steps"][-1]["frame"]
    for s in plan["steps"]:
        if t < s["duration_ms"]:
            frame = s["frame"]
            break
        t -= s["duration_ms"]
    if control and control["mode"] == "hold" and "frame" in control:
        frame = min(control["frame"],len(plan["rectangles"])-1)
    x,y,w,h = plan["rectangles"][frame]
    return document.canvas.composite().crop((x,y,x+w,y+h))


def contact_sheet(document):
    duration = document.scene_animation["duration_ms"]
    out = Image.new("RGBA", (1024,568), "#141b25")
    draw = ImageDraw.Draw(out)
    for i in range(8):
        t = duration*i/8
        image = render(document.shapes,texture_at(document,t),size=256,yaw=35,pitch=28,overlays=[],
                       scene=document.scene_animation,time_ms=t,annotate=False)
        x,y = i%4*256,i//4*284
        out.paste(image,(x,y+28))
        from .scene_program import resolve, is_program
        clip,_ = resolve(document.scene_animation,t)
        label = clip["id"] if is_program(document.scene_animation) else "scene"
        draw.text((x+4,y+3),f"{t:g} ms / {label}",fill="#e0e8d5")
    return out


def preview(document, options=None):
    from .session import image_data
    from .document import StudioError
    options = options or {}
    metadata = {k:document.status()[k] for k in ("document_id","revision","content_digest")}
    metadata["project_name"] = document.project_path.name if document.project_path else "场景动画"
    try:
        report=analyze(document.scene_animation,document.shapes["model"])
    except StudioError as error:
        if error.code!='ANIMATION_TRACK_STATIC':
            raise
        # Read-only evidence can display a static pose. Motion analysis and the
        # requested-animation workflow still require actual motion.
        report={'passed':False,'code':error.code,'error':str(error),'motion_present':False,
                'scene_schema':document.scene_animation['schema'],'not_human_approval':True,
                'not_aesthetic_or_game_validation':True}
    return {"state":document.status(),"report":report,
            "image":image_data(contact_sheet(document)),
            "html":html(document.shapes,document.canvas,document.animation,metadata,scene=document.scene_animation)}
