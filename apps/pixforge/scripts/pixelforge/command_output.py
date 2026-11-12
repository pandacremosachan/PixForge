"""Application-owned command response artifacts and exit status."""
import base64
from pathlib import Path
import uuid


def artifacts(data, runtime):
    """Discussion images stay files, never base64 blobs in command output."""
    data = dict(data)
    image, html = data.pop('image', None), data.pop('html', None)
    if image or html:
        folder = runtime / 'previews'
        folder.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex
        if image:
            existing = data.get('preview_path') or data.get('capture', {}).get('path')
            if existing:
                data['preview_path'] = existing
            else:
                path = folder / (name + '.png')
                with path.open('xb') as stream:
                    stream.write(base64.b64decode(image, validate=True))
                data['preview_path'] = str(path)
        if html:
            path = folder / (name + '.html')
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(html)
            data['html_path'] = str(path)
    return data


def exit_code(data):
    code = data.get('code', '')
    if code in ('INVALID_ARGUMENT', 'UNKNOWN_ACTION'):
        return 2
    if code in ('REVISION_CONFLICT', 'DOCUMENT_CONFLICT', 'FILE_CONFLICT'):
        return 3
    if code == 'FILE_EXISTS':
        return 4
    if code == 'BUSY' or 'TIMEOUT' in code:
        return 5
    if 'APPROV' in code or 'CONFIRM' in code or 'STALE' in code or 'FINGERPRINT' in code:
        return 6
    if code in ('SESSION_UNAVAILABLE', 'NATIVE_UNAVAILABLE', 'DESKTOP_UNAVAILABLE'):
        return 7
    return 1


