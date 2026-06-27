from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import math
import subprocess


ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class AnalysisResult:
    bpm: float | None
    method: str = ""
    confidence: float = 0.0


def _load_with_ffmpeg(path: Path, progress: ProgressCallback | None = None):
    """Decode almost any YouTube audio file to mono float samples using bundled ffmpeg.

    This avoids the Build 004.4A failure where librosa could not directly decode
    webm/opus/m4a files inside the Windows EXE.
    """
    try:
        import imageio_ffmpeg
        import numpy as np
    except Exception as exc:
        raise RuntimeError("Audio decoder package imageio-ffmpeg is not installed in this build") from exc

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    sample_rate = 22050

    if progress:
        progress("decoding audio with ffmpeg...", 20)

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-t",
        "180",
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "pipe:1",
    ]

    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=90,
        )
    except Exception as exc:
        raise RuntimeError(f"Could not run ffmpeg audio decoder: {exc}") from exc

    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", errors="ignore").strip()
        if not detail:
            detail = "ffmpeg produced no audio data"
        raise RuntimeError(f"Could not decode audio for BPM analysis: {detail}")

    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size < sample_rate:
        raise RuntimeError("Decoded audio was too short for tempo detection")

    return audio, sample_rate


def analyse_tempo(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    """Estimate tempo from a downloaded YouTube audio file.

    Build 004.4B decode fix:
    - uses bundled ffmpeg via imageio-ffmpeg for webm/opus/m4a files
    - then uses librosa only for the tempo/beat calculation
    """
    path = Path(path)
    if not path or not path.exists():
        raise RuntimeError("Audio file not found for analysis")

    try:
        import librosa
    except Exception as exc:
        raise RuntimeError("Audio analysis package librosa is not installed in this build") from exc

    y, sr = _load_with_ffmpeg(path, progress)

    if progress:
        progress("measuring beats...", 60)

    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    except Exception as exc:
        raise RuntimeError(f"Tempo analysis failed: {exc}") from exc

    try:
        # Newer librosa/numpy can return scalar arrays.
        bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
    except Exception:
        bpm = 0.0

    # Bring common half/double tempo errors into a usable practice range.
    while bpm and bpm < 55:
        bpm *= 2
    while bpm and bpm > 180:
        bpm /= 2

    if not bpm or math.isnan(bpm):
        raise RuntimeError("No reliable tempo detected")

    confidence = min(1.0, max(0.15, len(beats) / 80)) if beats is not None else 0.2

    if progress:
        progress("tempo found", 100)

    return AnalysisResult(bpm=bpm, method="ffmpeg decode + librosa beat tracker", confidence=confidence)
