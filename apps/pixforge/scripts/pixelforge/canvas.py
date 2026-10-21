"""Layered RGBA canvas with mirror-symmetry drawing and snapshot undo."""
import base64
import io

from PIL import Image, ImageDraw

from .palette import Palette


class Layer:
    __slots__ = ("name", "img", "visible")

    def __init__(self, name: str, w: int, h: int):
        self.name = name
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.visible = True


class Canvas:
    UNDO_LIMIT = 50

    def __init__(self, w: int, h: int):
        if type(w) is not int or type(h) is not int or not (1 <= w <= 4096 and 1 <= h <= 4096):
            raise ValueError(f"canvas size must be 1..4096 per side, got {w}x{h}")
        self.w = w
        self.h = h
        self.layers: list[Layer] = [Layer("main", w, h)]
        self.active_index = 0
        self.mirror = False
        self.palette = Palette()
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []

    # ------------------------------------------------------------ layers
    @property
    def active(self) -> Layer:
        return self.layers[self.active_index]

    def layer_named(self, name: str) -> Layer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise KeyError(f"no layer named {name!r} (layers: {self.layer_names()})")

    def layer_names(self) -> list[str]:
        return [l.name for l in self.layers]

    def add_layer(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise KeyError("layer name must not be empty")
        if any(l.name == name for l in self.layers):
            raise KeyError(f"layer {name!r} already exists")
        if len(self.layers) >= 16:
            raise KeyError("layer limit is 16")
        self.layers.append(Layer(name, self.w, self.h))
        self.active_index = len(self.layers) - 1

    def remove_layer(self, name: str) -> None:
        if len(self.layers) == 1:
            raise KeyError("cannot remove the last layer")
        if name not in self.layer_names():
            raise KeyError(f"no layer named {name!r}")
        idx = next(i for i, l in enumerate(self.layers) if l.name == name)
        del self.layers[idx]
        self.active_index = min(self.active_index, len(self.layers) - 1)

    def use_layer(self, name: str) -> None:
        self.active_index = self.layer_names().index(name)

    # ------------------------------------------------------------ undo
    def _snapshot(self) -> tuple:
        return (self.w, self.h, [(l.name, l.img.copy(), l.visible) for l in self.layers],
                self.active_index, self.mirror, self.palette.chars.copy())

    def _restore(self, snap: tuple) -> None:
        self.w, self.h, layers, active, self.mirror, colors = snap
        self.palette = Palette()
        self.palette.chars = colors.copy()
        self.layers = [Layer(n, self.w, self.h) for n, _, _ in layers]
        for layer, (_, img, visible) in zip(self.layers, layers):
            layer.img = img.copy()
            layer.visible = visible
        self.active_index = min(active, len(self.layers) - 1)

    def clone(self) -> "Canvas":
        result = Canvas(self.w, self.h)
        result._restore(self._snapshot())
        # History snapshots are immutable; restoring one always copies its pixels.
        result._undo = list(self._undo)
        result._redo = list(self._redo)
        return result

    def push_undo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > self.UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    # ------------------------------------------------------------ drawing
    @staticmethod
    def _tile_from_pixels(pixels: list[tuple[int, int, int, int]], w: int, h: int) -> Image:
        buf = bytearray()
        for px in pixels:
            buf += bytes(px)
        return Image.frombytes("RGBA", (w, h), bytes(buf))

    def _paste_clipped(self, tile: Image, x: int, y: int) -> None:
        img = self.active.img
        sx = max(0, -x)
        sy = max(0, -y)
        dx = max(0, x)
        dy = max(0, y)
        w = min(tile.width - sx, self.w - dx)
        h = min(tile.height - sy, self.h - dy)
        if w > 0 and h > 0:
            img.paste(tile.crop((sx, sy, sx + w, sy + h)), (dx, dy))

    def apply_tile(self, tile: Image, x: int, y: int) -> None:
        """Paste tile replacing pixels (alpha written as-is). Honors mirror."""
        self._paste_clipped(tile, x, y)
        if self.mirror:
            self._paste_clipped(tile.transpose(Image.FLIP_LEFT_RIGHT), self.w - x - tile.width, y)

    def set_pixel(self, x: int, y: int, rgba: tuple[int, int, int, int]) -> None:
        self.push_undo()
        self._set_pixel_raw(x, y, rgba)

    def _set_pixel_raw(self, x: int, y: int, rgba: tuple[int, int, int, int]) -> None:
        self._paste_clipped(self._tile_from_pixels([rgba], 1, 1), x, y)
        if self.mirror:
            self._paste_clipped(self._tile_from_pixels([rgba], 1, 1), self.w - 1 - x, y)

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int, rgba: tuple[int, int, int, int]) -> None:
        """Inclusive-corner rect fill; clipped to canvas. Honors mirror."""
        self.push_undo()
        self._fill_rect_raw(x0, y0, x1, y1, rgba)

    def _fill_rect_raw(self, x0: int, y0: int, x1: int, y1: int, rgba) -> None:
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if x1 < 0 or y1 < 0 or x0 >= self.w or y0 >= self.h:
            return
        draw = ImageDraw.Draw(self.active.img)
        draw.rectangle([x0, y0, min(x1, self.w - 1), min(y1, self.h - 1)], fill=rgba)
        if self.mirror:
            mx0, mx1 = self.w - 1 - x1, self.w - 1 - x0
            if mx1 < 0 or mx0 >= self.w:
                return
            draw.rectangle(
                [max(mx0, 0), y0, min(mx1, self.w - 1), min(y1, self.h - 1)], fill=rgba
            )

    # ------------------------------------------------------------ output
    def composite(self) -> Image:
        out = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for layer in self.layers:
            if layer.visible:
                out.alpha_composite(layer.img)
        return out

    def region(self, x: int, y: int, w: int, h: int) -> Image:
        return self.composite().crop((x, y, x + w, y + h))

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {
            "w": self.w,
            "h": self.h,
            "mirror": self.mirror,
            "active": self.active.name,
            "palette": {ch: list(c) for ch, c in self.palette.chars.items()},
            "layers": [
                {
                    "name": l.name,
                    "visible": l.visible,
                    "data": base64.b64encode(l.img.tobytes()).decode("ascii"),
                }
                for l in self.layers
            ],
        }

    def save(self, path: str) -> None:
        import json
        import os

        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: str) -> "Canvas":
        import json

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Canvas":
        if not isinstance(data, dict):
            raise ValueError("session must be a JSON object")
        canvas = cls(data["w"], data["h"])
        if type(data.get("mirror", False)) is not bool:
            raise ValueError("mirror must be boolean")
        canvas.mirror = data.get("mirror", False)
        if not isinstance(data.get("palette", {}), dict):
            raise ValueError("palette must be an object")
        for ch, c in data.get("palette", {}).items():
            if not isinstance(c, (list, tuple)) or len(c) != 4 or any(type(n) is not int or not 0 <= n <= 255 for n in c):
                raise ValueError("palette entries must be RGBA bytes")
            canvas.palette.define(ch, tuple(c))
        if not isinstance(data.get("layers"), list) or not 1 <= len(data["layers"]) <= 16:
            raise ValueError("session must contain 1..16 layers")
        canvas.layers = []
        for ld in data["layers"]:
            if not isinstance(ld, dict) or not isinstance(ld.get("name"), str) or not ld["name"].strip() or ld["name"] in canvas.layer_names():
                raise ValueError("layer names must be nonempty and unique")
            if type(ld.get("visible", True)) is not bool:
                raise ValueError("layer visibility must be boolean")
            layer = Layer(ld["name"], canvas.w, canvas.h)
            layer.visible = ld.get("visible", True)
            raw = base64.b64decode(ld["data"], validate=True)
            if len(raw) != canvas.w * canvas.h * 4:
                raise ValueError("layer pixel byte count does not match canvas dimensions")
            layer.img = Image.frombytes("RGBA", (canvas.w, canvas.h), raw)
            canvas.layers.append(layer)
        canvas.active_index = canvas.layer_names().index(data.get("active", canvas.layers[0].name))
        return canvas

    def render_png(self, scale: int, path: str | None = None) -> Image.Image:
        img = self.composite()
        if scale != 1:
            img = img.resize((self.w * scale, self.h * scale), Image.NEAREST)
        if path:
            import os

            d = os.path.dirname(os.path.abspath(path))
            os.makedirs(d, exist_ok=True)
            img.save(path)
        return img

    def layer_png_bytes(self, layer: Layer) -> bytes:
        buf = io.BytesIO()
        layer.img.save(buf, "PNG")
        return buf.getvalue()
