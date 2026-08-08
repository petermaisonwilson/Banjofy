# PyInstaller runtime hook for the BeatNet laboratory Windows package.
# Packaging-only: this does not alter BeatNet analysis or inference.
# IMPORTANT: keep this hook limited to DLL search-path setup. Package imports
# must occur after PyInstaller has run its standard runtime hooks (especially
# pyi_rth_pkgres), otherwise madmom's pkg_resources lookup can fail even when
# its .dist-info metadata is correctly bundled.

import os
import sys
from pathlib import Path

_DLL_HANDLES = []


if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    root = Path(sys._MEIPASS)
    candidates = [
        root,
        root / "numpy.libs",
        root / "scipy.libs",
        root / "numpy" / ".libs",
        root / "scipy" / ".libs",
    ]

    existing = [str(path) for path in candidates if path.is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])

    if hasattr(os, "add_dll_directory"):
        for directory in existing:
            try:
                _DLL_HANDLES.append(os.add_dll_directory(directory))
            except OSError:
                pass
