import os
import sys

import uv
from PyInstaller.utils.hooks import collect_submodules, copy_metadata


project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = []
for distribution in ("uv", "zigpy", "zha", "zha-quirks"):
    datas += copy_metadata(distribution)

uv_binary = uv.find_uv_bin()
hiddenimports = [
    "zigpy.types",
    "zigpy.quirks",
    "zigpy.zcl.foundation",
    "zhaquirks.builder",
]
hiddenimports += collect_submodules("zhaquirks.builder")

analysis = Analysis(
    [os.path.join(project_root, "src", "zha_quirk_builder", "__main__.py")],
    pathex=[os.path.join(project_root, "src")],
    binaries=[(uv_binary, ".")],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

if sys.platform == "win32":
    executable = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name="ZHA Quirk Builder",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
    )
else:
    executable = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name="ZHA Quirk Builder",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
    )
    bundle_files = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=True,
        name="ZHA Quirk Builder",
    )
    application = BUNDLE(
        bundle_files,
        name="ZHA Quirk Builder.app",
        icon=None,
        bundle_identifier="io.github.faronov.zha-quirk-builder",
        info_plist={
            "CFBundleDisplayName": "ZHA Quirk Builder",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
