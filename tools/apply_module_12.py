from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

identity_pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 11 Build 001 - BPM Verification"':
        'APP_VERSION = "Banjofy 006.3.0 Module 12 Build 001 - Grid Click Seeking"',
    'self.statusBar().showMessage("Ready - Module 11 BPM verification loaded")':
        'self.statusBar().showMessage("Ready - Module 12 clickable grid seeking loaded")',
    'note = QLabel("Module 11: Verify, tap, adjust and save BPM before relying on the beat grid.")':
        'note = QLabel("Module 12: Click any bar or beat to jump playback. Repeat selection comes next.")',
    'title = QLabel("Practice Studio - Module 11")':
        'title = QLabel("Practice Studio - Module 12")',
    'hint = QLabel("Module 11: Check detected BPM, tap along or correct it. Chords remain provisional.")':
        'hint = QLabel("Module 12: Click a bar number or individual beat to jump there. Chords remain provisional.")',
}

for old, new in identity_pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 11 text not found: {old}")
    text = text.replace(old, new, 1)

old_bar = '''            bar_label = QLabel(str(bar + 1))
            bar_label.setObjectName("BarLabel")
            bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beat_grid_layout.addWidget(bar_label, bar + 1, 0)
'''

new_bar = '''            bar_label = QLabel(str(bar + 1))
            bar_label.setObjectName("BarLabel")
            bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar_label.setToolTip(f"Jump to Bar {bar + 1}, Beat 1")
            bar_label.setCursor(Qt.CursorShape.PointingHandCursor)
            bar_label.mousePressEvent = (
                lambda event, beat_index=bar * 4: self._grid_cell_clicked(event, beat_index)
            )
            self.beat_grid_layout.addWidget(bar_label, bar + 1, 0)
'''

if old_bar not in text:
    raise RuntimeError("Could not find the beat-grid bar label block.")
text = text.replace(old_bar, new_bar, 1)

old_cell = '''                cell.setMinimumSize(54, 30)
                cell.setProperty("beat_index", bar * 4 + beat)
                self.beat_grid_layout.addWidget(cell, bar + 1, beat + 1)
                self.grid_cells.append(cell)
'''

new_cell = '''                cell.setMinimumSize(54, 30)
                beat_index = bar * 4 + beat
                cell.setProperty("beat_index", beat_index)
                cell.setToolTip(f"Jump to Bar {bar + 1}, Beat {beat + 1}")
                cell.setCursor(Qt.CursorShape.PointingHandCursor)
                cell.mousePressEvent = (
                    lambda event, target_beat=beat_index: self._grid_cell_clicked(event, target_beat)
                )
                self.beat_grid_layout.addWidget(cell, bar + 1, beat + 1)
                self.grid_cells.append(cell)
'''

if old_cell not in text:
    raise RuntimeError("Could not find the beat-grid cell block.")
text = text.replace(old_cell, new_cell, 1)

anchor = "    def _highlight_beat(self, beat_index: int) -> None:\n"

methods = '''    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._seek_to_grid_beat(beat_index)

    def _seek_to_grid_beat(self, beat_index: int) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a Library song into Practice first.")
            return

        beat_index = max(0, min(int(beat_index), len(self.grid_cells) - 1))
        bpm = int(self.current_practice_bpm or self.practice_song.bpm or 0)
        duration = int(self.media_player.duration())

        if bpm <= 0:
            self.practice_message.setText("Cannot jump by beat because BPM is unavailable.")
            return

        beat_ms = 60000.0 / bpm
        position = int(round(beat_index * beat_ms))

        if duration > 0:
            position = max(0, min(position, max(0, duration - 1)))
        else:
            position = max(0, position)

        self.user_is_seeking = True
        try:
            self.media_player.setPosition(position)

            if hasattr(self, "position_slider"):
                blocked = self.position_slider.blockSignals(True)
                self.position_slider.setValue(position)
                self.position_slider.blockSignals(blocked)

            if hasattr(self, "time_label"):
                self._update_time_label(position, duration)

            self._highlight_beat(beat_index)
        finally:
            self.user_is_seeking = False

        bar_number = beat_index // 4 + 1
        beat_number = beat_index % 4 + 1
        self.practice_message.setText(
            f"Jumped to Bar {bar_number}, Beat {beat_number} "
            f"(approximate until first-downbeat alignment is added)."
        )

'''

if "def _grid_cell_clicked" not in text:
    if anchor not in text:
        raise RuntimeError("Could not find _highlight_beat insertion point.")
    text = text.replace(anchor, methods + anchor, 1)

required = [
    "Module 12 Build 001",
    "Practice Studio - Module 12",
    "def _grid_cell_clicked",
    "def _seek_to_grid_beat",
    "PointingHandCursor",
    "Jumped to Bar",
]

missing = [item for item in required if item not in text]
if missing:
    raise RuntimeError("Module 12 patch verification failed: " + ", ".join(missing))

path.write_text(text, encoding="utf-8")
print("Module 12 clickable grid seeking applied.")
