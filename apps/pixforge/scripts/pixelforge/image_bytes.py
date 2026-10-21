"""Encode discussion/resource images without feature-specific dependencies."""
import io


def png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
