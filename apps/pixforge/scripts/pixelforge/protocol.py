"""Text command protocol: parse + execute PixForge scripts.

Commands are one per line; `grid`, `rle` and `patch` take a payload made of
the following raw lines, terminated by a blank line or the next command.
All errors carry absolute coordinates so a model can self-correct.
`read` emits a copy-pasteable script fragment.
"""
import re
import io
import json
from pathlib import Path
from collections import Counter

from .canvas import Canvas
from .palette import CHAR_POOL, TRANSPARENT, TRANSPARENT_CHAR, Palette, color_to_hex, parse_color

COMMANDS = {
    "new", "layer", "mirror", "palette", "grid", "rle", "patch", "set",
    "rect", "clear", "read", "render", "save", "load", "undo", "redo",
    "info", "stats",
}

INT_RE = re.compile(r"^[+-]?\d+$")
RLE_TOKEN_RE = re.compile(r"(\d*)(\S)")
READ_MAX_COLORS = 64


class PixForgeError(Exception):
    pass


def _int(token: str, what: str) -> int:
    if not INT_RE.match(token):
        raise PixForgeError(f"{what} must be an integer, got {token!r}")
    return int(token)


def _color(token: str, what: str = "color") -> tuple[int, int, int, int]:
    try:
        return parse_color(token)
    except ValueError as e:
        raise PixForgeError(f"{what}: {e}") from e


def _need_canvas(canvas: Canvas | None) -> Canvas:
    if canvas is None:
        raise PixForgeError("no canvas: run 'new W H' first")
    return canvas


class Executor:
    """Parses and runs PixForge scripts against one canvas session."""

    def __init__(self, canvas: Canvas | None = None):
        self.canvas = canvas
        self._pending_outputs = None
        self._input_paths = set()

    def run_batch(self, text: str, *, dry_run: bool = False, output=None, scale=1, save=None,
                  include_preview=False, preview_path=None, preview_options=None, publish_outputs=True):
        """Execute on a clone; publish outputs and one undo step only after success."""
        from .transactions import BatchResult, canvas_digest, change_summary, commit_files

        candidate = Executor(self.canvas.clone() if self.canvas is not None else None)
        candidate._pending_outputs = {}
        messages = candidate.run_script(text)
        if output is not None and save is not None and Path(output).resolve() == Path(save).resolve():
            raise PixForgeError("PNG and session output paths must be distinct")
        if output is not None:
            messages.extend(candidate.cmd_render([str(output), str(scale)], []))
        if save is not None:
            messages.extend(candidate.cmd_save([str(save)], []))
        evidence = None
        evidence_files = {}
        if include_preview or preview_path is not None:
            from .preview import render_canvas
            evidence = render_canvas(candidate.canvas, **(preview_options or {}))
            if preview_path is not None:
                path = Path(preview_path).resolve()
                if path in candidate._pending_outputs or path in candidate._input_paths:
                    raise PixForgeError("preview must not overwrite a production PNG or session output")
                buffer = io.BytesIO()
                evidence.save(buffer, format="PNG")
                evidence_files[path] = buffer.getvalue()
        summary = change_summary(self.canvas, candidate.canvas)
        changed = canvas_digest(self.canvas) != canvas_digest(candidate.canvas)
        summary.update(dry_run=dry_run, state_changed=changed,
                       outputs=[str(path) for path in candidate._pending_outputs])
        if preview_path is not None:
            summary["preview"] = str(Path(preview_path).resolve())
        if not dry_run:
            if candidate.canvas is not None:
                baseline = self.canvas or Canvas(candidate.canvas.w, candidate.canvas.h)
                candidate.canvas._undo = list(self.canvas._undo) if self.canvas else []
                candidate.canvas._redo = list(self.canvas._redo) if self.canvas else []
                if canvas_digest(baseline) != canvas_digest(candidate.canvas):
                    candidate.canvas._undo.append(baseline._snapshot())
                    candidate.canvas._undo = candidate.canvas._undo[-candidate.canvas.UNDO_LIMIT:]
                    candidate.canvas._redo.clear()
            commit_files({**(candidate._pending_outputs if publish_outputs else {}), **evidence_files})
            self.canvas = candidate.canvas
        else:
            commit_files(evidence_files)
            messages = ["planned: " + message if message.startswith(("saved ", "session saved:")) else message for message in messages]
        if not publish_outputs:
            summary["deferred_outputs"] = summary["outputs"]
            summary["outputs"] = []
            messages = ["deferred export: " + message if message.startswith(("saved ", "session saved:")) else message for message in messages]
        return BatchResult(messages, summary, candidate.canvas, evidence)

    def run_script(self, text: str) -> list[str]:
        out: list[str] = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            parts = stripped.split()
            cmd = parts[0].lower()
            lineno = i + 1
            payload: list[str] = []
            if cmd not in COMMANDS:
                raise PixForgeError(
                    f"line {lineno}: unknown command {parts[0]!r} "
                    f"(known: {', '.join(sorted(COMMANDS))})"
                )
            if cmd in ("grid", "rle", "patch"):
                j = i + 1
                while j < len(lines):
                    s = lines[j].strip()
                    if not s or s.startswith("#") or s.split()[0].lower() in COMMANDS:
                        break
                    payload.append(s)
                    j += 1
                i = j
            else:
                i += 1
            try:
                out.extend(self._dispatch(cmd, parts[1:], payload))
            except PixForgeError as e:
                raise PixForgeError(f"line {lineno} [{cmd}]: {e}") from None
            except (ValueError, KeyError) as e:  # e.g. PixColorError, bad layer name
                raise PixForgeError(f"line {lineno} [{cmd}]: {str(e).strip(chr(39))}") from None
        return out

    # ------------------------------------------------------------- dispatch
    def _dispatch(self, cmd: str, args: list[str], payload: list[str]) -> list[str]:
        handler = getattr(self, f"cmd_{cmd}")
        return handler(args, payload)

    def _check_no_payload(self, payload: list[str]) -> None:
        if payload:
            raise PixForgeError("this command does not take payload lines")

    # ------------------------------------------------------------- commands
    def cmd_new(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        if len(args) != 2:
            raise PixForgeError("usage: new W H")
        w, h = _int(args[0], "W"), _int(args[1], "H")
        self.canvas = Canvas(w, h)
        return [f"new canvas {w}x{h} (layer: main)"]

    def cmd_layer(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if not args:
            raise PixForgeError("usage: layer add|use|show|hide|remove|list [NAME]")
        sub, name = args[0].lower(), (args[1] if len(args) > 1 else None)
        if sub == "list":
            marks = [
                ("*" if i == canvas.active_index else "") + l.name + ("" if l.visible else " (hidden)")
                for i, l in enumerate(canvas.layers)
            ]
            return ["layers: " + "  ".join(marks)]
        canvas.push_undo()
        try:
            if sub == "add":
                if not name:
                    raise PixForgeError("usage: layer add NAME")
                canvas.add_layer(name)
                return [f"layer added+active: {name}"]
            if sub == "use":
                if not name:
                    raise PixForgeError("usage: layer use NAME")
                canvas.use_layer(name)
                return [f"active layer: {name}"]
            if sub in ("show", "hide"):
                if not name:
                    raise PixForgeError(f"usage: layer {sub} NAME")
                layer = canvas.layer_named(name)
                layer.visible = sub == "show"
                return [f"layer {name}: visible={layer.visible}"]
            if sub == "remove":
                if not name:
                    raise PixForgeError("usage: layer remove NAME")
                canvas.remove_layer(name)
                return [f"layer removed: {name}"]
        except KeyError as e:
            raise PixForgeError(str(e).strip("'")) from None
        raise PixForgeError(f"unknown layer subcommand {sub!r} (add/use/show/hide/remove/list)")

    def cmd_mirror(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) != 1 or args[0].lower() not in ("on", "off"):
            raise PixForgeError("usage: mirror on|off")
        canvas.mirror = args[0].lower() == "on"
        return [f"mirror={canvas.mirror}"]

    def cmd_palette(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if not args:
            raise PixForgeError("usage: palette CHAR=#rrggbbaa CHAR=#rrggbb ...")
        for spec in args:
            if "=" not in spec:
                raise PixForgeError(f"palette spec {spec!r} must be CHAR=#hex")
            ch, color = spec.split("=", 1)
            canvas.palette.define(ch, _color(color, f"palette {ch}"))
        return [f"palette ({len(canvas.palette.chars)}): {canvas.palette.spec_string()}"]

    def cmd_grid(self, args: list[str], payload: list[str]) -> list[str]:
        canvas = _need_canvas(self.canvas)
        if len(args) != 2:
            raise PixForgeError("usage: grid X Y  (char rows follow as payload)")
        if not payload:
            raise PixForgeError("grid needs payload rows (end them with a blank line)")
        x, y = _int(args[0], "X"), _int(args[1], "Y")
        width = len(payload[0])
        pixels: list[tuple[int, int, int, int]] = []
        for r, row in enumerate(payload):
            if len(row) != width:
                raise PixForgeError(
                    f"payload row {r} has {len(row)} chars, expected {width} (row 0 length); "
                    f"absolute y={y + r}"
                )
            for c, ch in enumerate(row):
                color = canvas.palette.color_for(ch)
                if color is None:
                    raise PixForgeError(
                        f"payload row {r} col {c} (canvas {x + c},{y + r}): char {ch!r} "
                        f"is not defined; palette has: {TRANSPARENT_CHAR} "
                        f"{' '.join(canvas.palette.chars) or '(empty)'}"
                    )
                pixels.append(color)
        tile = Canvas._tile_from_pixels(pixels, width, len(payload))
        canvas.push_undo()
        canvas.apply_tile(tile, x, y)
        return [f"grid {width}x{len(payload)} at ({x},{y}) mirror={canvas.mirror}"]

    def cmd_rle(self, args: list[str], payload: list[str]) -> list[str]:
        canvas = _need_canvas(self.canvas)
        if len(args) != 2:
            raise PixForgeError("usage: rle X Y  (run rows follow as payload, e.g. '4H2.6H')")
        if not payload:
            raise PixForgeError("rle needs payload rows (end them with a blank line)")
        x, y = _int(args[0], "X"), _int(args[1], "Y")
        width = None
        pixels: list[tuple[int, int, int, int]] = []
        for r, row in enumerate(payload):
            consumed = 0
            row_pixels: list[tuple[int, int, int, int]] = []
            for m in RLE_TOKEN_RE.finditer(row):
                count = int(m.group(1)) if m.group(1) else 1
                ch = m.group(2)
                consumed += len(m.group(1)) + 1
                if ch.isdigit():
                    raise PixForgeError(
                        f"payload row {r}: digit {ch!r} in char position — "
                        f"every run count needs a palette char after it "
                        f"(e.g. 4H not 4), and digits cannot be palette chars"
                    )
                color = canvas.palette.color_for(ch)
                if color is None:
                    raise PixForgeError(
                        f"payload row {r} (canvas y={y + r}): char {ch!r} is not defined; "
                        f"palette has: {TRANSPARENT_CHAR} {' '.join(canvas.palette.chars) or '(empty)'}"
                    )
                if count > 4096:
                    raise PixForgeError(f"payload row {r}: run length {count} > 4096")
                row_pixels.extend([color] * count)
            if consumed != len(row):
                raise PixForgeError(
                    f"payload row {r}: {len(row) - consumed} trailing digit(s) have no char"
                )
            if width is None:
                width = len(row_pixels)
            elif len(row_pixels) != width:
                raise PixForgeError(
                    f"payload row {r} decodes to {len(row_pixels)} px, expected {width} (row 0)"
                )
            pixels.extend(row_pixels)
        tile = Canvas._tile_from_pixels(pixels, width, len(payload))
        canvas.push_undo()
        canvas.apply_tile(tile, x, y)
        return [f"rle {width}x{len(payload)} at ({x},{y}) mirror={canvas.mirror}"]

    def cmd_patch(self, args: list[str], payload: list[str]) -> list[str]:
        canvas = _need_canvas(self.canvas)
        if len(args) != 4:
            raise PixForgeError("usage: patch X Y W H  (rows of rrggbbaa cells follow)")
        if not payload:
            raise PixForgeError("patch needs payload rows (end them with a blank line)")
        x, y = _int(args[0], "X"), _int(args[1], "Y")
        w, h = _int(args[2], "W"), _int(args[3], "H")
        if len(payload) != h:
            raise PixForgeError(f"patch expected {h} payload rows, got {len(payload)}")
        pixels: list[tuple[int, int, int, int]] = []
        for r, row in enumerate(payload):
            cells = row.split()
            if len(cells) != w:
                raise PixForgeError(
                    f"payload row {r} has {len(cells)} cells, expected {w} (canvas y={y + r})"
                )
            for c, cell in enumerate(cells):
                if cell == TRANSPARENT_CHAR:
                    pixels.append(TRANSPARENT)
                else:
                    try:
                        pixels.append(parse_color(cell))
                    except ValueError as e:
                        raise PixForgeError(
                            f"payload row {r} cell {c} (canvas {x + c},{y + r}): {e}"
                        ) from None
        tile = Canvas._tile_from_pixels(pixels, w, h)
        canvas.push_undo()
        canvas.apply_tile(tile, x, y)
        return [f"patch {w}x{h} at ({x},{y}) mirror={canvas.mirror}"]

    def cmd_set(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) != 3:
            raise PixForgeError("usage: set X Y #rrggbbaa")
        x, y = _int(args[0], "X"), _int(args[1], "Y")
        if not (0 <= x < canvas.w and 0 <= y < canvas.h):
            raise PixForgeError(f"set ({x},{y}) is outside canvas {canvas.w}x{canvas.h}")
        canvas.set_pixel(x, y, _color(args[2]))
        return [f"set ({x},{y})"]

    def cmd_rect(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) != 5:
            raise PixForgeError("usage: rect X0 Y0 X1 Y1 #rrggbbaa  (inclusive corners)")
        x0, y0, x1, y1 = (_int(a, "coord") for a in args[:4])
        canvas.fill_rect(x0, y0, x1, y1, _color(args[4]))
        return [f"rect ({x0},{y0})-({x1},{y1})"]

    def cmd_clear(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) != 4:
            raise PixForgeError("usage: clear X0 Y0 X1 Y1  (inclusive corners)")
        x0, y0, x1, y1 = (_int(a, "coord") for a in args)
        canvas.fill_rect(x0, y0, x1, y1, TRANSPARENT)
        return [f"cleared ({x0},{y0})-({x1},{y1})"]

    def cmd_read(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) not in (4, 5) or (len(args) == 5 and args[4] != "raw"):
            raise PixForgeError("usage: read X Y W H [raw]")
        x, y, w, h = (_int(a, "coord") for a in args[:4])
        if w < 1 or h < 1:
            raise PixForgeError("read W and H must be >= 1")
        if x < 0 or y < 0 or x + w > canvas.w or y + h > canvas.h:
            raise PixForgeError(
                f"read region ({x},{y}) {w}x{h} exceeds canvas {canvas.w}x{canvas.h}"
            )
        img = canvas.region(x, y, w, h)
        data = img.tobytes()
        raw = [tuple(data[i:i + 4]) for i in range(0, len(data), 4)]
        def raw_fragment():
            out = [f"# read raw ({x},{y}) {w}x{h}", f"patch {x} {y} {w} {h}"]
            for r in range(h):
                out.append(" ".join(color_to_hex(raw[r * w + c]) for c in range(w)))
            return out
        colors = dict.fromkeys(raw)
        new_colors = sum(canvas.palette.char_for(color) is None for color in colors)
        available = sum(char not in canvas.palette.chars for char in CHAR_POOL)
        if len(args) == 5 or len(colors) > READ_MAX_COLORS or new_colors > available:
            return raw_fragment()
        new_defs: dict[str, tuple[int, int, int, int]] = {}
        char_of: dict[tuple[int, int, int, int], str] = {}
        for color in colors:  # distinct, row-major first-seen order
            ch = canvas.palette.char_for(color)
            if ch is None:
                ch = canvas.palette.alloc_char()
                canvas.palette.define(ch, color)
            char_of[color] = ch
            if ch != TRANSPARENT_CHAR:
                new_defs[ch] = color  # emit every used char so the fragment is self-contained
        rows = ["".join(char_of[raw[r * w + c]] for c in range(w)) for r in range(h)]
        if any(row.startswith("#") or row.lower() in COMMANDS for row in rows):
            return raw_fragment()
        out = [f"# read ({x},{y}) {w}x{h}, {len(char_of)} colors"]
        if new_defs:
            out.append("palette " + " ".join(f"{c}={color_to_hex(v)}" for c, v in new_defs.items()))
        out.append(f"grid {x} {y}")
        out.extend(rows)
        return out

    def cmd_render(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) not in (1, 2):
            raise PixForgeError("usage: render PATH [SCALE]")
        scale = _int(args[1], "SCALE") if len(args) == 2 else 1
        if not (1 <= scale <= 64):
            raise PixForgeError("SCALE must be 1..64")
        img = canvas.render_png(scale, args[0] if self._pending_outputs is None else None)
        if self._pending_outputs is not None:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            self._pending_outputs[Path(args[0]).resolve()] = buffer.getvalue()
        return [f"saved {args[0]} ({img.width}x{img.height}, scale {scale})"]

    def cmd_save(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) != 1:
            raise PixForgeError("usage: save PATH")
        if self._pending_outputs is None:
            canvas.save(args[0])
        else:
            self._pending_outputs[Path(args[0]).resolve()] = json.dumps(canvas.to_dict()).encode("utf-8")
        return [f"session saved: {args[0]}"]

    def cmd_load(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        if len(args) != 1:
            raise PixForgeError("usage: load PATH")
        path = Path(args[0]).resolve()
        self._input_paths.add(path)
        if self._pending_outputs is not None and path in self._pending_outputs:
            self.canvas = Canvas.from_dict(json.loads(self._pending_outputs[path]))
        else:
            self.canvas = Canvas.load(args[0])
        return [f"session loaded: {args[0]} ({self.canvas.w}x{self.canvas.h})"]

    def cmd_undo(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if not canvas.undo():
            return ["nothing to undo"]
        return ["undo ok"]

    def cmd_redo(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if not canvas.redo():
            return ["nothing to redo"]
        return ["redo ok"]

    def cmd_info(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        layers = "  ".join(
            ("*" if i == canvas.active_index else "") + l.name + ("" if l.visible else " (hidden)")
            for i, l in enumerate(canvas.layers)
        )
        pal = canvas.palette.spec_string()
        return [
            f"canvas {canvas.w}x{canvas.h}  mirror={'on' if canvas.mirror else 'off'}",
            f"layers: {layers}",
            f"palette ({len(canvas.palette.chars)}): {pal if pal else '(empty)'}",
        ]

    def cmd_stats(self, args: list[str], payload: list[str]) -> list[str]:
        self._check_no_payload(payload)
        canvas = _need_canvas(self.canvas)
        if len(args) == 4:
            x, y, w, h = (_int(a, "coord") for a in args)
            if x < 0 or y < 0 or w < 1 or h < 1 or x + w > canvas.w or y + h > canvas.h:
                raise PixForgeError(
                    f"stats region ({x},{y}) {w}x{h} exceeds canvas {canvas.w}x{canvas.h}"
                )
            region_img = canvas.region(x, y, w, h)
        elif not args:
            x, y, w, h = 0, 0, canvas.w, canvas.h
            region_img = canvas.composite()
        else:
            raise PixForgeError("usage: stats [X Y W H]")
        counts = Counter(region_img.getdata())
        out = [f"# stats ({x},{y}) {w}x{h}, {len(counts)} distinct colors, top:"]
        for color, n in counts.most_common(16):
            out.append(f"  #{color_to_hex(color)} x{n}")
        return out
