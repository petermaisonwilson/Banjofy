# -*- mode: python ; coding: utf-8 -*-
from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules
import imageio_ffmpeg


# PyInstaller resolves relative paths in a spec relative to the spec directory.
# Use explicit absolute paths from SPECPATH so CI cannot accidentally duplicate
# laboratories/beatnet_lab in entry-point or runtime-hook paths.
spec_root = Path(SPECPATH).resolve()
main_script = spec_root / "main.py"
dll_hook = spec_root / "dll_hook.py"
if not main_script.is_file():
    raise RuntimeError(f"Build 008 entry point missing: {main_script}")
if not dll_hook.is_file():
    raise RuntimeError(f"Build 008 runtime hook missing: {dll_hook}")


datas = []
binaries = []
hiddenimports = []


def add_binary_tree(source: Path, destination: str, suffixes=(".dll", ".pyd")):
    if not source.is_dir():
        return
    for file in source.rglob("*"):
        if file.is_file() and file.suffix.lower() in suffixes:
            relative_parent = file.parent.relative_to(source)
            target = Path(destination) / relative_parent
            binaries.append((str(file), str(target)))


def package_dir(name: str) -> Path:
    spec = find_spec(name)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"Cannot locate installed package: {name}")
    return Path(spec.origin).resolve().parent


# Keep the proven BeatNet application unchanged; this spec only hardens packaging.
# imageio_ffmpeg is explicit because main.py imports it dynamically when audio is
# converted, so its package data must not depend on automatic hidden-import luck.
for package in ["numpy", "scipy", "madmom", "librosa", "BeatNet", "imageio_ffmpeg"]:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

for package in ["numpy", "scipy", "madmom"]:
    binaries += collect_dynamic_libs(package)
    hiddenimports += collect_submodules(package)

hiddenimports += collect_submodules("BeatNet")
hiddenimports += ["pkg_resources"]

# NumPy/SciPy Windows wheels keep dependent BLAS/runtime DLLs in sibling
# *.libs directories. Preserve those directories explicitly instead of relying
# solely on automatic hook discovery.
for package in ["numpy", "scipy"]:
    pkg = package_dir(package)
    add_binary_tree(pkg.parent / f"{package}.libs", f"{package}.libs", (".dll",))

# madmom ships Cython extension modules as .pyd files inside its package tree.
madmom_dir = package_dir("madmom")
add_binary_tree(madmom_dir, "madmom", (".pyd", ".dll"))

# Include Microsoft VC runtime DLLs supplied beside the GitHub Python runtime
# when present. These are harmless duplicates if PyInstaller already found them.
python_root = Path(__import__("sys").base_prefix)
for runtime_name in ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"]:
    runtime = python_root / runtime_name
    if runtime.is_file():
        binaries.append((str(runtime), "."))

ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
if ffmpeg.is_file():
    binaries.append((str(ffmpeg), "."))

# De-duplicate exact PyInstaller tuples after explicit collection.
def unique(items):
    seen = set()
    result = []
    for item in items:
        key = tuple(item) if isinstance(item, (tuple, list)) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


datas = unique(datas)
binaries = unique(binaries)
hiddenimports = list(dict.fromkeys(hiddenimports))


a = Analysis(
    [str(main_script)],
    pathex=[str(spec_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(dll_hook)],
    excludes=["pytest", "tensorboard"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BN008",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BN008",
)
