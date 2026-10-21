"""Atomic drawing batches and staged file publication; no changes during a dry run."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from PIL import Image, ImageChops


@dataclass
class BatchResult:
    messages: list[str]
    summary: dict
    canvas: object
    preview: object = None


def canvas_digest(canvas):
    if canvas is None:
        return None
    digest = hashlib.sha256(json.dumps({"size": [canvas.w, canvas.h], "active": canvas.active_index,
        "mirror": canvas.mirror, "palette": canvas.palette.chars}, sort_keys=True).encode())
    for layer in canvas.layers:
        digest.update(json.dumps([layer.name, layer.visible]).encode())
        digest.update(layer.img.tobytes())
    return digest.hexdigest()


def change_summary(before, after):
    if before is None and after is None:
        return {"size_before": None, "size_after": None, "changed_pixels": 0, "changed_region": None,
                "changed_layers": []}
    width = max(c.w for c in (before, after) if c is not None)
    height = max(c.h for c in (before, after) if c is not None)
    views = []
    for canvas in (before, after):
        view = Image.new("RGBA", (width, height))
        if canvas is not None:
            view.paste(canvas.composite(), (0, 0))
        views.append(view)
    channels = ImageChops.difference(*views).split()
    mask = channels[0]
    for channel in channels[1:]:
        mask = ImageChops.lighter(mask, channel)
    box = mask.getbbox()
    previous = {layer.name: (layer.visible, layer.img.size, layer.img.tobytes()) for layer in before.layers} if before else {}
    current = {layer.name: (layer.visible, layer.img.size, layer.img.tobytes()) for layer in after.layers} if after else {}
    return {"size_before": [before.w, before.h] if before else None,
            "size_after": [after.w, after.h] if after else None,
            "changed_pixels": width * height - mask.histogram()[0],
            "changed_region": [box[0], box[1], box[2] - box[0], box[3] - box[1]] if box else None,
            "changed_layers": [name for name in dict.fromkeys([*previous, *current]) if previous.get(name) != current.get(name)]}


def commit_files(outputs):
    """Stage every file before replacing any target; roll back a failed publication.

    Atomic to callers on ordinary exceptions, not a crash-safe filesystem transaction.
    Each individual replacement is atomic. Only explicit output paths are touched.
    """
    staged, backups, published = {}, {}, []
    try:
        for path, content in outputs.items():
            path = Path(path)
            if path.exists() and not path.is_file():
                raise OSError(f"Output is not a file: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".pixelforge-", dir=path.parent)
            staged[path] = Path(temporary)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
            if path.exists():
                fd, temporary = tempfile.mkstemp(prefix=".pixelforge-backup-", dir=path.parent)
                backups[path] = Path(temporary)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(path.read_bytes())
            else:
                backups[path] = None
        for path, temporary in staged.items():
            os.replace(temporary, path)
            published.append(path)
    except OSError as error:
        recovery = []
        for path in reversed(published):
            try:
                if backups[path] is None:
                    path.unlink()
                else:
                    os.replace(backups[path], path)
            except OSError:
                recovery.append(str(backups.pop(path, None) or path))
        if recovery:
            raise OSError(f"{error}; rollback incomplete; retained recovery files: {recovery}") from error
        raise
    finally:
        for path in [*staged.values(), *(value for value in backups.values() if value is not None)]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # Cleanup failure must not turn a committed transaction into an
                # apparent failure with an unchanged in-memory canvas.
                pass
