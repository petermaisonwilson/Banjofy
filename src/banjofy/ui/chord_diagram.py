from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget
from banjofy.banjo.chords import frets_for


class ChordDiagram(QWidget):
    def __init__(self, chord="G", compact=False, parent=None):
        super().__init__(parent)
        self.chord = chord
        self.compact = compact
        self.setMinimumSize(90 if compact else 145, 90 if compact else 145)

    def set_chord(self, chord):
        self.chord = chord
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#10151d"))

        title_font = QFont("Arial", 10 if self.compact else 16, QFont.Bold)
        p.setFont(title_font)
        p.setPen(QColor("#f7d76a"))
        p.drawText(0, 2, w, 24, Qt.AlignCenter, self.chord)

        frets = frets_for(self.chord)
        top = 34 if not self.compact else 28
        left = 18
        right = w - 18
        bottom = h - 16
        string_count = 5
        fret_lines = 5

        grid_pen = QPen(QColor("#d9e1ee"), 1.2)
        p.setPen(grid_pen)
        for i in range(string_count):
            x = left + i * (right - left) / (string_count - 1)
            p.drawLine(int(x), top, int(x), bottom)
        for j in range(fret_lines):
            y = top + j * (bottom - top) / (fret_lines - 1)
            p.drawLine(left, int(y), right, int(y))

        p.setBrush(QBrush(QColor("#f7d76a")))
        p.setPen(QPen(QColor("#f7d76a"), 1))
        max_fret = max([f for f in frets if isinstance(f, int)] or [0])
        base = 1 if max_fret <= 4 else max(1, max_fret - 3)
        dot_r = 5 if self.compact else 8
        for i, fret in enumerate(frets):
            x = left + i * (right - left) / (string_count - 1)
            if fret == 0:
                p.setPen(QColor("#d9e1ee"))
                p.drawText(int(x-8), top-18, 16, 14, Qt.AlignCenter, "○")
                p.setPen(QColor("#f7d76a"))
            elif isinstance(fret, int):
                pos = max(1, fret - base + 1)
                y1 = top + (pos - 1) * (bottom - top) / (fret_lines - 1)
                y2 = top + pos * (bottom - top) / (fret_lines - 1)
                y = (y1 + y2) / 2
                p.drawEllipse(QRectF(x-dot_r, y-dot_r, dot_r*2, dot_r*2))

        if base > 1 and not self.compact:
            p.setPen(QColor("#d9e1ee"))
            p.drawText(2, top+12, 22, 18, Qt.AlignCenter, str(base))
