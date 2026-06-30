from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QGridLayout, QScrollArea

from banjofy.ui.widgets import BeatCell


class ChordGridController:
    """Builds and updates the beat/chord grid.

    This is Build 004.9's refactor step. The visual behaviour should remain the
    same, but grid construction, highlighting and scrolling now live outside
    main_window.py so future grid improvements are safer and easier.
    """

    def __init__(self, grid: QGridLayout, scroll: QScrollArea, on_cell_clicked: Callable[[int], None]) -> None:
        self.grid = grid
        self.scroll = scroll
        self.on_cell_clicked = on_cell_clicked
        self.cells: list[BeatCell] = []
        self.beats_per_row = 12

    def build(self, beat_chords: list[str], display_chord: Callable[[str], str]) -> list[BeatCell]:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.cells = []
        bars_per_row = 3
        self.beats_per_row = bars_per_row * 4

        for bar_start in range(0, len(beat_chords), self.beats_per_row):
            visual_row = (bar_start // self.beats_per_row) * 2

            for bar_offset in range(bars_per_row):
                bar_num = (bar_start // 4) + bar_offset + 1
                if (bar_num - 1) * 4 >= len(beat_chords):
                    continue
                hdr = QLabel(f"Bar {bar_num}")
                hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hdr.setObjectName("BarHeader")
                self.grid.addWidget(hdr, visual_row, bar_offset * 4, 1, 4)

            for i in range(self.beats_per_row):
                idx = bar_start + i
                if idx >= len(beat_chords):
                    break
                raw = beat_chords[idx]
                cell = BeatCell(idx, display_chord(raw) if raw else "")
                cell.clicked.connect(self.on_cell_clicked)
                self.cells.append(cell)
                self.grid.addWidget(cell, visual_row + 1, i)

        for col in range(self.beats_per_row):
            self.grid.setColumnStretch(col, 1)

        return self.cells

    def update(
        self,
        beat_chords: list[str],
        position: int,
        loop_start: int | None,
        loop_end: int | None,
        display_chord: Callable[[str], str],
    ) -> None:
        for idx, cell in enumerate(self.cells):
            if idx >= len(beat_chords):
                break
            raw = beat_chords[idx]
            cell.set_chord(display_chord(raw) if raw else "")
            cell.set_active(idx == position)
            cell.set_loop(loop_start is not None and loop_end is not None and loop_start <= idx <= loop_end)
        self.scroll_to_position(position)

    def scroll_to_position(self, position: int) -> None:
        """Place the active row near the top of the grid viewport."""
        if not self.cells or position >= len(self.cells):
            return

        current_row_start = (position // self.beats_per_row) * self.beats_per_row
        current_cell = self.cells[current_row_start]
        target_y = max(0, current_cell.y() - 2)
        self.scroll.verticalScrollBar().setValue(target_y)
