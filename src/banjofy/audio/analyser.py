from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import math
import subprocess
import tempfile


ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class AnalysisResult:
    bpm: float | None
    method: str = ""
    confidence: float = 0.0


def _convert_to_wav_with_bundled_ffmpeg(source: Path, progress: ProgressCallback | None = None) -> Path:
    """Convert whatever yt-dlp downloaded into a temporary WAV file.

    This avoids relying on Windows/Librosa being able to decode .webm/.opus/.m4a
    directly. imageio-ffmpeg supplies a private ffmpeg executable that should be
    bundled into the GitHub-built EXE by Banjofy.spec.
    """
    try:
        import imageio_ffmpeg
    except Exception as exc:
        raise RuntimeError("Bundled ffmpeg package imageio-ffmpeg is not available") from exc

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not ffmpeg:
        raise RuntimeError("Bundled ffmpeg executable could not be located")

    if progress:
        progress("converting audio for analysis...", 25)

    temp_dir = Path(tempfile.gettempdir()) / "Banjofy" / "analysis"
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / f"{source.stem}_analysis.wav"

    cmd = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-t",
        "180",
        "-ac",
        "1",
        "-ar",
        "22050",
        "-vn",
        "-f",
        "wav",
        str(wav_path),
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except Exception as exc:
        raise RuntimeError(f"ffmpeg conversion could not run: {exc}") from exc

    if completed.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size < 1000:
        details = (completed.stderr or completed.stdout or "unknown ffmpeg error").strip()
        raise RuntimeError(f"ffmpeg could not convert audio for analysis: {details[:400]}")

    return wav_path


def analyse_tempo(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    """Estimate tempo from a downloaded YouTube audio file.

    Build 004.4C converts the audio to WAV first using bundled ffmpeg, then asks
    librosa to detect tempo. This is more reliable than asking librosa to decode
    YouTube's original webm/opus/m4a formats directly.
    """
    source = Path(path)
    if not source.exists():
        raise RuntimeError("Audio file not found for analysis")

    if progress:
        progress("preparing audio...", 10)

    wav_path = _convert_to_wav_with_bundled_ffmpeg(source, progress=progress)

    try:
        import librosa
    except Exception as exc:
        raise RuntimeError("Audio analysis package librosa is not installed in this build") from exc

    if progress:
        progress("loading converted audio...", 45)

    try:
        y, sr = librosa.load(str(wav_path), sr=22050, mono=True, duration=180)
    except Exception as exc:
        raise RuntimeError(f"Could not load converted WAV for BPM analysis: {exc}") from exc

    if y is None or len(y) < sr:
        raise RuntimeError("Audio was too short for tempo detection")

    if progress:
        progress("measuring beats...", 70)

    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    except Exception as exc:
        raise RuntimeError(f"Tempo analysis failed: {exc}") from exc

    # librosa versions may return a float, numpy scalar, or short array.
    try:
        if hasattr(tempo, "__len__") and not isinstance(tempo, (str, bytes)):
            tempo = tempo[0] if len(tempo) else 0
        bpm = float(tempo)
    except Exception:
        bpm = 0.0

    # Pull common half/double estimates into a useful practice range.
    while bpm and bpm < 55:
        bpm *= 2
    while bpm and bpm > 180:
        bpm /= 2

    if not bpm or math.isnan(bpm):
        raise RuntimeError("No reliable tempo detected")

    confidence = min(1.0, max(0.1, len(beats) / 80)) if beats is not None else 0.2

    if progress:
        progress("tempo found", 100)

    return AnalysisResult(
        bpm=bpm,
        method="ffmpeg WAV conversion + librosa beat tracker",
        confidence=confidence,
    )
