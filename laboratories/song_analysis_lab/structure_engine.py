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


def _phase_pattern_metrics(
    strengths: np.ndarray,
    beats_per_bar: int,
    phase: int,
) -> tuple[float, float, float, list[float]]:
    """Measure repeating bar-position evidence without using chord changes.

    The candidate beat grid is rotated so *phase* is Beat 1. Complete bars are
    normalised individually, preventing one loud passage from dominating the
    whole recording. The returned values reward:

    - Beat 1 being stronger than the other bar positions.
    - The same accent ordering recurring from bar to bar.
    - Beat 1 rising from the preceding beat, useful when a phrase leads into ONE.
    """
    values = np.asarray(strengths, dtype=float)
    rotated = values[phase:]
    complete = (len(rotated) // beats_per_bar) * beats_per_bar
    if complete < beats_per_bar * 4:
        return 0.0, 0.0, 0.0, [0.0] * beats_per_bar

    bars = rotated[:complete].reshape(-1, beats_per_bar)
    lo = np.min(bars, axis=1, keepdims=True)
    hi = np.max(bars, axis=1, keepdims=True)
    normalised = np.divide(
        bars - lo,
        np.maximum(1e-9, hi - lo),
    )

    profile = np.median(normalised, axis=0)
    beat_one = normalised[:, 0]
    others = normalised[:, 1:].reshape(-1)

    contrast = float(np.median(beat_one) - np.median(others))
    contrast_score = max(0.0, min(1.0, 0.5 + contrast * 0.9))

    # How often Beat 1 is at least as strong as the average of the other beats.
    bar_wins = np.mean(
        beat_one >= np.mean(normalised[:, 1:], axis=1)
    )
    consistency_score = max(0.0, min(1.0, float(bar_wins)))

    # Reward a recurring lift into Beat 1 from the final beat of the prior bar.
    if len(normalised) > 1:
        rises = normalised[1:, 0] - normalised[:-1, -1]
        rise_score = max(
            0.0,
            min(1.0, 0.5 + float(np.median(rises)) * 0.8),
        )
    else:
        rise_score = 0.5

    return (
        contrast_score,
        consistency_score,
        rise_score,
        [round(float(value), 6) for value in profile.tolist()],
    )


def score_timing_candidates(
    candidates: dict[str, dict],
    full_onset: np.ndarray,
    low_onset: np.ndarray,
    frame_times: np.ndarray,
    chord_change_times: list[float],
) -> list[dict]:
    """Score 3/4 and 4/4 candidates using repeating rhythmic patterns.

    Build 020 deliberately does not use chord-change proximity to choose the
    downbeat phase. Chord changes may occur on any beat and are retained only
    as a weak beat-grid quality signal.
    """
    rows: list[dict] = []
    full = _normalise_vector(full_onset)
    low = _normalise_vector(low_onset)

    for method, candidate in candidates.items():
        if not isinstance(candidate, dict):
            continue

        beats = [
            float(value)
            for value in candidate.get("beat_times", [])
            if isinstance(value, (int, float))
        ]
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

        # Low-frequency rhythm is important for the underlying pulse, while the
        # full mix still contributes transient evidence.
        method_strength = 0.38 * full_strength + 0.62 * low_strength
        beat_support = (
            float(np.mean(method_strength))
            if method_strength.size
            else 0.0
        )

        # Chord changes contribute only to selecting a plausible beat grid.
        # They never decide which beat is Beat 1.
        chord_grid_support = 0.0
        if chord_change_times:
            beat_array = np.asarray(beats)
            support = []
            for change in chord_change_times:
                index = int(np.argmin(np.abs(beat_array - change)))
                distance = abs(float(beat_array[index]) - float(change))
                support.append(
                    max(
                        0.0,
                        1.0
                        - distance / max(0.12, median_interval * 0.55),
                    )
                )
            chord_grid_support = float(np.mean(support)) if support else 0.0

        for beats_per_bar, meter in ((3, "3/4"), (4, "4/4")):
            for phase in range(beats_per_bar):
                (
                    repeating_accent,
                    bar_consistency,
                    lead_in_rise,
                    bar_position_profile,
                ) = _phase_pattern_metrics(
                    method_strength,
                    beats_per_bar,
                    phase,
                )

                # A slight 4/4 prior remains, but repeating evidence dominates.
                meter_prior = 0.52 if meter == "4/4" else 0.48

                total = (
                    0.23 * stability
                    + 0.20 * beat_support
                    + 0.05 * chord_grid_support
                    + 0.27 * repeating_accent
                    + 0.18 * bar_consistency
                    + 0.05 * lead_in_rise
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
                    "chord_grid_support": round(chord_grid_support, 6),
                    "repeating_accent_score": round(repeating_accent, 6),
                    "bar_pattern_consistency": round(bar_consistency, 6),
                    "lead_in_rise_score": round(lead_in_rise, 6),
                    "bar_position_profile": bar_position_profile,
                    "phase_chord_weight": 0.0,
                    "bpm": round(
                        float(candidate.get("bpm") or 60.0 / median_interval),
                        3,
                    ),
                })

    return sorted(rows, key=lambda row: row["score"], reverse=True)


def recommend_timing_structure(
    audio_path: Path,
    candidates: dict[str, dict],
    chord_segments: list[dict],
) -> dict:
    """Recommend timing using repeating bar-accent evidence from the audio."""
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_recommend_020_") as temporary:
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




TRUTH_FIELD_ALIASES = {
    "meter": (
        "confirmed_meter",
        "manual_meter",
        "meter",
        "best_meter_candidate",
        "detected_meter_candidate",
    ),
    "beat_grid_method": (
        "confirmed_beat_grid_method",
        "confirmed_pulse_method",
        "pulse_interpretation",
        "beat_grid_method",
        "selected_beat_grid_method",
    ),
    "phase_number": (
        "confirmed_phase_number",
        "manual_phase_number",
        "downbeat_phase_number",
        "selected_phase_number",
        "phase_number",
    ),
    "phase_offset": (
        "confirmed_phase_offset",
        "downbeat_phase_offset",
        "phase_offset",
    ),
    "first_downbeat_beat_index": (
        "confirmed_first_downbeat_beat_index",
        "first_downbeat_beat_index",
        "detected_first_downbeat_beat_index",
    ),
}


def _walk_json_values(value, path: str = "$") -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            found.append((child_path, child))
            found.extend(_walk_json_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            found.extend(_walk_json_values(child, child_path))
    return found


def _normalise_truth_value(field: str, value):
    if value in (None, ""):
        return None
    if field == "meter":
        text = str(value).strip()
        return text if text in {"3/4", "4/4"} else None
    if field == "beat_grid_method":
        return _normalise_method_name(value)
    if field in {"phase_number", "phase_offset", "first_downbeat_beat_index"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return value


def _collect_truth_candidates(
    source_name: str,
    source_path: Path,
    payload: dict,
) -> list[dict]:
    rows: list[dict] = []
    aliases_to_field = {
        alias: field
        for field, aliases in TRUTH_FIELD_ALIASES.items()
        for alias in aliases
    }
    for json_path, value in _walk_json_values(payload):
        key = json_path.rsplit(".", 1)[-1]
        field = aliases_to_field.get(key)
        if not field:
            continue
        normalised = _normalise_truth_value(field, value)
        if normalised is None:
            continue
        rows.append({
            "field": field,
            "value": normalised,
            "raw_value": value,
            "source_name": source_name,
            "source_file": str(source_path),
            "json_path": json_path,
            "source_key": key,
        })
    return rows


def _priority(row: dict) -> tuple[int, int]:
    key = str(row.get("source_key") or "")
    path = str(row.get("json_path") or "")
    explicit = 0
    if key.startswith("confirmed_"):
        explicit = 100
    elif key.startswith("manual_"):
        explicit = 90
    elif "confirmed" in path:
        explicit = 80
    elif key in {"selected_phase_number", "selected_beat_grid_method"}:
        explicit = 70
    elif key in {"meter", "pulse_interpretation", "phase_number"}:
        explicit = 40
    elif key.startswith("detected_") or key.startswith("best_"):
        explicit = 10

    source_score = {
        "song_analysis.json": 30,
        "song_structure.json": 20,
        "library_record.json": 10,
    }.get(str(row.get("source_name")), 0)
    return explicit, source_score


def recover_manual_truth(
    record: dict,
    analysis: dict,
    structure: dict,
    song_title: str,
    record_path: Path,
    analysis_path: Path,
    structure_path: Path,
) -> dict:
    """Recover every known timing value and consolidate explicit manual truth."""
    candidates: list[dict] = []
    candidates.extend(
        _collect_truth_candidates(
            "library_record.json", record_path, record
        )
    )
    candidates.extend(
        _collect_truth_candidates(
            "song_analysis.json", analysis_path, analysis
        )
    )
    candidates.extend(
        _collect_truth_candidates(
            "song_structure.json", structure_path, structure
        )
    )

    grouped: dict[str, list[dict]] = {
        field: [] for field in TRUTH_FIELD_ALIASES
    }
    for row in candidates:
        grouped[row["field"]].append(row)

    selected: dict[str, object] = {}
    selected_sources: dict[str, dict] = {}
    conflicts: list[dict] = []

    for field, rows in grouped.items():
        ordered = sorted(rows, key=_priority, reverse=True)
        if ordered:
            winner = ordered[0]
            selected[field] = winner["value"]
            selected_sources[field] = winner

            unique_values = []
            for row in ordered:
                if row["value"] not in unique_values:
                    unique_values.append(row["value"])
            if len(unique_values) > 1:
                conflicts.append({
                    "field": field,
                    "selected_value": winner["value"],
                    "all_values": unique_values,
                    "candidates": ordered,
                })
        else:
            selected[field] = None

    # Derive phase number from confirmed first-downbeat index when an explicit
    # phase number is absent. This is deterministic within the active meter.
    derived = []
    if selected.get("phase_number") is None:
        meter = selected.get("meter")
        first_index = selected.get("first_downbeat_beat_index")
        detected_index = None
        for row in grouped.get("first_downbeat_beat_index", []):
            if row.get("source_key") == "detected_first_downbeat_beat_index":
                detected_index = int(row["value"])
                break
        beats_per_bar = 3 if meter == "3/4" else 4 if meter == "4/4" else None
        if (
            beats_per_bar
            and first_index is not None
            and detected_index is not None
        ):
            offset = (int(first_index) - int(detected_index)) % beats_per_bar
            selected["phase_number"] = offset + 1
            derived.append({
                "field": "phase_number",
                "value": offset + 1,
                "method": (
                    "(confirmed_first_downbeat_beat_index - "
                    "detected_first_downbeat_beat_index) modulo beats_per_bar + 1"
                ),
                "inputs": {
                    "confirmed_first_downbeat_beat_index": first_index,
                    "detected_first_downbeat_beat_index": detected_index,
                    "beats_per_bar": beats_per_bar,
                },
            })

    missing = [
        field
        for field in ("meter", "beat_grid_method", "phase_number")
        if selected.get(field) in (None, "")
    ]

    canonical = {
        "schema": "banjofy.manual_truth.v1",
        "laboratory_build": 22,
        "song_title": song_title,
        "meter": selected.get("meter"),
        "beat_grid_method": selected.get("beat_grid_method"),
        "phase_number": selected.get("phase_number"),
        "phase_offset": selected.get("phase_offset"),
        "first_downbeat_beat_index": selected.get(
            "first_downbeat_beat_index"
        ),
        "complete": not missing,
        "missing_fields": missing,
        "has_conflicts": bool(conflicts),
        "conflict_count": len(conflicts),
        "selected_sources": selected_sources,
        "derived_values": derived,
        "source_files": {
            "library_record": str(record_path),
            "song_analysis": str(analysis_path),
            "song_structure": str(structure_path),
        },
        "timing_data_changed": False,
        "scoring_weights_changed": False,
    }

    return {
        "canonical_record": canonical,
        "all_candidates": candidates,
        "grouped_candidates": grouped,
        "conflicts": conflicts,
        "missing_fields": missing,
        "derived_values": derived,
    }


def format_manual_truth_recovery(result: dict) -> str:
    canonical = result["canonical_record"]
    lines = [
        "BANJOFY SONG ANALYSIS LABORATORY 022",
        "MANUAL TRUTH RECOVERY REPORT",
        "",
        f"Song: {canonical.get('song_title')}",
        f"Meter: {canonical.get('meter')}",
        f"Beat-grid method: {canonical.get('beat_grid_method')}",
        f"Phase number: {canonical.get('phase_number')}",
        f"Complete: {'YES' if canonical.get('complete') else 'NO'}",
        f"Conflicts: {canonical.get('conflict_count')}",
        f"Missing fields: {', '.join(canonical.get('missing_fields') or []) or 'None'}",
        "Timing data changed: NO",
        "Scoring weights changed: NO",
        "",
        "SELECTED SOURCES",
    ]

    for field in (
        "meter",
        "beat_grid_method",
        "phase_number",
        "phase_offset",
        "first_downbeat_beat_index",
    ):
        source = (canonical.get("selected_sources") or {}).get(field)
        if source:
            lines.extend([
                f"{field}: {source.get('value')}",
                f"  file: {source.get('source_file')}",
                f"  JSON path: {source.get('json_path')}",
                f"  source key: {source.get('source_key')}",
            ])
        else:
            lines.append(f"{field}: no direct stored value found")

    if result.get("derived_values"):
        lines.extend(["", "DERIVED VALUES"])
        for item in result["derived_values"]:
            lines.append(
                f"{item.get('field')}: {item.get('value')} via {item.get('method')}"
            )
            lines.append(f"  inputs: {item.get('inputs')}")

    lines.extend(["", "CONFLICTS"])
    if not result.get("conflicts"):
        lines.append("None")
    else:
        for conflict in result["conflicts"]:
            lines.append(
                f"{conflict.get('field')}: selected "
                f"{conflict.get('selected_value')}; all values "
                f"{conflict.get('all_values')}"
            )
            for row in conflict.get("candidates", []):
                lines.append(
                    f"  {row.get('value')} — "
                    f"{row.get('source_file')} {row.get('json_path')}"
                )

    lines.extend(["", "ALL LOCATED VALUES"])
    for field, rows in result.get("grouped_candidates", {}).items():
        lines.append(f"{field}:")
        if not rows:
            lines.append("  none")
        for row in sorted(rows, key=_priority, reverse=True):
            lines.append(
                f"  {row.get('value')} — {row.get('source_file')} "
                f"{row.get('json_path')} ({row.get('source_key')})"
            )

    lines.extend([
        "",
        "INTERPRETATION",
        "The canonical record chooses explicit confirmed/manual values before",
        "generic or detected values. It does not modify the song analysis.",
        "",
    ])
    return "\n".join(lines)



VERIFIED_EXPLICIT_KEYS = {
    "meter": ("confirmed_meter",),
    "beat_grid_method": ("confirmed_beat_grid_method",),
    "phase_number": ("confirmed_phase_number",),
    "phase_offset": ("confirmed_phase_offset",),
    "first_downbeat_beat_index": ("confirmed_first_downbeat_beat_index",),
}


def _walk_explicit_truth(value, path: str = "$") -> list[tuple[str, object]]:
    """Walk JSON while excluding candidate/recommendation containers."""
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {
                "timing_recommendation",
                "ranked_candidates",
                "candidate_meters",
                "timing_candidates",
                "candidates",
            }:
                continue
            found.append((child_path, child))
            found.extend(_walk_explicit_truth(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_explicit_truth(child, f"{path}[{index}]"))
    return found


def _find_explicit_values(
    source_name: str,
    source_path: Path,
    payload: dict,
) -> list[dict]:
    key_to_field = {
        key: field
        for field, keys in VERIFIED_EXPLICIT_KEYS.items()
        for key in keys
    }
    rows = []
    for json_path, value in _walk_explicit_truth(payload):
        key = json_path.rsplit(".", 1)[-1]
        field = key_to_field.get(key)
        if not field:
            continue
        normalised = _normalise_truth_value(field, value)
        if normalised is None:
            continue
        rows.append({
            "field": field,
            "value": normalised,
            "source_name": source_name,
            "source_file": str(source_path),
            "json_path": json_path,
            "source_key": key,
        })
    return rows


def _first_explicit(rows: list[dict], field: str):
    matches = [row for row in rows if row["field"] == field]
    if not matches:
        return None, None
    source_order = {
        "song_analysis.json": 3,
        "song_structure.json": 2,
        "library_record.json": 1,
    }
    matches.sort(
        key=lambda row: source_order.get(row.get("source_name"), 0),
        reverse=True,
    )
    return matches[0]["value"], matches[0]


def recover_verified_truth(
    record: dict,
    analysis: dict,
    structure: dict,
    song_title: str,
    record_path: Path,
    analysis_path: Path,
    structure_path: Path,
) -> dict:
    """Recover only explicit confirmed values; never use scorer candidates."""
    rows = []
    rows.extend(_find_explicit_values("library_record.json", record_path, record))
    rows.extend(_find_explicit_values("song_analysis.json", analysis_path, analysis))
    rows.extend(_find_explicit_values("song_structure.json", structure_path, structure))

    meter, meter_source = _first_explicit(rows, "meter")
    grid, grid_source = _first_explicit(rows, "beat_grid_method")
    phase, phase_source = _first_explicit(rows, "phase_number")
    phase_offset, phase_offset_source = _first_explicit(rows, "phase_offset")
    first_downbeat, first_downbeat_source = _first_explicit(
        rows, "first_downbeat_beat_index"
    )

    notes = []
    if meter is None:
        # Historical Build 014 songs stored best meter but not confirmed_meter.
        # This is an inference and is labelled as such.
        inferred_meter = (
            analysis.get("best_meter_candidate")
            or structure.get("best_meter_candidate")
            or (record.get("structure_summary") or {}).get("best_meter_candidate")
        )
        inferred_meter = _normalise_truth_value("meter", inferred_meter)
        if inferred_meter:
            meter = inferred_meter
            notes.append(
                "Meter was inferred from best_meter_candidate because no "
                "confirmed_meter field exists."
            )

    if grid is None and phase is not None:
        grid = "standard"
        notes.append(
            "Beat-grid method was inferred as standard because this phase was "
            "confirmed before alternative beat-grid confirmation was introduced."
        )

    if phase is None:
        notes.append(
            "No explicit confirmed phase exists. A phase must be chosen manually."
        )

    source_label = lambda row: (
        f"{row['source_file']} {row['json_path']}" if row else None
    )

    canonical = {
        "schema": "banjofy.truth_review.v1",
        "laboratory_build": 23,
        "song_title": song_title,
        "meter": meter,
        "beat_grid_method": grid,
        "phase_number": phase,
        "phase_offset": phase_offset,
        "first_downbeat_beat_index": first_downbeat,
        "meter_source_label": source_label(meter_source),
        "beat_grid_source_label": source_label(grid_source),
        "phase_source_label": source_label(phase_source),
        "phase_offset_source_label": source_label(phase_offset_source),
        "first_downbeat_source_label": source_label(first_downbeat_source),
        "explicit_values": rows,
        "notes": notes,
        "timing_data_changed": False,
        "scoring_weights_changed": False,
    }
    return {"canonical_record": canonical}


def build_verified_truth_record(
    recovered: dict,
    meter: str,
    beat_grid_method: str,
    phase_number: int,
) -> dict:
    max_phase = 3 if meter == "3/4" else 4
    if meter not in {"3/4", "4/4"}:
        raise ValueError("Verified meter must be 3/4 or 4/4.")
    if beat_grid_method not in {
        "standard", "percussive", "low_frequency", "steady_pulse"
    }:
        raise ValueError("Unknown beat-grid method.")
    if not 1 <= int(phase_number) <= max_phase:
        raise ValueError("Verified phase does not match the meter.")

    return {
        "schema": "banjofy.manual_truth.v2",
        "laboratory_build": 23,
        "song_title": recovered.get("song_title"),
        "meter": meter,
        "beat_grid_method": beat_grid_method,
        "phase_number": int(phase_number),
        "verified_by_user": True,
        "complete": True,
        "source_review": {
            "meter_source": recovered.get("meter_source_label"),
            "beat_grid_source": recovered.get("beat_grid_source_label"),
            "phase_source": recovered.get("phase_source_label"),
            "notes": recovered.get("notes") or [],
        },
        "timing_data_changed": False,
        "scoring_weights_changed": False,
    }


def format_verified_truth_record(record: dict) -> str:
    lines = [
        "BANJOFY SONG ANALYSIS LABORATORY 023",
        "VERIFIED TIMING TRUTH",
        "",
        f"Song: {record.get('song_title')}",
        f"Meter: {record.get('meter')}",
        f"Beat-grid method: {record.get('beat_grid_method')}",
        f"Phase number: {record.get('phase_number')}",
        "Verified by user: YES",
        "Complete: YES",
        "Timing data changed: NO",
        "Scoring weights changed: NO",
        "",
        "SOURCE REVIEW",
    ]
    review = record.get("source_review") or {}
    lines.append(f"Meter source: {review.get('meter_source') or 'User confirmation'}")
    lines.append(
        f"Beat-grid source: {review.get('beat_grid_source') or 'User confirmation/inference'}"
    )
    lines.append(f"Phase source: {review.get('phase_source') or 'User confirmation'}")
    for note in review.get("notes") or []:
        lines.append(f"Note: {note}")
    lines.extend([
        "",
        "This file is the canonical validation truth for timing comparison.",
        "",
    ])
    return "\n".join(lines)



def _automatic_winner_from_analysis(analysis: dict) -> dict:
    recommendation = analysis.get("timing_recommendation") or {}
    winner = recommendation.get("automatic_winner")
    if isinstance(winner, dict):
        return dict(winner)
    ranked = recommendation.get("ranked_candidates") or []
    if isinstance(ranked, list) and ranked and isinstance(ranked[0], dict):
        return dict(ranked[0])
    raise ValueError("No automatic timing winner was found in song_analysis.json.")


def validate_automatic_timing(
    song_title: str,
    analysis: dict,
    truth: dict,
    analysis_path: Path,
    truth_path: Path,
) -> dict:
    if truth.get("schema") != "banjofy.manual_truth.v2":
        raise ValueError("manual_truth_023.json has the wrong schema.")
    if not truth.get("verified_by_user") or not truth.get("complete"):
        raise ValueError("The manual truth record is not complete and user verified.")

    winner = _automatic_winner_from_analysis(analysis)
    automatic = {
        "meter": _normalise_truth_value("meter", winner.get("meter")),
        "beat_grid_method": _normalise_method_name(
            winner.get("beat_grid_method") or winner.get("grid_method") or winner.get("method")
        ),
        "phase_number": _normalise_truth_value("phase_number", winner.get("phase_number")),
        "score": winner.get("score"),
    }
    verified = {
        "meter": _normalise_truth_value("meter", truth.get("meter")),
        "beat_grid_method": _normalise_method_name(truth.get("beat_grid_method")),
        "phase_number": _normalise_truth_value("phase_number", truth.get("phase_number")),
    }

    checks = {}
    for field in ("meter", "beat_grid_method", "phase_number"):
        passed = automatic[field] is not None and automatic[field] == verified[field]
        checks[field] = {
            "automatic": automatic[field],
            "verified": verified[field],
            "pass": passed,
            "result": "PASS" if passed else "FAIL",
        }

    overall = all(item["pass"] for item in checks.values())
    return {
        "schema": "banjofy.timing_validation.v1",
        "laboratory_build": 24,
        "song_title": song_title,
        "automatic": automatic,
        "verified_truth": verified,
        "checks": checks,
        "overall_pass": overall,
        "overall_result": "PASS" if overall else "FAIL",
        "analysis_file": str(analysis_path),
        "truth_file": str(truth_path),
        "scoring_model_changed": False,
        "scoring_weights_changed": False,
        "timing_data_changed": False,
    }


def format_timing_validation(result: dict) -> str:
    a = result["automatic"]
    v = result["verified_truth"]
    c = result["checks"]
    return "\n".join([
        "BANJOFY SONG ANALYSIS LABORATORY 024",
        "AUTOMATED TRUTH VALIDATION REPORT",
        "",
        f"Song: {result['song_title']}",
        "",
        "AUTOMATIC WINNER",
        f"Meter: {a['meter']}",
        f"Beat-grid method: {a['beat_grid_method']}",
        f"Phase number: {a['phase_number']}",
        f"Score: {a['score']}",
        "",
        "VERIFIED TRUTH",
        f"Meter: {v['meter']}",
        f"Beat-grid method: {v['beat_grid_method']}",
        f"Phase number: {v['phase_number']}",
        "",
        "VALIDATION",
        f"Meter: {c['meter']['result']} (automatic {c['meter']['automatic']} / verified {c['meter']['verified']})",
        f"Beat grid: {c['beat_grid_method']['result']} (automatic {c['beat_grid_method']['automatic']} / verified {c['beat_grid_method']['verified']})",
        f"Phase: {c['phase_number']['result']} (automatic {c['phase_number']['automatic']} / verified {c['phase_number']['verified']})",
        f"Overall: {result['overall_result']}",
        "",
        "Scoring model changed: NO",
        "Scoring weights changed: NO",
        "Timing data changed: NO",
        "",
    ])



def _candidate_grid(analysis: dict, method: str) -> dict:
    grids = analysis.get("alternative_beat_grids") or {}
    if not isinstance(grids, dict):
        raise ValueError("Alternative beat grids are missing.")
    candidate = grids.get(method)
    if not isinstance(candidate, dict):
        raise ValueError(f"Beat grid '{method}' is missing.")
    return candidate


def _phase_boundary_score(
    beat_times: list[float],
    chord_segments: list[dict],
    beats_per_bar: int,
    phase_number: int,
) -> dict:
    beats = np.asarray(
        [float(v) for v in beat_times if isinstance(v, (int, float))],
        dtype=float,
    )
    if beats.size < beats_per_bar * 4:
        return {
            "boundary_support": 0.0,
            "long_change_support": 0.0,
            "opening_anchor": 0.0,
            "changes_used": 0,
        }

    interval = float(np.median(np.diff(beats)))
    phase_index = int(phase_number) - 1
    rows = []

    clean_segments = [
        item for item in chord_segments
        if isinstance(item, dict)
        and isinstance(item.get("start_s"), (int, float))
    ]
    clean_segments.sort(key=lambda item: float(item.get("start_s", 0.0)))

    durations = []
    for index, item in enumerate(clean_segments):
        start = float(item.get("start_s", 0.0))
        if isinstance(item.get("end_s"), (int, float)):
            end = float(item["end_s"])
        elif index + 1 < len(clean_segments):
            end = float(clean_segments[index + 1].get("start_s", start))
        else:
            end = start + interval
        durations.append(max(interval * 0.25, end - start))
    median_duration = float(np.median(durations)) if durations else interval

    for index, item in enumerate(clean_segments):
        change = float(item.get("start_s", 0.0))
        if change <= 0.05 or change < beats[0] - interval or change > beats[-1] + interval:
            continue
        nearest = int(np.argmin(np.abs(beats - change)))
        distance = abs(float(beats[nearest]) - change)
        proximity = max(0.0, 1.0 - distance / max(0.12, interval * 0.55))
        is_downbeat = (nearest % beats_per_bar) == phase_index
        duration_weight = min(2.0, max(0.5, durations[index] / max(interval, median_duration)))
        rows.append({
            "proximity": proximity,
            "downbeat": 1.0 if is_downbeat else 0.0,
            "duration_weight": duration_weight,
            "change": change,
            "nearest_beat_index": nearest,
        })

    if not rows:
        return {
            "boundary_support": 0.0,
            "long_change_support": 0.0,
            "opening_anchor": 0.0,
            "changes_used": 0,
        }

    weighted_total = sum(r["proximity"] * r["duration_weight"] for r in rows)
    weighted_hits = sum(
        r["proximity"] * r["duration_weight"] * r["downbeat"] for r in rows
    )
    boundary_support = weighted_hits / max(1e-9, weighted_total)

    long_rows = [r for r in rows if r["duration_weight"] >= 1.0]
    if long_rows:
        long_total = sum(r["proximity"] * r["duration_weight"] for r in long_rows)
        long_hits = sum(
            r["proximity"] * r["duration_weight"] * r["downbeat"]
            for r in long_rows
        )
        long_support = long_hits / max(1e-9, long_total)
    else:
        long_support = boundary_support

    first = rows[0]
    opening_anchor = first["proximity"] * first["downbeat"]

    return {
        "boundary_support": round(float(boundary_support), 6),
        "long_change_support": round(float(long_support), 6),
        "opening_anchor": round(float(opening_anchor), 6),
        "changes_used": len(rows),
    }


def test_phase_challenger(
    song_title: str,
    analysis: dict,
    truth: dict,
    analysis_path: Path,
    truth_path: Path,
) -> dict:
    """Test a phase-only challenger while freezing meter and beat-grid choice."""
    if truth.get("schema") != "banjofy.manual_truth.v2":
        raise ValueError("manual_truth_023.json has the wrong schema.")
    if not truth.get("verified_by_user") or not truth.get("complete"):
        raise ValueError("The verified truth is incomplete.")

    winner = _automatic_winner_from_analysis(analysis)
    meter = _normalise_truth_value("meter", winner.get("meter"))
    method = _normalise_method_name(
        winner.get("beat_grid_method")
        or winner.get("grid_method")
        or winner.get("method")
    )
    old_phase = _normalise_truth_value("phase_number", winner.get("phase_number"))
    if meter not in {"3/4", "4/4"} or not method or old_phase is None:
        raise ValueError("The automatic winner is incomplete.")

    beats_per_bar = 3 if meter == "3/4" else 4
    grid = _candidate_grid(analysis, method)
    beats = grid.get("beat_times") or []
    segments = analysis.get("segments") or []

    ranked = (
        (analysis.get("timing_recommendation") or {}).get("ranked_candidates")
        or []
    )
    phase_rows = [
        row for row in ranked
        if isinstance(row, dict)
        and row.get("meter") == meter
        and _normalise_method_name(row.get("method") or row.get("beat_grid_method")) == method
    ]
    old_scores = {
        int(row.get("phase_number")): float(row.get("score", 0.0))
        for row in phase_rows
        if isinstance(row.get("phase_number"), (int, float))
    }
    score_values = list(old_scores.values())
    lo = min(score_values) if score_values else 0.0
    hi = max(score_values) if score_values else 1.0

    candidates = []
    for phase in range(1, beats_per_bar + 1):
        harmonic = _phase_boundary_score(
            beats, segments, beats_per_bar, phase
        )
        raw_rhythm = old_scores.get(phase, lo)
        rhythm = 0.5 if hi <= lo + 1e-9 else (raw_rhythm - lo) / (hi - lo)

        # Phase-only challenger:
        # 72% harmonic boundary evidence, 28% frozen rhythmic phase evidence.
        harmonic_total = (
            0.58 * harmonic["boundary_support"]
            + 0.30 * harmonic["long_change_support"]
            + 0.12 * harmonic["opening_anchor"]
        )
        challenger_score = 0.72 * harmonic_total + 0.28 * rhythm
        candidates.append({
            "phase_number": phase,
            "challenger_score": round(float(challenger_score), 6),
            "harmonic_boundary_score": round(float(harmonic_total), 6),
            "rhythmic_phase_score": round(float(rhythm), 6),
            **harmonic,
        })

    candidates.sort(key=lambda row: row["challenger_score"], reverse=True)
    challenger_phase = int(candidates[0]["phase_number"])
    truth_phase = int(truth.get("phase_number"))

    old_pass = old_phase == truth_phase
    challenger_pass = challenger_phase == truth_phase

    return {
        "schema": "banjofy.phase_challenger.v1",
        "laboratory_build": 25,
        "song_title": song_title,
        "frozen_meter": meter,
        "frozen_beat_grid_method": method,
        "old_phase_number": old_phase,
        "challenger_phase_number": challenger_phase,
        "verified_phase_number": truth_phase,
        "old_phase_result": "PASS" if old_pass else "FAIL",
        "challenger_phase_result": "PASS" if challenger_pass else "FAIL",
        "improved": challenger_pass and not old_pass,
        "regressed": old_pass and not challenger_pass,
        "candidate_phases": candidates,
        "meter_changed": False,
        "beat_grid_changed": False,
        "scoring_model_applied": False,
        "timing_data_changed": False,
        "interpretation": (
            "The challenger uses chord-boundary alignment only to test phase. "
            "It does not change the frozen meter, beat grid, stored recommendation "
            "or song timing."
        ),
        "analysis_file": str(analysis_path),
        "truth_file": str(truth_path),
    }


def format_phase_challenger(result: dict) -> str:
    lines = [
        "BANJOFY SONG ANALYSIS LABORATORY 025",
        "PHASE CHALLENGER REPORT",
        "",
        f"Song: {result['song_title']}",
        f"Frozen meter: {result['frozen_meter']}",
        f"Frozen beat-grid method: {result['frozen_beat_grid_method']}",
        "",
        f"Old automatic phase: {result['old_phase_number']} — {result['old_phase_result']}",
        f"Challenger phase: {result['challenger_phase_number']} — {result['challenger_phase_result']}",
        f"Verified phase: {result['verified_phase_number']}",
        f"Improved: {'YES' if result['improved'] else 'NO'}",
        f"Regressed: {'YES' if result['regressed'] else 'NO'}",
        "",
        "PHASE CANDIDATES",
        "Rank | Phase | Challenger | Harmonic boundary | Rhythm | Boundary | Long changes | Opening | Changes used",
    ]
    for index, row in enumerate(result["candidate_phases"], start=1):
        lines.append(
            f"{index:>4} | {row['phase_number']:>5} | "
            f"{row['challenger_score']:.6f} | "
            f"{row['harmonic_boundary_score']:.6f} | "
            f"{row['rhythmic_phase_score']:.6f} | "
            f"{row['boundary_support']:.6f} | "
            f"{row['long_change_support']:.6f} | "
            f"{row['opening_anchor']:.6f} | "
            f"{row['changes_used']}"
        )
    lines.extend([
        "",
        "Meter changed: NO",
        "Beat grid changed: NO",
        "Stored recommendation changed: NO",
        "Timing data changed: NO",
        "",
        "INTERPRETATION",
        result["interpretation"],
        "",
    ])
    return "\n".join(lines)



TIMING_BENCHMARK_ENGINES = {
    "current_banjofy": "Current Banjofy saved winner",
    "librosa_full_mix_dp": "Librosa dynamic-programming full mix",
    "librosa_percussive_dp": "Librosa dynamic-programming percussion",
    "librosa_low_frequency_dp": "Librosa dynamic-programming low frequency",
    "librosa_plp": "Librosa predominant local pulse",
}


def _plp_grid(y: np.ndarray, sr: int) -> tuple[float, list[float]]:
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    pulse = librosa.beat.plp(onset_envelope=onset, sr=sr)
    peaks = scipy.signal.find_peaks(
        np.asarray(pulse, dtype=float),
        height=max(0.05, float(np.percentile(pulse, 70.0))),
        distance=max(1, int((60.0 / 180.0) * sr / 512)),
    )[0]
    times = librosa.frames_to_time(peaks, sr=sr)
    values = [round(float(v), 6) for v in times]
    if len(values) < 8:
        raise RuntimeError("Predominant local pulse produced too few beats.")
    intervals = np.diff(np.asarray(values, dtype=float))
    bpm = 60.0 / float(np.median(intervals))
    return round(float(bpm), 3), values


def _benchmark_generated_grids(audio_path: Path) -> dict[str, dict]:
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_benchmark_026_") as temporary:
        wav = prepare_wav(audio_path, Path(temporary))
        y, sr = librosa.load(wav, sr=22050, mono=True)
        if y is None or len(y) == 0:
            raise RuntimeError("Benchmark audio was empty.")

        grids = {}
        bpm, times = _beat_track_from_audio(y, sr, start_bpm=90.0, tightness=100.0)
        grids["librosa_full_mix_dp"] = {
            "label": TIMING_BENCHMARK_ENGINES["librosa_full_mix_dp"],
            "bpm": bpm,
            "beat_times": times,
        }

        _, percussion = librosa.effects.hpss(y)
        bpm, times = _beat_track_from_audio(percussion, sr, start_bpm=90.0, tightness=80.0)
        grids["librosa_percussive_dp"] = {
            "label": TIMING_BENCHMARK_ENGINES["librosa_percussive_dp"],
            "bpm": bpm,
            "beat_times": times,
        }

        sos = scipy.signal.butter(6, [35.0, 320.0], btype="bandpass", fs=sr, output="sos")
        low = scipy.signal.sosfiltfilt(sos, y).astype(np.float32)
        bpm, times = _beat_track_from_audio(low, sr, start_bpm=80.0, tightness=70.0)
        grids["librosa_low_frequency_dp"] = {
            "label": TIMING_BENCHMARK_ENGINES["librosa_low_frequency_dp"],
            "bpm": bpm,
            "beat_times": times,
        }

        bpm, times = _plp_grid(y, sr)
        grids["librosa_plp"] = {
            "label": TIMING_BENCHMARK_ENGINES["librosa_plp"],
            "bpm": bpm,
            "beat_times": times,
        }
    return grids


def _winner_for_single_grid(audio_path: Path, grid: dict, segments: list[dict]) -> dict:
    result = recommend_timing_structure(
        audio_path,
        {"benchmark_grid": grid},
        segments,
    )
    ranked = result.get("ranked_candidates") or []
    if not ranked:
        raise RuntimeError("Timing approach produced no ranked candidates.")
    return dict(ranked[0])


def _normalised_truth_for_benchmark(truth: dict) -> dict:
    return {
        "meter": _normalise_truth_value("meter", truth.get("meter")),
        "beat_grid_method": _normalise_method_name(truth.get("beat_grid_method")),
        "phase_number": _normalise_truth_value("phase_number", truth.get("phase_number")),
    }


def benchmark_library_timing_engines(
    songs: list[dict],
    progress_callback=lambda _text: None,
) -> dict:
    """Run complete timing approaches across every verified Library song."""
    results = []
    engine_totals = {
        key: {
            "engine": key,
            "label": label,
            "songs_tested": 0,
            "meter_matches": 0,
            "grid_matches": 0,
            "phase_matches": 0,
            "exact_matches": 0,
            "errors": 0,
        }
        for key, label in TIMING_BENCHMARK_ENGINES.items()
    }

    for index, song in enumerate(songs, start=1):
        title = str(song.get("title") or song.get("song_id") or f"Song {index}")
        progress_callback(f"[{index}/{len(songs)}] Benchmarking {title}")
        audio_path = Path(song["audio_path"])
        analysis_path = Path(song["analysis_path"])
        truth_path = analysis_path.parent / "manual_truth_023.json"
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        verified = _normalised_truth_for_benchmark(truth)
        segments = analysis.get("segments") or []

        song_rows = []

        # Existing saved Banjofy winner.
        try:
            existing = _automatic_winner_from_analysis(analysis)
            existing_method = _normalise_method_name(
                existing.get("beat_grid_method")
                or existing.get("method")
                or existing.get("grid_method")
            )
            row = {
                "engine": "current_banjofy",
                "label": TIMING_BENCHMARK_ENGINES["current_banjofy"],
                "meter": _normalise_truth_value("meter", existing.get("meter")),
                "beat_grid_method": existing_method,
                "phase_number": _normalise_truth_value("phase_number", existing.get("phase_number")),
                "bpm": existing.get("bpm"),
                "score": existing.get("score"),
            }
            song_rows.append(row)
        except Exception as exc:
            song_rows.append({
                "engine": "current_banjofy",
                "label": TIMING_BENCHMARK_ENGINES["current_banjofy"],
                "error": str(exc),
            })

        generated = _benchmark_generated_grids(audio_path)
        method_truth_map = {
            "librosa_full_mix_dp": "standard",
            "librosa_percussive_dp": "percussive",
            "librosa_low_frequency_dp": "low_frequency",
            "librosa_plp": "plp",
        }

        for engine_key, grid in generated.items():
            try:
                winner = _winner_for_single_grid(audio_path, grid, segments)
                song_rows.append({
                    "engine": engine_key,
                    "label": TIMING_BENCHMARK_ENGINES[engine_key],
                    "meter": _normalise_truth_value("meter", winner.get("meter")),
                    "beat_grid_method": method_truth_map[engine_key],
                    "phase_number": _normalise_truth_value("phase_number", winner.get("phase_number")),
                    "bpm": winner.get("bpm") or grid.get("bpm"),
                    "score": winner.get("score"),
                    "beat_count": len(grid.get("beat_times") or []),
                })
            except Exception as exc:
                song_rows.append({
                    "engine": engine_key,
                    "label": TIMING_BENCHMARK_ENGINES[engine_key],
                    "error": str(exc),
                })

        for row in song_rows:
            totals = engine_totals[row["engine"]]
            if row.get("error"):
                totals["errors"] += 1
                continue
            totals["songs_tested"] += 1
            meter_ok = row.get("meter") == verified["meter"]
            grid_ok = row.get("beat_grid_method") == verified["beat_grid_method"]
            phase_ok = row.get("phase_number") == verified["phase_number"]
            exact = meter_ok and grid_ok and phase_ok
            row["checks"] = {
                "meter": "PASS" if meter_ok else "FAIL",
                "beat_grid": "PASS" if grid_ok else "FAIL",
                "phase": "PASS" if phase_ok else "FAIL",
                "exact": "PASS" if exact else "FAIL",
            }
            totals["meter_matches"] += int(meter_ok)
            totals["grid_matches"] += int(grid_ok)
            totals["phase_matches"] += int(phase_ok)
            totals["exact_matches"] += int(exact)

        results.append({
            "song_title": title,
            "truth": verified,
            "engines": song_rows,
        })

    leaderboard = list(engine_totals.values())
    for row in leaderboard:
        tested = max(1, row["songs_tested"])
        row["meter_accuracy"] = round(row["meter_matches"] / tested, 4)
        row["grid_accuracy"] = round(row["grid_matches"] / tested, 4)
        row["phase_accuracy"] = round(row["phase_matches"] / tested, 4)
        row["exact_accuracy"] = round(row["exact_matches"] / tested, 4)
        row["ranking_score"] = round(
            0.25 * row["meter_accuracy"]
            + 0.25 * row["grid_accuracy"]
            + 0.25 * row["phase_accuracy"]
            + 0.25 * row["exact_accuracy"],
            6,
        )
    leaderboard.sort(
        key=lambda row: (
            row["ranking_score"],
            row["exact_matches"],
            row["phase_matches"],
            row["grid_matches"],
            row["meter_matches"],
        ),
        reverse=True,
    )

    return {
        "schema": "banjofy.timing_engine_benchmark.v1",
        "laboratory_build": 26,
        "verified_song_count": len(songs),
        "engines_compared": list(TIMING_BENCHMARK_ENGINES),
        "leaderboard": leaderboard,
        "songs": results,
        "song_data_changed": False,
        "stored_recommendations_changed": False,
        "benchmark_limitations": [
            "The current truth files verify meter, selected beat-grid family and phase.",
            "They do not yet contain timestamp-level beat and downbeat annotations.",
            "Therefore this first benchmark ranks structural correctness, not millisecond beat accuracy.",
            "BeatNet and madmom are not bundled in this Windows build because their current dependency and licensing constraints require a separate packaging decision.",
        ],
    }


def format_timing_engine_benchmark(result: dict) -> str:
    lines = [
        "BANJOFY SONG ANALYSIS LABORATORY 026",
        "LIBRARY TIMING ENGINE BENCHMARK",
        "",
        f"Verified songs tested: {result['verified_song_count']}",
        "",
        "LEADERBOARD",
        "Rank | Timing approach | Meter | Grid | Phase | Exact | Score | Errors",
    ]
    for index, row in enumerate(result["leaderboard"], start=1):
        total = max(1, row["songs_tested"])
        lines.append(
            f"{index:>4} | {row['label']} | "
            f"{row['meter_matches']}/{total} | "
            f"{row['grid_matches']}/{total} | "
            f"{row['phase_matches']}/{total} | "
            f"{row['exact_matches']}/{total} | "
            f"{row['ranking_score']:.4f} | {row['errors']}"
        )

    for song in result["songs"]:
        lines.extend([
            "",
            f"SONG: {song['song_title']}",
            (
                "Verified: "
                f"{song['truth']['meter']} · "
                f"{song['truth']['beat_grid_method']} · "
                f"Phase {song['truth']['phase_number']}"
            ),
        ])
        for row in song["engines"]:
            if row.get("error"):
                lines.append(f"- {row['label']}: ERROR — {row['error']}")
            else:
                checks = row["checks"]
                lines.append(
                    f"- {row['label']}: "
                    f"{row['meter']} · {row['beat_grid_method']} · "
                    f"Phase {row['phase_number']} | "
                    f"Meter {checks['meter']} | Grid {checks['beat_grid']} | "
                    f"Phase {checks['phase']} | Exact {checks['exact']}"
                )

    lines.extend([
        "",
        "LIMITATIONS",
    ])
    for item in result["benchmark_limitations"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "Song data changed: NO",
        "Stored recommendations changed: NO",
        "",
    ])
    return "\n".join(lines)


def _first_present(mapping_list: list[dict], keys: tuple[str, ...]):
    for mapping in mapping_list:
        if not isinstance(mapping, dict):
            continue
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _normalise_method_name(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "standard_grid": "standard",
        "standard_full_mix": "standard",
        "full_mix": "standard",
        "low_frequency_rhythm": "low_frequency",
        "low_frequency": "low_frequency",
        "percussion_focused": "percussive",
        "percussion": "percussive",
        "steady_slow_pulse": "steady_pulse",
        "steady": "steady_pulse",
    }
    return aliases.get(text, text)


def _saved_manual_truth(record: dict, analysis: dict) -> dict:
    summary = record.get("structure_summary")
    if not isinstance(summary, dict):
        summary = {}
    sources = [analysis, record, summary]

    meter = _first_present(sources, ("confirmed_meter", "manual_meter", "meter"))
    method = _first_present(
        sources,
        ("confirmed_beat_grid_method", "confirmed_pulse_method", "pulse_interpretation"),
    )
    phase = _first_present(
        sources,
        ("confirmed_phase_number", "manual_phase_number"),
    )

    try:
        phase_number = int(phase) if phase not in (None, "") else None
    except (TypeError, ValueError):
        phase_number = None

    meter_text = str(meter) if meter not in (None, "") else None
    method_text = _normalise_method_name(method)

    return {
        "meter": meter_text,
        "beat_grid_method": method_text,
        "phase_number": phase_number,
        "complete": (
            meter_text in {"3/4", "4/4"}
            and method_text is not None
            and phase_number is not None
        ),
        "source_fields": {
            "meter": meter,
            "beat_grid_method": method,
            "phase_number": phase,
        },
    }


def _component_difference(winner: dict, verified: dict) -> dict:
    keys = (
        "stability",
        "beat_support",
        "chord_grid_support",
        "repeating_accent_score",
        "bar_pattern_consistency",
        "lead_in_rise_score",
    )
    return {
        key: round(
            float(winner.get(key, 0.0)) - float(verified.get(key, 0.0)),
            6,
        )
        for key in keys
    }


def build_timing_evidence_report(
    audio_path: Path,
    candidates: dict[str, dict],
    chord_segments: list[dict],
    record: dict,
    analysis: dict,
    song_title: str,
) -> dict:
    """Run the unchanged Build 020 scoring and expose all evidence."""
    ensure_scipy_signal_compatibility()
    with tempfile.TemporaryDirectory(prefix="banjofy_evidence_021_") as temporary:
        wav = prepare_wav(audio_path, Path(temporary))
        y, sr = librosa.load(
            wav, sr=22050, mono=True, duration=AUDIBLE_PREVIEW_SECONDS
        )
        if y is None or len(y) == 0:
            raise RuntimeError("Evidence-report audio was empty.")

        full_onset = librosa.onset.onset_strength(y=y, sr=sr)
        sos = scipy.signal.butter(
            6, [35.0, 320.0], btype="bandpass", fs=sr, output="sos"
        )
        low_audio = scipy.signal.sosfiltfilt(sos, y).astype(np.float32)
        low_onset = librosa.onset.onset_strength(y=low_audio, sr=sr)
        frame_times = librosa.frames_to_time(
            np.arange(len(full_onset)), sr=sr
        )

    changes = sorted({
        float(item.get("start_s"))
        for item in chord_segments
        if isinstance(item, dict)
        and isinstance(item.get("start_s"), (int, float))
        and float(item.get("start_s")) > 0.05
        and float(item.get("start_s")) <= AUDIBLE_PREVIEW_SECONDS
    })

    ranked = score_timing_candidates(
        candidates, full_onset, low_onset, frame_times, changes
    )
    if not ranked:
        raise RuntimeError("No timing candidate could be scored.")

    truth = _saved_manual_truth(record, analysis)
    verified_row = None
    verified_rank = None
    if truth["complete"]:
        for index, row in enumerate(ranked, start=1):
            if (
                row.get("meter") == truth["meter"]
                and _normalise_method_name(row.get("method"))
                == truth["beat_grid_method"]
                and int(row.get("phase_number") or 0) == truth["phase_number"]
            ):
                verified_row = dict(row)
                verified_rank = index
                break

    winner = dict(ranked[0])
    runner = dict(ranked[1] if len(ranked) > 1 else ranked[0])

    best_by_meter = {}
    for meter in ("3/4", "4/4"):
        matching = [row for row in ranked if row.get("meter") == meter]
        if matching:
            best_by_meter[meter] = matching[0]

    best_by_grid = {}
    for method in sorted({str(row.get("method")) for row in ranked}):
        matching = [row for row in ranked if str(row.get("method")) == method]
        if matching:
            best_by_grid[method] = matching[0]

    verified_payload = {
        **truth,
        "rank": verified_rank,
        "candidate": verified_row,
        "score_gap_from_winner": (
            round(float(winner["score"]) - float(verified_row["score"]), 6)
            if verified_row is not None else None
        ),
        "winner_minus_verified_components": (
            _component_difference(winner, verified_row)
            if verified_row is not None else None
        ),
    }

    return {
        "laboratory_build": 21,
        "purpose": "diagnostic_only",
        "scoring_model": "unchanged_build_020_repeating_pattern",
        "song_title": song_title,
        "candidate_count": len(ranked),
        "chord_change_count_in_preview": len(changes),
        "winner": winner,
        "runner_up": runner,
        "winner_margin": round(
            float(winner["score"]) - float(runner["score"]), 6
        ),
        "verified_candidate": verified_payload,
        "best_candidate_by_meter": best_by_meter,
        "best_candidate_by_beat_grid": best_by_grid,
        "all_ranked_candidates": [
            {"rank": index, **row}
            for index, row in enumerate(ranked, start=1)
        ],
        "timing_data_changed": False,
        "scoring_weights_changed": False,
    }


def format_timing_evidence_text(report: dict) -> str:
    lines = [
        "BANJOFY SONG ANALYSIS LABORATORY 021",
        "TIMING EVIDENCE AND COMPARISON REPORT",
        "",
        f"Song: {report.get('song_title')}",
        f"Candidates scored: {report.get('candidate_count')}",
        f"Chord changes in preview: {report.get('chord_change_count_in_preview')}",
        "Scoring model: unchanged Build 020 scoring",
        "Timing data changed: NO",
        "Scoring weights changed: NO",
        "",
        "AUTOMATIC WINNER",
    ]

    winner = report.get("winner") or {}
    lines.extend([
        f"Meter: {winner.get('meter')}",
        f"Beat grid: {winner.get('label')} ({winner.get('method')})",
        f"Phase: {winner.get('phase_number')}",
        f"Score: {winner.get('score')}",
        f"Margin over runner-up: {report.get('winner_margin')}",
        "",
        "SAVED MANUAL RESULT",
    ])

    verified = report.get("verified_candidate") or {}
    lines.extend([
        f"Meter: {verified.get('meter')}",
        f"Beat grid method: {verified.get('beat_grid_method')}",
        f"Phase: {verified.get('phase_number')}",
        f"Complete saved result: {'YES' if verified.get('complete') else 'NO'}",
        f"Rank: {verified.get('rank')}",
        f"Score gap from winner: {verified.get('score_gap_from_winner')}",
        "",
    ])

    if verified.get("winner_minus_verified_components"):
        lines.append("WHY THE WINNER BEAT THE SAVED RESULT")
        for key, value in verified["winner_minus_verified_components"].items():
            sign = "+" if float(value) >= 0 else ""
            lines.append(f"{key}: {sign}{value}")
        lines.append("")

    lines.extend([
        "ALL CANDIDATES",
        (
            "Rank | Score | Meter | Grid | Phase | Stability | Beat support | "
            "Chord-grid support | Repeating accent | Bar consistency | Lead-in rise"
        ),
    ])

    for row in report.get("all_ranked_candidates", []):
        lines.append(
            f"{row.get('rank'):>4} | "
            f"{float(row.get('score', 0.0)):.6f} | "
            f"{row.get('meter'):>3} | "
            f"{str(row.get('method')):<13} | "
            f"{int(row.get('phase_number', 0)):>2} | "
            f"{float(row.get('stability', 0.0)):.6f} | "
            f"{float(row.get('beat_support', 0.0)):.6f} | "
            f"{float(row.get('chord_grid_support', 0.0)):.6f} | "
            f"{float(row.get('repeating_accent_score', 0.0)):.6f} | "
            f"{float(row.get('bar_pattern_consistency', 0.0)):.6f} | "
            f"{float(row.get('lead_in_rise_score', 0.0)):.6f}"
        )

    lines.extend([
        "",
        "INTERPRETATION",
        "This report does not decide that the automatic winner is musically correct.",
        "It shows exactly which measured components caused it to outrank the saved result.",
        "No recommendation was applied and no confirmation was changed.",
        "",
    ])
    return "\n".join(lines)


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
