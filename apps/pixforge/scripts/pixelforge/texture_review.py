"""Read-only pixel constraints and native/zoom/tile previews; not an aesthetic score."""

from collections import Counter
import json
import re

from PIL import Image, ImageChops, ImageDraw, ImageStat


TRANSFORMS = {
    "lr": Image.Transpose.FLIP_LEFT_RIGHT,
    "ud": Image.Transpose.FLIP_TOP_BOTTOM,
    "rotate_90": Image.Transpose.ROTATE_90,
    "rotate_180": Image.Transpose.ROTATE_180,
    "diagonal": Image.Transpose.TRANSPOSE,
    "antidiagonal": Image.Transpose.TRANSVERSE,
}
REQUIRED = {
    "none": (), "lr": ("lr",), "ud": ("ud",), "both": ("lr", "ud"),
    "diagonal": ("diagonal",), "antidiagonal": ("antidiagonal",),
    "rotate90": ("rotate_90",), "rotate180": ("rotate_180",),
    "d4": ("lr", "ud", "rotate_90"),
}
SQUARE_TRANSFORMS = {"rotate_90", "diagonal", "antidiagonal"}


def rgba_pixels(image):
    data = image.tobytes()
    # Hidden RGB in fully transparent pixels is visually irrelevant.
    return [tuple(data[i:i + 4]) if data[i + 3] else (0, 0, 0, 0)
            for i in range(0, len(data), 4)]


def load_palette(path):
    """Explicit allowed visible RGBA values; never quantize or recolor the input."""
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list) or not values:
        raise ValueError("palette must be a nonempty JSON array of #RRGGBB or #RRGGBBAA strings")
    colors = set()
    for value in values:
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", value):
            raise ValueError(f"invalid palette RGBA value: {value!r}")
        value = value[1:] + ("ff" if len(value) == 7 else "")
        colors.add(tuple(bytes.fromhex(value)))
    return colors


def palette_metrics(pixels, width, allowed):
    outside = [(index, pixel) for index, pixel in enumerate(pixels) if pixel[3] and pixel not in allowed]
    return {"outside_pixels": len(outside), "outside_colors": sorted({"".join(f"{c:02x}" for c in p) for _, p in outside}),
            "positions": [{"x": i % width, "y": i // width} for i, _ in outside[:64]],
            "positions_omitted": max(0, len(outside) - 64),
            "note": "Exact visible RGBA, including alpha; fully transparent hidden RGB is ignored. No automatic palette reduction."}


def preserved_pixels(image, before, mask):
    if image.size != before.size or mask.size != image.size:
        raise ValueError("preserve-mask, current PNG and comparison PNG must have identical full source dimensions")
    alpha = mask.getchannel("A").tobytes()
    if any(value not in (0, 255) for value in alpha) or not any(alpha):
        raise ValueError("preserve-mask must use binary alpha 0/255 and protect at least one pixel")
    current, previous = rgba_pixels(image), rgba_pixels(before)
    changed = [i for i, value in enumerate(alpha) if value and current[i] != previous[i]]
    return {"protected_pixels": sum(value == 255 for value in alpha), "changed_pixels": len(changed),
            "exact": not changed, "positions": [{"x": i % image.width, "y": i // image.width} for i in changed[:64]],
            "positions_omitted": max(0, len(changed) - 64),
            "note": "Full source coordinates, regardless of --region. Alpha 255 protects RGBA; alpha 0 allows edits. Hidden RGB at alpha 0 is ignored."}


def comparison_image(image, space="rgba", alpha_cutoff=0):
    """Prepare once, then compare/transform with Pillow's native pixel operations."""
    alpha = image.getchannel("A")
    if space == "alpha":
        return alpha
    if space == "silhouette":
        return alpha.point([int(value > alpha_cutoff) for value in range(256)])
    if alpha.getextrema()[0] != 0:
        return image
    result = image.copy()
    result.paste((0, 0, 0, 0), mask=alpha.point([255] + [0] * 255))
    return result


def image_comparison(left, right, space="rgba"):
    """Compare prepared RGBA or L images, including every channel."""
    if left.size != right.size or left.mode != right.mode:
        raise ValueError("image comparisons require equal dimensions and channel modes")
    total = left.width * left.height
    delta = ImageChops.difference(left, right)
    bands = delta.split()
    unequal = bands[0]
    for band in bands[1:]:
        unequal = ImageChops.lighter(unequal, band)
    matches = unequal.histogram()[0]
    delta_key = {"rgba": "mean_rgba_delta", "alpha": "mean_alpha_delta", "silhouette": "mean_silhouette_delta"}[space]
    return {"equal_pixels": matches, "total_pixels": total, "exact": matches == total,
            "match_percent": round(100 * matches / total, 3) if total else None,
            delta_key: round(sum(ImageStat.Stat(delta).sum) / (len(bands) * total), 3) if total else None}


def image_geometry(image, cutoff):
    mask = image.getchannel("A").point([255 if value > cutoff else 0 for value in range(256)])
    bbox = mask.getbbox()
    count = mask.histogram()[255]
    center, edges = None, []
    if bbox:
        left, top, right, bottom = bbox
        center = [(left + right - 1) / 2, (top + bottom - 1) / 2]
        edges = [name for name, touched in (("left", left == 0), ("top", top == 0),
                                           ("right", right == image.width), ("bottom", bottom == image.height)) if touched]
    return {"alpha_cutoff": cutoff, "visible_pixels": count,
            "coverage_percent": 100 * count / (image.width * image.height),
            "bbox": list(bbox) if bbox else None, "bbox_center": center, "touches_edges": edges,
            "note": "Local pixel coordinates; right/bottom bounds exclusive. Edge contact and center shifts are not failures by themselves. This threshold does not change the PNG or renderer."}


def image_tile_metrics(image):
    width, height = image.size
    return {
        "left_right_edges": image_comparison(image.crop((0, 0, 1, height)), image.crop((width - 1, 0, width, height))),
        "top_bottom_edges": image_comparison(image.crop((0, 0, width, 1)), image.crop((0, height - 1, width, height))),
        "horizontal_interior_mean_rgba_delta": image_comparison(
            image.crop((0, 0, width - 1, height)), image.crop((1, 0, width, height)))["mean_rgba_delta"] if width > 1 else None,
        "vertical_interior_mean_rgba_delta": image_comparison(
            image.crop((0, 0, width, height - 1)), image.crop((0, 1, width, height)))["mean_rgba_delta"] if height > 1 else None,
    }


def cluster_metrics(pixels, width, height):
    """Exact visible RGBA, four-neighbor components; diagonal contact does not connect."""
    visited, sizes, isolated = set(), Counter(), []
    for start, color in enumerate(pixels):
        if not color[3] or start in visited:
            continue
        visited.add(start)
        pending, size = [start], 0
        while pending:
            position = pending.pop()
            size += 1
            x, y = position % width, position // width
            neighbors = []
            if x:
                neighbors.append(position - 1)
            if x + 1 < width:
                neighbors.append(position + 1)
            if y:
                neighbors.append(position - width)
            if y + 1 < height:
                neighbors.append(position + width)
            for neighbor in neighbors:
                if neighbor not in visited and pixels[neighbor] == color:
                    visited.add(neighbor)
                    pending.append(neighbor)
        sizes[size] += 1
        if size == 1:
            isolated.append({"x": start % width, "y": start // width,
                             "rgba": "".join(f"{channel:02x}" for channel in color)})
    return {
        "connectivity": 4,
        "visible_pixels": sum(size * count for size, count in sizes.items()),
        "component_count": sum(sizes.values()),
        "size_histogram": {str(size): count for size, count in sorted(sizes.items())},
        "smallest_component": min(sizes) if sizes else None,
        "isolated_pixels": sizes[1],
        "isolated_positions": isolated[:64],
        "isolated_positions_omitted": max(0, len(isolated) - 64),
        "note": "Exact visible RGBA; diagonal lines and deliberate highlights may be singletons. Not a noise score. Coordinates are local to the reviewed region.",
    }


def review_region(image, region):
    if region is None:
        return image
    x, y, width, height = region
    if x < 0 or y < 0 or width < 1 or height < 1 or x + width > image.width or y + height > image.height:
        raise ValueError(f"region {region} lies outside image/frame size {image.size}")
    return image.crop((x, y, x + width, y + height))


def analyze(image, args):
    width, height = image.size
    needs_pixels = args.palette_colors is not None or args.clusters or args.max_isolated_pixels is not None
    pixels = rgba_pixels(image) if needs_pixels else None
    prepared = comparison_image(image, args.symmetry_space, args.alpha_cutoff)
    symmetry = {key: (image_comparison(prepared, prepared.transpose(transform), args.symmetry_space)
                      if key not in SQUARE_TRANSFORMS or width == height else None)
                for key, transform in TRANSFORMS.items()}
    failures = []
    palette = palette_metrics(pixels, width, args.palette_colors) if args.palette_colors is not None else None
    if palette and palette["outside_pixels"]:
        failures.append(f"palette: {palette['outside_pixels']} visible pixels outside declared RGBA palette")
    if args.expect_size and tuple(args.expect_size) != image.size:
        failures.append(f"size: expected {args.expect_size}, got {[width, height]}")
    alpha = image.getchannel("A")
    alpha_range, alpha_histogram = list(alpha.getextrema()), alpha.histogram()
    if args.opaque and alpha_range[0] != 255:
        failures.append("opacity: non-opaque pixels found")
    if args.binary_alpha and sum(alpha_histogram[1:255]):
        failures.append("alpha: semi-transparent pixels found under binary-alpha requirement")
    for key in REQUIRED[args.symmetry]:
        if symmetry[key] is None:
            failures.append(f"symmetry: {key} requires a square image/frame region")
        elif not symmetry[key]["exact"]:
            failures.append(f"symmetry: {key} is not exact")
    tiling = image_tile_metrics(prepared if args.symmetry_space == "rgba" else comparison_image(image)) if args.tile or args.match_edges else None
    if args.match_edges:
        for key in ("left_right_edges", "top_bottom_edges"):
            if not tiling[key]["exact"]:
                failures.append(f"edges: {key} do not match")
    clusters = cluster_metrics(pixels, width, height) if args.clusters or args.max_isolated_pixels is not None else None
    if args.max_isolated_pixels is not None and clusters["isolated_pixels"] > args.max_isolated_pixels:
        failures.append(f"clusters: {clusters['isolated_pixels']} isolated pixels exceed {args.max_isolated_pixels}")
    return {
        "size": [width, height],
        "alpha_range": alpha_range,
        "alpha_coverage": {"transparent_percent": alpha_histogram[0] / (width * height) * 100,
                           "semi_transparent_percent": sum(alpha_histogram[1:255]) / (width * height) * 100,
                           "opaque_percent": alpha_histogram[255] / (width * height) * 100},
        "visible_geometry": image_geometry(image, args.alpha_cutoff),
        "symmetry": symmetry,
        "symmetry_space": args.symmetry_space,
        "tiling": tiling,
        "clusters": clusters,
        "palette": palette,
        "failed_requirements": failures,
        "constraints_passed": not failures,
    }


def draw_panel(sheet, panel, x0, y0, background):
    draw = ImageDraw.Draw(sheet)
    if background == "checker":
        for y in range(y0, y0 + panel.height, 8):
            for x in range(x0, x0 + panel.width, 8):
                shade = "#354154" if ((x - x0) // 8 + (y - y0) // 8) % 2 else "#283244"
                draw.rectangle((x, y, min(x + 7, x0 + panel.width - 1), min(y + 7, y0 + panel.height - 1)), fill=shade)
    else:
        draw.rectangle((x0, y0, x0 + panel.width - 1, y0 + panel.height - 1),
                       fill="#f1f3f5" if background == "light" else "#10151b")
    sheet.alpha_composite(panel, (x0, y0))


def tiled_image(image):
    repeated = Image.new("RGBA", (image.width * 3, image.height * 3))
    for y in range(3):
        for x in range(3):
            repeated.paste(image, (x * image.width, y * image.height))
    return repeated


def preview_sheet(image, output, scale, tiled, before=None, backgrounds=("checker",), display_size=None):
    area = sum(candidate.width * candidate.height * (1 + scale * scale * (10 if tiled else 1))
               + (display_size[0] * display_size[1] if display_size else 0)
               for candidate in (before, image) if candidate is not None) * len(backgrounds)
    if area > 16_000_000:
        raise ValueError("preview exceeds 16M pixels; reduce scale/backgrounds or select a region")
    panels = []
    for label, candidate in (("Before", before), ("After" if before is not None else "", image)):
        if candidate is None:
            continue
        width, height = candidate.size
        for background in backgrounds:
            suffix = f" on {background}" if tuple(backgrounds) != ("checker",) else ""
            panels.extend([(f"{label} Native {width} x {height}{suffix}".strip(), candidate, background),
                           (f"{label} Nearest x{scale}{suffix}".strip(), candidate.resize(
                               (width * scale, height * scale), Image.Resampling.NEAREST), background)])
            if display_size:
                panels.append((f"{label} Display {display_size[0]} x {display_size[1]}{suffix}".strip(),
                               candidate.resize(tuple(display_size), Image.Resampling.NEAREST), background))
    if tiled:
        for label, candidate in (("Before", before), ("After" if before is not None else "", image)):
            if candidate is None:
                continue
            repeated = tiled_image(candidate)
            for background in backgrounds:
                panels.append(((f"{label} 3 x 3 tiling" + (f" on {background}" if tuple(backgrounds) != ("checker",) else "")).strip(),
                               repeated.resize((repeated.width * scale, repeated.height * scale), Image.Resampling.NEAREST), background))
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [max(144, panel.width + 16, measure.textbbox((0, 0), label)[2] + 16) for label, panel, _ in panels]
    dimensions = (sum(widths) + 16, max(panel.height for _, panel, _ in panels) + 64)
    if dimensions[0] * dimensions[1] > 16_000_000:
        raise ValueError("preview exceeds 16M pixels; reduce scale/backgrounds or select a region")
    sheet = Image.new("RGBA", dimensions, "#131c28")
    draw = ImageDraw.Draw(sheet)
    offset = 8
    for (label, panel, background), panel_width in zip(panels, widths):
        draw.text((offset + 8, 10), label, fill="#e0e9f4")
        x0, y0 = offset + (panel_width - panel.width) // 2, 36
        draw_panel(sheet, panel, x0, y0, background)
        offset += panel_width
    result = sheet.convert("RGB")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format="PNG")
    return result


def animation_preview(frames, output, scale, backgrounds=("checker",), display_size=None, tiled=False):
    area = sum(frame.width * frame.height * (1 + scale * scale * (10 if tiled else 1))
               + (display_size[0] * display_size[1] if display_size else 0)
               for frame in frames) * len(backgrounds)
    if area > 16_000_000:
        raise ValueError("frame sheet exceeds 16M pixels; reduce scale/backgrounds or use the timed player")
    entries = []
    for index, frame in enumerate(frames):
        panels = [("Native", frame), (f"x{scale}", frame.resize((frame.width * scale, frame.height * scale), Image.Resampling.NEAREST))]
        if display_size:
            panels.append(("Display", frame.resize(tuple(display_size), Image.Resampling.NEAREST)))
        if tiled:
            tile = tiled_image(frame)
            panels.append(("3x3", tile.resize((tile.width * scale, tile.height * scale), Image.Resampling.NEAREST)))
        entries.extend((index, panels, background) for background in backgrounds)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    def segment_width(label, panel):
        return max(panel.width, measure.textbbox((0, 0), label)[2]) + 8
    cell_width = max(144, max(sum(segment_width(label, panel) for label, panel in panels) + 8 for _, panels, _ in entries))
    cell_height = max(panel.height for _, panels, _ in entries for _, panel in panels) + 60
    columns = max(1, min(8, len(entries), 1600 // cell_width))
    rows = (len(entries) + columns - 1) // columns
    if columns * cell_width * rows * cell_height > 16_000_000:
        raise ValueError("frame sheet exceeds 16M pixels; reduce scale/backgrounds or use the timed player")
    sheet = Image.new("RGBA", (columns * cell_width, rows * cell_height), "#131c28")
    draw = ImageDraw.Draw(sheet)
    for position, (index, panels, background) in enumerate(entries):
        x0, y0 = position % columns * cell_width, position // columns * cell_height
        draw.text((x0 + 8, y0 + 8), f"Frame {index} / {background}", fill="#e0e9f4")
        x = x0 + 8
        for label, panel in panels:
            draw.text((x, y0 + 24), label, fill="#a8b8c9")
            draw_panel(sheet, panel, x, y0 + 42, background)
            x += segment_width(label, panel)
    result = sheet.convert("RGB")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format="PNG")
    coverage = {"frame_indices": list(range(len(frames))), "all_frames": True,
            "backgrounds": list(backgrounds), "display_size": display_size,
            "note": "All strip frames shown. This sheet is not timed playback and does not interpret animation metadata."}
    return coverage if output is not None else (result, coverage)


def load_png(path):
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError(f"input must be a PNG: {path}")
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError(f"APNG is not supported; review explicit native frames or a declared strip, not only the first frame: {path}")
        return source.convert("RGBA")
