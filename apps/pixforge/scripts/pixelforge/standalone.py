"""Independent image inspection and atomic offline drafts."""
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from .document import Document, StudioError, playback
from .image_bytes import png_base64
from .transactions import commit_files
from . import texture_review as review


def inspect_texture(path, options=None):
    defaults = dict(expect_size=None, opaque=False, binary_alpha=False, symmetry="none",
        symmetry_space="rgba", alpha_cutoff=0, region=None, clusters=False,
        max_isolated_pixels=None, compare=None, palette=None, preserve_mask=None,
        tile=False, match_edges=False, scale=6, backgrounds=["checker"], display_size=None,
        frame_height=None, animation_plan=None)
    options = {} if options is None else options
    if not isinstance(options, dict) or set(options) - defaults.keys():
        raise StudioError("未知图片检查选项: " + str(set(options) - defaults.keys()) if isinstance(options, dict) else "options 须为对象")
    args = SimpleNamespace(**(defaults | options))
    for name in ("opaque", "binary_alpha", "clusters", "tile", "match_edges"):
        if type(getattr(args, name)) is not bool:
            raise StudioError(name + " 须为布尔值")
    for name, count, minimum in (("expect_size", 2, 1), ("display_size", 2, 1), ("region", 4, 0)):
        value = getattr(args, name)
        if value is not None and (not isinstance(value, list) or len(value) != count or any(type(n) is not int or n < minimum for n in value)):
            raise StudioError(name + " 的尺寸或坐标无效")
    if args.symmetry not in review.REQUIRED or args.symmetry_space not in ("rgba", "alpha", "silhouette"):
        raise StudioError("未知对称规则或比较空间")
    if type(args.scale) is not int or not 1 <= args.scale <= 16 or type(args.alpha_cutoff) is not int or not 0 <= args.alpha_cutoff <= 254:
        raise StudioError("scale 使用 1..16，alpha_cutoff 使用 0..254")
    if args.max_isolated_pixels is not None and (type(args.max_isolated_pixels) is not int or args.max_isolated_pixels < 0):
        raise StudioError("max_isolated_pixels 须为非负整数")
    if not isinstance(args.backgrounds, list) or not args.backgrounds or any(b not in ("checker", "light", "dark") for b in args.backgrounds):
        raise StudioError("backgrounds 使用 checker/light/dark")
    args.backgrounds = list(dict.fromkeys(args.backgrounds))
    path = Path(path).resolve()
    inputs = [path]
    for name in ("compare", "preserve_mask"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(value).resolve())
            inputs.append(getattr(args, name))
    if isinstance(args.palette, str):
        inputs.append(Path(args.palette).resolve())
        args.palette_colors = review.load_palette(Path(args.palette))
    elif args.palette is not None:
        from .palette import parse_color
        if not isinstance(args.palette, list) or not args.palette:
            raise StudioError("palette 使用非空 RGBA 数组或调色板文件路径")
        args.palette_colors = set(parse_color(color) for color in args.palette)
    else:
        args.palette_colors = None
    animated = args.frame_height is not None or args.animation_plan is not None
    if args.frame_height is not None and args.animation_plan is not None:
        raise StudioError("frame_height 和 animation_plan 不能同时指定")
    if args.compare and animated or args.preserve_mask and (not args.compare or animated):
        raise StudioError("前后对照和保护蒙版只用于静态图片；保护蒙版需要 compare")
    source = review.load_png(path)
    frames, timing, html = None, None, None
    if args.animation_plan is not None:
        from .texture_animation import load_plan, build_report, player_html
        plan, image_path, rectangles, native_frames = load_plan(args.animation_plan, base_directory=path.parent)
        if image_path != path:
            raise StudioError("animation_plan 须引用被检查的 PNG")
        if isinstance(args.animation_plan, str):
            inputs.append(Path(args.animation_plan).resolve())
        frames = [review.review_region(frame, args.region) for frame in native_frames]
        timing = build_report(plan, image_path, rectangles, native_frames)
        html = player_html(timing, native_frames, args.scale)
    elif args.frame_height is not None:
        height = args.frame_height
        if type(height) is not int or height < 1 or source.height % height:
            raise StudioError("frame_height 须为正整数并整除图片高度")
        frames = [review.review_region(source.crop((0, y, source.width, y + height)), args.region) for y in range(0, source.height, height)]
    declared = [key for key, value in (("size", args.expect_size is not None), ("opaque", args.opaque),
        ("binary_alpha", args.binary_alpha), ("symmetry", args.symmetry != "none"),
        ("match_edges", args.match_edges), ("palette", args.palette is not None),
        ("max_isolated_pixels", args.max_isolated_pixels is not None), ("preserve_mask", args.preserve_mask is not None)) if value]
    common = {"input": str(path), "constraints_declared": declared, "constraints_evaluated": bool(declared),
              "region": args.region, "note": "声明约束检查；视觉效果和实际游戏行为仍须查看。"}
    if frames is not None:
        reports = [{"frame": i, **review.analyze(frame, args)} for i, frame in enumerate(frames)]
        prepared = [review.comparison_image(frame) for frame in frames]
        report = {**common, "frames": reports, "constraints_passed": all(r["constraints_passed"] for r in reports),
            "animation": {"adjacent_frame_mean_rgba_deltas": [review.image_comparison(a, b)["mean_rgba_delta"] for a, b in zip(prepared, prepared[1:])],
                          "loop_transition_mean_rgba_delta": review.image_comparison(prepared[-1], prepared[0])["mean_rgba_delta"]}}
        picture, coverage = review.animation_preview(frames, None, args.scale, args.backgrounds, args.display_size, args.tile)
        report["animation_preview_coverage"] = coverage
        if timing is not None:
            report["playback"] = timing
    else:
        image = review.review_region(source, args.region)
        before_source = review.load_png(args.compare) if args.compare else None
        before = review.review_region(before_source, args.region) if before_source is not None else None
        report = {**common, **review.analyze(image, args), "source_size": list(source.size)}
        if before is not None:
            report["comparison"] = {"same_size": before.size == image.size,
                "pixels": review.image_comparison(review.comparison_image(before), review.comparison_image(image)) if before.size == image.size else None}
        if args.preserve_mask:
            preservation = review.preserved_pixels(source, before_source, review.load_png(args.preserve_mask))
            report["preservation"] = preservation
            if not preservation["exact"]:
                report["failed_requirements"].append("保护区域发生变化")
                report["constraints_passed"] = False
        picture = review.preview_sheet(image, None, args.scale, args.tile, before, args.backgrounds, args.display_size)
    result = {"report": report, "image": png_base64(picture), "inputs": [str(p) for p in inputs]}
    if html is not None:
        result["html"] = html
    return result


def preview_animation(plan, scale=6, base_directory=None):
    from .texture_animation import load_plan, build_report, player_html
    value, image_path, rectangles, frames = load_plan(plan, base_directory=base_directory)
    report = build_report(value, image_path, rectangles, frames)
    return {"report": report, "html": player_html(report, frames, scale),
            "inputs": [str(image_path), *([str(Path(plan).resolve())] if isinstance(plan, str) else [])]}


def publish_discussion(result, *, preview_path=None, html_path=None, report_path=None, overwrite=False, protected=()):
    inputs = {Path(p).resolve() for p in [*result.get("inputs", []), *protected] if p}
    outputs = {}
    for name, suffix, content in ((preview_path, ".png", base64.b64decode(result["image"]) if result.get("image") else None),
            (html_path, ".html", result.get("html", "").encode("utf-8") if result.get("html") else None),
            (report_path, ".json", json.dumps(result["report"], ensure_ascii=False, indent=2).encode("utf-8"))):
        if name is None:
            continue
        path = Path(name).resolve()
        if path.suffix.lower() != suffix or content is None:
            raise StudioError("输出类型与内容不匹配: " + str(path))
        if path in inputs or path in outputs:
            raise StudioError("讨论输出不能覆盖输入，且各输出路径须不同")
        if path.exists() and not overwrite:
            raise StudioError("输出已存在: " + str(path), "FILE_EXISTS")
        outputs[path] = content
    commit_files(outputs)
    result["outputs"] = [str(p) for p in outputs]
    if html_path:
        result.pop("html", None)
    return result


def offline_batch(commands, workspace, *, dry_run=True, project_path=None, scale=6, tile=False, backgrounds=None, overwrite=False):
    from .protocol import Executor
    result = Executor().run_batch(commands, dry_run=True, publish_outputs=False, include_preview=True,
        preview_options={"scale": scale, "tile": tile, "backgrounds": backgrounds or ["checker"]})
    response = {"batch": result.summary, "messages": result.messages, "image": png_base64(result.preview)}
    response["batch"]["dry_run"] = dry_run
    if not dry_run:
        if project_path is None or Path(project_path).suffix.lower() != ".pixforge":
            raise StudioError("提交离线草稿时指定 .pixforge project_path")
        path = Path(project_path).resolve()
        if path.exists() and not overwrite:
            raise StudioError("离线草稿已存在", "FILE_EXISTS")
        document = Document(workspace, Path(workspace) / ".runtime" / "pixforge-offline" / uuid.uuid4().hex)
        document.executor.canvas = result.canvas
        document.animation = playback({}, (result.canvas.w, result.canvas.h))
        document.save(path)
        response["project"] = str(path)
    response["formal_export"] = "通过 open_project 打开草稿后，沿用当前内容确认与导出工具；批次内输出保持延后。"
    return response
