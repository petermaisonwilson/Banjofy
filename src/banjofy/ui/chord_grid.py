from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea

from banjofy.ui.widgets import BeatCell


class ChordGridController:
    def __init__(
        self,
        grid: QGridLayout,
        scroll: QScrollArea,
        cell_clicked_callback: Callable[[int], None],
    ) -> None:
        self.grid = grid
        self.scroll = scroll
        self.cell_clicked_callback = cell_clicked_callback
        self.cells: list[BeatCell] = []
        self.bar_labels: list[QLabel] = []

    def _clear(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.cells = []
        self.bar_labels = []

    def build(
        self,
        beat_chords: list[str],
        display_chord: Callable[[str], str],
    ) -> list[BeatCell]:
        self._clear()

        if not beat_chords:
            beat_chords = [""]

        bars = (len(beat_chords) + 3) // 4

        for bar_index in range(bars):
            bar_label = QLabel(f"Bar {bar_index + 1}")
            bar_label.setObjectName("BarLabel")
            self.grid.addWidget(bar_label, bar_index * 2, 0, 1, 4)
            self.bar_labels.append(bar_label)

            for beat_in_bar in range(4):
                beat_index = bar_index * 4 + beat_in_bar
                raw_chord = beat_chords[beat_index] if beat_index < len(beat_chords) else ""
                cell = BeatCell(beat_index, display_chord(raw_chord))
                cell.clicked.connect(self.cell_clicked_callback)
                self.grid.addWidget(cell, bar_index * 2 + 1, beat_in_bar)
                self.cells.append(cell)

        for col in range(4):
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
        if not self.cells or len(self.cells) < len(beat_chords):
            self.build(beat_chords, display_chord)

        for i, cell in enumerate(self.cells):
            raw_chord = beat_chords[i] if i < len(beat_chords) else ""
            cell.set_chord(display_chord(raw_chord))

            in_loop = (
                loop_start is not None
                and loop_end is not None
                and loop_start <= i <= loop_end
            )

            cell.set_active(i == position)
            if in_loop and i != position:
                cell.set_loop(True)

        self._keep_current_row_visible(position)

    def _keep_current_row_visible(self, position: int) -> None:
        if position < 0:
            return

        row = position // 4
        estimated_row_height = 96
        target_y = max(0, row * estimated_row_height - estimated_row_height)

        def apply_scroll() -> None:
            bar = self.scroll.verticalScrollBar()
            bar.setValue(min(target_y, bar.maximum()))

        QTimer.singleShot(0, apply_scroll)
