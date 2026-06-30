from __future__ import annotations

from PySide6.QtWidgets import QLabel


class SongInfoController:
    """Song progress display helper.

    Shows the player where they are in the generated song grid.
    """

    @staticmethod
    def update_progress(label: QLabel, beat: int, total_beats: int) -> None:
        total_beats = max(1, total_beats)
        beat = max(0, min(beat, total_beats - 1))
        current_bar = beat // 4 + 1
        total_bars = (total_beats + 3) // 4
        percent = int((beat / max(1, total_beats - 1)) * 100)
        label.setText(f"Bar {current_bar}/{total_bars}   {percent}%")
