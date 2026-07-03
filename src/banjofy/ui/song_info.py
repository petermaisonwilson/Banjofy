from __future__ import annotations


class SongInfoController:
    @staticmethod
    def update_progress(label, position: int, total: int) -> None:
        label.setText(f"Beat {position + 1} of {max(total, 1)}")
