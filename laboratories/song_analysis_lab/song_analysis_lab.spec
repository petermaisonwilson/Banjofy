# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH)
chordmini = project_root / "ChordMini"

datas = [(str(chordmini), "ChordMini")]
binaries = []
hiddenimports = []

for package in (
    "torch", "librosa", "soundfile", "scipy", "sklearn", "yaml",
    "mir_eval", "tqdm", "audioread", "numba", "llvmlite",
    "imageio_ffmpeg", "matplotlib", "seaborn", "pandas",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += [
    "analysis_engine",
    "src", "src.evaluation", "src.evaluation.utils", "src.models", "src.utils",
    "seaborn", "seaborn.axisgrid", "seaborn.categorical",
    "seaborn.distributions", "seaborn.matrix", "seaborn.regression",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root), str(chordmini)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tensorflow", "onnxruntime", "basic_pitch"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="BanjofySongAnalysisLab001",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
