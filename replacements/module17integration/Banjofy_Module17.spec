# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

SRC_DIR = os.path.abspath("src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

hiddenimports = []
hiddenimports += collect_submodules("banjofy")
hiddenimports += collect_submodules("yt_dlp")
hiddenimports += collect_submodules("yt_dlp_plugins")
hiddenimports += collect_submodules("curl_cffi")
hiddenimports += [
    "torch",
    "librosa",
    "soundfile",
    "yaml",
    "mir_eval",
    "sklearn",
    "pandas",
    "matplotlib",
    "seaborn",
    "tqdm",
]

a = Analysis(
    ["src/main.py"],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[("ChordMini", "ChordMini")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Banjofy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
