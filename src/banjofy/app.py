from __future__ import annotations

import sys
from pathlib import Path


def _add_packaged_source_path() -> None:
    """Allow the EXE to import Banjofy modules from bundled source files."""
    candidates: list[Path] = []

    # Normal source run: src folder
    try:
        candidates.append(Path(__file__).resolve().parents[1])
    except Exception:
        pass

    # PyInstaller one-file runtime: bundled src/banjofy copied as data
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "banjofy_src")

    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def run() -> int:
    _add_packaged_source_path()

    from PySide6.QtWidgets import QApplication
    from banjofy.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Banjofy")
    app.setOrganizationName("Banjofy")
    window = MainWindow()
    window.show()
    return app.exec()
