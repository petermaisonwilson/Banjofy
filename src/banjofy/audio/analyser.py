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
    key: str | None = None
    key_confidence: float = 0.0
    method: str = ""
    confidence: float = 0.0
    beat_count: int = 0
    estimated_bars: int = 0
    time_signature: str = "4/4"
    chords_by_bar: list[str] | None = None


def _convert_to_wav_with_bundled_ffmpeg(source: Path, progress: ProgressCallback | None = None) -> Path:
    try:
        import imageio_ffmpeg
    except Exception as exc:
        raise RuntimeError("Bundled ffmpeg package imageio-ffmpeg is not available") from exc

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not ffmpeg:
        raise RuntimeError("Bundled ffmpeg executable could not be located")

    if progress:
        progress("converting audio for analysis...", 18)

    temp_dir = Path(tempfile.gettempdir()) / "Banjofy" / "analysis"
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / f"{source.stem}_analysis.wav"

    cmd = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-t", "180", "-ac", "1", "-ar", "22050",
        "-vn", "-f", "wav", str(wav_path),
    ]

    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except Exception as exc:
        raise RuntimeError(f"ffmpeg conversion could not run: {exc}") from exc

    if completed.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size < 1000:
        details = (completed.stderr or completed.stdout or "unknown ffmpeg error").strip()
        raise RuntimeError(f"ffmpeg could not convert audio for analysis: {details[:400]}")

    return wav_path


def _estimate_key(y, sr: int) -> tuple[str | None, float]:
    import numpy as np
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    if chroma is None or chroma.size == 0:
        return None, 0.0

    profile = np.mean(chroma, axis=1)
    total = np.sum(profile)
    if not total:
        return None, 0.0
    profile = profile / total

    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    major_profile = major_profile / np.sum(major_profile)
    minor_profile = minor_profile / np.sum(minor_profile)

    note_names = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]

    scores: list[tuple[float, str]] = []
    for i, note in enumerate(note_names):
        maj = float(np.corrcoef(profile, np.roll(major_profile, i))[0, 1])
        minr = float(np.corrcoef(profile, np.roll(minor_profile, i))[0, 1])
        if not np.isnan(maj):
            scores.append((maj, f"{note} Major"))
        if not np.isnan(minr):
            scores.append((minr, f"{note} Minor"))

    if not scores:
        return None, 0.0

    scores.sort(reverse=True, key=lambda x: x[0])
    best_score, best_key = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0.0
    gap = max(0.0, best_score - second_score)
    confidence = max(0.2, min(0.98, 0.55 + gap * 2.5))
    return best_key, confidence


def _root_names() -> list[str]:
    return ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _template_for_chord(root: int, quality: str):
    import numpy as np

    template = np.zeros(12, dtype=float)
    if quality == "maj":
        intervals = [0, 4, 7]
    elif quality == "min":
        intervals = [0, 3, 7]
    elif quality == "7":
        intervals = [0, 4, 7, 10]
    else:
        intervals = [0, 4, 7]

    for interval in intervals:
        template[(root + interval) % 12] = 1.0

    # Lightly reward fifth/root stability.
    template[root % 12] += 0.35
    template[(root + 7) % 12] += 0.15
    total = template.sum()
    return template / total if total else template


def _estimate_bar_chords(y, sr: int, beats, max_bars: int = 180) -> list[str]:
    """Very first-stage chord detection.

    This compares each 4-beat bar's chroma profile against simple major/minor/7
    chord templates. It is intentionally conservative and will improve in later
    builds, but it gives us real automatic chord labels to test against audio.
    """
    import numpy as np
    import librosa

    if beats is None or len(beats) < 4:
        return []

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    if chroma is None or chroma.size == 0:
        return []

    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)
    roots = _root_names()

    chord_templates: list[tuple[str, object]] = []
    for root_index, name in enumerate(roots):
        chord_templates.append((name, _template_for_chord(root_index, "maj")))
        chord_templates.append((f"{name}m", _template_for_chord(root_index, "min")))
        chord_templates.append((f"{name}7", _template_for_chord(root_index, "7")))

    chords: list[str] = []
    beat_times = list(beats)
    if len(beat_times) < 5:
        return []

    max_start = min(len(beat_times) - 4, max_bars * 4)
    previous = ""
    for start in range(0, max_start, 4):
        bar_start = beat_times[start]
        bar_end = beat_times[start + 4] if start + 4 < len(beat_times) else beat_times[-1]
        if bar_end <= bar_start:
            continue

        mask = (times >= bar_start) & (times < bar_end)
        if not np.any(mask):
            chords.append(previous or "")
            continue

        profile = np.mean(chroma[:, mask], axis=1)
        total = np.sum(profile)
        if not total:
            chords.append(previous or "")
            continue
        profile = profile / total

        best_name = ""
        best_score = -999.0
        for name, template in chord_templates:
            score = float(np.dot(profile, template))
            if score > best_score:
                best_score = score
                best_name = name

        # Avoid flickering repeated labels: the grid only needs a chord at the
        # point where the chord changes.
        if best_name == previous:
            chords.append("")
        else:
            chords.append(best_name)
            previous = best_name

    return chords


def analyse_audio(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    source = Path(path)
    if not source.exists():
        raise RuntimeError("Audio file not found for analysis")

    if progress:
        progress("preparing audio...", 5)

    wav_path = _convert_to_wav_with_bundled_ffmpeg(source, progress=progress)

    try:
        import librosa
    except Exception as exc:
        raise RuntimeError("Audio analysis package librosa is not installed in this build") from exc

    if progress:
        progress("loading converted audio...", 34)

    try:
        y, sr = librosa.load(str(wav_path), sr=22050, mono=True, duration=180)
    except Exception as exc:
        raise RuntimeError(f"Could not load converted WAV for analysis: {exc}") from exc

    if y is None or len(y) < sr:
        raise RuntimeError("Audio was too short for analysis")

    if progress:
        progress("measuring tempo and beats...", 52)

    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    except Exception as exc:
        raise RuntimeError(f"Tempo/beat analysis failed: {exc}") from exc

    try:
        if hasattr(tempo, "__len__") and not isinstance(tempo, (str, bytes)):
            tempo = tempo[0] if len(tempo) else 0
        bpm = float(tempo)
    except Exception:
        bpm = 0.0

    while bpm and bpm < 55:
        bpm *= 2
    while bpm and bpm > 180:
        bpm /= 2

    if not bpm or math.isnan(bpm):
        raise RuntimeError("No reliable tempo detected")

    beat_count = int(len(beats)) if beats is not None else 0
    estimated_bars = int(round(beat_count / 4)) if beat_count else 0

    if progress:
        progress("detecting key...", 70)

    key, key_confidence = _estimate_key(y, sr)

    if progress:
        progress("detecting first-pass chords...", 86)

    chords_by_bar = _estimate_bar_chords(y, sr, beats)
    if chords_by_bar:
        estimated_bars = len(chords_by_bar)

    if progress:
        progress("analysis complete", 100)

    bpm_confidence = min(1.0, max(0.1, beat_count / 80)) if beat_count else 0.2

    return AnalysisResult(
        bpm=bpm,
        key=key,
        key_confidence=key_confidence,
        method="ffmpeg WAV conversion + librosa tempo/key + first-pass chroma chords",
        confidence=bpm_confidence,
        beat_count=beat_count,
        estimated_bars=estimated_bars,
        time_signature="4/4",
        chords_by_bar=chords_by_bar,
    )


def analyse_tempo(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    return analyse_audio(path, progress=progress)
