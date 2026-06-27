from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from banjofy.player.demo_data import DEMO_SONGS, DemoSong
from banjofy.ui.widgets import BeatCell, ChordPanel

APP_VERSION = "Banjofy 0.3.1 - Build 003.1 Restore 002.6 + Layout"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_VERSION)
        self.resize(1360, 840)
        self.setMinimumSize(980, 650)

        self.song: DemoSong = DEMO_SONGS[0]
        self.position = 0
        self.is_playing = False
        self.count_in_remaining = 0
        self.loop_start: int | None = None
        self.loop_end: int | None = None
        self.selection_mode: str | None = None
        self.cells: list[BeatCell] = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._apply_style()
        self.setCentralWidget(self._build_ui())
        self.setStatusBar(QStatusBar())
        self._load_song(self.song)
        self._update_all()
        self.statusBar().showMessage("Build 003.1 ready - restored demo player/navigation. Real audio is next.")

    def _build_ui(self) -> QWidget:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(6)
        outer.addLayout(top, 0)

        # Search / demo song choice panel. YouTube integration will attach here later.
        search_panel = self._panel()
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("YouTube search comes after layout/player stability - demo songs below for now")
        search_button = QPushButton("Search")
        search_button.setEnabled(False)
        search_row.addWidget(self.search)
        search_row.addWidget(search_button)
        search_layout.addLayout(search_row)
        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(150)
        self.result_list.currentRowChanged.connect(self._select_demo_song)
        for song in DEMO_SONGS:
            self.result_list.addItem(QListWidgetItem(f"{song.title}\n{song.artist} · {song.duration} · {song.bpm} BPM"))
        search_layout.addWidget(self.result_list)
        top.addWidget(search_panel, 2)

        meta_panel = self._panel()
        meta_layout = QVBoxLayout(meta_panel)
        meta_layout.setContentsMargins(8, 6, 8, 6)
        self.title_label = QLabel("—")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f3d99a;")
        self.artist_label = QLabel("—")
        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.artist_label)
        self.bpm_label = QLabel("BPM: —")
        self.key_label = QLabel("Key: —")
        self.duration_label = QLabel("Duration: —")
        for w in [self.bpm_label, self.key_label, self.duration_label]:
            meta_layout.addWidget(w)
        top.addWidget(meta_panel, 1)

        centre = self._panel()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(8, 6, 8, 6)
        title = QLabel(APP_VERSION)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f3d99a;")
        centre_layout.addWidget(title)
        chord_row = QHBoxLayout()
        self.current_panel = ChordPanel("CURRENT", "—", "#65b95c")
        self.next_panel = ChordPanel("NEXT", "—", "#c99424", "in 1 beat")
        chord_row.addWidget(self.current_panel, 1)
        chord_row.addWidget(self.next_panel, 1)
        centre_layout.addLayout(chord_row)
        top.addWidget(centre, 4)

        settings = self._panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(8, 6, 8, 6)
        settings_layout.addWidget(QLabel("Mode"))
        self.mode = QComboBox()
        self.mode.addItems(["Beginner", "Intermediate", "Professional"])
        self.mode.setCurrentText("Intermediate")
        self.mode.currentTextChanged.connect(self._mode_changed)
        settings_layout.addWidget(self.mode)
        settings_layout.addWidget(QLabel("Capo"))
        self.capo = QSpinBox()
        self.capo.setRange(0, 12)
        self.capo.valueChanged.connect(self._update_all)
        settings_layout.addWidget(self.capo)
        settings_layout.addWidget(QLabel("Show"))
        self.show_mode = QComboBox()
        self.show_mode.addItems(["Concert Chords", "Banjo Shapes"])
        self.show_mode.currentTextChanged.connect(self._update_all)
        settings_layout.addWidget(self.show_mode)
        settings_layout.addWidget(QLabel("Count-in"))
        self.count_in = QComboBox()
        self.count_in.addItems(["0", "1", "2", "3", "4", "8"])
        self.count_in.setCurrentText("4")
        settings_layout.addWidget(self.count_in)
        settings_layout.addStretch()
        top.addWidget(settings, 1)

        controls = self._panel()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 6, 8, 6)
        controls_layout.setSpacing(8)
        self.back_btn = QPushButton("⏮ Back")
        self.back_btn.clicked.connect(self._back)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._play_pause)
        self.forward_btn = QPushButton("⏭ Forward")
        self.forward_btn.clicked.connect(self._forward)
        self.start_btn = QPushButton("⇤ To Start")
        self.start_btn.clicked.connect(self._to_start)
        for btn in [self.back_btn, self.play_btn, self.forward_btn, self.start_btn]:
            controls_layout.addWidget(btn)

        loop_box = self._panel("LoopBox")
        loop_layout = QHBoxLayout(loop_box)
        loop_layout.setContentsMargins(8, 4, 8, 4)
        self.loop_status = QLabel("Loop: off")
        self.select_start_btn = QPushButton("Select Start")
        self.select_start_btn.clicked.connect(lambda: self._set_selection_mode("start"))
        self.select_end_btn = QPushButton("Select End")
        self.select_end_btn.clicked.connect(lambda: self._set_selection_mode("end"))
        self.clear_loop_btn = QPushButton("Clear Loop")
        self.clear_loop_btn.clicked.connect(self._clear_loop)
        for w in [self.loop_status, self.select_start_btn, self.select_end_btn, self.clear_loop_btn]:
            loop_layout.addWidget(w)
        controls_layout.addWidget(loop_box, 2)

        controls_layout.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(50, 125)
        self.speed.setValue(100)
        self.speed.valueChanged.connect(self._speed_changed)
        self.speed.setMinimumWidth(150)
        controls_layout.addWidget(self.speed)
        self.speed_label = QLabel("100%")
        controls_layout.addWidget(self.speed_label)
        controls_layout.addStretch()
        outer.addWidget(controls, 0)

        grid_panel = self._panel()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(8, 6, 8, 6)
        grid_layout.addWidget(QLabel("Beat grid - 3 bars across / 12 beat squares per row. Click a beat when selecting loop start/end."))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.scroll.setWidget(self.grid_host)
        grid_layout.addWidget(self.scroll)
        outer.addWidget(grid_panel, 1)

        return root

    def _load_song(self, song: DemoSong) -> None:
        self.song = song
        self.position = 0
        self.loop_start = None
        self.loop_end = None
        self.selection_mode = None
        self.title_label.setText(song.title)
        self.artist_label.setText(song.artist)
        self.bpm_label.setText(f"BPM: {song.bpm}")
        self.key_label.setText(f"Key: {song.key}")
        self.duration_label.setText(f"Duration: {song.duration}")
        self._build_grid()
        self._update_loop_status()
        self._update_all()

    def _select_demo_song(self, row: int) -> None:
        if 0 <= row < len(DEMO_SONGS):
            self._stop()
            self._load_song(DEMO_SONGS[row])
            self.statusBar().showMessage(f"Loaded demo: {DEMO_SONGS[row].title}")

    def _build_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cells = []
        beats = self.song.beat_chords
        bars_per_row = 3
        beats_per_row = bars_per_row * 4
        for bar_start in range(0, len(beats), beats_per_row):
            visual_row = (bar_start // beats_per_row) * 2
            for bar_offset in range(bars_per_row):
                bar_num = (bar_start // 4) + bar_offset + 1
                if (bar_num - 1) * 4 >= len(beats):
                    continue
                hdr = QLabel(f"Bar {bar_num}")
                hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hdr.setObjectName("BarHeader")
                self.grid.addWidget(hdr, visual_row, bar_offset * 4, 1, 4)
            for i in range(beats_per_row):
                idx = bar_start + i
                if idx >= len(beats):
                    break
                chord = self._display_chord(beats[idx]) if beats[idx] else ""
                cell = BeatCell(idx, str((idx % 4) + 1), chord)
                cell.clicked.connect(self._cell_clicked)
                self.cells.append(cell)
                self.grid.addWidget(cell, visual_row + 1, i)
        for col in range(beats_per_row):
            self.grid.setColumnStretch(col, 1)

    def _display_chord(self, chord: str) -> str:
        if not chord:
            return ""
        if self.show_mode.currentText() == "Concert Chords":
            return transpose_chord(chord, self.capo.value())
        return chord

    def _shape_chord(self, chord: str) -> str:
        # In banjo-shape display, diagrams use the shape. In concert display, for now we keep the same shape
        # while the name changes, which mirrors capo use. A fuller voicing engine comes later.
        return chord

    def _current_raw_chord(self) -> str:
        beats = self.song.beat_chords
        for i in range(min(self.position, len(beats) - 1), -1, -1):
            if beats[i]:
                return beats[i]
        return "G"

    def _next_raw_chord(self) -> str:
        beats = self.song.beat_chords
        current = self._current_raw_chord()
        for i in range(self.position + 1, len(beats)):
            if beats[i] and beats[i] != current:
                return beats[i]
        return ""

    def _update_all(self) -> None:
        current = self._current_raw_chord()
        nxt = self._next_raw_chord()
        self.current_panel.set_chord(self._display_chord(current))
        self.next_panel.set_chord(self._display_chord(nxt) if nxt else "—")
        for idx, cell in enumerate(self.cells):
            raw = self.song.beat_chords[idx]
            cell.set_chord(self._display_chord(raw) if raw else "")
            cell.set_active(idx == self.position)
            cell.set_loop(self.loop_start is not None and self.loop_end is not None and self.loop_start <= idx <= self.loop_end)
        self._scroll_to_position()

    def _scroll_to_position(self) -> None:
        if not self.cells or self.position >= len(self.cells):
            return
        cell = self.cells[self.position]
        self.scroll.ensureWidgetVisible(cell, 20, 20)

    def _play_pause(self) -> None:
        if self.is_playing:
            self._stop()
            return
        if self.loop_start is not None and self.loop_end is not None:
            self.position = self.loop_start
        self.count_in_remaining = int(self.count_in.currentText())
        self.is_playing = True
        self.play_btn.setText("⏸ Pause")
        if self.count_in_remaining:
            self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
        else:
            self.statusBar().showMessage("Playing demo timing grid - no audio yet")
        self._update_all()
        self.timer.start(self._interval_ms())

    def _stop(self) -> None:
        self.is_playing = False
        self.timer.stop()
        self.play_btn.setText("▶ Play")
        self.statusBar().showMessage("Paused")

    def _tick(self) -> None:
        if self.count_in_remaining > 0:
            self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
            self.count_in_remaining -= 1
            return
        if self.count_in_remaining == 0:
            self.count_in_remaining = -1
            self.statusBar().showMessage("Playing demo timing grid - no audio yet")
        self._advance_one()

    def _advance_one(self) -> None:
        end = len(self.song.beat_chords) - 1
        if self.loop_start is not None and self.loop_end is not None:
            if self.position >= self.loop_end:
                self.position = self.loop_start
            else:
                self.position += 1
        else:
            if self.position >= end:
                self._stop()
                return
            self.position += 1
        self._update_all()

    def _back(self) -> None:
        if self.position > 0:
            self.position -= 1
            self._update_all()

    def _forward(self) -> None:
        if self.position < len(self.song.beat_chords) - 1:
            self.position += 1
            self._update_all()

    def _to_start(self) -> None:
        self.position = self.loop_start if self.loop_start is not None else 0
        self._update_all()

    def _speed_changed(self, value: int) -> None:
        self.speed_label.setText(f"{value}%")
        if self.timer.isActive():
            self.timer.start(self._interval_ms())

    def _interval_ms(self) -> int:
        speed_factor = self.speed.value() / 100
        return max(120, int((60000 / self.song.bpm) / speed_factor))

    def _set_selection_mode(self, mode: str) -> None:
        self.selection_mode = mode
        self.statusBar().showMessage(f"Click a beat square to set loop {mode}")

    def _cell_clicked(self, index: int) -> None:
        if self.selection_mode == "start":
            self.loop_start = index
            if self.loop_end is not None and self.loop_end < self.loop_start:
                self.loop_end = None
            self.selection_mode = None
        elif self.selection_mode == "end":
            if self.loop_start is None:
                self.loop_start = index
            else:
                self.loop_end = max(index, self.loop_start)
            self.selection_mode = None
        else:
            self.position = index
        self._update_loop_status()
        self._update_all()

    def _clear_loop(self) -> None:
        self.loop_start = None
        self.loop_end = None
        self.selection_mode = None
        self._update_loop_status()
        self._update_all()

    def _update_loop_status(self) -> None:
        if self.loop_start is None or self.loop_end is None:
            self.loop_status.setText("Loop: off")
        else:
            self.loop_status.setText(f"Loop: bar {self.loop_start // 4 + 1} to {self.loop_end // 4 + 1}")

    def _mode_changed(self) -> None:
        # Placeholder for future chord simplification. Visible message confirms the control is wired.
        self.statusBar().showMessage(f"Mode set to {self.mode.currentText()} - simplification engine comes later")
        self._update_all()

    def _panel(self, name: str = "Panel") -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        return frame

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111111;
                color: #f3e6cc;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#Panel, QFrame#LoopBox {
                background: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            QLabel#BarHeader {
                background: #2a2418;
                color: #f3d99a;
                border: 1px solid #4b3920;
                border-radius: 4px;
                padding: 3px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox, QListWidget {
                background: #252525;
                color: #f3e6cc;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background: #2f2f2f;
                color: #f3e6cc;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 82px;
            }
            QPushButton:hover { background: #3b3b3b; }
            QScrollArea { border: none; }
            """
        )
