# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for package in (
    "librosa", "numpy", "scipy", "soundfile", "audioread",
    "numba", "llvmlite", "imageio_ffmpeg",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += ["structure_engine"]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["torch", "tensorflow", "onnxruntime", "matplotlib", "seaborn", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="BanjofySongAnalysisLab025",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
