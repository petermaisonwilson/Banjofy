from __future__ import annotations

from pathlib import Path
import json
import os


APP_NAME = "Banjofy"


def settings_folder() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        folder = Path(base) / APP_NAME
    else:
        folder = Path.home() / f".{APP_NAME.lower()}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_file() -> Path:
    return settings_folder() / "settings.json"


def load_settings() -> dict:
    path = settings_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(settings: dict) -> None:
    settings_file().write_text(json.dumps(settings, indent=2), encoding="utf-8")


def get_library_path() -> Path | None:
    value = load_settings().get("library_path", "")
    if not value:
        return None
    return Path(value)


def set_library_path(path: str | Path) -> Path:
    library = Path(path).expanduser().resolve()
    create_library_folders(library)
    settings = load_settings()
    settings["library_path"] = str(library)
    save_settings(settings)
    return library


def create_library_folders(library: Path) -> None:
    library.mkdir(parents=True, exist_ok=True)
    for sub in ["Audio", "Analysis", "Artwork", "Songs"]:
        (library / sub).mkdir(parents=True, exist_ok=True)


def require_library_path() -> Path:
    library = get_library_path()
    if library is None:
        raise RuntimeError("Library folder has not been chosen")
    create_library_folders(library)
    return library


def audio_folder() -> Path:
    folder = require_library_path() / "Audio"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def analysis_folder() -> Path:
    folder = require_library_path() / "Analysis"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
