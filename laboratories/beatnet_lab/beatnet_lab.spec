# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import imageio_ffmpeg

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(ffmpeg, '.')],
    datas=[],
    hiddenimports=[
        'BeatNet', 'BeatNet.BeatNet', 'BeatNet.model', 'BeatNet.log_spect',
        'BeatNet.particle_filtering_cascade', 'madmom', 'madmom.features',
        'madmom.features.downbeats', 'madmom.features.beats',
        'librosa', 'soundfile', 'scipy', 'mido', 'yaml',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['pytest','tensorboard'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BanjofyBeatNetLab001',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
               upx_exclude=[], name='BanjofyBeatNetLab001')
