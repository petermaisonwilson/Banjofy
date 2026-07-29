from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np
import scipy.signal


STRUCTURE_VERSION = 7
METER_CONFIDENCE_THRESHOLD = 0.55
RHYTHMIC_WINDOW_BEATS = 64
AUDIBLE_PREVIEW_SECONDS = 180.0
SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))


def ensure_scipy_signal_compatibility() -> None:
    for name in ("hann", "hamming", "blackman", "blackmanharris", "bartlett", "boxcar"):
        if not hasattr(scipy.signal, name) and hasattr(scipy.signal.windows, name):
            setattr(scipy.signal, name, getattr(scipy.signal.windows, name))


@dataclass(frozen=True)
class MeterCandidate:
    meter: str
    beats_per_bar: int
    phase: int
    score: float
    confidence: float


@dataclass(frozen=True)
class StructureResult:
    structure_version: int
    source_audio: str
    raw_bpm: float
    beat_times: list[float]
    beat_count: int
    meter: str
    meter_status: str
    best_meter_candidate: str
    beats_per_bar: int
    meter_confidence: float
    full_track_meter_confidence: float
    rhythmic_window_candidate: str
    rhythmic_window_meter_confidence: float
    meter_candidate_agreement: bool
    rhythmic_window_start_beat: int
    rhythmic_window_end_beat: int
    rhythmic_window_start_s: float
    rhythmic_window_end_s: float
    first_downbeat_beat_index: int
    downbeat_times: list[float]
    bar_start_times: list[float]
    bar_count: int
    beat_grid: list[dict]
    bars: list[dict]
    bar_aligned_chords: list[dict]
    candidate_meters: list[dict]
    diagnostics: list[str]


def prepare_wav(source: Path, folder: Path) -> Path:
    target = folder / "structure_input.wav"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vn", "-ac", "1", "-ar", "22050", "-sample_fmt", "s16",
        str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        detail = (completed.stderr or completed.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(f"Could not prepare rhythm-analysis audio: {detail[-900:]}")
    return target


def robust_normalise(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = max(1e-8, 1.4826 * mad)
    return np.clip((values - median) / scale, -4.0, 4.0)


def beat_accent_values(y: np.ndarray, sr: int, beat_times: list[float]) -> np.ndarray:
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    frame_times = librosa.frames_to_time(np.arange(len(onset)), sr=sr)
    accents: list[float] = []
    half_window = 0.09
    for beat_time in beat_times:
        mask = (frame_times >= beat_time - half_window) & (frame_times <= beat_time + half_window)
        if np.any(mask):
            accents.append(float(np.max(onset[mask])))
        else:
            accents.append(0.0)
    return robust_normalise(np.asarray(accents, dtype=float))


def periodic_support(accents: np.ndarray, beats_per_bar: int) -> float:
    if len(accents) <= beats_per_bar * 3:
        return 0.0
    left = accents[:-beats_per_bar]
    right = accents[beats_per_bar:]
    if np.std(left) < 1e-8 or np.std(right) < 1e-8:
        return 0.0
    correlation = float(np.corrcoef(left, right)[0, 1])
    if not math.isfinite(correlation):
        return 0.0
    return max(-1.0, min(1.0, correlation))


def score_candidate(accents: np.ndarray, beats_per_bar: int, phase: int) -> float:
    indices = np.arange(len(accents))
    down_mask = ((indices - phase) % beats_per_bar) == 0
    if np.sum(down_mask) < 3 or np.sum(~down_mask) < 3:
        return -999.0
    down = accents[down_mask]
    other = accents[~down_mask]
    contrast = float(np.mean(down) - np.mean(other))
    consistency = -float(np.std(down)) * 0.10
    periodicity = periodic_support(accents, beats_per_bar) * 0.35
    return contrast + consistency + periodicity


def softmax_confidences(scores: list[float]) -> list[float]:
    finite = np.asarray([score if math.isfinite(score) else -999.0 for score in scores], dtype=float)
    shifted = finite - np.max(finite)
    weights = np.exp(np.clip(shifted * 1.7, -50.0, 50.0))
    total = float(np.sum(weights))
    return (weights / total).tolist() if total > 0 else [0.0] * len(scores)



def select_strongest_rhythmic_window(
    accents: np.ndarray,
    beat_times: list[float],
    window_beats: int = RHYTHMIC_WINDOW_BEATS,
) -> tuple[np.ndarray, int, int, float, float]:
    values = np.asarray(accents, dtype=float)
    if values.size == 0:
        raise RuntimeError("No beat accents were available for meter analysis.")
    window = min(max(24, int(window_beats)), len(values))
    if len(values) <= window:
        start, end = 0, len(values)
    else:
        best_score = -float("inf")
        start, end = 0, window
        for candidate_start in range(0, len(values) - window + 1):
            candidate_end = candidate_start + window
            section = values[candidate_start:candidate_end]
            score = (
                float(np.mean(np.abs(section)))
                + 0.55 * float(np.std(section))
                + 0.35 * float(np.mean(np.maximum(section, 0.0)))
            )
            if score > best_score:
                best_score = score
                start, end = candidate_start, candidate_end
    start_s = float(beat_times[start])
    end_s = float(beat_times[min(end - 1, len(beat_times)-1)])
    return values[start:end], start, end, start_s, end_s

def infer_meter(accents: np.ndarray) -> tuple[MeterCandidate, list[MeterCandidate]]:
    raw: list[tuple[int, str, int, float]] = []
    for beats_per_bar, label in SUPPORTED_METERS:
        for phase in range(beats_per_bar):
            raw.append((beats_per_bar, label, phase, score_candidate(accents, beats_per_bar, phase)))

    confidences = softmax_confidences([item[3] for item in raw])
    candidates = [
        MeterCandidate(
            meter=label,
            beats_per_bar=beats_per_bar,
            phase=phase,
            score=round(score, 6),
            confidence=round(confidence, 6),
        )
        for (beats_per_bar, label, phase, score), confidence in zip(raw, confidences)
    ]
    candidates.sort(key=lambda item: item.score, reverse=True)

    best = candidates[0]
    second = candidates[1]
    margin = max(0.0, best.score - second.score)
    evidence = min(1.0, max(0.0, (best.score + 0.5) / 2.0))
    confidence = min(0.99, max(0.05, 0.45 * best.confidence + 0.35 * min(1.0, margin) + 0.20 * evidence))
    best = MeterCandidate(best.meter, best.beats_per_bar, best.phase, best.score, round(confidence, 6))
    return best, candidates


def chord_at_time(segments: list[dict], moment: float) -> str:
    for segment in segments:
        try:
            start = float(segment.get("start_s", 0.0))
            end = float(segment.get("end_s", 0.0))
        except (TypeError, ValueError):
            continue
        if start <= moment < end:
            return str(segment.get("chord") or "N")
    return "N"


def build_bar_grid(
    beat_times: list[float],
    beats_per_bar: int,
    phase: int,
    segments: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[float]]:
    beat_grid: list[dict] = []
    for index, beat_time in enumerate(beat_times):
        relative = index - phase
        if relative < 0:
            bar_number = 0
            beat_in_bar = relative
        else:
            bar_number = relative // beats_per_bar + 1
            beat_in_bar = relative % beats_per_bar + 1
        beat_grid.append({
            "beat_index": index,
            "time_s": round(float(beat_time), 6),
            "bar_number": bar_number,
            "beat_in_bar": beat_in_bar,
            "is_downbeat": relative >= 0 and beat_in_bar == 1,
        })

    valid = [item for item in beat_grid if item["bar_number"] >= 1]
    bar_numbers = sorted({int(item["bar_number"]) for item in valid})
    bars: list[dict] = []
    downbeats: list[float] = []
    aligned: list[dict] = []

    for bar_number in bar_numbers:
        beats = [item for item in valid if item["bar_number"] == bar_number]
        if not beats:
            continue
        start_s = float(beats[0]["time_s"])
        next_bar = next((item for item in valid if item["bar_number"] == bar_number + 1 and item["beat_in_bar"] == 1), None)
        end_s = float(next_bar["time_s"]) if next_bar else (
            float(beat_times[-1]) + (float(np.median(np.diff(beat_times))) if len(beat_times) > 1 else 0.5)
        )
        downbeats.append(start_s)

        beat_chords = []
        for beat in beats:
            chord = chord_at_time(segments, float(beat["time_s"]))
            beat_chords.append({
                "beat_in_bar": int(beat["beat_in_bar"]),
                "time_s": float(beat["time_s"]),
                "chord": chord,
            })

        compressed: list[str] = []
        for item in beat_chords:
            if not compressed or compressed[-1] != item["chord"]:
                compressed.append(item["chord"])

        bars.append({
            "bar_number": bar_number,
            "start_s": round(start_s, 6),
            "end_s": round(end_s, 6),
            "beats_present": len(beats),
            "beat_chords": beat_chords,
        })
        aligned.append({
            "bar_number": bar_number,
            "start_s": round(start_s, 6),
            "end_s": round(end_s, 6),
            "chords": compressed,
            "display": " | ".join(compressed) if compressed else "N",
        })

    return beat_grid, bars, aligned, downbeats




ALTERNATIVE_BEAT_METHODS = {
    "standard": "Standard full mix",
    "percussive": "Percussion focused",
    "low_frequency": "Low-frequency rhythm",
    "steady_pulse": "Steady slow pulse",
}


def _tempo_value(value) -> float:
    array = np.asarray(value, dtype=float).reshape(-1)
    return float(array[0]) if array.size else 0.0


def _beat_track_from_audio(y: np.ndarray, sr: int, *, start_bpm: float = 90.0, tightness: float = 100.0) -> tuple[float, list[float]]:
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, frames = librosa.beat.beat_track(
        onset_envelope=onset,
        sr=sr,
        start_bpm=start_bpm,
        tightness=tightness,
        trim=False,
    )
    times = librosa.frames_to_time(np.asarray(frames), sr=sr)
    return _tempo_value(tempo), [round(float(v), 6) for v in times]


def _steady_regular_grid(y: np.ndarray, sr: int) -> tuple[float, list[float]]:
    """Build a genuinely regular slower pulse from the onset autocorrelation."""
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    if onset.size < 16:
        raise RuntimeError("Too little rhythmic evidence for the steady-pulse grid.")
    tempo_candidates = np.asarray(
        librosa.feature.tempo(onset_envelope=onset, sr=sr, aggregate=None),
        dtype=float,
    )
    tempo_candidates = tempo_candidates[np.isfinite(tempo_candidates)]
    tempo_candidates = tempo_candidates[(tempo_candidates >= 45.0) & (tempo_candidates <= 115.0)]
    bpm = float(np.median(tempo_candidates)) if tempo_candidates.size else 75.0
    interval = 60.0 / max(45.0, min(115.0, bpm))
    frame_times = librosa.frames_to_time(np.arange(len(onset)), sr=sr)
    duration = len(y) / sr
    phases = np.linspace(0.0, interval, 48, endpoint=False)
    best_phase = 0.0
    best_score = -1.0
    for phase in phases:
        grid = np.arange(phase, duration, interval)
        indices = np.searchsorted(frame_times, grid)
        indices = np.clip(indices, 0, len(onset)-1)
        score = float(np.mean(onset[indices])) if indices.size else 0.0
        if score > best_score:
            best_score = score; best_phase = float(phase)
    times = [round(float(v),6) for v in np.arange(best_phase, duration, interval)]
    return 60.0/interval, times


def generate_alternative_beat_grids(audio_path: Path, status_callback=lambda _text: None) -> dict[str, dict]:
    """Generate genuinely different beat timestamps from the original audio."""
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_alt_beats_") as temporary:
        wav = prepare_wav(audio_path, Path(temporary))
        y, sr = librosa.load(wav, sr=22050, mono=True, duration=AUDIBLE_PREVIEW_SECONDS)
        if y is None or len(y) == 0:
            raise RuntimeError("Alternative beat-grid audio was empty.")

        candidates: dict[str, dict] = {}
        status_callback("Creating standard full-mix beat grid…")
        bpm, times = _beat_track_from_audio(y, sr, start_bpm=90.0, tightness=100.0)
        candidates["standard"] = {"label": ALTERNATIVE_BEAT_METHODS["standard"], "bpm": bpm, "beat_times": times}

        status_callback("Creating percussion-focused beat grid…")
        _, percussion = librosa.effects.hpss(y)
        bpm, times = _beat_track_from_audio(percussion, sr, start_bpm=90.0, tightness=80.0)
        candidates["percussive"] = {"label": ALTERNATIVE_BEAT_METHODS["percussive"], "bpm": bpm, "beat_times": times}

        status_callback("Creating low-frequency rhythm grid…")
        sos = scipy.signal.butter(6, [35.0, 320.0], btype="bandpass", fs=sr, output="sos")
        low = scipy.signal.sosfiltfilt(sos, y).astype(np.float32)
        bpm, times = _beat_track_from_audio(low, sr, start_bpm=80.0, tightness=70.0)
        candidates["low_frequency"] = {"label": ALTERNATIVE_BEAT_METHODS["low_frequency"], "bpm": bpm, "beat_times": times}

        status_callback("Creating steady slower pulse grid…")
        bpm, times = _steady_regular_grid(y, sr)
        candidates["steady_pulse"] = {"label": ALTERNATIVE_BEAT_METHODS["steady_pulse"], "bpm": bpm, "beat_times": times}

    for key, value in candidates.items():
        if len(value["beat_times"]) < 8:
            raise RuntimeError(f"{value['label']} produced too few beats.")
    return candidates



def _normalise_vector(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return array
    lo = float(np.percentile(array, 10.0))
    hi = float(np.percentile(array, 95.0))
    if hi <= lo + 1e-9:
        return np.zeros_like(array)
    return np.clip((array - lo) / (hi - lo), 0.0, 1.0)


def _nearest_frame_strength(envelope: np.ndarray, frame_times: np.ndarray, times: list[float]) -> np.ndarray:
    if envelope.size == 0 or not times:
        return np.zeros(0, dtype=float)
    indices = np.searchsorted(frame_times, np.asarray(times, dtype=float))
    indices = np.clip(indices, 0, len(envelope) - 1)
    left = np.clip(indices - 1, 0, len(envelope) - 1)
    choose_left = np.abs(frame_times[left] - np.asarray(times)) < np.abs(frame_times[indices] - np.asarray(times))
    indices = np.where(choose_left, left, indices)
    return envelope[indices]


def score_timing_candidates(
    candidates: dict[str, dict],
    full_onset: np.ndarray,
    low_onset: np.ndarray,
    frame_times: np.ndarray,
    chord_change_times: list[float],
) -> list[dict]:
    """Score 3/4 and 4/4 phase choices without changing saved timing."""
    rows: list[dict] = []
    full = _normalise_vector(full_onset)
    low = _normalise_vector(low_onset)
    for method, candidate in candidates.items():
        if not isinstance(candidate, dict):
            continue
        beats = [float(v) for v in candidate.get("beat_times", []) if isinstance(v, (int, float))]
        if len(beats) < 12:
            continue
        intervals = np.diff(np.asarray(beats, dtype=float))
        median_interval = float(np.median(intervals))
        if median_interval <= 0:
            continue
        cv = float(np.std(intervals) / max(1e-6, np.mean(intervals)))
        stability = max(0.0, 1.0 - min(1.0, cv / 0.22))
        full_strength = _nearest_frame_strength(full, frame_times, beats)
        low_strength = _nearest_frame_strength(low, frame_times, beats)
        method_strength = 0.55 * full_strength + 0.45 * low_strength
        beat_support = float(np.mean(method_strength)) if method_strength.size else 0.0
        chord_proximity = 0.0
        if chord_change_times:
            distances = []
            beat_array = np.asarray(beats)
            for change in chord_change_times:
                idx = int(np.argmin(np.abs(beat_array - change)))
                distances.append(abs(float(beat_array[idx]) - float(change)))
            chord_proximity = float(np.mean([max(0.0, 1.0 - d / max(0.12, median_interval * 0.55)) for d in distances]))
        for beats_per_bar, meter in ((3, "3/4"), (4, "4/4")):
            for phase in range(beats_per_bar):
                down = method_strength[phase::beats_per_bar]
                other_parts = [method_strength[offset::beats_per_bar] for offset in range(beats_per_bar) if offset != phase]
                other = np.concatenate(other_parts) if other_parts else np.zeros(0)
                accent = float(np.mean(down) - np.mean(other)) if down.size and other.size else 0.0
                accent_score = max(0.0, min(1.0, 0.5 + accent * 1.8))
                downbeat_chord = 0.0
                if chord_change_times:
                    downbeats = np.asarray(beats[phase::beats_per_bar])
                    vals = []
                    for change in chord_change_times:
                        if downbeats.size:
                            d = float(np.min(np.abs(downbeats - change)))
                            vals.append(max(0.0, 1.0 - d / max(0.15, median_interval * 0.75)))
                    downbeat_chord = float(np.mean(vals)) if vals else 0.0
                meter_prior = 0.52 if meter == "4/4" else 0.48
                total = (
                    0.25 * stability
                    + 0.25 * beat_support
                    + 0.18 * chord_proximity
                    + 0.22 * accent_score
                    + 0.08 * downbeat_chord
                    + 0.02 * meter_prior
                )
                rows.append({
                    "method": str(method),
                    "label": str(candidate.get("label") or method),
                    "meter": meter,
                    "phase_number": phase + 1,
                    "score": round(float(total), 6),
                    "stability": round(stability, 6),
                    "beat_support": round(beat_support, 6),
                    "chord_proximity": round(chord_proximity, 6),
                    "accent_score": round(accent_score, 6),
                    "downbeat_chord_support": round(downbeat_chord, 6),
                    "bpm": round(float(candidate.get("bpm") or 60.0 / median_interval), 3),
                })
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def recommend_timing_structure(
    audio_path: Path,
    candidates: dict[str, dict],
    chord_segments: list[dict],
) -> dict:
    """Recommend meter, beat-grid method and downbeat phase from audio evidence."""
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_recommend_019_") as temporary:
        wav = prepare_wav(audio_path, Path(temporary))
        y, sr = librosa.load(wav, sr=22050, mono=True, duration=AUDIBLE_PREVIEW_SECONDS)
        if y is None or len(y) == 0:
            raise RuntimeError("Recommendation audio was empty.")
        full_onset = librosa.onset.onset_strength(y=y, sr=sr)
        sos = scipy.signal.butter(6, [35.0, 320.0], btype="bandpass", fs=sr, output="sos")
        low_audio = scipy.signal.sosfiltfilt(sos, y).astype(np.float32)
        low_onset = librosa.onset.onset_strength(y=low_audio, sr=sr)
        frame_times = librosa.frames_to_time(np.arange(len(full_onset)), sr=sr)
    changes = sorted({
        float(item.get("start_s"))
        for item in chord_segments
        if isinstance(item, dict)
        and isinstance(item.get("start_s"), (int, float))
        and float(item.get("start_s")) > 0.05
        and float(item.get("start_s")) <= AUDIBLE_PREVIEW_SECONDS
    })
    ranked = score_timing_candidates(candidates, full_onset, low_onset, frame_times, changes)
    if not ranked:
        raise RuntimeError("No timing candidate could be scored.")
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else best
    margin = max(0.0, float(best["score"]) - float(runner["score"]))
    confidence = min(95.0, max(20.0, 45.0 + best["score"] * 35.0 + margin * 220.0))
    return {
        "recommended_meter": best["meter"],
        "recommended_beat_grid_method": best["method"],
        "recommended_beat_grid_label": best["label"],
        "recommended_phase_number": best["phase_number"],
        "recommended_bpm": best["bpm"],
        "confidence_percent": round(confidence, 1),
        "winning_score": best["score"],
        "runner_up_score": runner["score"],
        "score_margin": round(margin, 6),
        "ranked_candidates": ranked[:12],
        "recommendation_applied": False,
    }


def create_audible_beat_grid_check(audio_path: Path, beat_times: list[float], target: Path, preview_seconds: float = AUDIBLE_PREVIEW_SECONDS) -> Path:
    """Create an audio proof with one identical click per candidate beat."""
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_alt_clicks_") as temporary:
        wav = prepare_wav(audio_path, Path(temporary))
        y, sr = librosa.load(wav, sr=22050, mono=True, duration=preview_seconds)
        duration = len(y) / sr
        times = np.asarray([v for v in beat_times if 0.0 <= float(v) < duration], dtype=float)
        clicks = librosa.clicks(times=times, sr=sr, click_freq=1050.0, click_duration=0.045, length=len(y)).astype(np.float32)
        mixed = y.astype(np.float32) * 0.84 + clicks * 0.30
        peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
        if peak > 0.98: mixed = mixed / (peak / 0.98)
        target.parent.mkdir(parents=True, exist_ok=True)
        working = target.with_name(target.stem + '.working' + target.suffix)
        import soundfile as sf
        sf.write(working, mixed, sr, subtype='PCM_16')
        if not working.is_file() or working.stat().st_size == 0:
            raise RuntimeError('Alternative beat-grid WAV was not created.')
        working.replace(target)
    return target

def create_audible_bar_check(
    audio_path: Path,
    beat_times: list[float],
    downbeat_times: list[float],
    target: Path,
    preview_seconds: float = AUDIBLE_PREVIEW_SECONDS,
) -> Path:
    """Create a listening proof from any supported media container.

    M4A and MP4 are first converted to PCM WAV through the bundled FFmpeg route.
    Librosa never opens the original compressed container directly.
    """
    ensure_scipy_signal_compatibility()

    with tempfile.TemporaryDirectory(prefix="banjofy_audible_check_") as temporary_folder:
        wav_source = prepare_wav(audio_path, Path(temporary_folder))
        y, sr = librosa.load(
            wav_source,
            sr=22050,
            mono=True,
            duration=preview_seconds,
        )
        if y is None or len(y) == 0:
            raise RuntimeError(
                "Could not create the audible bar check because the converted audio was empty."
            )

        duration = len(y) / sr
        ordinary_times = np.asarray(
            [value for value in beat_times if 0.0 <= value < duration],
            dtype=float,
        )
        strong_times = np.asarray(
            [value for value in downbeat_times if 0.0 <= value < duration],
            dtype=float,
        )

        beat_clicks = librosa.clicks(
            times=ordinary_times,
            sr=sr,
            click_freq=1200.0,
            click_duration=0.035,
            length=len(y),
        ).astype(np.float32)
        downbeat_clicks = librosa.clicks(
            times=strong_times,
            sr=sr,
            click_freq=320.0,
            click_duration=0.10,
            length=len(y),
        ).astype(np.float32)

        audio = y.astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0.95:
            audio = audio / (peak / 0.95)

        mixed = audio * 0.82 + beat_clicks * 0.18 + downbeat_clicks * 0.42
        mixed_peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
        if mixed_peak > 0.98:
            mixed = mixed / (mixed_peak / 0.98)

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.stem + ".working" + target.suffix)
        temporary.unlink(missing_ok=True)

        import soundfile as sf
        sf.write(temporary, mixed, sr, subtype="PCM_16")
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("The audible bar-check file was not created.")
        temporary.replace(target)

    return target


def choose_primary_meter(
    full_best: MeterCandidate,
    rhythmic_best: MeterCandidate,
) -> tuple[MeterCandidate, bool]:
    """Keep the whole-track candidate primary.

    A short rhythmic window may support the whole-track result, but it cannot
    overturn it. Disagreement is recorded and leaves the result uncertain.
    """
    agreement = full_best.meter == rhythmic_best.meter
    return full_best, agreement

def analyse_structure(audio_path: Path, chord_segments: list[dict], status_callback) -> StructureResult:
    ensure_scipy_signal_compatibility()
    diagnostics = [
        "Metre is estimated from recurring beat-level accent patterns.",
        "Supported candidates in this laboratory are 3/4 and 4/4 only.",
        "Downbeats are estimates and must be checked on real songs before Practice integration.",
        "The whole-track candidate remains primary; a short rhythmic window cannot overturn it.",
    ]

    with tempfile.TemporaryDirectory(prefix="banjofy_structure_002_") as temporary:
        status_callback("Preparing rhythm-analysis audio...")
        wav = prepare_wav(audio_path, Path(temporary))

        status_callback("Detecting the musical pulse and beat positions...")
        y, sr = librosa.load(wav, sr=22050, mono=True)
        if y is None or len(y) == 0:
            raise RuntimeError("Rhythm-analysis audio was empty.")

        tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
        bpm = float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 0.0
        beat_times = [float(value) for value in librosa.frames_to_time(frames, sr=sr).tolist()]
        if bpm <= 0.0 or len(beat_times) < 12:
            raise RuntimeError("Not enough dependable beats were detected to estimate bars.")

        status_callback("Measuring accents at each detected beat...")
        accents = beat_accent_values(y, sr, beat_times)

        status_callback("Comparing 3/4 and 4/4 across the full track...")
        full_best, full_candidates = infer_meter(accents)

        status_callback("Finding the strongest rhythmic section for confidence...")
        rhythmic_accents, rhythmic_start, rhythmic_end, rhythmic_start_s, rhythmic_end_s = (
            select_strongest_rhythmic_window(accents, beat_times)
        )
        status_callback("Comparing 3/4 and 4/4 in the strongest rhythmic section...")
        rhythmic_best, rhythmic_candidates = infer_meter(rhythmic_accents)

        status_callback("Keeping the whole-track meter as the primary candidate...")
        best, meter_candidate_agreement = choose_primary_meter(full_best, rhythmic_best)

        status_callback("Numbering beats and constructing estimated bars...")
        beat_grid, bars, aligned, downbeats = build_bar_grid(
            beat_times, best.beats_per_bar, best.phase, chord_segments
        )
        if len(bars) < 3:
            raise RuntimeError("Too few complete bars were available for a useful structure result.")

        meter_status = (
            "confirmed"
            if (
                meter_candidate_agreement
                and best.confidence >= METER_CONFIDENCE_THRESHOLD
                and rhythmic_best.confidence >= METER_CONFIDENCE_THRESHOLD
            )
            else "uncertain"
        )
        reported_meter = best.meter if meter_status == "confirmed" else "Uncertain"

        return StructureResult(
            structure_version=STRUCTURE_VERSION,
            source_audio=str(audio_path),
            raw_bpm=round(bpm, 6),
            beat_times=[round(value, 6) for value in beat_times],
            beat_count=len(beat_times),
            meter=reported_meter,
            meter_status=meter_status,
            best_meter_candidate=best.meter,
            beats_per_bar=best.beats_per_bar,
            meter_confidence=full_best.confidence,
            full_track_meter_confidence=full_best.confidence,
            rhythmic_window_candidate=rhythmic_best.meter,
            rhythmic_window_meter_confidence=rhythmic_best.confidence,
            meter_candidate_agreement=meter_candidate_agreement,
            rhythmic_window_start_beat=rhythmic_start,
            rhythmic_window_end_beat=rhythmic_end,
            rhythmic_window_start_s=round(rhythmic_start_s, 6),
            rhythmic_window_end_s=round(rhythmic_end_s, 6),
            first_downbeat_beat_index=best.phase,
            downbeat_times=[round(value, 6) for value in downbeats],
            bar_start_times=[round(value, 6) for value in downbeats],
            bar_count=len(bars),
            beat_grid=beat_grid,
            bars=bars,
            bar_aligned_chords=aligned,
            candidate_meters=[asdict(item) for item in full_candidates],
            diagnostics=diagnostics,
        )
