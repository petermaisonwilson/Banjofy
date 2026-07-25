# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH)
img_datas, img_binaries, img_hiddenimports = collect_all("imageio_ffmpeg")

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=img_binaries,
    datas=img_datas,
    hiddenimports=img_hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="BanjofyFirefoxAcquisitionLab002",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
