from __future__ import annotations
from pathlib import Path
import sys

def app_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()

def library_folder() -> Path:
    folder = app_folder() / "Banjofy Library"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def audio_folder() -> Path:
    folder = library_folder() / "Audio"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
