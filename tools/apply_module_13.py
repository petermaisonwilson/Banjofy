from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 12A Build 001 - Download Compatibility"':
        'APP_VERSION = "Banjofy 006.3.0 Module 13 Build 001 - Repeat Sections"',
    'self.statusBar().showMessage("Ready - Module 12A grid seeking and resilient download loaded")':
        'self.statusBar().showMessage("Ready - Module 13 repeat sections loaded")',
    'note = QLabel("Module 12A: Clickable grid seeking with improved YouTube download compatibility.")':
        'note = QLabel("Module 13: Select repeat start and end beats, then loop the chosen section.")',
    'title = QLabel("Practice Studio - Module 12A")':
        'title = QLabel("Practice Studio - Module 13")',
    'hint = QLabel("Module 12A: Click a bar or beat to jump there. Chords remain provisional.")':
        'hint = QLabel("Module 13: Click a beat, set repeat start/end, then enable Repeat. Chords remain provisional.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 12A text not found: {old}")
    text = text.replace(old, new, 1)

# Add repeat state after the existing tap/BPM state.
state_anchor = "        self.tap_times: list[float] = []\n"
state_block = (
    "        self.tap_times: list[float] = []\n"
    "        self.repeat_start_beat: int | None = None\n"
    "        self.repeat_end_beat: int | None = None\n"
    "        self.repeat_enabled = False\n"
    "        self.repeat_jump_pending = False\n"
)

if "self.repeat_start_beat" not in text:
    if state_anchor not in text:
        raise RuntimeError("Could not find Module 11/12 state anchor.")
    text = text.replace(state_anchor, state_block, 1)

# Add repeat controls beneath the grid status label.
ui_anchor = '''        self.grid_status_label = QLabel("Grid: no song loaded")
        self.grid_status_label.setObjectName("LibraryMessage")
        self.grid_status_label.setWordWrap(True)
        right.addWidget(self.grid_status_label)

        self.beat_grid_container = QWidget()
'''

ui_block = '''        self.grid_status_label = QLabel("Grid: no song loaded")
        self.grid_status_label.setObjectName("LibraryMessage")
        self.grid_status_label.setWordWrap(True)
        right.addWidget(self.grid_status_label)

        self.repeat_status_label = QLabel("Repeat: not set")
        self.repeat_status_label.setObjectName("LibraryMessage")
        self.repeat_status_label.setWordWrap(True)
        right.addWidget(self.repeat_status_label)

        repeat_controls = QHBoxLayout()
        self.repeat_start_button = QPushButton("Set Start")
        self.repeat_end_button = QPushButton("Set End")
        self.repeat_toggle_button = QPushButton("Repeat Off")
        self.repeat_clear_button = QPushButton("Clear Repeat")
        self.repeat_toggle_button.setCheckable(True)

        self.repeat_start_button.clicked.connect(self._set_repeat_start)
        self.repeat_end_button.clicked.connect(self._set_repeat_end)
        self.repeat_toggle_button.toggled.connect(self._toggle_repeat)
        self.repeat_clear_button.clicked.connect(self._clear_repeat)

        repeat_controls.addWidget(self.repeat_start_button)
        repeat_controls.addWidget(self.repeat_end_button)
        repeat_controls.addWidget(self.repeat_toggle_button)
        repeat_controls.addWidget(self.repeat_clear_button)
        right.addLayout(repeat_controls)

        self.beat_grid_container = QWidget()
'''

if "self.repeat_status_label" not in text:
    if ui_anchor not in text:
        raise RuntimeError("Could not find grid status UI anchor.")
    text = text.replace(ui_anchor, ui_block, 1)

# Clear repeat selection when a different song is loaded.
load_anchor = '''        self.tap_times = []
        self.practice_bpm_label.setText(f"BPM: {self.current_practice_bpm}")
'''

load_block = '''        self.tap_times = []
        self.repeat_start_beat = None
        self.repeat_end_beat = None
        self.repeat_enabled = False
        self.repeat_jump_pending = False
        if hasattr(self, "repeat_toggle_button"):
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(False)
            self.repeat_toggle_button.setText("Repeat Off")
            self.repeat_toggle_button.blockSignals(False)
        self.practice_bpm_label.setText(f"BPM: {self.current_practice_bpm}")
'''

if load_anchor not in text:
    raise RuntimeError("Could not find song-load state anchor.")
text = text.replace(load_anchor, load_block, 1)

# Insert repeat functions before grid click handling.
method_anchor = "    def _grid_cell_clicked(self, event, beat_index: int) -> None:\n"

methods = '''    def _beat_label(self, beat_index: int | None) -> str:
        if beat_index is None:
            return "not set"
        return f"Bar {beat_index // 4 + 1}, Beat {beat_index % 4 + 1}"

    def _repeat_bounds_ms(self) -> tuple[int, int] | None:
        if self.repeat_start_beat is None or self.repeat_end_beat is None:
            return None
        if not self.practice_song:
            return None

        bpm = int(self.current_practice_bpm or self.practice_song.bpm or 0)
        if bpm <= 0:
            return None

        start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
        end_beat = max(self.repeat_start_beat, self.repeat_end_beat)
        beat_ms = 60000.0 / bpm

        start_ms = int(round(start_beat * beat_ms))
        # End is exclusive so the selected final beat plays in full.
        end_ms = int(round((end_beat + 1) * beat_ms))

        duration = int(self.media_player.duration())
        if duration > 0:
            start_ms = max(0, min(start_ms, max(0, duration - 1)))
            end_ms = max(start_ms + 1, min(end_ms, duration))

        return start_ms, end_ms

    def _update_repeat_status(self) -> None:
        if not hasattr(self, "repeat_status_label"):
            return

        state = "ON" if self.repeat_enabled else "OFF"
        self.repeat_status_label.setText(
            f"Repeat {state} | Start: {self._beat_label(self.repeat_start_beat)} | "
            f"End: {self._beat_label(self.repeat_end_beat)}"
        )
        self._refresh_repeat_markers()

    def _set_repeat_start(self) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a song and click a beat first.")
            return

        self.repeat_start_beat = int(self.current_beat_index)
        if self.repeat_end_beat is not None and self.repeat_end_beat < self.repeat_start_beat:
            self.repeat_end_beat = self.repeat_start_beat

        self._update_repeat_status()
        self.practice_message.setText(
            f"Repeat start set to {self._beat_label(self.repeat_start_beat)}."
        )

    def _set_repeat_end(self) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a song and click a beat first.")
            return

        self.repeat_end_beat = int(self.current_beat_index)
        if self.repeat_start_beat is not None and self.repeat_end_beat < self.repeat_start_beat:
            self.repeat_start_beat = self.repeat_end_beat

        self._update_repeat_status()
        self.practice_message.setText(
            f"Repeat end set to {self._beat_label(self.repeat_end_beat)}."
        )

    def _toggle_repeat(self, enabled: bool) -> None:
        if enabled and (self.repeat_start_beat is None or self.repeat_end_beat is None):
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(False)
            self.repeat_toggle_button.blockSignals(False)
            self.repeat_toggle_button.setText("Repeat Off")
            self.repeat_enabled = False
            self.practice_message.setText("Set both repeat start and repeat end first.")
            self._update_repeat_status()
            return

        self.repeat_enabled = bool(enabled)
        self.repeat_toggle_button.setText("Repeat On" if self.repeat_enabled else "Repeat Off")
        self._update_repeat_status()

        if self.repeat_enabled:
            bounds = self._repeat_bounds_ms()
            if bounds is not None:
                start_ms, end_ms = bounds
                current = int(self.media_player.position())
                if current < start_ms or current >= end_ms:
                    self._seek_to_grid_beat(min(self.repeat_start_beat, self.repeat_end_beat))
            self.practice_message.setText("Repeat enabled for the selected section.")
        else:
            self.practice_message.setText("Repeat disabled.")

    def _clear_repeat(self) -> None:
        self.repeat_start_beat = None
        self.repeat_end_beat = None
        self.repeat_enabled = False
        self.repeat_jump_pending = False

        if hasattr(self, "repeat_toggle_button"):
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(False)
            self.repeat_toggle_button.setText("Repeat Off")
            self.repeat_toggle_button.blockSignals(False)

        self._update_repeat_status()
        self.practice_message.setText("Repeat selection cleared.")

    def _refresh_repeat_markers(self) -> None:
        if not self.grid_cells:
            return

        for index, cell in enumerate(self.grid_cells):
            marker = ""
            if index == self.repeat_start_beat and index == self.repeat_end_beat:
                marker = "S/E "
            elif index == self.repeat_start_beat:
                marker = "S "
            elif index == self.repeat_end_beat:
                marker = "E "

            current_text = cell.text()
            for prefix in ("S/E ", "S ", "E "):
                if current_text.startswith(prefix):
                    current_text = current_text[len(prefix):]
                    break
            cell.setText(marker + current_text)

    def _check_repeat_loop(self, position: int) -> bool:
        if not self.repeat_enabled or self.repeat_jump_pending:
            return False

        bounds = self._repeat_bounds_ms()
        if bounds is None:
            return False

        start_ms, end_ms = bounds
        if position < end_ms:
            return False

        self.repeat_jump_pending = True
        try:
            self.media_player.setPosition(start_ms)

            if hasattr(self, "position_slider"):
                blocked = self.position_slider.blockSignals(True)
                self.position_slider.setValue(start_ms)
                self.position_slider.blockSignals(blocked)

            start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
            self._highlight_beat(start_beat)

            if hasattr(self, "time_label"):
                self._update_time_label(start_ms, self.media_player.duration())
        finally:
            self.repeat_jump_pending = False

        return True

'''

if "def _set_repeat_start" not in text:
    if method_anchor not in text:
        raise RuntimeError("Could not find grid-click method anchor.")
    text = text.replace(method_anchor, methods + method_anchor, 1)

# Ensure repeat markers remain visible after normal beat highlighting.
highlight_anchor = '''        self._scroll_grid_to_beat(beat_index)
'''

highlight_block = '''        self._refresh_repeat_markers()
        self._scroll_grid_to_beat(beat_index)
'''

if highlight_anchor not in text:
    raise RuntimeError("Could not find highlight scroll anchor.")
text = text.replace(highlight_anchor, highlight_block, 1)

# Add repeat loop check to player position callback.
position_anchor = '''    def _player_position_changed(self, position: int) -> None:
        if self.practice_stop_reset_pending:
            return
'''

position_block = '''    def _player_position_changed(self, position: int) -> None:
        if self.practice_stop_reset_pending:
            return
        if self._check_repeat_loop(position):
            return
'''

if position_anchor not in text:
    raise RuntimeError("Could not find player position callback anchor.")
text = text.replace(position_anchor, position_block, 1)

# Keep repeat status and markers current when the grid is rebuilt.
grid_done_anchor = '''        self.grid_status_label.setText(f"Grid: {bars} bars / {bars * 4} beats | provisional chords")
        self._highlight_beat(0)
'''

grid_done_block = '''        self.grid_status_label.setText(f"Grid: {bars} bars / {bars * 4} beats | provisional chords")
        self._highlight_beat(0)
        self._update_repeat_status()
'''

if grid_done_anchor not in text:
    raise RuntimeError("Could not find grid completion anchor.")
text = text.replace(grid_done_anchor, grid_done_block, 1)

required = [
    "Module 13 Build 001",
    "Practice Studio - Module 13",
    "def _set_repeat_start",
    "def _set_repeat_end",
    "def _toggle_repeat",
    "def _check_repeat_loop",
    "Repeat On",
    "Clear Repeat",
]

missing = [item for item in required if item not in text]
if missing:
    raise RuntimeError("Module 13 patch verification failed: " + ", ".join(missing))

path.write_text(text, encoding="utf-8")
print("Module 13 repeat sections applied.")
