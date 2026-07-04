from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout

from banjofy.ui.widgets import BeatCell


class BarPanel(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("BarPanel")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)

        self.title = QLabel(title)
        self.title.setObjectName("BarHeader")
        self.layout.addWidget(self.title)

        self.beat_grid = QGridLayout()
        self.beat_grid.setSpacing(4)
        self.layout.addLayout(self.beat_grid)


class ChordGridController:
    """Practice grid controller.

    006.1F restores visible beat squares and a strong active cursor.
    """

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
        self.bar_panels: list[BarPanel] = []
        self.bars_per_row = 3
        self.beats_per_bar = 4

    def _clear(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.cells = []
        self.bar_panels = []

    def build(self, beat_chords: list[str], display_chord: Callable[[str], str]) -> list[BeatCell]:
        self._clear()
        if not beat_chords:
            beat_chords = [""]

        bars = (len(beat_chords) + self.beats_per_bar - 1) // self.beats_per_bar

        for bar_index in range(bars):
            row = bar_index // self.bars_per_row
            col = bar_index % self.bars_per_row

            panel = BarPanel(f"Bar {bar_index + 1}")
            self.grid.addWidget(panel, row, col)
            self.bar_panels.append(panel)

            for beat_in_bar in range(self.beats_per_bar):
                beat_index = bar_index * self.beats_per_bar + beat_in_bar
                raw_chord = beat_chords[beat_index] if beat_index < len(beat_chords) else ""
                cell = BeatCell(beat_index, display_chord(raw_chord))
                cell.setMinimumHeight(78)
                cell.clicked.connect(self.cell_clicked_callback)
                panel.beat_grid.addWidget(cell, 0, beat_in_bar)
                self.cells.append(cell)

        for col in range(self.bars_per_row):
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
            in_loop = loop_start is not None and loop_end is not None and loop_start <= i <= loop_end
            cell.set_active(i == position)
            if in_loop and i != position:
                cell.set_loop(True)

        self._keep_current_row_visible(position)

    def _keep_current_row_visible(self, position: int) -> None:
        if position < 0:
            return

        bar = position // self.beats_per_bar
        visual_row = bar // self.bars_per_row
        estimated_row_height = 128
        target_y = max(0, visual_row * estimated_row_height - estimated_row_height)

        def apply_scroll() -> None:
            scrollbar = self.scroll.verticalScrollBar()
            scrollbar.setValue(min(target_y, scrollbar.maximum()))

        QTimer.singleShot(0, apply_scroll)
