from __future__ import annotations

import sys
from dataclasses import dataclass
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget
)


@dataclass(frozen=True)
class ChordShape:
    name: str
    frets: tuple[int, int, int, int, int]  # strings 5,4,3,2,1, -1=mute


CHORDS = {
    'G': ChordShape('G', (0, 0, 0, 0, 0)),
    'C': ChordShape('C', (0, 2, 0, 1, 2)),
    'D': ChordShape('D', (0, 0, 2, 3, 4)),
    'Em': ChordShape('Em', (0, 2, 0, 0, 2)),
    'Am': ChordShape('Am', (0, 2, 2, 1, 2)),
    'A': ChordShape('A', (0, 2, 2, 2, 2)),
    'E': ChordShape('E', (0, 2, 1, 0, 2)),
    'F': ChordShape('F', (0, 3, 2, 1, 3)),
    'Bm': ChordShape('Bm', (0, 4, 4, 3, 4)),
    'D7': ChordShape('D7', (0, 0, 2, 1, 0)),
    'G7': ChordShape('G7', (0, 0, 0, 0, 3)),
    'C7': ChordShape('C7', (0, 2, 0, 1, 1)),
}

SEMITONES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_TO_SHARP = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}


def split_chord(chord: str) -> tuple[str, str]:
    if len(chord) >= 2 and chord[1] in '#b':
        root, suffix = chord[:2], chord[2:]
    else:
        root, suffix = chord[:1], chord[1:]
    return FLAT_TO_SHARP.get(root, root), suffix


def transpose_name(chord: str, semitones: int) -> str:
    root, suffix = split_chord(chord)
    if root not in SEMITONES:
        return chord
    return SEMITONES[(SEMITONES.index(root) + semitones) % 12] + suffix


class BanjoDiagram(QWidget):
    def __init__(self, chord: str = 'G', compact: bool = False):
        super().__init__()
        self.chord = chord
        self.compact = compact
        self.setMinimumSize(90 if compact else 150, 70 if compact else 135)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_chord(self, chord: str) -> None:
        self.chord = chord
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor('#151922'))
        painter.setPen(QColor('#f7d774'))
        title_font = QFont('Arial', 10 if self.compact else 16, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(0, 2, w, 24, Qt.AlignCenter, self.chord)

        shape = CHORDS.get(self.chord) or CHORDS.get(split_chord(self.chord)[0])
        if shape is None:
            painter.setPen(QColor('#e7e7e7'))
            painter.drawText(0, h//2, w, 20, Qt.AlignCenter, 'shape missing')
            return

        top = 28 if self.compact else 34
        left = 12 if self.compact else 22
        right = w - left
        bottom = h - 10
        strings = 5
        frets = 4
        pen = QPen(QColor('#dfe6f3'), 1)
        painter.setPen(pen)
        for i in range(strings):
            x = left + i * (right - left) / (strings - 1)
            painter.drawLine(int(x), top, int(x), bottom)
        for f in range(frets + 1):
            y = top + f * (bottom - top) / frets
            painter.drawLine(left, int(y), right, int(y))
        painter.setBrush(QColor('#f7d774'))
        painter.setPen(Qt.NoPen)
        max_fret = max([f for f in shape.frets if f > 0], default=0)
        for i, fret in enumerate(shape.frets):
            if fret <= 0:
                continue
            x = left + i * (right - left) / (strings - 1)
            y = top + (fret - 0.5) * (bottom - top) / frets
            r = 5 if self.compact else 8
            painter.drawEllipse(int(x-r), int(y-r), r*2, r*2)


class BeatCell(QFrame):
    def __init__(self, chord: str = ''):
        super().__init__()
        self.chord = chord
        self.setFixedSize(76, 56)
        self.setObjectName('beatCell')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.label = QLabel(chord)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont('Arial', 10, QFont.Bold))
        layout.addWidget(self.label)

    def set_active(self, active: bool):
        self.setProperty('active', active)
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Banjofy 0.1.0')
        self.resize(1280, 820)
        self.current_beat = 0
        self.capo = 0
        self.timeline = ['G','','','', 'C','','','', 'D','','','', 'G','','','', 'Em','','','', 'C','','','', 'D7','','','', 'G','','','']
        self.cells: list[BeatCell] = []
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(600)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(16, 12, 16, 16)
        main.setSpacing(10)

        top = QFrame(); top.setObjectName('topPanel')
        top_layout = QHBoxLayout(top)
        left = QVBoxLayout()
        search_row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Search YouTube - coming in 0.2.0')
        self.load_btn = QPushButton('Load Song')
        search_row.addWidget(self.search); search_row.addWidget(self.load_btn)
        left.addLayout(search_row)
        self.results = QListWidget(); self.results.setMaximumHeight(95)
        for title in ['Cripple Creek - sample layout', 'Wagon Wheel - sample layout', 'Country Roads - sample layout']:
            item = QListWidgetItem('▣  ' + title + '    3:24')
            self.results.addItem(item)
        left.addWidget(self.results)
        top_layout.addLayout(left, stretch=3)

        mid = QVBoxLayout()
        controls = QHBoxLayout()
        controls.addWidget(QPushButton('▶ Play'))
        controls.addWidget(QPushButton('⏸ Pause'))
        controls.addWidget(QLabel('Speed'))
        speed = QSlider(Qt.Horizontal); speed.setRange(50, 100); speed.setValue(100); speed.setMaximumWidth(140)
        controls.addWidget(speed)
        controls.addWidget(QLabel('Mode'))
        mode = QComboBox(); mode.addItems(['Beginner', 'Intermediate', 'Professional'])
        controls.addWidget(mode)
        controls.addWidget(QLabel('Capo'))
        self.capo_box = QComboBox(); self.capo_box.addItems([str(i) for i in range(0, 8)])
        self.capo_box.currentIndexChanged.connect(self.update_capo)
        controls.addWidget(self.capo_box)
        mid.addLayout(controls)
        chord_row = QHBoxLayout()
        self.current_label = QLabel('Current')
        self.current_diagram = BanjoDiagram('G')
        self.next_label = QLabel('Next in 1 beat')
        self.next_diagram = BanjoDiagram('C')
        chord_row.addWidget(self.current_label); chord_row.addWidget(self.current_diagram)
        chord_row.addSpacing(15)
        chord_row.addWidget(self.next_label); chord_row.addWidget(self.next_diagram)
        mid.addLayout(chord_row)
        top_layout.addLayout(mid, stretch=4)
        main.addWidget(top)

        grid_title = QLabel('Beat grid - 1 square = 1 beat, 4 squares = 1 bar, 4 bars per row')
        grid_title.setObjectName('sectionTitle')
        main.addWidget(grid_title)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setObjectName('gridScroll')
        grid_host = QWidget(); self.grid = QGridLayout(grid_host); self.grid.setSpacing(6); self.grid.setContentsMargins(8,8,8,8)
        self.build_grid()
        scroll.setWidget(grid_host)
        main.addWidget(scroll, stretch=1)
        self.apply_styles()

    def build_grid(self):
        for i, chord in enumerate(self.timeline):
            cell = BeatCell(self.display_chord(chord) if chord else '')
            cell.set_active(i == 0)
            self.cells.append(cell)
            self.grid.addWidget(cell, i // 16, i % 16)

    def display_chord(self, chord: str) -> str:
        return transpose_name(chord, self.capo) if chord else ''

    def update_capo(self):
        self.capo = int(self.capo_box.currentText())
        for i, cell in enumerate(self.cells):
            cell.label.setText(self.display_chord(self.timeline[i]))
        self.update_chord_panels()

    def tick(self):
        if not self.cells:
            return
        self.cells[self.current_beat].set_active(False)
        self.current_beat = (self.current_beat + 1) % len(self.cells)
        self.cells[self.current_beat].set_active(True)
        self.update_chord_panels()

    def chord_at_or_before(self, idx: int) -> str:
        for j in range(idx, -1, -1):
            if self.timeline[j]:
                return self.timeline[j]
        return 'G'

    def next_chord_after(self, idx: int) -> str:
        current = self.chord_at_or_before(idx)
        for j in range(idx + 1, len(self.timeline)):
            if self.timeline[j] and self.timeline[j] != current:
                return self.timeline[j]
        return current

    def update_chord_panels(self):
        current = self.display_chord(self.chord_at_or_before(self.current_beat))
        nxt = self.display_chord(self.next_chord_after(self.current_beat))
        self.current_diagram.set_chord(current)
        self.next_diagram.set_chord(nxt)

    def apply_styles(self):
        self.setStyleSheet('''
            QMainWindow, QWidget { background: #0f1117; color: #edf1f7; font-family: Arial; }
            #topPanel { background: #171b25; border: 1px solid #2b3242; border-radius: 12px; }
            QLineEdit, QListWidget, QComboBox { background: #0f1117; border: 1px solid #31394a; border-radius: 8px; padding: 8px; color: #edf1f7; }
            QPushButton { background: #f7d774; color: #111; border: none; border-radius: 8px; padding: 9px 14px; font-weight: bold; }
            QLabel { color: #edf1f7; }
            #sectionTitle { color: #f7d774; font-weight: bold; }
            #gridScroll { background: #11151d; border: 1px solid #2b3242; border-radius: 12px; }
            #beatCell { background: #1b2130; border: 1px solid #30384a; border-radius: 8px; }
            #beatCell[active="true"] { background: #f7d774; border: 2px solid #ffffff; color: #111; }
            #beatCell[active="true"] QLabel { color: #111; }
        ''')


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
