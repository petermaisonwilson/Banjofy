from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
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

from banjofy.banjo.chords import transpose_chord
from banjofy.player.demo_songs import DEMO_SONGS, DemoSong
from banjofy.ui.widgets import BanjoDiagram, ChordPanel

BUILD_LABEL = "Banjofy 0.2.2 - Build 002.2 Grid Diagram Alignment"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(BUILD_LABEL)
        self.resize(1320, 820)
        self.song: DemoSong | None = None
        self.beat_index = 0
        self.is_playing = False
        self.grid_cells: list[QFrame] = []
        self.chord_labels: list[QLabel] = []
        self.grid_diagrams: list[BanjoDiagram] = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_beat)

        self._apply_style()
        self.setCentralWidget(self._build_ui())
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Build 002.2 ready - grid diagrams aligned")
        self._load_demo_song(0)

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
        self.search.setPlaceholderText("Build 002.2: demo search only - YouTube comes later")
        self.search.textChanged.connect(self._filter_demo_results)
        search_row.addWidget(self.search)
        search_layout.addLayout(search_row)
        search_layout.addWidget(QLabel("Demo songs"))
        self.results_layout = QVBoxLayout()
        search_layout.addLayout(self.results_layout)
        self.result_widgets: list[QWidget] = []
        self._build_demo_results()
        top.addWidget(search_panel, 2)

        meta_panel = self._panel()
        meta_layout = QVBoxLayout(meta_panel)
        self.bpm_value = self._info_box("BPM", "—")
        self.key_value = self._info_box("Key", "—")
        self.time_value = self._info_box("Time Sig", "4/4")
        self.duration_value = self._info_box("Duration", "—")
        for item in [self.bpm_value, self.key_value, self.time_value, self.duration_value]:
            meta_layout.addWidget(item["frame"])
        top.addWidget(meta_panel, 1)

        centre = self._panel()
        centre_layout = QVBoxLayout(centre)
        title = QLabel(BUILD_LABEL)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #f3d99a;")
        centre_layout.addWidget(title)
        chord_row = QHBoxLayout()
        self.current_panel = ChordPanel("CURRENT", "D", "#65b95c")
        self.next_panel = ChordPanel("NEXT", "G", "#c99424", "in 1 beat")
        chord_row.addWidget(self.current_panel, 1)
        chord_row.addWidget(self.next_panel, 1)
        centre_layout.addLayout(chord_row)
        top.addWidget(centre, 5)

        settings = self._panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.addWidget(QLabel("Mode"))
        self.mode = QComboBox()
        self.mode.addItems(["Beginner", "Intermediate", "Professional"])
        self.mode.setCurrentText("Intermediate")
        self.mode.currentTextChanged.connect(self._refresh_grid)
        settings_layout.addWidget(self.mode)
        settings_layout.addWidget(QLabel("Capo"))
        self.capo = QSpinBox()
        self.capo.setRange(0, 12)
        self.capo.valueChanged.connect(self._refresh_grid)
        settings_layout.addWidget(self.capo)
        settings_layout.addWidget(QLabel("Show"))
        self.show_mode = QComboBox()
        self.show_mode.addItems(["Concert Chords", "Banjo Shapes"])
        self.show_mode.currentTextChanged.connect(self._refresh_grid)
        settings_layout.addWidget(self.show_mode)
        settings_layout.addStretch()
        top.addWidget(settings, 1)

        controls = self._panel()
        controls_layout = QHBoxLayout(controls)
        self.back_btn = QPushButton("⏮ Back")
        self.play_btn = QPushButton("▶ Play")
        self.forward_btn = QPushButton("⏭ Forward")
        self.back_btn.clicked.connect(lambda: self._move_beat(-1))
        self.play_btn.clicked.connect(self._toggle_play)
        self.forward_btn.clicked.connect(lambda: self._move_beat(1))
        controls_layout.addWidget(self.back_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.forward_btn)
        controls_layout.addSpacing(30)
        controls_layout.addWidget(QLabel("Loop bars"))
        self.loop_start = QSpinBox()
        self.loop_start.setRange(1, 99)
        self.loop_start.setValue(1)
        self.loop_end = QSpinBox()
        self.loop_end.setRange(1, 99)
        self.loop_end.setValue(4)
        controls_layout.addWidget(self.loop_start)
        controls_layout.addWidget(QLabel("to"))
        controls_layout.addWidget(self.loop_end)
        controls_layout.addSpacing(30)
        controls_layout.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(50, 150)
        self.speed.setValue(100)
        self.speed.valueChanged.connect(self._set_timer_interval)
        controls_layout.addWidget(self.speed)
        self.speed_label = QLabel("100%")
        controls_layout.addWidget(self.speed_label)
        controls_layout.addStretch()
        outer.addWidget(controls, 0)

        grid_panel = self._panel()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.addWidget(QLabel("Build 002.2 demo beat grid - aligned chord diagrams / 4 bars across"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(2)
        self.scroll.setWidget(self.grid_widget)
        grid_layout.addWidget(self.scroll)
        outer.addWidget(grid_panel, 1)

        return root

    def _build_demo_results(self) -> None:
        for index, song in enumerate(DEMO_SONGS):
            item = QFrame()
            item.setObjectName("ResultItemFrame")
            row = QHBoxLayout(item)
            label = QLabel(f"<b>{song.title}</b><br><span style='color:#aaa'>{song.artist} • {song.bpm} BPM • Key {song.key}</span>")
            label.setTextFormat(Qt.TextFormat.RichText)
            row.addWidget(label, 1)
            btn = QPushButton("Load")
            btn.clicked.connect(lambda checked=False, i=index: self._load_demo_song(i))
            row.addWidget(btn)
            self.results_layout.addWidget(item)
            self.result_widgets.append(item)

    def _filter_demo_results(self, text: str) -> None:
        text = text.lower().strip()
        for widget, song in zip(self.result_widgets, DEMO_SONGS):
            haystack = f"{song.title} {song.artist}".lower()
            widget.setVisible(text in haystack)

    def _load_demo_song(self, index: int) -> None:
        self.song = DEMO_SONGS[index]
        self.beat_index = 0
        self.bpm_value["value"].setText(str(self.song.bpm))
        self.key_value["value"].setText(self.song.key)
        self.duration_value["value"].setText(self.song.duration)
        self.loop_start.setMaximum(max(1, len(self.song.chords) // 4))
        self.loop_end.setMaximum(max(1, len(self.song.chords) // 4))
        self.loop_end.setValue(min(4, self.loop_end.maximum()))
        self._build_grid()
        self._set_timer_interval()
        self._update_position()
        self.statusBar().showMessage(f"Loaded demo song: {self.song.title}")

    def _build_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.grid_cells.clear()
        self.chord_labels.clear()
        self.grid_diagrams.clear()
        if not self.song:
            return
        for i, chord in enumerate(self.song.chords):
            cell = QFrame()
            cell.setObjectName("BeatCell")
            cell.setMinimumHeight(122)
            cell.setMinimumWidth(92)
            box = QVBoxLayout(cell)
            box.setContentsMargins(5, 4, 5, 4)
            box.setSpacing(2)

            beat = QLabel(str((i % 4) + 1))
            beat.setAlignment(Qt.AlignmentFlag.AlignLeft)
            beat.setStyleSheet("color:#9e927d; font-size:10px;")
            box.addWidget(beat, 0)

            label = QLabel(self._display_chord(chord) if chord else "")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f4e2bd;")
            box.addWidget(label, 0)

            diagram = BanjoDiagram(self._diagram_chord(chord) if chord else "G", compact=True)
            diagram.setVisible(bool(chord))
            diagram.setMinimumSize(86, 76)
            diagram.setMaximumHeight(82)
            box.addWidget(diagram, 1, Qt.AlignmentFlag.AlignCenter)

            self.grid_layout.addWidget(cell, i // 16, i % 16)
            self.grid_cells.append(cell)
            self.chord_labels.append(label)
            self.grid_diagrams.append(diagram)

    def _refresh_grid(self) -> None:
        if not self.song:
            return
        for i, chord in enumerate(self.song.chords):
            if chord:
                self.chord_labels[i].setText(self._display_chord(chord))
                self.grid_diagrams[i].set_chord(self._diagram_chord(chord))
        self._update_position()

    def _display_chord(self, chord: str) -> str:
        if not chord:
            return ""
        if self.show_mode.currentText() == "Banjo Shapes":
            return chord
        return transpose_chord(chord, self.capo.value())

    def _diagram_chord(self, chord: str) -> str:
        if not chord:
            return "G"
        if self.show_mode.currentText() == "Banjo Shapes":
            return chord
        # For now diagrams stay playable simple shapes; naming changes for capo/concert mode.
        return chord

    def _chord_at(self, index: int) -> str:
        if not self.song:
            return "G"
        index = max(0, min(index, len(self.song.chords) - 1))
        for i in range(index, -1, -1):
            if self.song.chords[i]:
                return self.song.chords[i]
        return "G"

    def _next_chord_after(self, index: int) -> str:
        if not self.song:
            return "G"
        current = self._chord_at(index)
        for i in range(index + 1, len(self.song.chords)):
            if self.song.chords[i] and self.song.chords[i] != current:
                return self.song.chords[i]
        return current

    def _toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.setText("⏸ Pause")
            self.timer.start()
            self.statusBar().showMessage("Playing demo grid")
        else:
            self.play_btn.setText("▶ Play")
            self.timer.stop()
            self.statusBar().showMessage("Paused")

    def _set_timer_interval(self) -> None:
        if not self.song:
            return
        self.speed_label.setText(f"{self.speed.value()}%")
        beat_ms = int(60000 / self.song.bpm)
        adjusted = int(beat_ms * 100 / self.speed.value())
        self.timer.setInterval(max(80, adjusted))

    def _advance_beat(self) -> None:
        self._move_beat(1)

    def _move_beat(self, amount: int) -> None:
        if not self.song:
            return
        self.beat_index += amount
        loop_start_index = max(0, (self.loop_start.value() - 1) * 4)
        loop_end_index = min(len(self.song.chords) - 1, self.loop_end.value() * 4 - 1)
        if self.beat_index > loop_end_index:
            self.beat_index = loop_start_index
        if self.beat_index < loop_start_index:
            self.beat_index = loop_end_index
        self._update_position()

    def _update_position(self) -> None:
        if not self.song or not self.grid_cells:
            return
        for cell in self.grid_cells:
            cell.setProperty("active", False)
            cell.style().unpolish(cell)
            cell.style().polish(cell)
        current_cell = self.grid_cells[self.beat_index]
        current_cell.setProperty("active", True)
        current_cell.style().unpolish(current_cell)
        current_cell.style().polish(current_cell)
        current = self._chord_at(self.beat_index)
        nxt = self._next_chord_after(self.beat_index)
        self.current_panel.set_chord(self._display_chord(current))
        self.current_panel.diagram.set_chord(self._diagram_chord(current))
        self.next_panel.set_chord(self._display_chord(nxt))
        self.next_panel.diagram.set_chord(self._diagram_chord(nxt))
        row = self.beat_index // 16
        self.scroll.ensureWidgetVisible(current_cell, 40, 40)
        self.statusBar().showMessage(f"Beat {self.beat_index + 1} • Row {row + 1} • Current {self._display_chord(current)} • Next {self._display_chord(nxt)}")

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        return frame

    def _info_box(self, label: str, value: str) -> dict[str, object]:
        frame = QFrame()
        frame.setObjectName("InfoBox")
        layout = QHBoxLayout(frame)
        layout.addWidget(QLabel(label))
        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignRight)
        val.setStyleSheet("font-weight: bold;")
        layout.addWidget(val)
        return {"frame": frame, "value": val}

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
            QFrame#InfoBox, QFrame#ResultItemFrame {
                background: #202020;
                border: 1px solid #333333;
                border-radius: 6px;
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
            QPushButton:hover {
                background: #3b3b3b;
            }
            QFrame#BeatCell {
                background: #1d1d1d;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
            }
            QFrame#BeatCell[active="true"] {
                background: #5a3d12;
                border: 2px solid #f3c25b;
                border-radius: 4px;
            }
            """
        )
