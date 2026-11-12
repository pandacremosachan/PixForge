"""Package the skill with its generated Windows portable application."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(skill, output):
    skill, output = Path(skill).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Choose a new archive path; existing deliveries are not overwritten.')
    metadata = json.loads((skill / 'skill.json').read_text(encoding='utf-8'))
    if metadata.get('transport') != 'resident-http' or 'client' in metadata or 'client_runtime' in metadata:
        raise ValueError('The skill must use the resident command interface without an external client.')
    application = PurePosixPath(metadata['bundled_application'])
    if application.is_absolute() or '..' in application.parts or ':' in str(application):
        raise ValueError('Bundled application must use a skill-relative path.')
    executable = (skill / application).resolve()
    if not executable.is_relative_to(skill):
        raise ValueError('Bundled application must remain inside the skill.')
    runtime = executable.parent
    manifest_path = runtime / 'package-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    description = json.loads((runtime / 'application.json').read_text(encoding='utf-8'))
    if (not {'resident-http', 'command-line'} <= set(description.get('interfaces', ()))
            or description.get('public_api_version') not in metadata['supported_public_api_versions']):
        raise ValueError('The bundled application does not expose the required executable commands.')
    if manifest['version'] != metadata['software_baseline']:
        raise ValueError('Bundled application does not match the skill software baseline.')
    if (runtime / 'pixforge-development.json').exists():
        raise ValueError('Development installations cannot be distributed as portable software.')
    for required in (executable, runtime / 'application.json', runtime / 'command-help.json', runtime / 'backend/python.exe',
                     runtime / 'backend/python312.dll', runtime / 'backend/python312._pth'):
        if not required.is_file():
            raise ValueError('Incomplete portable application: ' + str(required))

    selected = {}
    for relative in ('SKILL.md', 'skill.json', 'INSTALL.md'):
        selected[relative] = skill / relative
    for folder in ('agents', 'assets', 'references', 'scripts'):
        for path in sorted((skill / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
                selected[path.relative_to(skill).as_posix()] = path

    # Only immutable application release files, never a later workspace/session.
    runtime_prefix = runtime.relative_to(skill).as_posix()
    for name, expected in manifest['files'].items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name
                or relative.parts[0] in ('workspace', '.runtime') or '__pycache__' in relative.parts):
            raise ValueError('Invalid application manifest path: ' + name)
        path = runtime / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Application release file changed or missing: ' + name)
        selected[runtime_prefix + '/' + name] = path
    selected[runtime_prefix + '/package-manifest.json'] = manifest_path

    sources = {name: digest(path) for name, path in selected.items() if not name.startswith(runtime_prefix + '/')}
    distribution = {
        'schema': 'pixforge.skill-distribution/v1', 'skill_version': metadata['version'],
        'application_version': manifest['version'], 'platform': 'windows-x64',
        'portable': True, 'installation_required': False,
        'application': metadata['bundled_application'],
        'application_manifest_sha256': digest(manifest_path), 'skill_files': sources,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pixforge-package-', dir=output.parent) as temporary:
        staged = Path(temporary) / 'delivery.zip'
        with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, path in sorted(selected.items()):
                archive.write(path, 'pixelforge/' + name)
            archive.writestr('pixelforge/distribution.json', json.dumps(distribution, ensure_ascii=False, indent=2) + '\n')
        staged.rename(output)
    return {'archive': str(output), 'bytes': output.stat().st_size, 'sha256': digest(output),
            'files': len(selected) + 1, 'skill_version': metadata['version'], 'application_version': manifest['version']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, default=ROOT / '.agents/skills/pixelforge')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(package(arguments.skill, arguments.output), ensure_ascii=False, indent=2))
