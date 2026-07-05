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
        self.label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f3d99a;")
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
    SIMPLE_BANJO_SHAPES = {
        "G":  (0,  ["0", "0", "0", "0", "0"], ["", "", "", "", ""]),
        "C":  (0,  ["0", "2", "0", "1", "2"], ["", "2", "", "1", "3"]),
        "D":  (0,  ["0", "0", "2", "3", "4"], ["", "", "1", "2", "3"]),
        "D7": (0,  ["0", "0", "2", "1", "0"], ["", "", "2", "1", ""]),
        "Em": (0,  ["0", "0", "2", "0", "2"], ["", "", "1", "", "2"]),
        "Am": (0,  ["0", "2", "2", "1", "2"], ["", "2", "3", "1", "4"]),
        "A":  (0,  ["0", "2", "2", "2", "2"], ["", "1", "2", "3", "4"]),
        "B":  (0,  ["0", "4", "4", "4", "4"], ["", "1", "2", "3", "4"]),
        "E":  (0,  ["0", "2", "1", "0", "2"], ["", "2", "1", "", "3"]),
        "F":  (0,  ["0", "3", "2", "1", "3"], ["", "3", "2", "1", "4"]),
        "F#": (0,  ["0", "4", "3", "2", "4"], ["", "3", "2", "1", "4"]),
        "G#": (1,  ["1", "1", "1", "1", "1"], ["1", "1", "1", "1", "1"]),
        "C#m": (4, ["4", "6", "6", "5", "4"], ["1", "3", "4", "2", "1"]),
    }

    def __init__(self, title: str, chord: str = "—", colour: str = "#f3d99a", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("ChordPanel")
        self.title = QLabel(title)
        self.chord_label = QLabel(chord)
        self.diagram_label = QLabel("")
        self.subtitle = QLabel(subtitle)

        self.chord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chord_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #f3d99a;")
        self.diagram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diagram_label.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 11px; color: #eeeeee;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self.title)
        layout.addWidget(self.chord_label)
        layout.addWidget(self.diagram_label)
        layout.addWidget(self.subtitle)
        self.set_chord(chord)

    def set_chord(self, chord: str) -> None:
        clean = (chord or "—").strip()
        self.chord_label.setText(clean)
        self.diagram_label.setText(self._diagram_text(clean))

    def _diagram_text(self, chord: str) -> str:
        if not chord or chord == "—":
            return ""
        lookup = chord.strip()
        shape = self.SIMPLE_BANJO_SHAPES.get(lookup)
        if shape is None:
            root = lookup.replace("maj7", "").replace("sus4", "").replace("sus2", "").replace("add9", "").replace("7", "")
            shape = self.SIMPLE_BANJO_SHAPES.get(root)
        if shape is None:
            return "diagram coming"
        start_fret, frets, fingers = shape
        strings = ["g", "D", "G", "B", "D"]
        lines = ["Open G banjo"]
        if start_fret:
            lines.append(f"start fret {start_fret}")
        for string, fret, finger in zip(strings, frets, fingers):
            if fret == "0":
                marker = "open"
            elif finger:
                marker = f"{fret}({finger})"
            else:
                marker = fret
            lines.append(f"{string} ─● {marker}")
        return "\n".join(lines)
