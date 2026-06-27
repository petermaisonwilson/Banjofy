from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import math


ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class AnalysisResult:
    bpm: float | None
    method: str = ""
    confidence: float = 0.0


def analyse_tempo(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    """Estimate tempo from an audio file.

    Build 004.4A uses librosa if it can decode the downloaded file. Some YouTube
    files may still fail if Windows/Librosa cannot decode that format; the UI
    will show that clearly rather than silently failing.
    """
    if not path or not Path(path).exists():
        raise RuntimeError("Audio file not found for analysis")

    if progress:
        progress("loading audio...", 15)

    try:
        import librosa
    except Exception as exc:
        raise RuntimeError("Audio analysis package librosa is not installed in this build") from exc

    try:
        # mono=True is fine for tempo. duration limits CPU use for long songs.
        y, sr = librosa.load(str(path), sr=22050, mono=True, duration=180)
    except Exception as exc:
        raise RuntimeError(f"Could not decode audio for BPM analysis: {exc}") from exc

    if progress:
        progress("measuring beats...", 55)

    if y is None or len(y) < sr:
        raise RuntimeError("Audio was too short for tempo detection")

    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    except Exception as exc:
        raise RuntimeError(f"Tempo analysis failed: {exc}") from exc

    if isinstance(tempo, (list, tuple)):
        tempo = tempo[0] if tempo else 0
    try:
        bpm = float(tempo)
    except Exception:
        bpm = 0.0

    # Bring common half/double tempo errors into a usable practice range.
    while bpm and bpm < 55:
        bpm *= 2
    while bpm and bpm > 180:
        bpm /= 2

    if not bpm or math.isnan(bpm):
        raise RuntimeError("No reliable tempo detected")

    confidence = min(1.0, max(0.1, len(beats) / 80)) if beats is not None else 0.2

    if progress:
        progress("tempo found", 100)

    return AnalysisResult(bpm=bpm, method="librosa beat tracker", confidence=confidence)
