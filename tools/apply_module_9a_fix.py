from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

simple_replacements = {
    'APP_VERSION = "Banjofy 006.3.0 Module 8B Build 001 - Data Display and Safe Seeking"':
        'APP_VERSION = "Banjofy 006.3.0 Module 9A Build 001 - BPM and Practice Stop Fix"',
    'APP_VERSION = "Banjofy 006.3.0 Module 9 Build 001 - Real BPM Detection"':
        'APP_VERSION = "Banjofy 006.3.0 Module 9A Build 001 - BPM and Practice Stop Fix"',
    'self.statusBar().showMessage("Ready - Module 8B data display and safe seeking loaded")':
        'self.statusBar().showMessage("Ready - Module 9A BPM detection and Practice Stop fix loaded")',
    'self.statusBar().showMessage("Ready - Module 9 real BPM detection loaded")':
        'self.statusBar().showMessage("Ready - Module 9A BPM detection and Practice Stop fix loaded")',
    'note = QLabel("Module 5 test build: Search + Download + Analysis + Library save/list. No Practice yet.")':
        'note = QLabel("Module 9A: Real BPM detection with stable Practice playback and Stop reset.")',
    'note = QLabel("Module 9: Real audio BPM detection with Library and Practice integration.")':
        'note = QLabel("Module 9A: Real BPM detection with stable Practice playback and Stop reset.")',
    'title = QLabel("Practice Studio - Player Foundation")':
        'title = QLabel("Practice Studio - Module 9A")',
    'hint = QLabel("Module 6: Library song playback only. Chord grid, timing and diagrams come later.")':
        'hint = QLabel("Module 9A: Detected BPM drives the beat grid. Chords remain provisional.")',
}

for old, new in simple_replacements.items():
    if old in text:
        text = text.replace(old, new)

needle = "        self.user_is_seeking = False\n"
replacement = (
    "        self.user_is_seeking = False\n"
    "        self.practice_stop_reset_pending = False\n"
)
if "self.practice_stop_reset_pending" not in text:
    if needle not in text:
        raise RuntimeError("Could not find the Practice state initialisation point.")
    text = text.replace(needle, replacement, 1)

old_stop = '''    def _practice_stop(self) -> None:
        self.media_player.stop()
        self.position_slider.setValue(0)
        self.current_beat_index = 0
        self._highlight_beat(0)
'''

new_stop = '''    def _practice_stop(self) -> None:
        # Stop media first, then reset the UI on the next Qt event cycle.
        if self.practice_stop_reset_pending:
            return

        self.practice_stop_reset_pending = True
        self.media_player.stop()
        QTimer.singleShot(0, self._finish_practice_stop)

    def _finish_practice_stop(self) -> None:
        try:
            self.user_is_seeking = False
            self.media_player.setPosition(0)

            if hasattr(self, "position_slider"):
                blocked = self.position_slider.blockSignals(True)
                self.position_slider.setValue(0)
                self.position_slider.blockSignals(blocked)

            self.current_beat_index = 0
            if self.grid_cells:
                self._highlight_beat(0)

            if hasattr(self, "time_label"):
                self._update_time_label(0, self.media_player.duration())

            if hasattr(self, "practice_message") and self.practice_song:
                self.practice_message.setText(f"Stopped: {self.practice_song.title}")
        finally:
            self.practice_stop_reset_pending = False
'''

if new_stop not in text:
    if old_stop not in text:
        raise RuntimeError("Could not find the existing Practice Stop function.")
    text = text.replace(old_stop, new_stop, 1)

old_position = '''    def _player_position_changed(self, position: int) -> None:
        if hasattr(self, "position_slider") and not self.user_is_seeking:
            self.position_slider.setValue(position)
        if hasattr(self, "time_label"):
            self._update_time_label(position, self.media_player.duration())
        self._update_grid_cursor_from_position(position)
'''

new_position = '''    def _player_position_changed(self, position: int) -> None:
        if self.practice_stop_reset_pending:
            return
        if hasattr(self, "position_slider") and not self.user_is_seeking:
            self.position_slider.setValue(position)
        if hasattr(self, "time_label"):
            self._update_time_label(position, self.media_player.duration())
        self._update_grid_cursor_from_position(position)
'''

if new_position not in text:
    if old_position not in text:
        raise RuntimeError("Could not find the player position callback.")
    text = text.replace(old_position, new_position, 1)

required = [
    'Module 9A Build 001',
    'Practice Studio - Module 9A',
    'Detected BPM drives the beat grid',
    'def _finish_practice_stop',
    'if self.practice_stop_reset_pending:',
]
missing = [item for item in required if item not in text]
if missing:
    raise RuntimeError("Module 9A patch verification failed: " + ", ".join(missing))

path.write_text(text, encoding="utf-8")
print("Module 9A Practice title and guarded Stop fix applied.")
