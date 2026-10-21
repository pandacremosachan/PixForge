"""Assemble an offline Windows native desktop with a private CPython/Pillow/MCP core.

The frontend is C++. Python is retained only for the existing independent core;
no Qt bindings or global installation are included or required by this bundle.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import sysconfig
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
    (backend/'python312._pth').write_text('python312.zip\nDLLs\nsite-packages\nsite-packages/win32\nsite-packages/win32/lib\nsite-packages/Pythonwin\nsite-packages/pywin32_system32\n.\nimport site\n',encoding='utf-8',newline='\n')
    packages = backend/'site-packages';packages.mkdir()
    site = Path(sysconfig.get_paths()['purelib'])
    skipped = ('pyside6','shiboken6','pip','setuptools','wheel','_distutils_hack','pixelforge','_virtualenv','__pycache__','hatchling','editables','_pixelforge')
    for source in site.iterdir():
        lower = source.name.lower()
        if lower.startswith(skipped) or source.suffix in ('.pth','.pyc'):continue
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
    (packages/'sitecustomize.py').write_text('import os\nfrom pathlib import Path\n_directory = Path(__file__).parent / "pywin32_system32"\n_dll_handles = [os.add_dll_directory(str(_directory))] if _directory.exists() and hasattr(os, "add_dll_directory") else []\n',encoding='utf-8',newline='\n')
    shutil.copytree(source_root/'pixelforge',packages/'pixelforge',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    metadata=packages/'pixelforge-2.9.0.dist-info';metadata.mkdir()
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: pixelforge\nVersion: 2.9.0\nSummary: PixForge independent pixel, animation, shape and scene core\n',encoding='utf-8')
    (metadata/'WHEEL').write_text('Wheel-Version: 1.0\nGenerator: PixForge native local packager\nRoot-Is-Purelib: true\nTag: py3-none-any\n',encoding='utf-8')
    (output/'打开PixForge.cmd').write_text('@echo off\nstart "PixForge" "%~dp0PixForgeNative.exe" --workspace "%~dp0workspace"\n',encoding='utf-8',newline='\r\n')
    notice=source_root.parent/'THIRD_PARTY_NOTICES.md'
    if notice.exists():shutil.copy2(notice,output/'THIRD_PARTY_NOTICES.md')
    examples=source_root.parent/'examples'
    if examples.is_dir():
        shutil.copytree(examples,output/'examples',ignore=shutil.ignore_patterns('.runtime','__pycache__','*.pyc'))
        for title,kind,alias in [('打开场景动画示例.cmd','scene-animation','scene'),('打开关键帧与状态示例.cmd','keyframe-states','state')]:
            (output/title).write_text(f'@echo off\nstart "PixForge example" "%~dp0PixForgeNative.exe" --cli gui "%~dp0examples\\{kind}\\{alias}-demo.pixforge" --workspace "%~dp0workspace" --runtime "%~dp0workspace\\.runtime\\{alias}-demo"\n',encoding='utf-8',newline='\r\n')
        if (examples/'forge-1.20.1/target-demo.pixforge').is_file():
            (output/'打开Minecraft资源示例.cmd').write_text('@echo off\nstart "PixForge Minecraft example" "%~dp0PixForgeNative.exe" --cli gui "%~dp0examples\\forge-1.20.1\\target-demo.pixforge" --workspace "%~dp0workspace" --runtime "%~dp0workspace\\.runtime\\minecraft-demo"\n',encoding='utf-8',newline='\r\n')
        if (examples/'forge-runtime-1.20.1/runtime-demo.pixforge').is_file():
            (output/'打开Forge模组接入示例.cmd').write_text('@echo off\nstart "PixForge Forge integration example" "%~dp0PixForgeNative.exe" --cli gui "%~dp0examples\\forge-runtime-1.20.1\\runtime-demo.pixforge" --workspace "%~dp0workspace" --runtime "%~dp0workspace\\.runtime\\forge-runtime-demo"\n',encoding='utf-8',newline='\r\n')
    if (output/'examples/forge-preview-1.20.1/preview-demo.pixforge').is_file():
        (output/'打开Minecraft渲染示例.cmd').write_text('@echo off\nstart "PixForge render example" "%~dp0PixForgeNative.exe" --workspace "%~dp0examples\\forge-preview-1.20.1" --runtime "%~dp0workspace\\.runtime\\minecraft-preview-demo" --open "%~dp0examples\\forge-preview-1.20.1\\preview-demo.pixforge" --open-minecraft-preview "%~dp0examples\\forge-preview-1.20.1\\preview.json"\n',encoding='utf-8',newline='\r\n')
    if (output/'examples/forge-runtime-678-1.20.1/machine-runtime.pixforge').is_file():
        for title,project,session in [('打开机器实例与回归示例.cmd','machine-runtime.pixforge','machine-runtime-demo')]:
            (output/title).write_text(f'@echo off\nstart "PixForge runtime example" "%~dp0PixForgeNative.exe" --workspace "%~dp0examples\\forge-runtime-678-1.20.1" --runtime "%~dp0workspace\\.runtime\\{session}" --open "%~dp0examples\\forge-runtime-678-1.20.1\\{project}" --open-minecraft-workbench\n',encoding='utf-8',newline='\r\n')
    readme='''# PixForge C++ 2.9.0 · Windows

双击 `打开PixForge.cmd` 或 `PixForgeNative.exe`。完整保留此文件夹中的 `backend`。无需安装 Python 或 Qt，也不需要安装 C++ 编译器。

EXE 会自动启动随包核心，无须先打开 CLI 或后台服务。可以从其他工作目录启动，默认工作区仍位于 EXE 旁的 `workspace`。下载后须完整解压压缩包；只复制一个 EXE 到桌面会缺少 `backend`，需要桌面入口时可为原目录的 EXE 创建快捷方式。

程序、窗口与任务栏使用紫色体素方块和橙色火花图标。图标已嵌入 EXE，`icons/pixforge.ico` 同时提供独立的多尺寸 Windows 图标；透明 PNG 原图和生成说明也保存在 `icons`。

软件与配套 skill 分别安装、版本管理和更新。软件不读取 skill 文件；skill 只通过本软件公开的 `--describe`、`--cli`、`--mcp` 入口调用，不访问私有运行环境。公开接口主版本为 1，完整约定见 `PUBLIC_API.md`；`application.json` 是软件公开的安装描述。更新软件时保留自己的 `workspace` 和外部工程。

桌面界面、像素交互与实时模型预览由 C++/Win32 实现。OpenGL 可用时复用 GPU 几何与纹理；不支持时自动使用 C++ 软件渲染。现有独立核心继续使用随包 Python/Pillow，负责工程、共享历史、CLI/MCP与导出校验。

默认作品与会话位于本文件夹的 `workspace`。打开已有工程不会重绘或自动批准导出。保存可编辑工程始终可用；正式图片和形状导出仍需当前版本的真实用户确认。

```powershell
# 指定项目及共享会话
.\\PixForgeNative.exe --workspace D:\\your-project --runtime D:\\your-project\\.runtime\\pixelforge-desktop
# 模型通过 CLI/MCP 调用同一核心
.\\PixForgeNative.exe --cli session --runtime D:\\your-project\\.runtime\\pixelforge-desktop status
.\\PixForgeNative.exe --mcp --workspace D:\\your-project --runtime D:\\your-project\\.runtime\\pixelforge-desktop
# 读取桌面命令结构、工具状态和鼠标命中检查
.\\PixForgeNative.exe --cli ui --runtime D:\\your-project\\.runtime\\pixelforge-desktop help
.\\PixForgeNative.exe --cli ui --runtime D:\\your-project\\.runtime\\pixelforge-desktop controls
```

“文件 → 新建工程”（Ctrl+N）先选择模型：六面独立、六面共用、导入模型 JSON 或纯像素画布。窗口先展示 UV 布局和模型几何，再确认纹理尺寸；创建时一次性绑定空白画布、模型和 UV，不使用祭坛固定布局。修改尺寸后更新预览才可创建，取消不改变原工程。空白纹理显示真实模型线框，开始绘制后显示实际贴图。

AI 与桌面直接编辑同一工程。先读取当前工程 ID 和 revision，修改时提交这两个版本令牌；冲突后重读。模型面域使用 model-uv 查询，绘图、模型、材质帧和场景分别调用对应接口，不要求登记阶段、签发计划或填写验收回执。需要增加动画源帧时，session animation-prepare 接受 frame_count 和可选 steps/loop/interpolation，保留已有像素和图层，可一次撤销。预览与工程保存始终可用，正式导出仍绑定用户对当前内容的明确确认。

部件运动与粒子由 C++ 实时预览：在“模型与形状”面板下部载入场景 JSON，或由 AI 的动画设计接口准备。支持旋转、平移、缩放、发射方向/扰动、初速度、重力、寿命、尺寸与颜色渐变，以及透明/加色混合；移动喷口仅影响出生时的位置和方向。底部场景时钟和时间条可连续定位，暂停后恢复保留当前时间；材质帧可以只有一张。默认目标为 Forge / Minecraft 1.20.1，可在 scene.target 覆盖。场景随工程保存、撤销和恢复，改动使旧确认失效。session animation-capabilities、session scene-sample 与 ui scene-sample 可查询能力和数值。HTML 动画预览也播放部件与粒子，正式接入仍需真实模组的渲染器、粒子注册和状态同步；当前没有自定义着色器、世界碰撞或 Minecraft 光照。

通用关键帧与状态编辑器位于“动画 → 关键帧与状态编辑器…”以及“模型与形状”面板顶部。可以创建、复制、命名和删除状态，设置片段时长、循环、启动/停机事件、结束后的自动状态以及完整流程。旋转、平移、缩放和粒子发射强度均可编辑明确的时间、值与插值；支持保持、线性、平滑、缓入、缓出。已有周期运动可在草稿中采样为关键帧。先校验并查看当前模型的草稿预览，再一次应用到工程；取消不改变作品，应用可一次撤销。状态切换保留部件姿态与已经飞出的粒子；完整流程和单个状态均可在时间轴上预览。随包 `打开关键帧与状态示例.cmd` 使用独立示例工程，不修改已有作品。

左侧第一项为平移，后续是画笔、橡皮、填充、吸管、直线、矩形、椭圆、矩形选区和移动。启动、打开或新建工程后默认选择平移，避免意外落笔。画布上的平移光标使用张手，拖动时切为抓手；空格和中键临时平移使用同样的反馈。悬浮可看中文说明和快捷键，点击会切换到像素画布。吸管快捷键 I，右键或 Alt 临时取色。M 框选、V 移动，Ctrl+A 全选当前帧，Ctrl+D/Esc 取消选区，Ctrl+C/X/V 复制/剪切/粘贴，Delete 清空选区；方向键微调，Shift 移动十像素。剪贴板保留 RGBA，粘贴裁切到当前帧，编辑共用撤销。像素和模型预览固定使用透明棋盘背景，工具栏不再提供背景切换。网格、平铺、洋葱皮、镜像、形状填充、循环播放、模型与形状叠加、图层显示中的开关项统一使用滑动开关：开启时紫色轨道、滑块在右，关闭时灰色轨道、滑块在左；轨道为 28 × 16 的紧凑尺寸，整组标签仍可点击，状态名称保留在辅助信息与命令接口中；点击标签或开关均可切换，快捷键与命令接口同步状态。鼠标点击不绘制外围白框，Tab 键导航时使用细主题色焦点提示。载入带 UV 的模型后，顶部“面域”开关显示真实区域边界，画布不显示遮挡像素的文字标签；右侧“面域”页签列出部件、局部面方向及共用关系；悬停画布查看全部对应面，Ctrl+单击或点击面域条目固定，点击“已固定”一行解除。辅助线不写入图层或 PNG。替换模型与其 UV 时保留已有像素，不自动重排纹理；新模型与贴图布局需要配套。AI 可用 session model-uv / MCP model_uv 查询同样的映射。模型页可直接拖动旋转；时间轴遵循真实步骤和毫秒时长。`PIXFORGE_DISABLE_GPU=1` 可用于诊断软件渲染路径。

本文件夹是本地交付，不宣称原有 PixForge 源码具有新增的开源授权。CPython 许可位于 `backend/LICENSE.txt`，依赖元数据与许可证保留在 `backend/site-packages/*dist-info/`。本次交付不包含 Qt、私人作品、旧会话令牌或客户端配置。
'''
    (output/'使用说明.md').write_text(readme,encoding='utf-8',newline='\n')
    with (output/'使用说明.md').open('a',encoding='utf-8',newline='\n') as guide:
        guide.write('''\n## Minecraft 目标与资源\n\n“资源”菜单提供目标配置、引用检查和版本化导出。第一项适配器支持 Forge / Minecraft Java 1.20.1，资源格式 15；目录、ZIP 和 JAR 来源按优先级解析，依赖来源不随包分发。配置及历史随工程保存，检查会追踪父模型、纹理别名、状态与物品、动画元数据和图集生成精灵的真实输入。正式资源导出重新检查指纹，并沿用当前版本的用户确认。详见 MINECRAFT_ASSETS.md。\n\n旧工程未配置目标时保持原格式；配置目标后使用 v2 元数据，需 PixForge 2.3+，旧软件会拒绝而不静默丢失设置。离线检查不代表游戏内验收，资源 ZIP 不会自动安装到游戏或修改模组源码。

软件 2.4 的 Forge 接入草稿与只读代码预览保留部件关键帧 / 状态和粒子。资源菜单可导出现有模组接入包或可构建示例模组；代码由独立软件生成，skill 只调用公开接口。实际服务端运行状态和同步须接到消费项目，不能用离线面板状态冒充机器检测。随包“打开Forge模组接入示例.cmd”打开原创合成工程，未自动批准导出。具体接线、构建和验证见 FORGE_RUNTIME.md。配置运行时后工程 / 历史使用 v3，需要软件 2.4+；旧工程继续保留原格式。\n''')
    with (output/'使用说明.md').open('a',encoding='utf-8',newline='\n') as guide:
        guide.write('\nForge 1.20.1 rendering preview: open Resources / 资源 → Minecraft 模型与渲染预览…, or run 打开Minecraft渲染示例.cmd. Sampling, state/display contexts, separate tint and controlled light/AO are read-only. See MINECRAFT_PREVIEW.md for CLI/MCP options and verification scope.\n')
    with (output/'使用说明.md').open('a',encoding='utf-8',newline='\n') as guide:
        guide.write('\nPixForge 2.6: 资源 → Minecraft 动画与场景回归…，提供 .mcmeta 制作、实例启停 / 卸载恢复、整场景统计及游戏捕获比较。打开机器实例与回归示例.cmd 使用独立测试会话。游戏回归命令仅随显式启用的 Forge 导出生成；不会自动启动游戏或修改存档。详见 MINECRAFT_RUNTIME_WORKBENCH.md。\n')
    if (output/'examples/forge-labpbr-1.20.1/material-demo.pixforge').is_file():
        (output/'打开LabPBR数据材质示例.cmd').write_text('@echo off\nstart "PixForge LabPBR example" "%~dp0PixForgeNative.exe" --workspace "%~dp0examples\\forge-labpbr-1.20.1" --runtime "%~dp0workspace\\.runtime\\labpbr-demo" --open "%~dp0examples\\forge-labpbr-1.20.1\\material-demo.pixforge" --open-material-editor\n',encoding='utf-8',newline='\r\n')
    with (output/'使用说明.md').open('a',encoding='utf-8',newline='\n') as guide:
        guide.write('\nPixForge 2.7: 资源菜单的 LabPBR 数据材质编辑器分别查看和编辑八个原始数据通道，数据 alpha 保留为高度或发光数值。打开LabPBR数据材质示例.cmd 提供原创工程和可选诊断 shader，未自动安装或批准导出。数据工程及恢复历史使用 v4，需要软件 2.7+；普通工程保留旧格式。详见 MINECRAFT_MATERIAL_DATA.md。\n')
    files={str(p.relative_to(output)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    import json
    (output/'package-manifest.json').write_text(json.dumps({'version':'2.9.0','frontend':'C++20/Win32/OpenGL','core':'bundled CPython 3.12/Pillow/MCP','qt_included':False,'files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(build(args.binary,args.output))
