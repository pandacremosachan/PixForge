"""PixForge: a pixel-drawing tool designed for AI models.

The AI expresses pixels through a compact text protocol (palette + char grids,
RLE rows, or raw RGBA patches) and reads the canvas back the same way.
Use the public CLI help for the command reference.
"""
from .canvas import Canvas, Layer
from .palette import Palette, parse_color
from .protocol import Executor, PixForgeError
from .document import Document, StudioError
from .session import Session

__all__ = ["Canvas", "Layer", "Palette", "parse_color", "Executor", "PixForgeError", "Document", "Session", "StudioError"]
