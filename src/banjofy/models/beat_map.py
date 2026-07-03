from __future__ import annotations
from dataclasses import dataclass, field
from banjofy.models.beat import Beat

@dataclass
class BeatMap:
    beats: list[Beat] = field(default_factory=list)

    @property
    def beat_count(self) -> int:
        return len(self.beats)

    @property
    def bar_count(self) -> int:
        return max((beat.bar_number for beat in self.beats), default=0)

    def nearest_beat_index(self, timestamp_ms: int) -> int:
        if not self.beats:
            return 0
        return min(self.beats, key=lambda beat: abs(beat.timestamp_ms - timestamp_ms)).index
