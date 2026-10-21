"""Color parsing and char-to-RGBA palette mapping."""
import re

HEX_RE = re.compile(r"^([0-9a-fA-F]+)$")

TRANSPARENT = (0, 0, 0, 0)
# '.' is always fully transparent and cannot be redefined.
TRANSPARENT_CHAR = "."

# Chars handed out by `read` when it needs a fresh palette entry,
# in allocation order. Chars already taken by the user palette are skipped.
# Digits are excluded on purpose: RLE rows use digits as run counts.
CHAR_POOL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+*/#$%&@!?;:=<>[]{}()"


def parse_color(text: str) -> tuple[int, int, int, int]:
    """Parse #rgb / #rgba / #rrggbb / #rrggbbaa ('#' optional) into RGBA."""
    s = text.strip().lstrip("#")
    m = HEX_RE.match(s)
    if not m:
        raise PixColorError(f"invalid color {text!r}: expected hex like #rrggbb or #rrggbbaa")
    h = m.group(1)
    if len(h) == 3:
        r, g, b = (int(c * 2, 16) for c in h)
        return (r, g, b, 255)
    if len(h) == 4:
        r, g, b, a = (int(c * 2, 16) for c in h)
        return (r, g, b, a)
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    if len(h) == 8:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
    raise PixColorError(
        f"invalid color {text!r}: hex must have 3, 4, 6 or 8 digits (got {len(h)})"
    )


def color_to_hex(rgba: tuple[int, int, int, int]) -> str:
    return "".join(f"{v:02x}" for v in rgba)


class PixColorError(ValueError):
    pass


class Palette:
    """Maps single non-space chars to RGBA tuples."""

    def __init__(self) -> None:
        self.chars: dict[str, tuple[int, int, int, int]] = {}

    def define(self, char: str, rgba: tuple[int, int, int, int]) -> None:
        if len(char) != 1 or char.isspace():
            raise PixColorError(f"palette char must be one non-space char, got {char!r}")
        if char == TRANSPARENT_CHAR:
            raise PixColorError(f"char {TRANSPARENT_CHAR!r} is reserved for transparency")
        if char.isdigit():
            raise PixColorError(f"digit {char!r} cannot be a palette char (RLE uses digits as counts)")
        self.chars[char] = rgba

    def color_for(self, char: str) -> tuple[int, int, int, int] | None:
        if char == TRANSPARENT_CHAR:
            return TRANSPARENT
        return self.chars.get(char)

    def char_for(self, rgba: tuple[int, int, int, int]) -> str | None:
        """Existing char for this exact color, or None."""
        if rgba == TRANSPARENT:
            return TRANSPARENT_CHAR
        for ch, c in self.chars.items():
            if c == rgba:
                return ch
        return None

    def alloc_char(self) -> str:
        taken = set(self.chars)
        for ch in CHAR_POOL:
            if ch not in taken:
                return ch
        raise PixColorError("palette is full: no free chars left")

    def spec_string(self, only: dict[str, tuple[int, int, int, int]] | None = None) -> str:
        entries = self.chars if only is None else only
        return " ".join(f"{ch}={color_to_hex(c)}" for ch, c in sorted(entries.items()))
