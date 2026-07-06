from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from banjofy.ui.main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Banjofy")
    app.setOrganizationName("Banjofy")
    window = MainWindow()
    window.show()
    return app.exec()
