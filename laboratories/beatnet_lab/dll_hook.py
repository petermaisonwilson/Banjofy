# PyInstaller runtime hook for the BeatNet laboratory Windows package.
# Packaging-only: this does not alter BeatNet analysis or inference.

import json
import os
import sys
from pathlib import Path

_DLL_HANDLES = []


def _write_probe(stage: str, status: str = "starting"):
    probe = os.environ.get("BANJOFY_BEATNET_STARTUP_PROBE_FILE")
    if not probe:
        return
    Path(probe).write_text(
        json.dumps({"status": status, "stage": stage, "app": "BN008 packaged runtime"}),
        encoding="utf-8",
    )


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

    # CI-only stage markers make packaged startup failures diagnosable without
    # changing the proven BeatNet analysis path.
    _write_probe("numpy")
    import numpy  # noqa: F401,E402

    _write_probe("scipy")
    import scipy  # noqa: F401,E402

    _write_probe("madmom")
    import madmom  # noqa: F401,E402

    _write_probe("torch")
    import torch  # noqa: F401,E402

    _write_probe("imageio_ffmpeg")
    import imageio_ffmpeg  # noqa: E402

    _write_probe("BeatNet")
    from BeatNet.BeatNet import BeatNet  # noqa: F401,E402

    _write_probe("ffmpeg")
    ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not ffmpeg.is_file():
        raise RuntimeError(f"Packaged imageio-ffmpeg executable missing: {ffmpeg}")

    _write_probe("complete", "ready")
