# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules
import imageio_ffmpeg

datas=[]
binaries=[]
hiddenimports=[]

for package in ['numpy','scipy','madmom','librosa','BeatNet']:
    d,b,h=collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

for package in ['numpy','scipy','madmom']:
    binaries += collect_dynamic_libs(package)
    hiddenimports += collect_submodules(package)

hiddenimports += collect_submodules('BeatNet')

ffmpeg=Path(imageio_ffmpeg.get_ffmpeg_exe())
if ffmpeg.is_file():
    binaries.append((str(ffmpeg),'.'))

a=Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest','tensorboard'],
    noarchive=False,
)
pyz=PYZ(a.pure)
exe=EXE(
    pyz,a.scripts,[],
    exclude_binaries=True,
    name='BanjofyBeatNetLab007',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll=COLLECT(
    exe,a.binaries,a.zipfiles,a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BanjofyBeatNetLab007',
)
