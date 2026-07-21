from __future__ import annotations

import queue
import re
import threading
import time

import numpy as np
from pathlib import Path
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from banjofy.ui.main_window_legacy import MainWindow as LegacyMainWindow
from banjofy.library.song_library import LibrarySong
from banjofy.ui.timing_analyzer import TimingAnalysis, TimingAnalyzer
from banjofy.analysis.chord_engine import AnalysisResult, analyse_audio


APP_VERSION = "Banjofy 006.4.0 Module 17 Integration Build 001"


class MainWindow(LegacyMainWindow):
    """Clean Module 16 window built on the confirmed Module 14 foundation.

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
        self.repeat_continuous = False
        self.continuous_restart_pending = False

        self.timing_analyzer = TimingAnalyzer()
        self.timing_analysis: TimingAnalysis | None = None
        self.timing_queue: queue.Queue = queue.Queue()
        self.timing_analysis_running = False

        self.chord_analysis: AnalysisResult | None = None
        self.chord_queue: queue.Queue = queue.Queue()
        self.chord_analysis_running = False
        self.chord_level = "Beginner"

        super().__init__()

        self.setWindowTitle(APP_VERSION)
        self._set_visible_titles()

        self.count_in_timer = QTimer(self)
        self.count_in_timer.setInterval(1000)
        self.count_in_timer.setSingleShot(False)
        self.count_in_timer.timeout.connect(self._count_in_tick)

        self.timing_poll_timer = QTimer(self)
        self.timing_poll_timer.setInterval(100)
        self.timing_poll_timer.timeout.connect(self._poll_timing_analysis)

        self.chord_poll_timer = QTimer(self)
        self.chord_poll_timer.setInterval(100)
        self.chord_poll_timer.timeout.connect(self._poll_chord_analysis)

        self.statusBar().showMessage("Ready - Module 17 integrated chord analysis loaded")

    def _set_visible_titles(self) -> None:
        for label in self.findChildren(QLabel):
            if label.objectName() == "Title":
                if "Practice" in label.text():
                    label.setText("Practice Studio - Module 17")
                else:
                    label.setText(APP_VERSION)

    def _build_ui(self) -> None:
        super()._build_ui()
        self._set_visible_titles()

        self.delete_library_button = QPushButton("Delete Selected from Library")
        self.delete_library_button.setEnabled(False)
        self.delete_library_button.clicked.connect(self._delete_selected_library_song)
        self.library_page.layout().addWidget(self.delete_library_button)

        hints = self.library_page.findChildren(QLabel)
        for label in hints:
            if label.objectName() == "Hint":
                label.setText(
                    "Module 17 integration: confirmed Laboratory 016 chord analysis, automatic timing, "
                    "Practice controls and safe Library deletion."
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
                label.setText("Practice Studio - Module 17")
            elif label.objectName() == "Hint":
                label.setText(
                    "Timing source is shown as Fresh, Cached or BPM fallback. Detected metre "
                    "controls the number of beat columns in each bar."
                )

        self.timing_status_label = QLabel("Timing: load a song first")
        self.timing_status_label.setObjectName("LibraryMessage")
        self.timing_status_label.setWordWrap(True)
        outer.addWidget(self.timing_status_label)

        self.chord_status_label = QLabel("Chord analysis: load a song first")
        self.chord_status_label.setObjectName("LibraryMessage")
        self.chord_status_label.setWordWrap(True)
        outer.addWidget(self.chord_status_label)

        chord_level_row = QHBoxLayout()
        self.chord_level_button = QPushButton("Chord level: Beginner")
        self.chord_level_button.setToolTip("Cycle Beginner, Intermediate and Professional")
        self.chord_level_button.clicked.connect(self._cycle_chord_level)
        chord_level_row.addWidget(self.chord_level_button)
        outer.addLayout(chord_level_row)

        self.chord_summary_label = QLabel("Chords: waiting for analysis")
        self.chord_summary_label.setObjectName("LibraryMessage")
        self.chord_summary_label.setWordWrap(True)
        outer.addWidget(self.chord_summary_label)

        self.meter_button = QPushButton("Meter: Auto")
        self.meter_button.setToolTip("Cycle Auto, 3/4 and 4/4")
        self.meter_button.clicked.connect(self._cycle_meter_override)
        outer.addWidget(self.meter_button)

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

        self.repeat_mode_button = QPushButton("Mode: Single Run")
        self.repeat_mode_button.setToolTip(
            "Switch between one repeat run per Play press and automatic continuous practice"
        )

        self.repeat_clear_button = QPushButton("Clear Repeat")

        self.repeat_start_button.clicked.connect(self._set_repeat_start)
        self.repeat_end_button.clicked.connect(self._set_repeat_end)
        self.repeat_toggle_button.toggled.connect(self._toggle_repeat)
        self.repeat_mode_button.clicked.connect(self._toggle_repeat_mode)
        self.repeat_clear_button.clicked.connect(self._clear_repeat)

        repeat_row.addWidget(self.repeat_start_button)
        repeat_row.addWidget(self.repeat_end_button)
        repeat_row.addWidget(self.repeat_toggle_button)
        repeat_row.addWidget(self.repeat_mode_button)
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

    def _force_grid_to_start(self) -> None:
        if not hasattr(self, "grid_scroll"):
            return
        vertical = self.grid_scroll.verticalScrollBar()
        horizontal = self.grid_scroll.horizontalScrollBar()
        vertical.setValue(vertical.minimum())
        horizontal.setValue(horizontal.minimum())
        if self.grid_cells:
            self._highlight_beat(0)
            self.grid_scroll.ensureWidgetVisible(self.grid_cells[0], 0, 0)
            vertical.setValue(vertical.minimum())
            horizontal.setValue(horizontal.minimum())

    def _schedule_grid_reset(self) -> None:
        QTimer.singleShot(0, self._force_grid_to_start)
        QTimer.singleShot(120, self._force_grid_to_start)
        QTimer.singleShot(300, self._force_grid_to_start)

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
        self.meter_button.setText("Meter: Auto")
        self.chord_analysis = None
        self.chord_level = "Beginner"
        self.chord_level_button.setText("Chord level: Beginner")
        self.chord_status_label.setText("Chord analysis: queued")
        self.chord_summary_label.setText("Chords: waiting for analysis")
        self._schedule_grid_reset()
        self._start_automatic_timing_analysis()

    def _build_beat_grid(self, song: LibrarySong) -> None:
        timing = self.timing_analysis
        beats_per_bar = 4
        if timing is not None and timing.usable:
            beats_per_bar = int(timing.meter_numerator)
            detected_bars = max(
                1,
                (len(timing.beat_times_ms) + beats_per_bar - 1) // beats_per_bar,
            )
            song = replace(song, estimated_bars=detected_bars)
            self.practice_song = song

        if beats_per_bar == 4:
            super()._build_beat_grid(song)
        else:
            self._build_meter_aware_grid(song, beats_per_bar)

        if timing is not None and timing.usable:
            usable_beats = min(len(self.grid_cells), len(timing.beat_times_ms))
            if usable_beats < len(self.grid_cells):
                for cell in self.grid_cells[usable_beats:]:
                    cell.setEnabled(False)
                    cell.setToolTip("No detected musical beat at this position")

        for beat_index, cell in enumerate(self.grid_cells):
            bar = beat_index // beats_per_bar + 1
            beat = beat_index % beats_per_bar + 1
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

    def _build_meter_aware_grid(self, song: LibrarySong, beats_per_bar: int) -> None:
        while self.beat_grid_layout.count():
            item = self.beat_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.grid_cells = []
        bars = max(1, int(song.estimated_bars))
        self.grid_bar_count = bars
        chords_by_bar = getattr(song, "chords_by_bar", None) or []

        header = QLabel("Bar")
        header.setObjectName("GridHeader")
        self.beat_grid_layout.addWidget(header, 0, 0)

        for beat in range(beats_per_bar):
            beat_header = QLabel(f"Beat {beat + 1}")
            beat_header.setObjectName("GridHeader")
            beat_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beat_grid_layout.addWidget(beat_header, 0, beat + 1)

        for bar in range(bars):
            bar_label = QLabel(str(bar + 1))
            bar_label.setObjectName("BarLabel")
            bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beat_grid_layout.addWidget(bar_label, bar + 1, 0)
            for beat in range(beats_per_bar):
                chord_name = chords_by_bar[bar] if bar < len(chords_by_bar) else ""
                cell_text = chord_name if beat == 0 and chord_name else "•"
                cell = QLabel(cell_text)
                cell.setObjectName("BeatCell")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setMinimumSize(54, 30)
                cell.setProperty("beat_index", bar * beats_per_bar + beat)
                self.beat_grid_layout.addWidget(cell, bar + 1, beat + 1)
                self.grid_cells.append(cell)

        self.grid_status_label.setText(
            f"Grid: {bars} bars / {bars * beats_per_bar} beats | "
            f"meter {beats_per_bar}/4 | provisional chords"
        )
        self._highlight_beat(0)

    def _highlight_beat(self, beat_index: int) -> None:
        super()._highlight_beat(beat_index)
        self._refresh_repeat_markers()

    def _grid_cell_clicked(self, event, beat_index: int) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.continuous_restart_pending = False
        self._cancel_count_in("Ready")
        self.repeat_run_active = False
        self._seek_to_grid_beat(beat_index)

    def _beat_time_ms(self, beat_index: int) -> int | None:
        timing = self.timing_analysis
        if timing is not None and timing.usable:
            if 0 <= beat_index < len(timing.beat_times_ms):
                return int(timing.beat_times_ms[beat_index])
            return None

        if not self.practice_song:
            return None
        bpm = int(self.current_practice_bpm or getattr(self.practice_song, "bpm", 0) or 0)
        if bpm <= 0:
            return None
        return int(round(beat_index * (60000.0 / bpm)))

    def _beat_end_time_ms(self, beat_index: int) -> int | None:
        timing = self.timing_analysis
        if timing is not None and timing.usable:
            next_index = beat_index + 1
            if 0 <= next_index < len(timing.beat_times_ms):
                return int(timing.beat_times_ms[next_index])
            if 0 <= beat_index < len(timing.beat_times_ms):
                if len(timing.beat_times_ms) >= 2:
                    interval = timing.beat_times_ms[-1] - timing.beat_times_ms[-2]
                else:
                    interval = 500
                return int(timing.beat_times_ms[beat_index] + max(100, interval))
            return None

        start = self._beat_time_ms(beat_index)
        if start is None or not self.practice_song:
            return None
        bpm = int(self.current_practice_bpm or getattr(self.practice_song, "bpm", 0) or 0)
        return int(round(start + 60000.0 / max(1, bpm)))

    def _seek_to_grid_beat(self, beat_index: int) -> None:
        if not self.practice_song or not self.grid_cells:
            self.practice_message.setText("Load a Library song into Practice first.")
            return

        beat_index = max(0, min(int(beat_index), len(self.grid_cells) - 1))
        position = self._beat_time_ms(beat_index)
        if position is None:
            self.practice_message.setText("No detected timing is available for that beat.")
            return

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

        source = (
            "detected musical timing"
            if self.timing_analysis is not None and self.timing_analysis.usable
            else "BPM fallback timing"
        )
        self.practice_message.setText(
            f"Jumped to {self._beat_label(beat_index)} "
            f"using {source}."
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

    def _beats_per_bar(self) -> int:
        if self.timing_analysis is not None and self.timing_analysis.usable:
            return int(self.timing_analysis.meter_numerator)
        return 4

    def _beat_label(self, beat_index: int | None) -> str:
        if beat_index is None:
            return "not set"
        beats_per_bar = self._beats_per_bar()
        return (
            f"Bar {beat_index // beats_per_bar + 1}, "
            f"Beat {beat_index % beats_per_bar + 1}"
        )

    def _repeat_bounds_ms(self) -> tuple[int, int] | None:
        if (
            not self.practice_song
            or self.repeat_start_beat is None
            or self.repeat_end_beat is None
        ):
            return None

        start_beat = min(self.repeat_start_beat, self.repeat_end_beat)
        end_beat = max(self.repeat_start_beat, self.repeat_end_beat)

        start_ms = self._beat_time_ms(start_beat)
        end_ms = self._beat_end_time_ms(end_beat)
        if start_ms is None or end_ms is None:
            return None

        duration = int(self.media_player.duration())
        if duration > 0:
            start_ms = max(0, min(start_ms, max(0, duration - 1)))
            end_ms = max(start_ms + 1, min(end_ms, duration))
        return int(start_ms), int(end_ms)

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

    def _toggle_repeat_mode(self) -> None:
        self.repeat_continuous = not self.repeat_continuous
        self.continuous_restart_pending = False
        self.repeat_mode_button.setText(
            "Mode: Continuous" if self.repeat_continuous else "Mode: Single Run"
        )

        if self.repeat_continuous:
            self.practice_message.setText(
                "Continuous Practice selected. Each repeat run will use a fresh count-in."
            )
        else:
            self.practice_message.setText(
                "Single Run selected. Press Play for each counted repeat attempt."
            )

        self._update_repeat_status()

    def _clear_repeat(self, silent: bool = False) -> None:
        self.repeat_start_beat = None
        self.repeat_end_beat = None
        self.repeat_enabled = False
        self.repeat_run_active = False
        self.repeat_seek_pending = False
        self.continuous_restart_pending = False

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
        mode = "Continuous" if self.repeat_continuous else "Single Run"
        self.repeat_status_label.setText(
            f"Repeat {state} | Mode: {mode} | "
            f"Start: {self._beat_label(self.repeat_start_beat)} | "
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

        if self.repeat_continuous and self.repeat_enabled:
            self.practice_message.setText(
                "Repeat section complete. Starting the next count-in automatically."
            )
            self.continuous_restart_pending = True
            QTimer.singleShot(350, self._restart_continuous_repeat)
        else:
            self.continuous_restart_pending = False
            self.practice_message.setText(
                "Repeat section complete. Press Play for another counted run."
            )

    def _restart_continuous_repeat(self) -> None:
        if not self.continuous_restart_pending:
            return

        self.continuous_restart_pending = False

        if (
            not self.practice_song
            or not self.repeat_enabled
            or not self.repeat_continuous
            or self.repeat_start_beat is None
            or self.repeat_end_beat is None
        ):
            return

        self._begin_count_in()

    def _update_grid_cursor_from_position(self, position_ms: int) -> None:
        timing = self.timing_analysis
        if timing is not None and timing.usable and self.grid_cells:
            times = timing.beat_times_ms
            index = int(np.searchsorted(times, position_ms, side="right") - 1)
            index = max(0, min(index, min(len(times), len(self.grid_cells)) - 1))
            if index != self.current_beat_index:
                self._highlight_beat(index)
            return

        super()._update_grid_cursor_from_position(position_ms)

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
        self.continuous_restart_pending = False
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        if self.count_in_active:
            return
        self._begin_count_in()

    def _practice_pause(self) -> None:
        self.continuous_restart_pending = False
        self._cancel_count_in("Paused")
        self.repeat_run_active = False
        self.media_player.pause()

    def _practice_stop(self) -> None:
        self.continuous_restart_pending = False
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
        self.continuous_restart_pending = False
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

    # ---------- Library selection and deletion ----------

    def _refresh_library_list(self) -> None:
        super()._refresh_library_list()
        if hasattr(self, "delete_library_button"):
            self.delete_library_button.setEnabled(False)

    def _select_library_song(self, item) -> None:
        super()._select_library_song(item)
        if hasattr(self, "delete_library_button"):
            self.delete_library_button.setEnabled(
                self.selected_library_song is not None
            )

    def _library_song_record_path(self, song: LibrarySong) -> Path:
        safe = re.sub(
            r"[^A-Za-z0-9._ -]+",
            "_",
            f"{song.title} - {song.channel}",
        ).strip()
        safe = re.sub(r"\s+", " ", safe)[:140] or "song"
        analysis_path = Path(song.analysis_file)
        for root in (
            analysis_path.parent.parent,
            analysis_path.parent,
            Path(song.audio_file).parent.parent,
        ):
            candidate = root / "songs" / f"{safe}.song.json"
            if candidate.exists():
                return candidate
        return analysis_path.parent.parent / "songs" / f"{safe}.song.json"

    def _delete_selected_library_song(self) -> None:
        song = self.selected_library_song
        if song is None:
            self._set_library_message("Select a Library song before deleting")
            return

        answer = QMessageBox.question(
            self,
            "Delete Library Song",
            f"Remove '{song.title}' from the Banjofy Library?\n\n"
            "The Library record, saved analysis and timing cache will be deleted. "
            "Audio is handled separately.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        errors = []
        audio_path = Path(song.audio_file)

        try:
            self._practice_stop()
            self.media_player.stop()
            self.media_player.setSource(QUrl())
        except Exception as exc:
            errors.append(f"media unload: {exc}")

        if self.practice_song and self.practice_song.audio_file == song.audio_file:
            self.practice_song = None
            self.timing_analysis = None
            self.practice_message.setText(
                "The deleted song was unloaded from Practice."
            )

        record_path = self._library_song_record_path(song)
        try:
            if record_path.exists():
                record_path.unlink()
            else:
                errors.append(f"Library record not found: {record_path.name}")
        except Exception as exc:
            errors.append(f"Library record: {exc}")

        analysis_path = Path(getattr(song, "analysis_file", "") or "")
        try:
            if analysis_path.exists():
                analysis_path.unlink()
        except Exception as exc:
            errors.append(f"analysis file: {exc}")

        try:
            self.timing_analyzer.delete_cache(audio_path)
        except Exception as exc:
            errors.append(f"timing cache: {exc}")

        remove_audio = QMessageBox.question(
            self,
            "Delete Downloaded Audio",
            f"Also delete the downloaded audio file for '{song.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if remove_audio == QMessageBox.StandardButton.Yes:
            try:
                if audio_path.exists():
                    audio_path.unlink()
            except Exception as exc:
                errors.append(f"audio file: {exc}")

        self.selected_library_song = None
        self._refresh_library_list()

        if any(
            existing.title == song.title and existing.channel == song.channel
            for existing in self.library_songs
        ):
            errors.append("Library record still appears after refresh")

        if errors:
            self._set_library_message(
                "Deletion completed with details: " + "; ".join(errors)
            )
        else:
            self._set_library_message(f"Fully deleted from Library: {song.title}")

    # ---------- Integrated Laboratory 016 chord analysis ----------

    def _chord_output_folder(self) -> Path:
        if not self.practice_song:
            return Path.cwd() / "Banjofy Chord Reports"
        analysis_path = Path(self.practice_song.analysis_file)
        folder = analysis_path.parent / "chord_reports"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _start_chord_analysis(self) -> None:
        if not self.practice_song or self.chord_analysis_running:
            return
        audio_path = Path(self.practice_song.audio_file)
        if not audio_path.exists():
            self.chord_status_label.setText("Chord analysis: audio file is missing")
            return

        self.chord_analysis_running = True
        self.chord_status_label.setText("Chord analysis: starting confirmed Laboratory 016 engine...")
        output_folder = self._chord_output_folder()

        def worker() -> None:
            try:
                result = analyse_audio(
                    audio_path,
                    output_folder,
                    lambda message: self.chord_queue.put(("progress", message)),
                )
                self.chord_queue.put(("done", result))
            except Exception as exc:
                self.chord_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.chord_poll_timer.start()

    def _poll_chord_analysis(self) -> None:
        while True:
            try:
                kind, payload = self.chord_queue.get_nowait()
            except queue.Empty:
                return

            if kind == "progress":
                self.chord_status_label.setText(f"Chord analysis: {payload}")
                continue

            self.chord_poll_timer.stop()
            self.chord_analysis_running = False

            if kind == "error":
                self.chord_analysis = None
                self.chord_status_label.setText(f"Chord analysis failed: {payload}")
                self.chord_summary_label.setText("Chords: unavailable; all existing Practice functions remain available")
                return

            self.chord_analysis = payload
            self.current_practice_bpm = int(round(payload.practice_bpm))
            self.detected_practice_bpm = int(round(payload.practice_bpm))
            self.practice_bpm_label.setText(f"BPM: {self.current_practice_bpm}")
            self.chord_status_label.setText(
                f"Chord analysis ready | key {payload.key} "
                f"({int(round(payload.key_confidence * 100))}%) | "
                f"raw {payload.raw_bpm:.1f} BPM | Practice {payload.practice_bpm:.1f} BPM"
            )
            self._update_chord_summary()
            return

    def _cycle_chord_level(self) -> None:
        levels = ["Beginner", "Intermediate", "Professional"]
        index = levels.index(self.chord_level) if self.chord_level in levels else 0
        self.chord_level = levels[(index + 1) % len(levels)]
        self.chord_level_button.setText(f"Chord level: {self.chord_level}")
        self._update_chord_summary()

    def _update_chord_summary(self) -> None:
        result = self.chord_analysis
        if result is None:
            self.chord_summary_label.setText("Chords: waiting for analysis")
            return
        if self.chord_level == "Intermediate":
            chords = result.intermediate_chords
        elif self.chord_level == "Professional":
            chords = result.professional_chords
        else:
            chords = result.beginner_chords
        chord_text = ", ".join(chords) if chords else "No reliable chords found"
        self.chord_summary_label.setText(
            f"{self.chord_level} chords: {chord_text} | one analysis, three presentation levels"
        )

    # ---------- Automatic musical timing ----------

    def _start_automatic_timing_analysis(self) -> None:
        if not self.practice_song:
            return

        audio_path = Path(self.practice_song.audio_file)
        if not audio_path.exists():
            self.timing_status_label.setText("Timing: audio file is missing")
            return

        self.timing_analysis = None
        self.timing_analysis_running = True
        self.timing_status_label.setText(
            "Timing: analysing beats and Bar 1 Beat 1 automatically..."
        )

        def worker() -> None:
            try:
                result = self.timing_analyzer.analyse(
                    audio_path,
                    progress=lambda message: self.timing_queue.put(("progress", message)),
                )
                self.timing_queue.put(("done", result))
            except Exception as exc:
                self.timing_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.timing_poll_timer.start()

    def _poll_timing_analysis(self) -> None:
        while True:
            try:
                kind, payload = self.timing_queue.get_nowait()
            except queue.Empty:
                return

            if kind == "progress":
                self.timing_status_label.setText(f"Timing: {payload}")
                continue

            self.timing_poll_timer.stop()
            self.timing_analysis_running = False

            if kind == "error":
                self.timing_analysis = None
                self.timing_status_label.setText(
                    f"Timing source: BPM fallback | Exact failure: {payload}"
                )
                self.practice_message.setText(
                    "Automatic timing could not be completed. Existing BPM timing remains available."
                )
                self._start_chord_analysis()
                return

            self.timing_analysis = payload
            beats_per_bar = int(payload.meter_numerator)
            bars = max(
                1,
                (len(payload.beat_times_ms) + beats_per_bar - 1) // beats_per_bar,
            )
            confidence_percent = int(round(payload.confidence * 100))
            self.timing_status_label.setText(
                f"Timing source: {payload.source_kind} | "
                f"{len(payload.beat_times_ms)} beats / {bars} bars | "
                f"meter {payload.meter_numerator}/{payload.meter_denominator} | "
                f"first downbeat {payload.first_downbeat_ms / 1000:.2f}s | "
                f"confidence {confidence_percent}% | {payload.diagnostic}"
            )
            self.practice_message.setText(
                "Automatic timing ready. Grid seeking and repeat points now use detected beats."
            )
            self._build_beat_grid(self.practice_song)
            self._update_grid_cursor_from_position(self.media_player.position())
            self._schedule_grid_reset()
            self._start_chord_analysis()
            return

    # ---------- Meter correction ----------

    def _cycle_meter_override(self) -> None:
        if not self.practice_song:
            self.practice_message.setText(
                "Load a Library song into Practice first."
            )
            return

        if self.timing_analysis is None or not self.timing_analysis.usable:
            self.practice_message.setText(
                "Complete automatic timing analysis before changing meter."
            )
            return

        current = self.meter_button.text()
        if current == "Meter: Auto":
            new_meter = 3
            self.meter_button.setText("Meter: 3/4")
        elif current == "Meter: 3/4":
            new_meter = 4
            self.meter_button.setText("Meter: 4/4")
        else:
            new_meter = None
            self.meter_button.setText("Meter: Auto")

        audio_path = Path(self.practice_song.audio_file)

        if new_meter is None:
            self.timing_analyzer.clear_meter_override(audio_path)
            self.timing_analysis = None
            self.practice_message.setText(
                "Meter returned to Auto. Running fresh timing analysis..."
            )
            self._start_automatic_timing_analysis()
            return

        self.timing_analysis = self.timing_analyzer.save_meter_override(
            audio_path,
            new_meter,
            self.timing_analysis,
        )
        self._build_beat_grid(self.practice_song)
        self._schedule_grid_reset()
        bars = max(
            1,
            (
                len(self.timing_analysis.beat_times_ms)
                + new_meter - 1
            ) // new_meter,
        )
        self.timing_status_label.setText(
            f"Timing source: Manual meter correction | "
            f"{len(self.timing_analysis.beat_times_ms)} beats / {bars} bars | "
            f"meter {new_meter}/4 | detected timestamps retained"
        )
        self.practice_message.setText(
            f"Meter changed to {new_meter}/4, saved and grid rebuilt."
        )

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
        if self.timing_analysis is not None and self.timing_analysis.usable:
            self.practice_message.setText(
                f"BPM display set to {bpm} using {source}. Detected beat timestamps remain active."
            )
        else:
            self.practice_message.setText(
                f"BPM set to {bpm} using {source}. Save BPM to keep it."
            )

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
