# PyInstaller runtime hook for the BeatNet laboratory Windows package.
# Packaging-only: this does not alter BeatNet analysis or inference.

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
