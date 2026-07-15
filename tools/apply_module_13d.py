from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 13C Build 001 - Count-In Play Fix"':
        'APP_VERSION = "Banjofy 006.3.0 Module 13D Build 001 - Repeat Run Fix"',
    'self.statusBar().showMessage("Ready - Module 13C count-in Play fix loaded")':
        'self.statusBar().showMessage("Ready - Module 13D repeat run fix loaded")',
    'note = QLabel("Module 13C: Adjustable count-in with corrected Play handoff.")':
        'note = QLabel("Module 13D: Count-in, beep control and one-shot repeat playback.")',
    'title = QLabel("Practice Studio - Module 13C")':
        'title = QLabel("Practice Studio - Module 13D")',
    'hint = QLabel("Module 13C: Choose 2-5 count-in beats. Repeat sections play once per Play press.")':
        'hint = QLabel("Module 13D: Choose 2-5 counts, optional beep, and one repeat run per Play press.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 13C text not found: {old}")
    text = text.replace(old, new, 1)

state_anchor = "        self.count_in_active = False\n"
state_block = (
    "        self.count_in_active = False\n"
    "        self.count_in_beep_enabled = True\n"
    "        self.repeat_run_active = False\n"
)
if "self.repeat_run_active" not in text:
    if state_anchor not in text:
        raise RuntimeError("Could not find count-in state anchor.")
    text = text.replace(state_anchor, state_block, 1)

ui_anchor = '''        self.count_in_button = QPushButton("Count-in: 4")
        self.count_in_button.setToolTip("Click to choose 2, 3, 4 or 5 count-in beats")
        self.count_in_button.clicked.connect(self._cycle_count_in)
        self.count_in_label = QLabel("Ready")
'''
ui_block = '''        self.count_in_button = QPushButton("Count-in: 4")
        self.count_in_button.setToolTip("Click to choose 2, 3, 4 or 5 count-in beats")
        self.count_in_button.clicked.connect(self._cycle_count_in)

        self.count_in_beep_button = QPushButton("Beep On")
        self.count_in_beep_button.setCheckable(True)
        self.count_in_beep_button.setChecked(True)
        self.count_in_beep_button.setToolTip("Turn countdown beeps on or off")
        self.count_in_beep_button.toggled.connect(self._toggle_count_in_beep)

        self.count_in_label = QLabel("Ready")
'''
if "self.count_in_beep_button" not in text:
    if ui_anchor not in text:
        raise RuntimeError("Could not find count-in UI anchor.")
    text = text.replace(ui_anchor, ui_block, 1)

layout_anchor = '''        count_in_row.addWidget(self.count_in_button)
        count_in_row.addWidget(self.count_in_label, 1)
'''
layout_block = '''        count_in_row.addWidget(self.count_in_button)
        count_in_row.addWidget(self.count_in_beep_button)
        count_in_row.addWidget(self.count_in_label, 1)
'''
if "count_in_row.addWidget(self.count_in_beep_button)" not in text:
    if layout_anchor not in text:
        raise RuntimeError("Could not find count-in layout anchor.")
    text = text.replace(layout_anchor, layout_block, 1)

method_anchor = '    def _cancel_count_in(self, label: str = "Ready") -> None:\n'
beep_method = '''    def _toggle_count_in_beep(self, enabled: bool) -> None:
        self.count_in_beep_enabled = bool(enabled)
        self.count_in_beep_button.setText("Beep On" if enabled else "Beep Off")
        self.practice_message.setText(
            "Count-in beep enabled." if enabled else "Count-in beep disabled."
        )

'''
if "def _toggle_count_in_beep" not in text:
    if method_anchor not in text:
        raise RuntimeError("Could not find count-in method anchor.")
    text = text.replace(method_anchor, beep_method + method_anchor, 1)

old_beep = '''        QApplication.beep()
        self.practice_message.setText(
'''
new_beep = '''        if self.count_in_beep_enabled:
            QApplication.beep()
        self.practice_message.setText(
'''
if old_beep not in text:
    raise RuntimeError("Could not find countdown beep call.")
text = text.replace(old_beep, new_beep, 1)

start = text.find("    def _start_playback_after_count_in(self) -> None:\n")
end = text.find("    def _practice_play(self) -> None:\n", start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate count-in playback handoff.")

new_handoff = '''    def _start_playback_after_count_in(self) -> None:
        if not self.practice_song:
            return

        self.repeat_run_active = False

        if self.repeat_enabled:
            bounds = self._repeat_bounds_ms()
            if bounds is None:
                self.count_in_label.setText("Ready")
                self.practice_message.setText("Set repeat start and end first.")
                return

            start_ms, _ = bounds
            start_beat = min(self.repeat_start_beat, self.repeat_end_beat)

            self.repeat_jump_pending = True
            try:
                self.media_player.pause()
                self.media_player.setPosition(start_ms)

                if hasattr(self, "position_slider"):
                    blocked = self.position_slider.blockSignals(True)
                    self.position_slider.setValue(start_ms)
                    self.position_slider.blockSignals(blocked)

                self._highlight_beat(start_beat)

                if hasattr(self, "time_label"):
                    self._update_time_label(start_ms, self.media_player.duration())
            finally:
                self.repeat_jump_pending = False

            self.repeat_run_active = True
            self.practice_message.setText(
                f"Playing repeat once: {self._beat_label(self.repeat_start_beat)} "
                f"to {self._beat_label(self.repeat_end_beat)}."
            )
        else:
            duration = int(self.media_player.duration())
            position = int(self.media_player.position())
            if duration > 0 and position >= duration - 500:
                self.media_player.setPosition(0)
                self._highlight_beat(0)

        self.media_player.play()

'''
text = text[:start] + new_handoff + text[end:]

start = text.find("    def _check_repeat_loop(self, position: int) -> bool:\n")
end = text.find("    def _grid_cell_clicked", start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate repeat checker.")

new_checker = '''    def _check_repeat_loop(self, position: int) -> bool:
        if (
            not self.repeat_enabled
            or not self.repeat_run_active
            or self.repeat_jump_pending
        ):
            return False

        bounds = self._repeat_bounds_ms()
        if bounds is None:
            self.repeat_run_active = False
            return False

        start_ms, end_ms = bounds
        if position < end_ms:
            return False

        self.repeat_run_active = False
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
text = text[:start] + new_checker + text[end:]

text = text.replace(
'''    def _practice_pause(self) -> None:
        self._cancel_count_in("Paused")
        self.media_player.pause()
''',
'''    def _practice_pause(self) -> None:
        self._cancel_count_in("Paused")
        self.repeat_run_active = False
        self.media_player.pause()
''',
1)

text = text.replace(
'''    def _practice_stop(self) -> None:
        self._cancel_count_in("Ready")
''',
'''    def _practice_stop(self) -> None:
        self._cancel_count_in("Ready")
        self.repeat_run_active = False
''',
1)

text = text.replace(
'''    def _clear_repeat(self) -> None:
        self.repeat_start_beat = None
''',
'''    def _clear_repeat(self) -> None:
        self.repeat_run_active = False
        self.repeat_start_beat = None
''',
1)

text = text.replace(
'''    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._cancel_count_in("Ready")
''',
'''    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._cancel_count_in("Ready")
        self.repeat_run_active = False
''',
1)

for item in [
    "Module 13D Build 001",
    "Practice Studio - Module 13D",
    "Beep On",
    "def _toggle_count_in_beep",
    "self.repeat_run_active = True",
    "not self.repeat_run_active",
]:
    if item not in text:
        raise RuntimeError("Module 13D verification failed: " + item)

path.write_text(text, encoding="utf-8")
print("Module 13D repeat-run and beep control applied.")
