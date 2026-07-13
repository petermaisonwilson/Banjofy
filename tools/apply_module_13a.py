from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 13 Build 001 - Repeat Sections"':
        'APP_VERSION = "Banjofy 006.3.0 Module 13A Build 001 - Count-In Practice"',
    'self.statusBar().showMessage("Ready - Module 13 repeat sections loaded")':
        'self.statusBar().showMessage("Ready - Module 13A count-in practice loaded")',
    'note = QLabel("Module 13: Select repeat start and end beats, then loop the chosen section.")':
        'note = QLabel("Module 13A: Adjustable count-in before every Play; repeat sections play once.")',
    'title = QLabel("Practice Studio - Module 13")':
        'title = QLabel("Practice Studio - Module 13A")',
    'hint = QLabel("Module 13: Click a beat, set repeat start/end, then enable Repeat. Chords remain provisional.")':
        'hint = QLabel("Module 13A: Choose 2-5 count-in beats. Repeat sections play once per Play press.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 13 text not found: {old}")
    text = text.replace(old, new, 1)

# Add count-in state.
state_anchor = "        self.repeat_jump_pending = False\n"
state_block = (
    "        self.repeat_jump_pending = False\n"
    "        self.count_in_beats = 4\n"
    "        self.count_in_remaining = 0\n"
    "        self.count_in_token = 0\n"
    "        self.count_in_active = False\n"
)

if "self.count_in_beats" not in text:
    if state_anchor not in text:
        raise RuntimeError("Could not find Module 13 repeat state anchor.")
    text = text.replace(state_anchor, state_block, 1)

# Add count-in controls above normal playback controls.
controls_anchor = '''        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
'''

controls_block = '''        count_in_row = QHBoxLayout()
        self.count_in_button = QPushButton("Count-in: 4")
        self.count_in_button.setToolTip("Click to choose 2, 3, 4 or 5 count-in beats")
        self.count_in_button.clicked.connect(self._cycle_count_in)
        self.count_in_label = QLabel("Ready")
        self.count_in_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_in_label.setObjectName("LibraryMessage")
        count_in_row.addWidget(self.count_in_button)
        count_in_row.addWidget(self.count_in_label, 1)
        right.addLayout(count_in_row)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
'''

if "self.count_in_button" not in text:
    if controls_anchor not in text:
        raise RuntimeError("Could not find playback controls anchor.")
    text = text.replace(controls_anchor, controls_block, 1)

# Cancel any old count-in when loading a song.
load_anchor = '''        self.repeat_enabled = False
        self.repeat_jump_pending = False
'''

load_block = '''        self.repeat_enabled = False
        self.repeat_jump_pending = False
        self._cancel_count_in("Ready")
'''

if load_anchor not in text:
    raise RuntimeError("Could not find song-load repeat reset.")
text = text.replace(load_anchor, load_block, 1)

# Insert count-in helpers before Practice play.
play_anchor = "    def _practice_play(self) -> None:\n"

helpers = '''    def _cycle_count_in(self) -> None:
        values = [2, 3, 4, 5]
        try:
            index = values.index(self.count_in_beats)
        except ValueError:
            index = 1
        self.count_in_beats = values[(index + 1) % len(values)]
        self.count_in_button.setText(f"Count-in: {self.count_in_beats}")
        self.practice_message.setText(
            f"Count-in set to {self.count_in_beats} beats."
        )

    def _cancel_count_in(self, label: str = "Ready") -> None:
        self.count_in_token += 1
        self.count_in_active = False
        self.count_in_remaining = 0
        if hasattr(self, "count_in_label"):
            self.count_in_label.setText(label)

    def _count_in_interval_ms(self) -> int:
        bpm = 0
        if self.practice_song:
            bpm = int(self.current_practice_bpm or self.practice_song.bpm or 0)
        if bpm <= 0:
            bpm = 100
        return max(200, min(2000, int(round(60000.0 / bpm))))

    def _begin_count_in(self) -> None:
        self._cancel_count_in("")
        self.count_in_active = True
        self.count_in_remaining = int(self.count_in_beats)
        token = self.count_in_token
        self._run_count_in_tick(token)

    def _run_count_in_tick(self, token: int) -> None:
        if token != self.count_in_token or not self.count_in_active:
            return

        if self.count_in_remaining <= 0:
            self.count_in_active = False
            self.count_in_label.setText("PLAY")
            self._start_playback_after_count_in()
            QTimer.singleShot(
                max(250, self._count_in_interval_ms() // 2),
                lambda current_token=token: self._clear_play_label(current_token),
            )
            return

        number = self.count_in_remaining
        self.count_in_label.setText(str(number))
        QApplication.beep()
        self.practice_message.setText(
            f"Count-in: {number} — playback starts after 1."
        )
        self.count_in_remaining -= 1
        QTimer.singleShot(
            self._count_in_interval_ms(),
            lambda current_token=token: self._run_count_in_tick(current_token),
        )

    def _clear_play_label(self, token: int) -> None:
        if token == self.count_in_token and not self.count_in_active:
            self.count_in_label.setText("Playing")

    def _start_playback_after_count_in(self) -> None:
        if not self.practice_song:
            return

        if self.repeat_enabled:
            bounds = self._repeat_bounds_ms()
            if bounds is None:
                self.practice_message.setText("Set repeat start and end first.")
                return
            start_ms, _ = bounds
            self.media_player.setPosition(start_ms)
            start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
            self._highlight_beat(start_beat)
        else:
            duration = int(self.media_player.duration())
            position = int(self.media_player.position())
            if duration > 0 and position >= duration - 500:
                self.media_player.setPosition(0)
                self._highlight_beat(0)

        self.media_player.play()

'''

if "def _begin_count_in" not in text:
    if play_anchor not in text:
        raise RuntimeError("Could not find Practice play method.")
    text = text.replace(play_anchor, helpers + play_anchor, 1)

# Replace Play so every click runs the count-in first.
old_play = '''    def _practice_play(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        self.media_player.play()
'''

new_play = '''    def _practice_play(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        if self.count_in_active:
            return
        self.media_player.pause()
        self._begin_count_in()
'''

if old_play not in text:
    raise RuntimeError("Could not find Module 13 Practice Play implementation.")
text = text.replace(old_play, new_play, 1)

# Pause cancels an active count-in.
old_pause = '''    def _practice_pause(self) -> None:
        self.media_player.pause()
'''

new_pause = '''    def _practice_pause(self) -> None:
        self._cancel_count_in("Paused")
        self.media_player.pause()
'''

if old_pause not in text:
    raise RuntimeError("Could not find Practice Pause implementation.")
text = text.replace(old_pause, new_pause, 1)

# Stop also cancels count-in.
stop_anchor = '''    def _practice_stop(self) -> None:
        if self.practice_stop_reset_pending:
            return
'''

stop_block = '''    def _practice_stop(self) -> None:
        self._cancel_count_in("Ready")
        if self.practice_stop_reset_pending:
            return
'''

if stop_anchor not in text:
    raise RuntimeError("Could not find guarded Practice Stop.")
text = text.replace(stop_anchor, stop_block, 1)

# Grid clicks cancel a pending count-in so playback cannot begin unexpectedly.
grid_click_anchor = '''    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
'''

grid_click_block = '''    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._cancel_count_in("Ready")
'''

if grid_click_anchor not in text:
    raise RuntimeError("Could not find grid click method.")
text = text.replace(grid_click_anchor, grid_click_block, 1)

# Replace continuous repeat looping with one-shot section completion.
start = text.find("    def _check_repeat_loop(self, position: int) -> bool:\n")
end = text.find("    def _grid_cell_clicked", start)

if start < 0 or end < 0:
    raise RuntimeError("Could not locate Module 13 repeat loop method.")

one_shot_repeat = '''    def _check_repeat_loop(self, position: int) -> bool:
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
            self.media_player.pause()
            self.media_player.setPosition(start_ms)

            if hasattr(self, "position_slider"):
                blocked = self.position_slider.blockSignals(True)
                self.position_slider.setValue(start_ms)
                self.position_slider.blockSignals(blocked)

            start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
            self._highlight_beat(start_beat)

            if hasattr(self, "time_label"):
                self._update_time_label(start_ms, self.media_player.duration())

            if hasattr(self, "count_in_label"):
                self.count_in_label.setText("Ready")

            self.practice_message.setText(
                "Repeat section complete. Press Play for another count-in and another run."
            )
        finally:
            self.repeat_jump_pending = False

        return True

'''

text = text[:start] + one_shot_repeat + text[end:]

# Update Repeat wording so it no longer promises continuous looping.
text = text.replace(
    'self.practice_message.setText("Repeat enabled for the selected section.")',
    'self.practice_message.setText("Repeat section armed. Each Play runs it once after the count-in.")',
)
text = text.replace(
    'self.practice_message.setText("Repeat disabled.")',
    'self.practice_message.setText("Repeat section mode disabled.")',
)

required = [
    "Module 13A Build 001",
    "Practice Studio - Module 13A",
    "Count-in: 4",
    "def _begin_count_in",
    "QApplication.beep",
    "Repeat section complete. Press Play",
]

missing = [item for item in required if item not in text]
if missing:
    raise RuntimeError("Module 13A patch verification failed: " + ", ".join(missing))

path.write_text(text, encoding="utf-8")
print("Module 13A adjustable count-in and one-shot repeat applied.")
