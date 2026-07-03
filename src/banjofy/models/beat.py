from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Beat:
    index: int
    timestamp_ms: int
    bar_number: int
    beat_in_bar: int
    chord: str = ""
    confidence: float | None = None
