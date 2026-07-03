from __future__ import annotations

import sys
from pathlib import Path


def _add_packaged_source_path() -> None:
    candidates: list[Path] = []

    try:
        candidates.append(Path(__file__).resolve().parents[1])
    except Exception:
        pass

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "banjofy_src")

    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))

    try:
        import banjofy

        existing = list(getattr(banjofy, "__path__", []))
        for candidate in candidates:
            package_path = candidate / "banjofy"
            if package_path.exists():
                package_path_text = str(package_path)
                if package_path_text not in existing:
                    banjofy.__path__.append(package_path_text)
    except Exception:
        pass


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
