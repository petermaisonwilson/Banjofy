from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class BeatCell(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, chord: str = "") -> None:
        super().__init__()
        self.index = index
        self.chord = chord
        self.label = QLabel(chord)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f3d99a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addWidget(self.label)
        self.setObjectName("BeatCell")
        self.setMinimumSize(72, 54)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.index)

    def set_chord(self, chord: str) -> None:
        self.chord = chord
        self.label.setText(chord)

    def set_active(self, active: bool) -> None:
        if active:
            self.setProperty("active", True)
            self.setStyleSheet("QFrame { border: 2px solid #f3d99a; background: #43351e; }")
        else:
            self.setProperty("active", False)
            self.setStyleSheet("")

    def set_loop(self, in_loop: bool) -> None:
        if in_loop:
            self.setStyleSheet("QFrame { border: 2px solid #6ea86e; }")


class ChordPanel(QFrame):
    def __init__(self, title: str, chord: str = "—", colour: str = "#f3d99a", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("ChordPanel")
        self.title = QLabel(title)
        self.chord_label = QLabel(chord)
        self.subtitle = QLabel(subtitle)
        self.chord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chord_label.setStyleSheet("font-size: 34px; font-weight: bold;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self.title)
        layout.addWidget(self.chord_label)
        layout.addWidget(self.subtitle)

    def set_chord(self, chord: str) -> None:
        self.chord_label.setText(chord)
