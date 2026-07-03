# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

SRC_DIR = os.path.abspath('src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

datas = []
datas += collect_data_files('imageio_ffmpeg')
datas += collect_data_files('librosa')

hiddenimports = []
hiddenimports += ['PySide6.QtMultimedia']
hiddenimports += [
    'banjofy',
    'banjofy.app',
    'banjofy.ui',
    'banjofy.ui.main_window',
    'banjofy.ui.widgets',
    'banjofy.ui.chord_grid',
    'banjofy.ui.youtube_panel',
    'banjofy.ui.analysis_panel',
    'banjofy.ui.song_info',
    'banjofy.audio',
    'banjofy.audio.analyser',
    'banjofy.banjo',
    'banjofy.banjo.chords',
    'banjofy.player',
    'banjofy.player.demo_data',
    'banjofy.player.playback_engine',
    'banjofy.youtube',
    'banjofy.youtube.search',
    'banjofy.youtube.downloader',
    'banjofy.library',
    'banjofy.models',
    'banjofy.models.song',
    'banjofy.models.beat',
    'banjofy.models.beat_map',
    'banjofy.models.chord_event',
    'banjofy.engine',
    'banjofy.engine.song_adapter',
]
hiddenimports += collect_submodules('imageio_ffmpeg')
hiddenimports += collect_submodules('librosa')
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
