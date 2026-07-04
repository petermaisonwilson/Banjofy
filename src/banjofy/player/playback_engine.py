from __future__ import annotations


class PlaybackClock:
    """Simple BPM-based clock used by 006.1 recovery build."""

    def __init__(self, bpm: float = 92, sync_offset_beats: int = 0) -> None:
        self.bpm = max(1.0, float(bpm or 92))
        self.sync_offset_beats = int(sync_offset_beats or 0)

    @property
    def ms_per_beat(self) -> float:
        return 60000.0 / self.bpm

    def audio_position_for_display_beat(self, display_beat: int) -> int:
        audio_beat = max(0, int(display_beat) + self.sync_offset_beats)
        return int(audio_beat * self.ms_per_beat)

    def display_beat_from_audio_ms(self, audio_ms: int, max_position: int) -> int:
        raw = int(round(float(audio_ms) / self.ms_per_beat)) - self.sync_offset_beats
        return max(0, min(int(max_position), raw))
