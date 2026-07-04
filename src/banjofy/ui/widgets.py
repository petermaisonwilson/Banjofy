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
        self.label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f3d99a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addWidget(self.label)
        self.setObjectName("BeatCell")
        self.setMinimumSize(76, 72)
        self._active = False
        self._loop = False
        self._apply_style()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.index)

    def set_chord(self, chord: str) -> None:
        self.chord = chord
        self.label.setText(chord)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def set_loop(self, in_loop: bool) -> None:
        self._loop = in_loop
        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                "QFrame { background: #6b4f17; border: 4px solid #ffe6a3; border-radius: 4px; }"
            )
        elif self._loop:
            self.setStyleSheet(
                "QFrame { background: #242424; border: 2px solid #6ea86e; border-radius: 4px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame { background: #1f1f1f; border: 2px solid #555555; border-radius: 4px; }"
            )


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
