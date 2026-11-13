"""Encode discussion/resource images without feature-specific dependencies."""
import base64
import io


def png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def png_base64(image):
    return base64.b64encode(png(image)).decode("ascii")
