from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QHBoxLayout

from banjofy.banjo.chords import ChordShape, get_chord


class BanjoDiagram(QWidget):
    def __init__(self, chord: str = "G", parent: QWidget | None = None, compact: bool = False) -> None:
        super().__init__(parent)
        self._shape: ChordShape = get_chord(chord)
        self.compact = compact
        if compact:
            self.setMinimumSize(88, 78)
        else:
            self.setMinimumSize(130, 105)

    def set_chord(self, chord: str) -> None:
        self._shape = get_chord(chord)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        left = 14 if self.compact else 24
        top = 12 if self.compact else 22
        bottom_gap = 10 if self.compact else 32
        grid_w = max(58, w - (left * 2))
        grid_h = max(48, h - top - bottom_gap)
        string_count = 5
        fret_count = 4

        ink = QColor("#f2e4c5")
        muted = QColor("#bcae91")
        dot = QColor("#f4e7c8")
        bg_dot = QColor("#111111")

        if not self.compact:
            painter.setPen(QPen(muted, 1))
            painter.setFont(QFont("Segoe UI", 8))
            labels = ["g", "D", "G", "B", "D"]
            for i, label in enumerate(labels):
                x = left + i * grid_w / (string_count - 1)
                painter.drawText(int(x - 5), int(top + grid_h + 18), label)

        painter.setPen(QPen(ink, 2))
        for i in range(string_count):
            x = left + i * grid_w / (string_count - 1)
            painter.drawLine(int(x), top, int(x), int(top + grid_h))

        for f in range(fret_count + 1):
            y = top + f * grid_h / fret_count
            painter.drawLine(left, int(y), int(left + grid_w), int(y))

        painter.setFont(QFont("Segoe UI", 7 if self.compact else 8, QFont.Weight.Bold))
        for i, fret in enumerate(self._shape.frets):
            x = left + i * grid_w / (string_count - 1)
            if fret == 0:
                painter.setPen(QPen(ink, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(x - 5), 6, 10, 10)
            else:
                display_fret = min(max(fret, 1), fret_count)
                y = top + (display_fret - 0.5) * grid_h / fret_count
                painter.setPen(QPen(dot, 1))
                painter.setBrush(QBrush(bg_dot))
                r = 10 if self.compact else 11
                painter.drawEllipse(int(x - r), int(y - r), r * 2, r * 2)
                finger = self._shape.fingers[i]
                if finger:
                    painter.setPen(QPen(dot, 1))
                    painter.drawText(int(x - 3), int(y + 4), str(finger))


class ChordPanel(QFrame):
    def __init__(self, title: str, chord: str, accent: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.chord = chord
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
        self.letter.setStyleSheet("font-size: 42px; font-weight: bold; color: #f4e2bd;")
        row.addWidget(self.letter, 1)

        self.diagram = BanjoDiagram(chord)
        row.addWidget(self.diagram, 2)
        layout.addLayout(row)

    def set_chord(self, chord: str) -> None:
        self.chord = chord
        self.letter.setText(chord)
        self.diagram.set_chord(chord)
