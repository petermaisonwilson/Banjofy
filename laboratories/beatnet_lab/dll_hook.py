# PyInstaller runtime hook for the BeatNet laboratory Windows package.
# Packaging-only: this does not alter BeatNet analysis or inference.

import json
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

    # Fail packaged startup immediately if any compiled scientific/runtime
    # component needed by the proven BeatNet path is unusable. GitHub's ready
    # proof is written only after this hook has completed successfully.
    import numpy  # noqa: F401,E402
    import scipy  # noqa: F401,E402
    import madmom  # noqa: F401,E402
    import torch  # noqa: F401,E402
    import imageio_ffmpeg  # noqa: E402
    from BeatNet.BeatNet import BeatNet  # noqa: F401,E402

    ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not ffmpeg.is_file():
        raise RuntimeError(f"Packaged imageio-ffmpeg executable missing: {ffmpeg}")

    # CI-only startup proof. Normal Windows launches do not set this variable.
    # Writing here proves the actual packaged EXE reached Python successfully and
    # loaded the complete compiled BeatNet runtime before any GUI is attempted.
    probe = os.environ.get("BANJOFY_BEATNET_STARTUP_PROBE_FILE")
    if probe:
        Path(probe).write_text(
            json.dumps({"status": "ready", "app": "BN008 packaged runtime"}),
            encoding="utf-8",
        )
