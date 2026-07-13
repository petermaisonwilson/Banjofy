from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

if "import time\n" not in text:
    text = text.replace("import threading\n", "import threading\nimport time\n", 1)
if "from dataclasses import replace\n" not in text:
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\nfrom dataclasses import replace\n", 1)

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 8B Build 001 - Data Display and Safe Seeking"':
        'APP_VERSION = "Banjofy 006.3.0 Module 11 Build 001 - BPM Verification"',
    'APP_VERSION = "Banjofy 006.3.0 Module 9 Build 001 - Real BPM Detection"':
        'APP_VERSION = "Banjofy 006.3.0 Module 11 Build 001 - BPM Verification"',
    'APP_VERSION = "Banjofy 006.3.0 Module 9A Build 001 - BPM and Practice Stop Fix"':
        'APP_VERSION = "Banjofy 006.3.0 Module 11 Build 001 - BPM Verification"',
    'APP_VERSION = "Banjofy 006.3.0 Module 10 Build 001 - Real Key Detection"':
        'APP_VERSION = "Banjofy 006.3.0 Module 11 Build 001 - BPM Verification"',
    'self.statusBar().showMessage("Ready - Module 8B data display and safe seeking loaded")':
        'self.statusBar().showMessage("Ready - Module 11 BPM verification loaded")',
    'self.statusBar().showMessage("Ready - Module 9 real BPM detection loaded")':
        'self.statusBar().showMessage("Ready - Module 11 BPM verification loaded")',
    'self.statusBar().showMessage("Ready - Module 9A BPM detection and Practice Stop fix loaded")':
        'self.statusBar().showMessage("Ready - Module 11 BPM verification loaded")',
    'self.statusBar().showMessage("Ready - Module 10 real BPM and key detection loaded")':
        'self.statusBar().showMessage("Ready - Module 11 BPM verification loaded")',
    'note = QLabel("Module 5 test build: Search + Download + Analysis + Library save/list. No Practice yet.")':
        'note = QLabel("Module 11: Verify, tap, adjust and save BPM before relying on the beat grid.")',
    'note = QLabel("Module 9A: Real BPM detection with stable Practice playback and Stop reset.")':
        'note = QLabel("Module 11: Verify, tap, adjust and save BPM before relying on the beat grid.")',
    'note = QLabel("Module 10: Real BPM and musical key detection with Practice integration.")':
        'note = QLabel("Module 11: Verify, tap, adjust and save BPM before relying on the beat grid.")',
    'title = QLabel("Practice Studio - Player Foundation")':
        'title = QLabel("Practice Studio - Module 11")',
    'title = QLabel("Practice Studio - Module 9A")':
        'title = QLabel("Practice Studio - Module 11")',
    'title = QLabel("Practice Studio - Module 10")':
        'title = QLabel("Practice Studio - Module 11")',
    'hint = QLabel("Module 6: Library song playback only. Chord grid, timing and diagrams come later.")':
        'hint = QLabel("Module 11: Check detected BPM, tap along or correct it. Chords remain provisional.")',
    'hint = QLabel("Module 9A: Detected BPM drives the beat grid. Chords remain provisional.")':
        'hint = QLabel("Module 11: Check detected BPM, tap along or correct it. Chords remain provisional.")',
    'hint = QLabel("Module 10: Detected BPM and key are shown. Chords remain provisional.")':
        'hint = QLabel("Module 11: Check detected BPM, tap along or correct it. Chords remain provisional.")',
}
for old, new in pairs.items():
    if old in text:
        text = text.replace(old, new)

state_anchor = "        self.user_is_seeking = False\n"
if "self.tap_times: list[float]" not in text:
    replacement = (
        "        self.user_is_seeking = False\n"
        "        self.detected_practice_bpm = 0\n"
        "        self.current_practice_bpm = 0\n"
        "        self.tap_times: list[float] = []\n"
    )
    if state_anchor not in text:
        raise RuntimeError("Practice state anchor not found")
    text = text.replace(state_anchor, replacement, 1)

if "self.practice_stop_reset_pending" not in text:
    text = text.replace(
        "        self.tap_times: list[float] = []\n",
        "        self.tap_times: list[float] = []\n        self.practice_stop_reset_pending = False\n",
        1,
    )

old_stop = '''    def _practice_stop(self) -> None:
        self.media_player.stop()
        self.position_slider.setValue(0)
        self.current_beat_index = 0
        self._highlight_beat(0)
'''
new_stop = '''    def _practice_stop(self) -> None:
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
if old_stop in text:
    text = text.replace(old_stop, new_stop, 1)

ps = text.find("    def _player_position_changed")
pe = text.find("    def _player_duration_changed", ps)
if ps >= 0 and pe > ps and "if self.practice_stop_reset_pending:" not in text[ps:pe]:
    text = text.replace(
        "    def _player_position_changed(self, position: int) -> None:\n",
        "    def _player_position_changed(self, position: int) -> None:\n"
        "        if self.practice_stop_reset_pending:\n"
        "            return\n",
        1,
    )

controls_anchor = '''        for label in [
            self.practice_title_label,
            self.practice_channel_label,
            self.practice_duration_label,
            self.practice_bpm_label,
            self.practice_key_label,
        ]:
            label.setObjectName("PracticeInfo")
            left.addWidget(label)

        body.addLayout(left, 1)
'''
controls = '''        for label in [
            self.practice_title_label,
            self.practice_channel_label,
            self.practice_duration_label,
            self.practice_bpm_label,
            self.practice_key_label,
        ]:
            label.setObjectName("PracticeInfo")
            left.addWidget(label)

        self.bpm_verify_label = QLabel("BPM check: load a song first")
        self.bpm_verify_label.setObjectName("LibraryMessage")
        self.bpm_verify_label.setWordWrap(True)
        left.addWidget(self.bpm_verify_label)

        bpm_row_one = QHBoxLayout()
        self.bpm_half_button = QPushButton("Half")
        self.bpm_minus_button = QPushButton("-1")
        self.bpm_plus_button = QPushButton("+1")
        self.bpm_double_button = QPushButton("Double")
        self.bpm_half_button.clicked.connect(self._bpm_half)
        self.bpm_minus_button.clicked.connect(lambda: self._adjust_practice_bpm(-1))
        self.bpm_plus_button.clicked.connect(lambda: self._adjust_practice_bpm(1))
        self.bpm_double_button.clicked.connect(self._bpm_double)
        bpm_row_one.addWidget(self.bpm_half_button)
        bpm_row_one.addWidget(self.bpm_minus_button)
        bpm_row_one.addWidget(self.bpm_plus_button)
        bpm_row_one.addWidget(self.bpm_double_button)
        left.addLayout(bpm_row_one)

        bpm_row_two = QHBoxLayout()
        self.bpm_tap_button = QPushButton("Tap BPM")
        self.bpm_reset_button = QPushButton("Reset Detected")
        self.bpm_save_button = QPushButton("Save BPM")
        self.bpm_tap_button.clicked.connect(self._tap_bpm)
        self.bpm_reset_button.clicked.connect(self._reset_detected_bpm)
        self.bpm_save_button.clicked.connect(self._save_corrected_bpm)
        bpm_row_two.addWidget(self.bpm_tap_button)
        bpm_row_two.addWidget(self.bpm_reset_button)
        bpm_row_two.addWidget(self.bpm_save_button)
        left.addLayout(bpm_row_two)

        body.addLayout(left, 1)
'''
if "self.bpm_verify_label" not in text:
    if controls_anchor not in text:
        raise RuntimeError("Practice control anchor not found")
    text = text.replace(controls_anchor, controls, 1)

load_anchor = '''        self.practice_bpm_label.setText(f"BPM: {song.bpm}")
        self.practice_key_label.setText(f"Key: {getattr(song, 'key', 'Not analysed yet')}")
'''
load_replacement = '''        self.detected_practice_bpm = int(getattr(song, "detected_bpm", 0) or song.bpm)
        self.current_practice_bpm = int(song.bpm)
        self.tap_times = []
        self.practice_bpm_label.setText(f"BPM: {self.current_practice_bpm}")
        self.practice_key_label.setText(f"Key: {getattr(song, 'key', 'Not analysed yet')}")
        self._update_bpm_verify_label()
'''
if load_anchor not in text:
    raise RuntimeError("BPM load anchor not found")
text = text.replace(load_anchor, load_replacement, 1)

methods = '''    def _duration_seconds(self, duration: str) -> int:
        try:
            parts = str(duration).strip().split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            pass
        return 0

    def _bars_for_bpm(self, duration: str, bpm: int) -> int:
        seconds = self._duration_seconds(duration)
        if seconds <= 0:
            return max(16, int(getattr(self.practice_song, "estimated_bars", 16)))
        beats = int(seconds * bpm / 60)
        return max(16, (beats + 3) // 4)

    def _update_bpm_verify_label(self) -> None:
        if not hasattr(self, "bpm_verify_label"):
            return
        if not self.practice_song:
            self.bpm_verify_label.setText("BPM check: load a song first")
            return
        state = "corrected" if self.current_practice_bpm != self.detected_practice_bpm else "detected"
        self.bpm_verify_label.setText(
            f"BPM check: detected {self.detected_practice_bpm} | current {self.current_practice_bpm} ({state})"
        )

    def _set_practice_bpm(self, bpm: int, source: str) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        bpm = max(30, min(300, int(round(bpm))))
        bars = self._bars_for_bpm(self.practice_song.duration, bpm)
        self.current_practice_bpm = bpm
        self.practice_song = replace(self.practice_song, bpm=bpm, estimated_bars=bars)
        self.practice_bpm_label.setText(f"BPM: {bpm}")
        self._update_bpm_verify_label()
        self._build_beat_grid(self.practice_song)
        self._update_grid_cursor_from_position(self.media_player.position())
        self.practice_message.setText(f"BPM set to {bpm} using {source}. Click Save BPM to keep it.")

    def _adjust_practice_bpm(self, amount: int) -> None:
        if self.practice_song:
            self._set_practice_bpm((self.current_practice_bpm or self.practice_song.bpm) + amount, f"{amount:+d}")

    def _bpm_half(self) -> None:
        if self.practice_song:
            current = self.current_practice_bpm or int(self.practice_song.bpm)
            self._set_practice_bpm(round(current / 2), "Half")

    def _bpm_double(self) -> None:
        if self.practice_song:
            current = self.current_practice_bpm or int(self.practice_song.bpm)
            self._set_practice_bpm(current * 2, "Double")

    def _reset_detected_bpm(self) -> None:
        if self.practice_song and self.detected_practice_bpm > 0:
            self.tap_times = []
            self._set_practice_bpm(self.detected_practice_bpm, "Reset Detected")

    def _tap_bpm(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load and play a song before tapping BPM.")
            return
        now = time.monotonic()
        if self.tap_times and now - self.tap_times[-1] > 2.5:
            self.tap_times = []
        self.tap_times.append(now)
        self.tap_times = self.tap_times[-8:]
        if len(self.tap_times) < 2:
            self.practice_message.setText("Tap BPM: keep tapping once on each beat.")
            return
        intervals = [
            self.tap_times[i] - self.tap_times[i - 1]
            for i in range(1, len(self.tap_times))
            if 0.20 <= self.tap_times[i] - self.tap_times[i - 1] <= 2.0
        ]
        if not intervals:
            self.tap_times = [now]
            self.practice_message.setText("Tap BPM restarted. Tap steadily with the beat.")
            return
        bpm = int(round(60.0 / (sum(intervals) / len(intervals))))
        self._set_practice_bpm(bpm, f"Tap BPM ({len(self.tap_times)} taps)")

    def _save_corrected_bpm(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song before saving BPM.")
            return
        try:
            bars = self._bars_for_bpm(self.practice_song.duration, self.current_practice_bpm)
            updated, saved_path = self.library_manager.update_bpm(
                self.practice_song, self.current_practice_bpm, bars
            )
            self.practice_song = updated
            self.selected_library_song = updated
            self.practice_bpm_label.setText(f"BPM: {updated.bpm}")
            self._update_bpm_verify_label()
            self._refresh_library_list()
            self.practice_message.setText(f"Saved BPM {updated.bpm} to Library: {saved_path.name}")
        except Exception as exc:
            self.practice_message.setText(f"Save BPM failed: {exc}")

'''
if "    def _tap_bpm(self) -> None:" not in text:
    anchor = "    def _practice_play(self) -> None:\n"
    if anchor not in text:
        raise RuntimeError("Practice play anchor not found")
    text = text.replace(anchor, methods + anchor, 1)

for required in [
    "Module 11 Build 001",
    "Practice Studio - Module 11",
    "self.bpm_verify_label",
    "def _tap_bpm",
    "def _save_corrected_bpm",
    "practice_stop_reset_pending",
]:
    if required not in text:
        raise RuntimeError("Module 11 verification failed: " + required)

path.write_text(text, encoding="utf-8")
print("Module 11 BPM verification UI applied.")
