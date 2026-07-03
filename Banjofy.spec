# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.building.datastruct import Tree

block_cipher = None

SRC_DIR = os.path.abspath('src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

datas = []
datas += collect_data_files('imageio_ffmpeg')
datas += collect_data_files('librosa')

# Build 006.2C:
# Bundle the actual Banjofy source tree as runtime data.
datas += Tree(os.path.join('src', 'banjofy'), prefix=os.path.join('banjofy_src', 'banjofy'))

hiddenimports = []
hiddenimports += ['PySide6.QtMultimedia']
hiddenimports += collect_submodules('imageio_ffmpeg')
hiddenimports += collect_submodules('librosa')
hiddenimports += [
    'banjofy',
    'banjofy.app',
    'banjofy.ui',
    'banjofy.ui.main_window',
]

try:
    hiddenimports += collect_submodules('banjofy')
except Exception:
    pass

a = Analysis(
    ['src/main.py'],
    pathex=[SRC_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Banjofy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
