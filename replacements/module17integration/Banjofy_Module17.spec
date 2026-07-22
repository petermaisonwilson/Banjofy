# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH)
src_dir = project_root / "src"
chordmini = project_root / "ChordMini"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(chordmini) not in sys.path:
    sys.path.insert(0, str(chordmini))

datas = [(str(chordmini), "ChordMini")]
binaries = []
hiddenimports = []

for package in (
    "torch", "librosa", "soundfile", "scipy", "sklearn", "yaml",
    "mir_eval", "tqdm", "audioread", "numba", "llvmlite",
    "imageio_ffmpeg", "matplotlib", "seaborn", "pandas",
    "yt_dlp", "curl_cffi", "PySide6",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

# Collect only the active Banjofy modules required by Module 17.
# Do not blindly collect legacy banjofy.engine, which imports a retired Beat model.
hiddenimports += collect_submodules("banjofy.ui")
hiddenimports += collect_submodules("banjofy.analysis")
hiddenimports += collect_submodules("banjofy.download")
hiddenimports += collect_submodules("banjofy.storage")
hiddenimports += collect_submodules("banjofy.models")
hiddenimports += collect_submodules("banjofy.services")
hiddenimports += collect_submodules("yt_dlp_plugins")

hiddenimports += [
    "src", "src.evaluation", "src.evaluation.utils", "src.models", "src.utils",
    "seaborn", "seaborn.axisgrid", "seaborn.categorical",
    "seaborn.distributions", "seaborn.matrix", "seaborn.regression",
]

a = Analysis(
    ["src/main.py"],
    pathex=[str(src_dir), str(chordmini)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "banjofy.engine",
        "tensorflow",
        "onnxruntime",
        "basic_pitch",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
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
