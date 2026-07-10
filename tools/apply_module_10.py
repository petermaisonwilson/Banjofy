from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 8B Build 001 - Data Display and Safe Seeking"':
        'APP_VERSION = "Banjofy 006.3.0 Module 10 Build 001 - Real Key Detection"',
    'APP_VERSION = "Banjofy 006.3.0 Module 9 Build 001 - Real BPM Detection"':
        'APP_VERSION = "Banjofy 006.3.0 Module 10 Build 001 - Real Key Detection"',
    'APP_VERSION = "Banjofy 006.3.0 Module 9A Build 001 - BPM and Practice Stop Fix"':
        'APP_VERSION = "Banjofy 006.3.0 Module 10 Build 001 - Real Key Detection"',
    'self.statusBar().showMessage("Ready - Module 8B data display and safe seeking loaded")':
        'self.statusBar().showMessage("Ready - Module 10 real BPM and key detection loaded")',
    'self.statusBar().showMessage("Ready - Module 9 real BPM detection loaded")':
        'self.statusBar().showMessage("Ready - Module 10 real BPM and key detection loaded")',
    'self.statusBar().showMessage("Ready - Module 9A BPM detection and Practice Stop fix loaded")':
        'self.statusBar().showMessage("Ready - Module 10 real BPM and key detection loaded")',
    'note = QLabel("Module 5 test build: Search + Download + Analysis + Library save/list. No Practice yet.")':
        'note = QLabel("Module 10: Real BPM and musical key detection with Practice integration.")',
    'note = QLabel("Module 9: Real audio BPM detection with Library and Practice integration.")':
        'note = QLabel("Module 10: Real BPM and musical key detection with Practice integration.")',
    'note = QLabel("Module 9A: Real BPM detection with stable Practice playback and Stop reset.")':
        'note = QLabel("Module 10: Real BPM and musical key detection with Practice integration.")',
    'title = QLabel("Practice Studio - Player Foundation")':
        'title = QLabel("Practice Studio - Module 10")',
    'title = QLabel("Practice Studio - Module 9A")':
        'title = QLabel("Practice Studio - Module 10")',
    'hint = QLabel("Module 6: Library song playback only. Chord grid, timing and diagrams come later.")':
        'hint = QLabel("Module 10: Detected BPM and key are shown. Chords remain provisional.")',
    'hint = QLabel("Module 9A: Detected BPM drives the beat grid. Chords remain provisional.")':
        'hint = QLabel("Module 10: Detected BPM and key are shown. Chords remain provisional.")',
}
for old, new in pairs.items():
    if old in text:
        text = text.replace(old, new)

if "self.practice_stop_reset_pending" not in text:
    text = text.replace(
        "        self.user_is_seeking = False\n",
        "        self.user_is_seeking = False\n        self.practice_stop_reset_pending = False\n",
        1,
    )

old_stop = """    def _practice_stop(self) -> None:
        self.media_player.stop()
        self.position_slider.setValue(0)
        self.current_beat_index = 0
        self._highlight_beat(0)
"""
new_stop = """    def _practice_stop(self) -> None:
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
"""
if old_stop in text:
    text = text.replace(old_stop, new_stop, 1)

segment_start = text.find("    def _player_position_changed")
segment_end = text.find("    def _player_duration_changed", segment_start)
segment = text[segment_start:segment_end]
if "if self.practice_stop_reset_pending:" not in segment:
    text = text.replace(
        "    def _player_position_changed(self, position: int) -> None:\n",
        "    def _player_position_changed(self, position: int) -> None:\n        if self.practice_stop_reset_pending:\n            return\n",
        1,
    )

for required in ["Module 10 Build 001", "Practice Studio - Module 10", "Detected BPM and key are shown", "practice_stop_reset_pending"]:
    if required not in text:
        raise RuntimeError("Missing: " + required)

path.write_text(text, encoding="utf-8")
print("Module 10 UI patch applied.")
