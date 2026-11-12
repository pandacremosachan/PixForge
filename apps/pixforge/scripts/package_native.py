"""Assemble the Windows desktop and commands with a private CPython/Pillow core.

The frontend is C++. Python is retained only for the existing independent core;
no Qt bindings or global installation are included or required by this bundle.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import sysconfig
import tempfile
import zipfile


def build(binary, output):
    binary, output = Path(binary).resolve(), Path(output).resolve()
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Build with the existing Windows CPython 3.12 core environment.')
    if output.exists():
        raise FileExistsError('Choose a new output folder; never replace an existing delivery implicitly.')
    output.mkdir(parents=True)
    backend = output/'backend';backend.mkdir()
    shutil.copy2(binary, output/'PixForgeNative.exe')
    shutil.copy2(binary.with_name('command-help.json'), output/'command-help.json')
    base = Path(sys.base_prefix)
    for name in ('python.exe','pythonw.exe','python312.dll','python3.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        source = base/name
        if source.is_file():shutil.copy2(source, backend/name)
    if not (backend/'python312.dll').exists():raise RuntimeError('Missing CPython runtime DLL.')
    dlls = backend/'DLLs';dlls.mkdir()
    for source in (base/'DLLs').iterdir():
        if source.suffix.lower() in ('.dll','.pyd') and not source.name.startswith(('_test','_tkinter','tcl','tk')):
            shutil.copy2(source, dlls/source.name)
    excluded = {'site-packages','test','tests','unittest','doctest.py','tkinter','turtledemo','idlelib','ensurepip','__pycache__'}
    with zipfile.ZipFile(backend/'python312.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source in sorted((base/'Lib').rglob('*')):
            relative = source.relative_to(base/'Lib')
            if source.is_file() and source.suffix in ('.py','.txt','.json','.pickle') and not any(p in excluded for p in relative.parts):
                archive.write(source, relative.as_posix())
    (backend/'python312._pth').write_text('python312.zip\nDLLs\nsite-packages\n.\nimport site\n',encoding='utf-8',newline='\n')
    packages = backend/'site-packages';packages.mkdir()
    site = Path(sysconfig.get_paths()['purelib'])
    required_packages = {'pil', 'pillow.libs', 'pydantic', 'pydantic_core', 'annotated_types', 'typing_inspection', 'typing_extensions.py'}
    required_metadata = ('pillow-', 'pydantic-', 'pydantic_core-', 'annotated_types-', 'typing_extensions-', 'typing_inspection-')
    for source in site.iterdir():
        lower = source.name.lower()
        if (lower not in required_packages and not lower.startswith(required_metadata)) or source.suffix in ('.pth','.pyc'):continue
        destination = packages/source.name
        if source.is_dir():shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc','direct_url.json','tests','test','test_*.py','*_test.py'))
        elif source.suffix in ('.py','.pyd','.dll','.typed'):shutil.copy2(source,destination)
    source_root = Path(__file__).resolve().parent
    icon_source=source_root/'native'/'assets'
    if icon_source.is_dir():
        shutil.copytree(icon_source,output/'icons')
    shutil.copy2(source_root.parent/'public-api.json',output/'application.json')
    shutil.copy2(source_root.parent/'PUBLIC_API.md',output/'PUBLIC_API.md')
    shutil.copy2(source_root.parent/'MINECRAFT_ASSETS.md',output/'MINECRAFT_ASSETS.md')
    shutil.copy2(source_root.parent/'FORGE_RUNTIME.md',output/'FORGE_RUNTIME.md')
    shutil.copy2(source_root.parent/'MINECRAFT_PREVIEW.md',output/'MINECRAFT_PREVIEW.md')
    shutil.copy2(source_root.parent/'MINECRAFT_RUNTIME_WORKBENCH.md',output/'MINECRAFT_RUNTIME_WORKBENCH.md')
    shutil.copy2(source_root.parent/'MINECRAFT_MATERIAL_DATA.md',output/'MINECRAFT_MATERIAL_DATA.md')
    shutil.copytree(source_root/'pixelforge',packages/'pixelforge',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    metadata=packages/'pixelforge-4.1.1.dist-info';metadata.mkdir()
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: pixelforge\nVersion: 4.1.1\nSummary: PixForge independent pixel, animation, shape and scene core\n',encoding='utf-8')
    (metadata/'WHEEL').write_text('Wheel-Version: 1.0\nGenerator: PixForge native local packager\nRoot-Is-Purelib: true\nTag: py3-none-any\n',encoding='utf-8')
    notice=source_root.parent/'THIRD_PARTY_NOTICES.md'
    if notice.exists():shutil.copy2(notice,output/'THIRD_PARTY_NOTICES.md')
    examples=source_root.parent/'examples'
    if examples.is_dir():
        shutil.copytree(examples,output/'examples',ignore=shutil.ignore_patterns('.runtime','__pycache__','*.pyc'))
    readme=(source_root.parent/'README.md').read_text(encoding='utf-8')
    (output/'使用说明.md').write_text(readme,encoding='utf-8',newline='\n')
    files={str(p.relative_to(output)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    import json
    (output/'package-manifest.json').write_text(json.dumps({'version':'4.1.1','frontend':'C++20/Win32/OpenGL','core':'bundled CPython 3.12/Pillow/Pydantic','qt_included':False,'files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New application directory or standalone portable .zip')
    args=parser.parse_args()
    if args.output.suffix.lower() == '.zip':
        destination = args.output.resolve()
        if destination.exists():
            parser.error('Choose a new archive path; existing deliveries are not overwritten.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pixforge-pack-', dir=destination.parent) as stage:
            package = build(args.binary, Path(stage) / 'PixForge')
            archive = shutil.make_archive(str(Path(stage) / 'delivery'), 'zip', stage, package.name)
            Path(archive).rename(destination)
        print(destination)
    else:
        print(build(args.binary,args.output))
