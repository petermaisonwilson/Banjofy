from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QHBoxLayout

from banjofy.banjo.chords import ChordShape, get_chord


class BanjoDiagram(QWidget):
    def __init__(self, chord: str = "G", compact: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shape: ChordShape = get_chord(chord)
        self._compact = compact
        self.setMinimumSize(92 if compact else 112, 92 if compact else 92)

    def set_chord(self, chord: str) -> None:
        self._shape = get_chord(chord)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        left = 18 if self._compact else 24
        top = 10 if self._compact else 18
        bottom_space = 16 if self._compact else 18
        grid_w = max(50, w - left - 12)
        grid_h = max(45, h - top - bottom_space)
        string_count = 5
        fret_count = 4

        ink = QColor("#f2e4c5")
        muted = QColor("#bcae91")
        dot = QColor("#f4e7c8")
        bg_dot = QColor("#111111")

        painter.setPen(QPen(ink, 2))
        for i in range(string_count):
            x = left + i * grid_w / (string_count - 1)
            painter.drawLine(int(x), top, int(x), int(top + grid_h))
        for f in range(fret_count + 1):
            y = top + f * grid_h / fret_count
            painter.drawLine(left, int(y), int(left + grid_w), int(y))

        painter.setFont(QFont("Segoe UI", 7 if self._compact else 9))
        painter.setPen(QPen(muted, 1))
        labels = ["g", "D", "G", "B", "D"]
        for i, label in enumerate(labels):
            x = left + i * grid_w / (string_count - 1)
            painter.drawText(int(x - 4), int(top + grid_h + (10 if self._compact else 16)), label)

        dot_size = 14 if self._compact else 22
        painter.setFont(QFont("Segoe UI", 7 if self._compact else 9, QFont.Weight.Bold))
        for i, fret in enumerate(self._shape.frets):
            x = left + i * grid_w / (string_count - 1)
            if fret == 0 and not self._compact:
                painter.setPen(QPen(ink, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(x - 4), 6, 8, 8)
            elif fret > 0:
                display_fret = min(max(fret, 1), fret_count)
                y = top + (display_fret - 0.5) * grid_h / fret_count
                painter.setPen(QPen(dot, 1))
                painter.setBrush(QBrush(bg_dot))
                painter.drawEllipse(int(x - dot_size / 2), int(y - dot_size / 2), dot_size, dot_size)
                finger = self._shape.fingers[i]
                if finger and not self._compact:
                    painter.setPen(QPen(dot, 1))
                    painter.drawText(int(x - 4), int(y + 4), str(finger))


class ChordPanel(QFrame):
    def __init__(self, title: str, chord: str, accent: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ChordPanel")
        self.setStyleSheet(f"#ChordPanel {{ border: 1px solid {accent}; border-radius: 8px; background: rgba(20,20,20,0.70); }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        header = QLabel(title if not subtitle else f"{title} <span style='color:#aaa'>({subtitle})</span>")
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setStyleSheet(f"color: {accent}; font-size: 13px;")
        layout.addWidget(header)
        row = QHBoxLayout()
        self.letter = QLabel(chord)
        self.letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.letter.setStyleSheet("font-size: 34px; font-weight: bold; color: #f4e2bd;")
        row.addWidget(self.letter, 1)
        self.diagram = BanjoDiagram(chord)
        row.addWidget(self.diagram, 2)
        layout.addLayout(row)

    def set_chord(self, chord: str) -> None:
        self.letter.setText(chord or "—")
        self.diagram.set_chord(chord or "G")


class BeatCell(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, chord: str = "", parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self.chord = chord
        self.is_active = False
        self.is_loop = False
        self.setObjectName("BeatCell")
        self.setMinimumHeight(138)
        self.setMinimumWidth(92)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.chord_label = QLabel(chord)
        self.chord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chord_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f4e2bd;")
        self.layout.addWidget(self.chord_label)
        self.diagram = BanjoDiagram(chord or "G", compact=True)
        self.diagram.setVisible(bool(chord))
        self.layout.addWidget(self.diagram, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch(1)
        self.refresh_style()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self.index)
        super().mousePressEvent(event)

    def set_chord(self, chord: str) -> None:
        self.chord = chord
        self.chord_label.setText(chord)
        self.diagram.set_chord(chord or "G")
        self.diagram.setVisible(bool(chord))

    def set_active(self, active: bool) -> None:
        self.is_active = active
        self.refresh_style()

    def set_loop(self, in_loop: bool) -> None:
        self.is_loop = in_loop
        self.refresh_style()

    def refresh_style(self) -> None:
        if self.is_active:
            bg = "#5b4419"
            border = "#f3c15f"
        elif self.is_loop:
            bg = "#1f3520"
            border = "#6abf69"
        else:
            bg = "#1d1d1d"
            border = "#3a3a3a"
        self.setStyleSheet(f"QFrame#BeatCell {{ background: {bg}; border: 2px solid {border}; border-radius: 5px; }}")
