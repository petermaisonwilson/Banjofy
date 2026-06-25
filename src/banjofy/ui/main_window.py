from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QComboBox, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QSizePolicy
)
from banjofy import __version__
from banjofy.banjo.chords import transpose_chord
from banjofy.ui.chord_diagram import ChordDiagram


class BeatBox(QFrame):
    def __init__(self, chord="", bar_start=False):
        super().__init__()
        self.chord = chord
        self.active = False
        self.setMinimumSize(70, 62)
        self.setMaximumHeight(62)
        self.label = QLabel(chord)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-weight:bold; color:#f7d76a; font-size:15px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2,2,2,2)
        layout.addWidget(self.label)
        self.bar_start = bar_start
        self.refresh()

    def set_active(self, active):
        self.active = active
        self.refresh()

    def refresh(self):
        border = "3px solid #f7d76a" if self.active else ("2px solid #4d9cff" if self.bar_start else "1px solid #344054")
        bg = "#2d3a4d" if self.active else "#151c27"
        self.setStyleSheet(f"QFrame {{background:{bg}; border:{border}; border-radius:8px;}}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Banjofy {__version__}")
        self.resize(1280, 820)
        self.current_beat = 0
        self.chords = ["G", "", "", "", "C", "", "", "", "D", "", "", "", "G", "", "", "",
                       "Em", "", "", "", "C", "", "", "", "D", "", "", "", "G", "", "", ""]
        self.beat_boxes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.setup_palette()
        self.build_ui()

    def setup_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#0b0f14"))
        palette.setColor(QPalette.WindowText, QColor("#e8edf5"))
        self.setPalette(palette)

    def build_ui(self):
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 12, 14, 12)
        main.setSpacing(10)

        title = QLabel("🪕 Banjofy Studio — 0.1.0 Application Shell")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#f7d76a;")
        main.addWidget(title)

        top = QHBoxLayout()
        left = QVBoxLayout()
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search YouTube — placeholder in 0.1.0")
        search_btn = QPushButton("Search")
        search_row.addWidget(self.search)
        search_row.addWidget(search_btn)
        left.addLayout(search_row)
        self.results = QListWidget()
        self.results.addItems(["Foggy Mountain Breakdown — demo result", "Wagon Wheel — demo result", "I'll Fly Away — demo result"])
        self.results.setMaximumHeight(110)
        left.addWidget(self.results)
        top.addLayout(left, 4)

        control = QGroupBox("Controls")
        cl = QGridLayout(control)
        self.play_btn = QPushButton("▶ Play demo grid")
        self.play_btn.clicked.connect(self.toggle_play)
        cl.addWidget(self.play_btn, 0, 0, 1, 2)
        cl.addWidget(QLabel("Mode"), 1, 0)
        self.mode = QComboBox(); self.mode.addItems(["Beginner", "Intermediate", "Professional"])
        cl.addWidget(self.mode, 1, 1)
        cl.addWidget(QLabel("Capo"), 2, 0)
        self.capo = QComboBox(); self.capo.addItems([str(i) for i in range(0, 8)]); self.capo.currentIndexChanged.connect(self.update_chord_panels)
        cl.addWidget(self.capo, 2, 1)
        cl.addWidget(QLabel("Display"), 3, 0)
        self.display = QComboBox(); self.display.addItems(["Concert chords", "Banjo shapes"]); self.display.currentIndexChanged.connect(self.update_chord_panels)
        cl.addWidget(self.display, 3, 1)
        top.addWidget(control, 2)

        self.current_diag = ChordDiagram("G")
        self.next_diag = ChordDiagram("C")
        top.addWidget(self.chord_panel("Current", self.current_diag), 1)
        top.addWidget(self.chord_panel("Coming next", self.next_diag), 1)
        main.addLayout(top)

        grid_box = QGroupBox("Beat grid — 4/4, one square per beat, 4 bars per row")
        grid_layout = QVBoxLayout(grid_box)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        grid_holder = QWidget(); self.grid = QGridLayout(grid_holder); self.grid.setSpacing(6)
        for i, chord in enumerate(self.chords):
            box = BeatBox(chord, i % 4 == 0)
            self.beat_boxes.append(box)
            self.grid.addWidget(box, i // 16, i % 16)
        scroll.setWidget(grid_holder)
        grid_layout.addWidget(scroll)
        main.addWidget(grid_box, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(self.stylesheet())
        self.update_active_box()

    def chord_panel(self, title, diagram):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(diagram)
        return box

    def display_chord(self, chord):
        if self.display.currentText() == "Concert chords":
            return transpose_chord(chord, int(self.capo.currentText()))
        return chord

    def update_chord_panels(self):
        current = self.chord_at(self.current_beat)
        nxt = self.next_chord_after(self.current_beat)
        self.current_diag.set_chord(self.display_chord(current))
        self.next_diag.set_chord(self.display_chord(nxt))

    def chord_at(self, beat):
        last = "G"
        for i in range(0, min(beat+1, len(self.chords))):
            if self.chords[i]: last = self.chords[i]
        return last

    def next_chord_after(self, beat):
        current = self.chord_at(beat)
        for i in range(beat+1, len(self.chords)):
            if self.chords[i] and self.chords[i] != current:
                return self.chords[i]
        return current

    def toggle_play(self):
        if self.timer.isActive():
            self.timer.stop(); self.play_btn.setText("▶ Play demo grid")
        else:
            self.timer.start(500); self.play_btn.setText("⏸ Pause")

    def tick(self):
        self.current_beat = (self.current_beat + 1) % len(self.beat_boxes)
        self.update_active_box()

    def update_active_box(self):
        for i, box in enumerate(self.beat_boxes):
            box.set_active(i == self.current_beat)
        self.update_chord_panels()

    def stylesheet(self):
        return """
        QWidget { background:#0b0f14; color:#e8edf5; font-family: Arial; }
        QGroupBox { border:1px solid #263244; border-radius:10px; margin-top:10px; padding:10px; font-weight:bold; }
        QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 4px; color:#9fb3c8; }
        QPushButton { background:#1d4ed8; color:white; border:0; border-radius:8px; padding:8px 12px; font-weight:bold; }
        QPushButton:hover { background:#2563eb; }
        QLineEdit, QComboBox, QListWidget { background:#111827; border:1px solid #334155; border-radius:8px; padding:6px; color:#e8edf5; }
        QScrollArea { border:0; }
        """
