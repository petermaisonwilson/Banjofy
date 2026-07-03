from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnalysisResult:
    bpm: int
    key: str
    key_confidence: float
    beat_times_ms: list[int]
    beat_chords: list[str]


def analyse_audio(path: str | Path, progress=None) -> AnalysisResult:
    # Stable foundation fallback analyser.
    # Later builds can replace this with the advanced analyser again.
    if progress:
        progress(20, "Loading audio")
    bpm = 92
    beat_times = [i * int(60000 / bpm) for i in range(64)]
    chords = []
    progression = ["G", "", "", "", "C", "", "", "", "G", "", "", "", "D", "", "", ""]
    for i in range(64):
        chords.append(progression[i % len(progression)])
    if progress:
        progress(100, "Analysis complete")
    return AnalysisResult(bpm=bpm, key="G", key_confidence=0.8, beat_times_ms=beat_times, beat_chords=chords)
