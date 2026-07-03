from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ChordEvent:
    chord: str
    beat_index: int
    timestamp_ms: int
    confidence: float | None = None
