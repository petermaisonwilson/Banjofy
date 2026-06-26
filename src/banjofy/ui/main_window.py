from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from banjofy.ui.widgets import BanjoDiagram, ChordPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Banjofy 0.1.0 - Build 001")
        self.resize(1320, 820)
        self._apply_style()
        self.setCentralWidget(self._build_ui())
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Build 001 ready - desktop shell only")

    def _build_ui(self) -> QWidget:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        top = QHBoxLayout()
        outer.addLayout(top, 0)

        search_panel = self._panel()
        search_layout = QVBoxLayout(search_panel)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search will be added in Build 002")
        search_button = QPushButton("Search")
        search_button.setEnabled(False)
        search_row.addWidget(self.search)
        search_row.addWidget(search_button)
        search_layout.addLayout(search_row)
        search_layout.addWidget(QLabel("YouTube results placeholder"))
        for text in ["John Denver - Country Roads", "AC/DC - Back In Black", "Lewis Capaldi - Someone You Loved"]:
            item = QLabel(f"▶ {text}\n   Load button coming in Build 002")
            item.setObjectName("ResultItem")
            search_layout.addWidget(item)
        top.addWidget(search_panel, 2)

        meta_panel = self._panel()
        meta_layout = QVBoxLayout(meta_panel)
        for label, value in [("BPM", "—"), ("Key", "—"), ("Time Sig", "4/4"), ("Duration", "—")]:
            meta_layout.addWidget(self._info_box(label, value))
        load_btn = QPushButton("♫ Load Song")
        load_btn.setEnabled(False)
        meta_layout.addWidget(load_btn)
        top.addWidget(meta_panel, 1)

        centre = self._panel()
        centre_layout = QVBoxLayout(centre)
        title = QLabel("Banjofy Build 001")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #f3d99a;")
        centre_layout.addWidget(title)
        chord_row = QHBoxLayout()
        chord_row.addWidget(ChordPanel("CURRENT", "D", "#65b95c"), 1)
        chord_row.addWidget(ChordPanel("NEXT", "G", "#c99424", "in 1 beat"), 1)
        centre_layout.addLayout(chord_row)
        top.addWidget(centre, 5)

        settings = self._panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.addWidget(QLabel("Mode"))
        mode = QComboBox()
        mode.addItems(["Beginner", "Intermediate", "Professional"])
        mode.setCurrentText("Intermediate")
        settings_layout.addWidget(mode)
        settings_layout.addWidget(QLabel("Capo"))
        capo = QSpinBox()
        capo.setRange(0, 12)
        settings_layout.addWidget(capo)
        settings_layout.addWidget(QLabel("Show"))
        show = QComboBox()
        show.addItems(["Concert Chords", "Banjo Shapes"])
        settings_layout.addWidget(show)
        settings_layout.addStretch()
        top.addWidget(settings, 1)

        controls = self._panel()
        controls_layout = QHBoxLayout(controls)
        for text in ["⏮ Back", "▶ Play", "⏭ Forward"]:
            btn = QPushButton(text)
            btn.setEnabled(False)
            controls_layout.addWidget(btn)
        controls_layout.addSpacing(30)
        controls_layout.addWidget(QLabel("Loop bars"))
        controls_layout.addWidget(QSpinBox())
        controls_layout.addWidget(QLabel("to"))
        controls_layout.addWidget(QSpinBox())
        controls_layout.addSpacing(30)
        controls_layout.addWidget(QLabel("Speed"))
        speed = QSlider(Qt.Orientation.Horizontal)
        speed.setRange(50, 100)
        speed.setValue(100)
        controls_layout.addWidget(speed)
        controls_layout.addWidget(QLabel("100%"))
        controls_layout.addStretch()
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setEnabled(False)
        controls_layout.addWidget(settings_btn)
        outer.addWidget(controls, 0)

        grid_panel = self._panel()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.addWidget(QLabel("Beat grid placeholder - 4 bars across / 16 beat squares per row"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._build_grid())
        grid_layout.addWidget(scroll)
        outer.addWidget(grid_panel, 1)

        return root

    def _build_grid(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(2)
        chords = ["D", "", "", "", "G", "", "", "", "A", "", "", "", "D", "", "", ""] * 4
        for i, chord in enumerate(chords):
            cell = QFrame()
            cell.setObjectName("BeatCell")
            cell.setMinimumHeight(105)
            box = QVBoxLayout(cell)
            box.setContentsMargins(6, 4, 6, 4)
            box.addWidget(QLabel(str((i % 4) + 1)))
            if chord:
                label = QLabel(chord)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("font-size: 24px; font-weight: bold; color: #f4e2bd;")
                box.addWidget(label)
                diagram = BanjoDiagram(chord)
                diagram.setMinimumSize(90, 70)
                box.addWidget(diagram)
            box.addStretch()
            layout.addWidget(cell, i // 16, i % 16)
        return widget

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        return frame

    def _info_box(self, label: str, value: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("InfoBox")
        layout = QHBoxLayout(frame)
        layout.addWidget(QLabel(label))
        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignRight)
        val.setStyleSheet("font-weight: bold;")
        layout.addWidget(val)
        return frame

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111111;
                color: #f3e6cc;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 14px;
            }
            QFrame#Panel {
                background: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            QFrame#InfoBox {
                background: #202020;
                border: 1px solid #333333;
                border-radius: 6px;
            }
            QLabel#ResultItem {
                background: #202020;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #252525;
                color: #f3e6cc;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 6px;
            }
            QPushButton {
                background: #2f2f2f;
                color: #f3e6cc;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:disabled {
                color: #777777;
            }
            QFrame#BeatCell {
                background: #1d1d1d;
                border: 1px solid #3a3a3a;
            }
            """
        )
