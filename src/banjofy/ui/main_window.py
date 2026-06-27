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

BUILD_LABEL = "Banjofy 0.2.6 - Build 002.6 Loop Select + To Start"


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
        self.loop_start_bar: int | None = None
        self.loop_end_bar: int | None = None
        self.loop_select_mode: str | None = None
        self.is_counting_in = False
        self.count_in_remaining = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_beat)

        self._apply_style()
        self.setCentralWidget(self._build_ui())
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Build 002.6 ready - click a beat to set loop start/end")
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
        self.search.setPlaceholderText("Build 002.6: demo search only - audio comes later")
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
        controls_layout.setContentsMargins(12, 8, 12, 8)
        controls_layout.setSpacing(10)

        self.to_start_btn = QPushButton("⏮ To Start")
        self.back_btn = QPushButton("◀ Back")
        self.play_btn = QPushButton("▶ Play")
        self.forward_btn = QPushButton("Forward ▶")
        self.to_start_btn.setMinimumWidth(110)
        self.back_btn.setMinimumWidth(90)
        self.play_btn.setMinimumWidth(95)
        self.forward_btn.setMinimumWidth(105)
        self.to_start_btn.clicked.connect(self._jump_to_start)
        self.back_btn.clicked.connect(lambda: self._move_beat(-1))
        self.play_btn.clicked.connect(self._toggle_play)
        self.forward_btn.clicked.connect(lambda: self._move_beat(1))
        controls_layout.addWidget(self.to_start_btn)
        controls_layout.addWidget(self.back_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.forward_btn)

        loop_box = QFrame()
        loop_box.setObjectName("ControlGroup")
        loop_layout = QHBoxLayout(loop_box)
        loop_layout.setContentsMargins(10, 4, 10, 4)
        loop_layout.setSpacing(8)
        loop_layout.addWidget(QLabel("Loop"))
        self.loop_start_label = QLabel("Start: —")
        self.loop_start_label.setMinimumWidth(70)
        self.loop_end_label = QLabel("End: —")
        self.loop_end_label.setMinimumWidth(70)
        self.set_loop_start_btn = QPushButton("Select Start")
        self.set_loop_end_btn = QPushButton("Select End")
        self.clear_loop_btn = QPushButton("Clear Loop")
        self.set_loop_start_btn.setMinimumWidth(130)
        self.set_loop_end_btn.setMinimumWidth(120)
        self.clear_loop_btn.setMinimumWidth(120)
        self.set_loop_start_btn.clicked.connect(self._set_loop_start)
        self.set_loop_end_btn.clicked.connect(self._set_loop_end)
        self.clear_loop_btn.clicked.connect(self._clear_loop)
        loop_layout.addWidget(self.loop_start_label)
        loop_layout.addWidget(self.loop_end_label)
        loop_layout.addWidget(self.set_loop_start_btn)
        loop_layout.addWidget(self.set_loop_end_btn)
        loop_layout.addWidget(self.clear_loop_btn)
        loop_box.setMinimumWidth(680)
        controls_layout.addWidget(loop_box, 0)

        speed_box = QFrame()
        speed_box.setObjectName("ControlGroup")
        speed_layout = QHBoxLayout(speed_box)
        speed_layout.setContentsMargins(10, 4, 10, 4)
        speed_layout.setSpacing(8)
        speed_layout.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(50, 150)
        self.speed.setValue(100)
        self.speed.setMinimumWidth(190)
        self.speed.valueChanged.connect(self._set_timer_interval)
        speed_layout.addWidget(self.speed)
        self.speed_label = QLabel("100%")
        self.speed_label.setMinimumWidth(48)
        speed_layout.addWidget(self.speed_label)
        controls_layout.addWidget(speed_box, 1)

        count_box = QFrame()
        count_box.setObjectName("ControlGroup")
        count_layout = QHBoxLayout(count_box)
        count_layout.setContentsMargins(10, 4, 10, 4)
        count_layout.setSpacing(8)
        count_layout.addWidget(QLabel("Count-in"))
        self.count_in = QComboBox()
        self.count_in.addItems(["0", "1", "2", "3", "4", "8"])
        self.count_in.setCurrentText("4")
        self.count_in.setMinimumWidth(70)
        count_layout.addWidget(self.count_in)
        self.count_in_display = QLabel("Ready")
        self.count_in_display.setObjectName("CountInDisplay")
        self.count_in_display.setMinimumWidth(110)
        self.count_in_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(self.count_in_display)
        controls_layout.addWidget(count_box, 0)

        controls_layout.addStretch()
        outer.addWidget(controls, 0)

        grid_panel = self._panel()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.addWidget(QLabel("Build 002.6 demo beat grid - click a beat to set loop start/end; 3 bars across / 12 beats per row"))
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
        self._clear_loop()
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
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            cell.mousePressEvent = lambda event, idx=i: self._grid_cell_clicked(idx)  # type: ignore[method-assign]
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

            group = i // 12
            col = i % 12
            if col == 0:
                for bar_offset in range(3):
                    bar_number = group * 3 + bar_offset + 1
                    if (bar_number - 1) * 4 < len(self.song.chords):
                        header = QLabel(f"Bar {bar_number}")
                        header.setObjectName("BarHeader")
                        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.grid_layout.addWidget(header, group * 2, bar_offset * 4, 1, 4)
            self.grid_layout.addWidget(cell, group * 2 + 1, col)
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

    def _current_bar(self) -> int:
        return self.beat_index // 4 + 1

    def _set_loop_start(self) -> None:
        self.loop_select_mode = "start"
        self.statusBar().showMessage("Click any beat in the grid to set the loop START bar")
        self.set_loop_start_btn.setText("Click beat…")
        self.set_loop_end_btn.setText("Select End")

    def _set_loop_end(self) -> None:
        self.loop_select_mode = "end"
        self.statusBar().showMessage("Click any beat in the grid to set the loop END bar")
        self.set_loop_end_btn.setText("Click beat…")
        self.set_loop_start_btn.setText("Select Start")

    def _grid_cell_clicked(self, beat_index: int) -> None:
        bar = beat_index // 4 + 1
        if self.loop_select_mode == "start":
            self.loop_start_bar = bar
            self.loop_select_mode = None
            self.statusBar().showMessage(f"Loop start set to bar {bar}")
        elif self.loop_select_mode == "end":
            self.loop_end_bar = bar
            self.loop_select_mode = None
            self.statusBar().showMessage(f"Loop end set to bar {bar}")
        else:
            self.beat_index = beat_index
            self.statusBar().showMessage(f"Moved cursor to bar {bar}, beat {(beat_index % 4) + 1}")
        if self.loop_start_bar is not None and self.loop_end_bar is not None and self.loop_start_bar > self.loop_end_bar:
            self.loop_start_bar, self.loop_end_bar = self.loop_end_bar, self.loop_start_bar
        self.set_loop_start_btn.setText("Select Start")
        self.set_loop_end_btn.setText("Select End")
        self._update_loop_labels()
        self._update_position()

    def _clear_loop(self) -> None:
        self.loop_start_bar = None
        self.loop_end_bar = None
        self.loop_select_mode = None
        if hasattr(self, "set_loop_start_btn"):
            self.set_loop_start_btn.setText("Select Start")
            self.set_loop_end_btn.setText("Select End")
        if hasattr(self, "loop_start_label"):
            self._update_loop_labels()

    def _loop_is_active(self) -> bool:
        return self.loop_start_bar is not None and self.loop_end_bar is not None

    def _update_loop_labels(self) -> None:
        self.loop_start_label.setText(f"Start: {self.loop_start_bar}" if self.loop_start_bar else "Start: —")
        self.loop_end_label.setText(f"End: {self.loop_end_bar}" if self.loop_end_bar else "End: —")
        active = self._loop_is_active()
        self.clear_loop_btn.setEnabled(active)


    def _jump_to_start(self) -> None:
        if not self.song:
            return
        if self._loop_is_active():
            start_bar = min(self.loop_start_bar, self.loop_end_bar)  # type: ignore[arg-type]
            self.beat_index = max(0, (start_bar - 1) * 4)
            self.statusBar().showMessage(f"Jumped to loop start: bar {start_bar}")
        else:
            self.beat_index = 0
            self.statusBar().showMessage("Jumped to song start")
        self._update_position()

    def _toggle_play(self) -> None:
        if self.is_playing or self.is_counting_in:
            self.is_playing = False
            self.is_counting_in = False
            self.timer.stop()
            self.play_btn.setText("▶ Play")
            self.count_in_display.setText("Ready")
            self.statusBar().showMessage("Paused")
            return

        if self._loop_is_active():
            start_bar = min(self.loop_start_bar, self.loop_end_bar)  # type: ignore[arg-type]
            self.beat_index = max(0, (start_bar - 1) * 4)
            self._update_position()

        beats = int(self.count_in.currentText())
        if beats > 0:
            self.is_counting_in = True
            self.count_in_remaining = beats
            self.play_btn.setText("⏸ Cancel")
            self.count_in_display.setText(str(self.count_in_remaining))
            self.timer.start()
            self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
            return

        self._start_playback_after_count_in()

    def _start_playback_after_count_in(self) -> None:
        self.is_counting_in = False
        self.is_playing = True
        self.play_btn.setText("⏸ Pause")
        self.count_in_display.setText("Play")
        self.timer.start()
        self.statusBar().showMessage("Playing demo grid")

    def _set_timer_interval(self) -> None:
        if not self.song:
            return
        self.speed_label.setText(f"{self.speed.value()}%")
        beat_ms = int(60000 / self.song.bpm)
        adjusted = int(beat_ms * 100 / self.speed.value())
        self.timer.setInterval(max(80, adjusted))

    def _advance_beat(self) -> None:
        if self.is_counting_in:
            self.count_in_remaining -= 1
            if self.count_in_remaining > 0:
                self.count_in_display.setText(str(self.count_in_remaining))
                self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
                return
            self._start_playback_after_count_in()
            return
        self._move_beat(1)

    def _move_beat(self, amount: int) -> None:
        if not self.song:
            return
        self.beat_index += amount
        if self._loop_is_active():
            start_bar, end_bar = sorted((self.loop_start_bar, self.loop_end_bar))  # type: ignore[arg-type]
            loop_start_index = max(0, (start_bar - 1) * 4)
            loop_end_index = min(len(self.song.chords) - 1, end_bar * 4 - 1)
            if self.beat_index > loop_end_index:
                self.beat_index = loop_start_index
            if self.beat_index < loop_start_index:
                self.beat_index = loop_end_index
        else:
            if self.beat_index >= len(self.song.chords):
                self.beat_index = len(self.song.chords) - 1
            if self.beat_index < 0:
                self.beat_index = 0
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
        row = self.beat_index // 12
        self.scroll.ensureWidgetVisible(current_cell, 40, 40)
        loop_text = " • Loop ON" if self._loop_is_active() else ""
        self.statusBar().showMessage(f"Beat {self.beat_index + 1} • Row {row + 1} • Current {self._display_chord(current)} • Next {self._display_chord(nxt)}{loop_text}")

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
            QFrame#InfoBox, QFrame#ResultItemFrame, QFrame#ControlGroup {
                background: #202020;
                border: 1px solid #333333;
                border-radius: 6px;
            }
            QLabel#CountInDisplay {
                background: #111111;
                color: #f3c25b;
                border: 1px solid #574018;
                border-radius: 6px;
                padding: 7px;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#BarHeader {
                background: #171717;
                color: #cdbb99;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #252525;
                color: #f3e6cc;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 6px;
                min-height: 24px;
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
