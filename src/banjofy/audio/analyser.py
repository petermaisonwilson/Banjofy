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
    beat_times_ms: list[int] | None = None
    chords_by_beat: list[str] | None = None


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
        "-i", str(source), "-t", "240", "-ac", "1", "-ar", "22050",
        "-vn", "-f", "wav", str(wav_path),
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)

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
    template[root % 12] += 0.35
    template[(root + 7) % 12] += 0.15
    total = template.sum()
    return template / total if total else template


def _chord_templates():
    roots = _root_names()
    templates: list[tuple[str, object]] = []
    for root_index, name in enumerate(roots):
        templates.append((name, _template_for_chord(root_index, "maj")))
        templates.append((f"{name}m", _template_for_chord(root_index, "min")))
        templates.append((f"{name}7", _template_for_chord(root_index, "7")))
    return templates


def _estimate_beat_chords(y, sr: int, beat_times: list[float], max_beats: int = 960) -> list[str]:
    """First true beat-level chord detection.

    One chord is estimated for each detected beat window. Repeated chords are
    left blank so the grid remains readable while still allowing changes on
    any beat.
    """
    import numpy as np
    import librosa

    if len(beat_times) < 2:
        return []

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    if chroma is None or chroma.size == 0:
        return []

    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)
    templates = _chord_templates()

    chords: list[str] = []
    previous = ""
    usable = min(len(beat_times) - 1, max_beats)

    for i in range(usable):
        start = beat_times[i]
        end = beat_times[i + 1]
        if end <= start:
            chords.append("")
            continue

        mask = (frame_times >= start) & (frame_times < end)
        if not np.any(mask):
            chords.append("")
            continue

        profile = np.mean(chroma[:, mask], axis=1)
        total = np.sum(profile)
        if not total:
            chords.append("")
            continue
        profile = profile / total

        best_name = ""
        best_score = -999.0
        for name, template in templates:
            score = float(np.dot(profile, template))
            if score > best_score:
                best_score = score
                best_name = name

        if best_name == previous:
            chords.append("")
        else:
            chords.append(best_name)
            previous = best_name

    return chords


def _bars_from_beat_chords(chords_by_beat: list[str]) -> list[str]:
    bars: list[str] = []
    previous = ""
    for start in range(0, len(chords_by_beat), 4):
        window = chords_by_beat[start:start + 4]
        chord = next((c for c in window if c), "")
        if chord and chord != previous:
            bars.append(chord)
            previous = chord
        else:
            bars.append("")
    return bars


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
        progress("loading converted audio...", 30)

    y, sr = librosa.load(str(wav_path), sr=22050, mono=True, duration=240)

    if y is None or len(y) < sr:
        raise RuntimeError("Audio was too short for analysis")

    if progress:
        progress("building beat map...", 48)

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")

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

    beat_times = [float(t) for t in list(beats or []) if float(t) >= 0]
    beat_times_ms = [int(round(t * 1000)) for t in beat_times]

    if progress:
        progress("detecting key...", 65)

    key, key_confidence = _estimate_key(y, sr)

    if progress:
        progress("detecting chords on each beat...", 82)

    chords_by_beat = _estimate_beat_chords(y, sr, beat_times)
    if chords_by_beat:
        beat_times_ms = beat_times_ms[:len(chords_by_beat)]
    beat_count = len(chords_by_beat) if chords_by_beat else len(beat_times_ms)
    estimated_bars = max(1, int(math.ceil(beat_count / 4))) if beat_count else 0
    chords_by_bar = _bars_from_beat_chords(chords_by_beat) if chords_by_beat else []

    if progress:
        progress("analysis complete", 100)

    bpm_confidence = min(1.0, max(0.1, beat_count / 120)) if beat_count else 0.2

    return AnalysisResult(
        bpm=bpm,
        key=key,
        key_confidence=key_confidence,
        method="ffmpeg WAV conversion + librosa beat map + beat-level chroma chords",
        confidence=bpm_confidence,
        beat_count=beat_count,
        estimated_bars=estimated_bars,
        time_signature="4/4",
        chords_by_bar=chords_by_bar,
        beat_times_ms=beat_times_ms,
        chords_by_beat=chords_by_beat,
    )


def analyse_tempo(path: Path, progress: ProgressCallback | None = None) -> AnalysisResult:
    return analyse_audio(path, progress=progress)
