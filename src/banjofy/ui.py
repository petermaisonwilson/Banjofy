from __future__ import annotations

import sys
from dataclasses import dataclass
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QComboBox, QCheckBox, QFrame,
    QGridLayout, QSlider, QSpinBox, QScrollArea, QSizePolicy
)

from banjofy.core.chords import get_chord, transpose_chord_name

DARK = "#141414"
PANEL = "#1f1f1f"
TEXT = "#f4e3bd"
MUTED = "#b8b0a0"
GREEN = "#78c65a"
AMBER = "#d39b2f"
BLUE = "#1b73e8"

@dataclass
class BeatCell:
    bar: int
    beat: int
    chord: str

class ChordDiagram(QWidget):
    def __init__(self, chord_name="G", compact=False, parent=None):
        super().__init__(parent)
        self.chord_name = chord_name
        self.compact = compact
        self.setMinimumSize(95 if compact else 170, 85 if compact else 145)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def set_chord(self, name: str):
        self.chord_name = name or "—"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(0,0,0,0))
        chord = get_chord(self.chord_name)
        margin = 14 if not self.compact else 8
        title_h = 0 if self.compact else 18
        gx, gy = margin + 22, margin + title_h + 8
        gw, gh = w - margin*2 - 30, h - margin*2 - title_h - 22
        if gw < 50 or gh < 45:
            return
        if not self.compact:
            p.setPen(QColor(TEXT))
            f = QFont("Segoe UI", 18, QFont.Bold)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, 25), Qt.AlignCenter, self.chord_name)
        strings = 5
        frets = 5
        pen = QPen(QColor("#dddddd"), 1)
        p.setPen(pen)
        for i in range(strings):
            x = gx + i * gw / (strings - 1)
            p.drawLine(x, gy, x, gy + gh)
        for j in range(frets + 1):
            y = gy + j * gh / frets
            p.drawLine(gx, y, gx + gw, y)
        p.setPen(QColor(TEXT))
        font_size = 8 if self.compact else 11
        p.setFont(QFont("Segoe UI", font_size))
        labels = ["g", "D", "G", "B", "D"]
        for i, lab in enumerate(labels):
            x = gx + i * gw / (strings - 1)
            p.drawText(QRectF(x-10, gy+gh+2, 20, 18), Qt.AlignCenter, lab)
        for i, fret in enumerate(chord.frets):
            x = gx + i * gw / (strings - 1)
            if fret == 0:
                p.setBrush(QBrush(QColor(DARK)))
                p.setPen(QPen(QColor("#eeeeee"), 1))
                p.drawEllipse(QRectF(x-4, gy-13, 8, 8))
            elif fret > 0:
                display_fret = min(fret, 5)
                y = gy + (display_fret - 0.5) * gh / frets
                r = 9 if self.compact else 14
                p.setBrush(QBrush(QColor("#111111")))
                p.setPen(QPen(QColor("#eeeeee"), 1.2))
                p.drawEllipse(QRectF(x-r, y-r, r*2, r*2))
                finger = chord.fingers[i]
                if finger:
                    p.setPen(QColor("#ffffff"))
                    p.setFont(QFont("Segoe UI", 7 if self.compact else 10, QFont.Bold))
                    p.drawText(QRectF(x-r, y-r, r*2, r*2), Qt.AlignCenter, str(finger))

class ChordPanel(QFrame):
    def __init__(self, title, accent, parent=None):
        super().__init__(parent)
        self.setObjectName("ChordPanel")
        self.setStyleSheet(f"#ChordPanel {{ border:1px solid {accent}; border-radius:10px; background:#172016; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        left = QVBoxLayout()
        self.title = QLabel(title)
        self.title.setStyleSheet(f"color:{accent}; font-size:14px;")
        self.letter = QLabel("—")
        self.letter.setStyleSheet("color:#f4e3bd; font-size:54px; font-weight:bold;")
        left.addWidget(self.title)
        left.addStretch(1)
        left.addWidget(self.letter, alignment=Qt.AlignCenter)
        left.addStretch(1)
        self.diagram = ChordDiagram("G", compact=False)
        lay.addLayout(left, 1)
        lay.addWidget(self.diagram, 2)

    def set_chord(self, name):
        self.letter.setText(name)
        self.diagram.set_chord(name)

class GridCell(QFrame):
    def __init__(self, cell: BeatCell, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.setMinimumSize(155, 96)
        self.setStyleSheet("QFrame{border:1px solid #444; background:#191919;} QLabel{color:#f4e3bd;}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 4)
        left = QVBoxLayout()
        beat = QLabel(str(cell.beat))
        beat.setStyleSheet("color:#aaa; font-size:11px;")
        chord = QLabel(cell.chord if cell.beat == 1 else "")
        chord.setStyleSheet("font-size:28px; font-weight:bold;")
        left.addWidget(beat)
        left.addStretch(1)
        left.addWidget(chord)
        left.addStretch(1)
        lay.addLayout(left)
        if cell.beat == 1 and cell.chord:
            lay.addWidget(ChordDiagram(cell.chord, compact=True))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Banjofy 0.1 Alpha")
        self.resize(1500, 900)
        self.setStyleSheet(f"""
            QWidget {{ background:{DARK}; color:{TEXT}; font-family: Segoe UI; font-size:14px; }}
            QFrame {{ background:{PANEL}; border-radius:8px; }}
            QPushButton {{ background:#302414; color:white; border:1px solid #555; border-radius:7px; padding:8px 12px; }}
            QPushButton:hover {{ background:#49351b; }}
            QLineEdit, QComboBox, QSpinBox {{ background:#242424; color:white; border:1px solid #444; border-radius:6px; padding:6px; }}
            QListWidget {{ background:#151515; border:1px solid #333; border-radius:6px; }}
            QScrollArea {{ border:1px solid #333; border-radius:8px; }}
        """)
        self.current_chord = "D"
        self.next_chord = "G"
        self._build()
        self._load_demo_results()
        self._build_grid()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10,10,10,10)
        top = QHBoxLayout()
        root.addLayout(top, 0)

        left = QFrame(); left.setMaximumWidth(360)
        llay = QVBoxLayout(left)
        searchrow = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search YouTube")
        btn = QPushButton("Search")
        searchrow.addWidget(self.search); searchrow.addWidget(btn)
        llay.addLayout(searchrow)
        llay.addWidget(QLabel("▶ Displaying results from YouTube"))
        self.results = QListWidget(); llay.addWidget(self.results, 1)
        top.addWidget(left)

        info = QFrame(); info.setMaximumWidth(170)
        il = QGridLayout(info)
        for r, (k,v) in enumerate([("BPM","108"),("Key","A Major"),("Time Sig","4/4"),("Duration","3:16")]):
            il.addWidget(QLabel(k), r, 0); val=QLabel(v); val.setStyleSheet("font-weight:bold;font-size:16px"); il.addWidget(val,r,1)
        load = QPushButton("♫ Load Song"); load.setStyleSheet(f"background:{BLUE};font-size:18px;padding:12px;")
        il.addWidget(load,4,0,1,2)
        top.addWidget(info)

        centre = QVBoxLayout()
        title = QLabel("Take Me Home, Country Roads")
        title.setAlignment(Qt.AlignCenter); title.setStyleSheet("font-size:22px;font-weight:bold;")
        centre.addWidget(title)
        panels = QHBoxLayout()
        self.current = ChordPanel("CURRENT", GREEN)
        self.next = ChordPanel("NEXT (in 1 beat)", AMBER)
        self.current.set_chord(self.current_chord); self.next.set_chord(self.next_chord)
        panels.addWidget(self.current); panels.addWidget(self.next)
        centre.addLayout(panels)
        top.addLayout(centre, 1)

        right = QFrame(); right.setMaximumWidth(210)
        rl = QGridLayout(right)
        rl.addWidget(QLabel("Mode"),0,0); mode=QComboBox(); mode.addItems(["Beginner","Intermediate","Professional"]); mode.setCurrentText("Intermediate"); rl.addWidget(mode,0,1)
        rl.addWidget(QLabel("Capo"),1,0); capo=QComboBox(); capo.addItems([str(i) for i in range(0,8)]); rl.addWidget(capo,1,1)
        rl.addWidget(QLabel("Show"),2,0); show=QComboBox(); show.addItems(["Concert Chords","Banjo Shapes"]); rl.addWidget(show,2,1)
        snap=QCheckBox("Snap to Beat"); snap.setChecked(True); rl.addWidget(snap,3,0,1,2)
        top.addWidget(right)

        controls = QFrame(); cl=QHBoxLayout(controls)
        for text in ["⏮ Back","▶ Play","⏭ Forward"]: cl.addWidget(QPushButton(text))
        cl.addWidget(QLabel("Loop")); cl.addWidget(QPushButton("A")); cl.addWidget(QPushButton("B")); cl.addStretch(1)
        cl.addWidget(QLabel("Speed")); sl=QSlider(Qt.Horizontal); sl.setValue(100); cl.addWidget(sl); cl.addWidget(QLabel("100%"))
        cl.addWidget(QLabel("Beat Nudge")); cl.addWidget(QPushButton("-")); cl.addWidget(QPushButton("+")); cl.addWidget(QLabel("0.00")); cl.addWidget(QPushButton("⚙ Settings"))
        root.addWidget(controls, 0)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.grid_container = QWidget(); self.grid_layout = QGridLayout(self.grid_container); self.grid_layout.setSpacing(0); self.grid_layout.setContentsMargins(8,8,8,8)
        self.scroll.setWidget(self.grid_container)
        root.addWidget(self.scroll, 1)
        status = QLabel("Ready — GitHub project starter")
        root.addWidget(status)

    def _load_demo_results(self):
        for title in ["John Denver - Take Me Home, Country Roads", "AC/DC - Back In Black", "Lewis Capaldi - Someone You Loved"]:
            item = QListWidgetItem(title + "\n3:16")
            self.results.addItem(item)

    def _build_grid(self):
        chords = ["D","D","G","D","A","A","D","D","G","G","D","D","A","A","Bm","Bm","G","D","A","A","G","D","Em","A"]
        idx=0
        for bar in range(1, 25):
            chord = chords[(bar-1) % len(chords)]
            for beat in range(1,5):
                cell = GridCell(BeatCell(bar, beat, chord if beat == 1 else ""))
                pos = idx
                row = pos // 16
                col = pos % 16
                self.grid_layout.addWidget(cell, row, col)
                idx += 1

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
