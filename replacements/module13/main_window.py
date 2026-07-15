from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from banjofy.ui.main_window_legacy import MainWindow as LegacyMainWindow
from banjofy.library.song_library import LibrarySong


APP_VERSION = "Banjofy 006.3.0 Module 13 Build 002 - Clean Count-In and Repeat"


class MainWindow(LegacyMainWindow):
    """Clean Module 13 window built on the preserved confirmed application foundation.

    This file is a complete replacement entry window. It does not modify the
    preserved legacy source and does not depend on any Module 13 patch scripts.
    """

    def __init__(self) -> None:
        self.detected_practice_bpm = 0
        self.current_practice_bpm = 0
        self.tap_times: list[float] = []
        self.practice_stop_reset_pending = False

        self.count_in_beats = 4
        self.count_in_remaining = 0
        self.count_in_beep_enabled = True
        self.count_in_active = False

        self.repeat_start_beat: int | None = None
        self.repeat_end_beat: int | None = None
        self.repeat_enabled = False
        self.repeat_run_active = False
        self.repeat_seek_pending = False

        super().__init__()

        self.setWindowTitle(APP_VERSION)
        self._set_visible_titles()

        self.count_in_timer = QTimer(self)
        self.count_in_timer.setInterval(1000)
        self.count_in_timer.setSingleShot(False)
        self.count_in_timer.timeout.connect(self._count_in_tick)

        self.statusBar().showMessage("Ready - Module 13 clean count-in and repeat loaded")

    def _set_visible_titles(self) -> None:
        for label in self.findChildren(QLabel):
            if label.objectName() == "Title":
                if "Practice" in label.text():
                    label.setText("Practice Studio - Module 13")
                else:
                    label.setText(APP_VERSION)

    def _build_ui(self) -> None:
        super()._build_ui()
        self._set_visible_titles()

        hints = self.library_page.findChildren(QLabel)
        for label in hints:
            if label.objectName() == "Hint":
                label.setText(
                    "Module 13 clean build: stable playback, adjustable count-in, "
                    "click seeking and one-shot repeat practice."
                )
                break

    def _build_practice_page(self) -> QWidget:
        page = super()._build_practice_page()
        outer = page.layout()
        if not isinstance(outer, QVBoxLayout):
            return page

        labels = page.findChildren(QLabel)
        for label in labels:
            if label.objectName() == "Title":
                label.setText("Practice Studio - Module 13")
            elif label.objectName() == "Hint":
                label.setText(
                    "Choose 2-5 one-second counts. Set S and E, then each Play "
                    "runs the selected section once."
                )

        self.bpm_verify_label = QLabel("BPM check: load a song first")
        self.bpm_verify_label.setObjectName("LibraryMessage")
        self.bpm_verify_label.setWordWrap(True)
        outer.addWidget(self.bpm_verify_label)

        bpm_row = QHBoxLayout()
        self.bpm_half_button = QPushButton("Half")
        self.bpm_minus_button = QPushButton("-1")
        self.bpm_plus_button = QPushButton("+1")
        self.bpm_double_button = QPushButton("Double")
        self.bpm_tap_button = QPushButton("Tap BPM")
        self.bpm_reset_button = QPushButton("Reset Detected")
        self.bpm_save_button = QPushButton("Save BPM")

        self.bpm_half_button.clicked.connect(self._bpm_half)
        self.bpm_minus_button.clicked.connect(lambda: self._adjust_practice_bpm(-1))
        self.bpm_plus_button.clicked.connect(lambda: self._adjust_practice_bpm(1))
        self.bpm_double_button.clicked.connect(self._bpm_double)
        self.bpm_tap_button.clicked.connect(self._tap_bpm)
        self.bpm_reset_button.clicked.connect(self._reset_detected_bpm)
        self.bpm_save_button.clicked.connect(self._save_corrected_bpm)

        for button in (
            self.bpm_half_button,
            self.bpm_minus_button,
            self.bpm_plus_button,
            self.bpm_double_button,
            self.bpm_tap_button,
            self.bpm_reset_button,
            self.bpm_save_button,
        ):
            bpm_row.addWidget(button)
        outer.addLayout(bpm_row)

        self.repeat_status_label = QLabel("Repeat OFF | Start: not set | End: not set")
        self.repeat_status_label.setObjectName("LibraryMessage")
        self.repeat_status_label.setWordWrap(True)
        outer.addWidget(self.repeat_status_label)

        repeat_row = QHBoxLayout()
        self.repeat_start_button = QPushButton("Set Start")
        self.repeat_end_button = QPushButton("Set End")
        self.repeat_toggle_button = QPushButton("Repeat Off")
        self.repeat_toggle_button.setCheckable(True)
        self.repeat_clear_button = QPushButton("Clear Repeat")

        self.repeat_start_button.clicked.connect(self._set_repeat_start)
        self.repeat_end_button.clicked.connect(self._set_repeat_end)
        self.repeat_toggle_button.toggled.connect(self._toggle_repeat)
        self.repeat_clear_button.clicked.connect(self._clear_repeat)

        repeat_row.addWidget(self.repeat_start_button)
        repeat_row.addWidget(self.repeat_end_button)
        repeat_row.addWidget(self.repeat_toggle_button)
        repeat_row.addWidget(self.repeat_clear_button)
        outer.addLayout(repeat_row)

        count_row = QHBoxLayout()
        self.count_in_button = QPushButton("Count-in: 4")
        self.count_in_button.clicked.connect(self._cycle_count_in)

        self.count_in_beep_button = QPushButton("Beep On")
        self.count_in_beep_button.setCheckable(True)
        self.count_in_beep_button.setChecked(True)
        self.count_in_beep_button.toggled.connect(self._toggle_count_in_beep)

        self.count_in_label = QLabel("Ready")
        self.count_in_label.setObjectName("LibraryMessage")
        self.count_in_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        count_row.addWidget(self.count_in_button)
        count_row.addWidget(self.count_in_beep_button)
        count_row.addWidget(self.count_in_label, 1)
        outer.addLayout(count_row)

        return page

    # ---------- Song loading and grid ----------

    def _load_selected_song_into_practice(self) -> None:
        super()._load_selected_song_into_practice()
        if not self.practice_song:
            return

        self.detected_practice_bpm = int(
            getattr(self.practice_song, "detected_bpm", 0)
            or getattr(self.practice_song, "bpm", 0)
            or 0
        )
        self.current_practice_bpm = int(getattr(self.practice_song, "bpm", 0) or 0)
        self.tap_times = []
        self._cancel_count_in("Ready")
        self._clear_repeat(silent=True)
        self._update_bpm_verify_label()
        self.practice_bpm_label.setText(f"BPM: {self.current_practice_bpm}")

    def _build_beat_grid(self, song: LibrarySong) -> None:
        super()._build_beat_grid(song)

        for beat_index, cell in enumerate(self.grid_cells):
            bar = beat_index // 4 + 1
            beat = beat_index % 4 + 1
            cell.setToolTip(f"Jump to Bar {bar}, Beat {beat}")
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            cell.mousePressEvent = (
                lambda event, target=beat_index: self._grid_cell_clicked(event, target)
            )

        for bar in range(self.grid_bar_count):
            item = self.beat_grid_layout.itemAtPosition(bar + 1, 0)
            label = item.widget() if item else None
            if isinstance(label, QLabel):
                label.setToolTip(f"Jump to Bar {bar + 1}, Beat 1")
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                label.mousePressEvent = (
                    lambda event, target=bar * 4: self._grid_cell_clicked(event, target)
                )

        self._refresh_repeat_markers()

    def _highlight_beat(self, beat_index: int) -> None:
        super()._highlight_beat(beat_index)
        self._refresh_repeat_markers()

    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._cancel_count_in("Ready")
        self.repeat_run_active = False
        self._seek_to_grid_beat(beat_index)

    def _seek_to_grid_beat(self, beat_index: int) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a Library song into Practice first.")
            return

        beat_index = max(0, min(int(beat_index), len(self.grid_cells) - 1))
        bpm = int(self.current_practice_bpm or getattr(self.practice_song, "bpm", 0) or 0)
        if bpm <= 0:
            self.practice_message.setText("Cannot seek by beat because BPM is unavailable.")
            return

        position = int(round(beat_index * (60000.0 / bpm)))
        duration = int(self.media_player.duration())
        if duration > 0:
            position = max(0, min(position, max(0, duration - 1)))

        self.user_is_seeking = True
        try:
            self.media_player.setPosition(position)
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(position)
            self.position_slider.blockSignals(False)
            self._update_time_label(position, duration)
            self._highlight_beat(beat_index)
        finally:
            self.user_is_seeking = False

        self.practice_message.setText(
            f"Jumped to Bar {beat_index // 4 + 1}, Beat {beat_index % 4 + 1}."
        )

    # ---------- Count-in ----------

    def _cycle_count_in(self) -> None:
        values = [2, 3, 4, 5]
        index = values.index(self.count_in_beats) if self.count_in_beats in values else 1
        self.count_in_beats = values[(index + 1) % len(values)]
        self.count_in_button.setText(f"Count-in: {self.count_in_beats}")

    def _toggle_count_in_beep(self, enabled: bool) -> None:
        self.count_in_beep_enabled = bool(enabled)
        self.count_in_beep_button.setText("Beep On" if enabled else "Beep Off")

    def _cancel_count_in(self, label: str = "Ready") -> None:
        if hasattr(self, "count_in_timer"):
            self.count_in_timer.stop()
        self.count_in_active = False
        self.count_in_remaining = 0
        if hasattr(self, "count_in_label"):
            self.count_in_label.setText(label)

    def _show_count(self) -> None:
        self.count_in_label.setText(str(self.count_in_remaining))
        if self.count_in_beep_enabled:
            QApplication.beep()

    def _begin_count_in(self) -> None:
        self._cancel_count_in("")
        self.media_player.pause()

        if self.repeat_enabled:
            bounds = self._repeat_bounds_ms()
            if bounds is None:
                self.practice_message.setText("Set both repeat Start and End first.")
                self.count_in_label.setText("Ready")
                return
            start_ms, _ = bounds
            self._set_player_position(start_ms)
            self._highlight_beat(min(self.repeat_start_beat, self.repeat_end_beat))

        self.count_in_active = True
        self.count_in_remaining = self.count_in_beats
        self._show_count()
        self.count_in_timer.start()

    def _count_in_tick(self) -> None:
        if not self.count_in_active:
            self.count_in_timer.stop()
            return

        self.count_in_remaining -= 1
        if self.count_in_remaining > 0:
            self._show_count()
            return

        self.count_in_timer.stop()
        self.count_in_active = False
        self.count_in_label.setText("PLAY")

        if self.repeat_enabled:
            self.repeat_run_active = True
        else:
            self.repeat_run_active = False

        self.media_player.play()
        QTimer.singleShot(500, lambda: self.count_in_label.setText("Playing"))

    # ---------- Repeat ----------

    def _beat_label(self, beat_index: int | None) -> str:
        if beat_index is None:
            return "not set"
        return f"Bar {beat_index // 4 + 1}, Beat {beat_index % 4 + 1}"

    def _repeat_bounds_ms(self) -> tuple[int, int] | None:
        if (
            not self.practice_song
            or self.repeat_start_beat is None
            or self.repeat_end_beat is None
        ):
            return None

        bpm = int(self.current_practice_bpm or getattr(self.practice_song, "bpm", 0) or 0)
        if bpm <= 0:
            return None

        start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
        end_beat = max(self.repeat_start_beat, self.repeat_end_beat)
        beat_ms = 60000.0 / bpm
        start_ms = int(round(start_beat * beat_ms))
        end_ms = int(round((end_beat + 1) * beat_ms))

        duration = int(self.media_player.duration())
        if duration > 0:
            start_ms = max(0, min(start_ms, max(0, duration - 1)))
            end_ms = max(start_ms + 1, min(end_ms, duration))
        return start_ms, end_ms

    def _set_repeat_start(self) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a song and click a beat first.")
            return
        self.repeat_start_beat = int(self.current_beat_index)
        if self.repeat_end_beat is not None and self.repeat_end_beat < self.repeat_start_beat:
            self.repeat_end_beat = self.repeat_start_beat
        self._update_repeat_status()

    def _set_repeat_end(self) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a song and click a beat first.")
            return
        self.repeat_end_beat = int(self.current_beat_index)
        if self.repeat_start_beat is not None and self.repeat_end_beat < self.repeat_start_beat:
            self.repeat_start_beat = self.repeat_end_beat

        if self.repeat_start_beat is not None:
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(True)
            self.repeat_toggle_button.setText("Repeat On")
            self.repeat_toggle_button.blockSignals(False)
            self.repeat_enabled = True

        self._update_repeat_status()

    def _toggle_repeat(self, enabled: bool) -> None:
        if enabled and (
            self.repeat_start_beat is None or self.repeat_end_beat is None
        ):
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(False)
            self.repeat_toggle_button.setText("Repeat Off")
            self.repeat_toggle_button.blockSignals(False)
            self.repeat_enabled = False
            self.practice_message.setText("Set both repeat Start and End first.")
            return

        self.repeat_enabled = bool(enabled)
        self.repeat_run_active = False
        self.repeat_toggle_button.setText("Repeat On" if enabled else "Repeat Off")
        self._update_repeat_status()

    def _clear_repeat(self, silent: bool = False) -> None:
        self.repeat_start_beat = None
        self.repeat_end_beat = None
        self.repeat_enabled = False
        self.repeat_run_active = False
        self.repeat_seek_pending = False

        if hasattr(self, "repeat_toggle_button"):
            self.repeat_toggle_button.blockSignals(True)
            self.repeat_toggle_button.setChecked(False)
            self.repeat_toggle_button.setText("Repeat Off")
            self.repeat_toggle_button.blockSignals(False)

        self._update_repeat_status()
        if not silent and hasattr(self, "practice_message"):
            self.practice_message.setText("Repeat selection cleared.")

    def _update_repeat_status(self) -> None:
        if not hasattr(self, "repeat_status_label"):
            return
        state = "ON" if self.repeat_enabled else "OFF"
        self.repeat_status_label.setText(
            f"Repeat {state} | Start: {self._beat_label(self.repeat_start_beat)} | "
            f"End: {self._beat_label(self.repeat_end_beat)}"
        )
        self._refresh_repeat_markers()

    def _refresh_repeat_markers(self) -> None:
        if not getattr(self, "grid_cells", None):
            return

        for index, cell in enumerate(self.grid_cells):
            text = cell.text()
            for prefix in ("S/E ", "S ", "E "):
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break

            if index == self.repeat_start_beat == self.repeat_end_beat:
                text = "S/E " + text
            elif index == self.repeat_start_beat:
                text = "S " + text
            elif index == self.repeat_end_beat:
                text = "E " + text
            cell.setText(text)

    def _finish_repeat_run(self) -> None:
        bounds = self._repeat_bounds_ms()
        if bounds is None:
            self.repeat_run_active = False
            return

        start_ms, _ = bounds
        self.repeat_run_active = False
        self.media_player.pause()
        self._set_player_position(start_ms)
        self._highlight_beat(min(self.repeat_start_beat, self.repeat_end_beat))
        self.count_in_label.setText("Ready")
        self.practice_message.setText(
            "Repeat section complete. Press Play for another counted run."
        )

    # ---------- Playback ----------

    def _set_player_position(self, position: int) -> None:
        self.repeat_seek_pending = True
        try:
            self.media_player.setPosition(position)
            if hasattr(self, "position_slider"):
                self.position_slider.blockSignals(True)
                self.position_slider.setValue(position)
                self.position_slider.blockSignals(False)
            if hasattr(self, "time_label"):
                self._update_time_label(position, self.media_player.duration())
        finally:
            self.repeat_seek_pending = False

    def _practice_play(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        if self.count_in_active:
            return
        self._begin_count_in()

    def _practice_pause(self) -> None:
        self._cancel_count_in("Paused")
        self.repeat_run_active = False
        self.media_player.pause()

    def _practice_stop(self) -> None:
        self._cancel_count_in("Ready")
        self.repeat_run_active = False

        if self.practice_stop_reset_pending:
            return
        self.practice_stop_reset_pending = True
        self.media_player.stop()
        QTimer.singleShot(0, self._finish_practice_stop)

    def _finish_practice_stop(self) -> None:
        try:
            self.user_is_seeking = False
            self._set_player_position(0)
            self.current_beat_index = 0
            if self.grid_cells:
                self._highlight_beat(0)
            if self.practice_song:
                self.practice_message.setText(f"Stopped: {self.practice_song.title}")
        finally:
            self.practice_stop_reset_pending = False

    def _practice_seek_started(self) -> None:
        self._cancel_count_in("Ready")
        self.repeat_run_active = False
        super()._practice_seek_started()

    def _practice_seek_released(self) -> None:
        self.repeat_run_active = False
        super()._practice_seek_released()

    def _player_position_changed(self, position: int) -> None:
        if self.practice_stop_reset_pending:
            return

        if self.repeat_run_active and not self.repeat_seek_pending:
            bounds = self._repeat_bounds_ms()
            if bounds is not None and position >= bounds[1]:
                self._finish_repeat_run()
                return

        super()._player_position_changed(position)

    # ---------- BPM verification ----------

    def _duration_seconds(self, duration: str) -> int:
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
        return max(16, (int(seconds * bpm / 60) + 3) // 4)

    def _update_bpm_verify_label(self) -> None:
        if not hasattr(self, "bpm_verify_label"):
            return
        if not self.practice_song:
            self.bpm_verify_label.setText("BPM check: load a song first")
            return
        state = (
            "corrected"
            if self.current_practice_bpm != self.detected_practice_bpm
            else "detected"
        )
        self.bpm_verify_label.setText(
            f"BPM check: detected {self.detected_practice_bpm} | "
            f"current {self.current_practice_bpm} ({state})"
        )

    def _set_practice_bpm(self, bpm: int, source: str) -> None:
        if not self.practice_song:
            return
        bpm = max(30, min(300, int(round(bpm))))
        bars = self._bars_for_bpm(self.practice_song.duration, bpm)
        self.current_practice_bpm = bpm
        self.practice_song = replace(self.practice_song, bpm=bpm, estimated_bars=bars)
        self.practice_bpm_label.setText(f"BPM: {bpm}")
        self._update_bpm_verify_label()
        self._build_beat_grid(self.practice_song)
        self._update_grid_cursor_from_position(self.media_player.position())
        self.practice_message.setText(f"BPM set to {bpm} using {source}. Save BPM to keep it.")

    def _adjust_practice_bpm(self, amount: int) -> None:
        if self.practice_song:
            self._set_practice_bpm(self.current_practice_bpm + amount, f"{amount:+d}")

    def _bpm_half(self) -> None:
        if self.practice_song:
            self._set_practice_bpm(round(self.current_practice_bpm / 2), "Half")

    def _bpm_double(self) -> None:
        if self.practice_song:
            self._set_practice_bpm(self.current_practice_bpm * 2, "Double")

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
            self.tap_times[index] - self.tap_times[index - 1]
            for index in range(1, len(self.tap_times))
            if 0.20 <= self.tap_times[index] - self.tap_times[index - 1] <= 2.0
        ]
        if not intervals:
            self.tap_times = [now]
            return

        bpm = int(round(60.0 / (sum(intervals) / len(intervals))))
        self._set_practice_bpm(bpm, f"Tap BPM ({len(self.tap_times)} taps)")

    def _save_corrected_bpm(self) -> None:
        if not self.practice_song:
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
            self.practice_message.setText(
                f"Saved BPM {updated.bpm} to Library: {saved_path.name}"
            )
        except Exception as exc:
            self.practice_message.setText(f"Save BPM failed: {exc}")
