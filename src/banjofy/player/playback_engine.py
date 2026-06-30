from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaybackClock:
    """Small playback timing helper.

    This is the first step in splitting Banjofy into cleaner modules.
    The UI still owns the buttons and player, but beat/audio position maths now
    lives here instead of inside main_window.py.
    """

    bpm: int
    sync_offset_beats: int = 0

    def ms_per_beat(self) -> int:
        return max(1, int(60000 / max(1, self.bpm)))

    def audio_position_for_display_beat(self, display_position: int) -> int:
        audio_index = display_position - self.sync_offset_beats
        return max(0, audio_index * self.ms_per_beat())

    def display_beat_from_audio_ms(self, audio_ms: int, max_position: int) -> int:
        base_pos = int(audio_ms / self.ms_per_beat())
        display_pos = base_pos + self.sync_offset_beats
        return max(0, min(display_pos, max_position))
