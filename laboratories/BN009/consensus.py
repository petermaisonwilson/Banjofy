from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass(frozen=True)
class ModelAssessment:
    model: int
    bpm: float
    meter: int
    beat_count: int
    downbeat_count: int
    interval_mad_s: float
    beat_agreement: float
    downbeat_agreement: float
    tempo_support: int
    meter_accent_score: float
    startup_lock_score: float
    startup_audio_score: float
    startup_quality: float
    score: float


def _normalise(data: np.ndarray) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError(f"Expected Nx2 BeatNet output, got {arr.shape}")
    arr = arr[:, :2]
    arr = arr[np.isfinite(arr).all(axis=1)]
    arr = arr[arr[:, 0] >= 0]
    arr = arr[np.argsort(arr[:, 0])]
    if len(arr) < 4:
        raise ValueError("BeatNet output contains fewer than four usable beats")
    return arr


def _summary(data: np.ndarray) -> tuple[float, int, float]:
    times = data[:, 0]
    beat_numbers = np.rint(data[:, 1]).astype(int)
    intervals = np.diff(times)
    intervals = intervals[(intervals > 0.12) & (intervals < 3.0)]
    if not len(intervals):
        return 0.0, 0, 999.0
    median_interval = float(np.median(intervals))
    bpm = 60.0 / median_interval
    mad = float(np.median(np.abs(intervals - median_interval)))
    positive = beat_numbers[beat_numbers > 0]
    meter = int(np.max(positive)) if len(positive) else 0
    return bpm, meter, mad


def _nearest_fraction(reference: np.ndarray, other: np.ndarray, tolerance_s: float) -> float:
    if not len(reference) or not len(other):
        return 0.0
    other = np.asarray(other, dtype=float)
    hits = 0
    for value in np.asarray(reference, dtype=float):
        idx = int(np.searchsorted(other, value))
        distances = []
        if idx < len(other):
            distances.append(abs(float(other[idx]) - float(value)))
        if idx:
            distances.append(abs(float(other[idx - 1]) - float(value)))
        if distances and min(distances) <= tolerance_s:
            hits += 1
    return hits / float(len(reference))


def _agreement_for(model: int, prepared: Dict[int, np.ndarray], downbeats: bool) -> float:
    own = prepared[model]
    own_numbers = np.rint(own[:, 1]).astype(int)
    own_times = own[own_numbers == 1, 0] if downbeats else own[:, 0]
    values = []
    for other_model, other in prepared.items():
        if other_model == model:
            continue
        other_numbers = np.rint(other[:, 1]).astype(int)
        other_times = other[other_numbers == 1, 0] if downbeats else other[:, 0]
        tolerance = 0.16 if downbeats else 0.10
        forward = _nearest_fraction(own_times, other_times, tolerance)
        reverse = _nearest_fraction(other_times, own_times, tolerance)
        values.append((forward + reverse) / 2.0)
    return float(np.mean(values)) if values else 1.0


def _tempo_support(model: int, summaries: Dict[int, tuple[float, int, float]], tolerance_ratio: float = 0.03) -> int:
    bpm = summaries[model][0]
    if bpm <= 0:
        return 0
    support = 0
    for other_model, (other_bpm, _, _) in summaries.items():
        if other_model == model or other_bpm <= 0:
            continue
        if abs(other_bpm - bpm) / max(bpm, other_bpm) <= tolerance_ratio:
            support += 1
    return support


def _startup_lock_score(data: np.ndarray) -> float:
    """Score whether the opening bar sequence joins the later stable bar phase cleanly."""
    numbers = np.rint(data[:, 1]).astype(int)
    downbeats = np.asarray(data[numbers == 1, 0], dtype=float)
    if len(downbeats) < 10:
        return 0.5

    split = min(7, max(4, len(downbeats) // 5))
    later_diffs = np.diff(downbeats[split:])
    later_diffs = later_diffs[(later_diffs > 0.35) & (later_diffs < 12.0)]
    if len(later_diffs) < 4:
        return 0.5
    stable_bar = float(np.median(later_diffs))
    if stable_bar <= 0:
        return 0.5

    opening_diffs = np.diff(downbeats[: split + 2])
    if len(opening_diffs) < 3:
        return 0.5
    relative_errors = np.abs(opening_diffs - stable_bar) / stable_bar

    # Penalise both sustained wrong spacing and a sudden snap into the later phase.
    median_error = float(np.median(relative_errors))
    worst_error = float(np.max(relative_errors))
    continuity_error = 0.65 * median_error + 0.35 * worst_error
    return float(np.clip(1.0 - continuity_error / 0.35, 0.0, 1.0))


def analyse_consensus(
    outputs: Dict[int, np.ndarray],
    meter_accent_scores: Optional[Dict[int, float]] = None,
    startup_audio_scores: Optional[Dict[int, float]] = None,
) -> dict:
    """Compare unchanged BeatNet outputs and recommend one timing source."""
    if not outputs:
        raise ValueError("No BeatNet outputs supplied")

    prepared = {int(model): _normalise(data) for model, data in outputs.items()}
    summaries = {model: _summary(data) for model, data in prepared.items()}
    accent_scores = {int(k): float(v) for k, v in (meter_accent_scores or {}).items()}
    startup_audio = {int(k): float(v) for k, v in (startup_audio_scores or {}).items()}
    startup_lock = {model: _startup_lock_score(data) for model, data in prepared.items()}

    tempo_support = {model: _tempo_support(model, summaries) for model in prepared}
    max_tempo_support = max(tempo_support.values()) if tempo_support else 0
    tempo_family = [model for model in sorted(prepared) if tempo_support[model] == max_tempo_support]
    candidate_models = tempo_family if max_tempo_support >= 1 else sorted(prepared)

    candidate_bpms = np.asarray([summaries[m][0] for m in candidate_models if summaries[m][0] > 0], dtype=float)
    consensus_bpm = float(np.median(candidate_bpms)) if len(candidate_bpms) else 0.0

    candidate_meters = [summaries[m][1] for m in candidate_models if summaries[m][1] > 0]
    meter_counts = {meter: candidate_meters.count(meter) for meter in sorted(set(candidate_meters))}
    max_meter_votes = max(meter_counts.values()) if meter_counts else 0
    winning_meters = [meter for meter, count in meter_counts.items() if count == max_meter_votes]
    meter_ambiguous = len(winning_meters) != 1 or max_meter_votes < 2
    consensus_meter_value = winning_meters[0] if not meter_ambiguous else 0
    meter_resolution = "vote" if not meter_ambiguous else "ambiguous"

    if meter_ambiguous and len(candidate_models) >= 2 and all(m in accent_scores for m in candidate_models):
        ranked_accent = sorted(candidate_models, key=lambda m: (-accent_scores[m], m))
        best_accent_model = ranked_accent[0]
        second_accent_model = ranked_accent[1]
        accent_margin = accent_scores[best_accent_model] - accent_scores[second_accent_model]
        if accent_scores[best_accent_model] >= 0.54 and accent_margin >= 0.04:
            consensus_meter_value = summaries[best_accent_model][1]
            meter_ambiguous = False
            meter_resolution = "audio_accent"

    assessments = []
    for model in sorted(prepared):
        data = prepared[model]
        bpm, meter, mad = summaries[model]
        beat_agreement = _agreement_for(model, prepared, downbeats=False)
        downbeat_agreement = _agreement_for(model, prepared, downbeats=True)
        support = tempo_support[model]
        accent = accent_scores.get(model, 0.5)
        start_lock = startup_lock[model]
        start_audio = startup_audio.get(model, 0.5)
        start_quality = 0.45 * start_lock + 0.55 * start_audio

        if model not in candidate_models:
            tempo_score = 0.0
        elif max_tempo_support >= 1:
            tempo_score = 1.0
        else:
            tempo_score = 0.5

        if meter_ambiguous:
            meter_score = 0.5
        else:
            meter_score = 1.0 if meter == consensus_meter_value else 0.0

        stability_score = max(0.0, 1.0 - min(mad / 0.10, 1.0))
        score = (
            0.29 * beat_agreement
            + 0.17 * downbeat_agreement
            + 0.20 * tempo_score
            + 0.10 * meter_score
            + 0.07 * accent
            + 0.12 * start_quality
            + 0.05 * stability_score
        )

        beat_numbers = np.rint(data[:, 1]).astype(int)
        assessments.append(ModelAssessment(
            model=model,
            bpm=round(float(bpm), 3),
            meter=meter,
            beat_count=int(len(data)),
            downbeat_count=int(np.sum(beat_numbers == 1)),
            interval_mad_s=round(float(mad), 6),
            beat_agreement=round(float(beat_agreement), 4),
            downbeat_agreement=round(float(downbeat_agreement), 4),
            tempo_support=int(support),
            meter_accent_score=round(float(accent), 4),
            startup_lock_score=round(float(start_lock), 4),
            startup_audio_score=round(float(start_audio), 4),
            startup_quality=round(float(start_quality), 4),
            score=round(float(score), 4),
        ))

    candidate_assessments = [item for item in assessments if item.model in candidate_models]
    if not meter_ambiguous:
        matches = [item for item in candidate_assessments if item.meter == consensus_meter_value]
        if matches:
            candidate_assessments = matches

    ranked = sorted(candidate_assessments, key=lambda item: (-item.score, -item.startup_quality, item.model))
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = best.score - runner_up.score if runner_up else best.score
    selection_reason = "overall_score"

    # When whole-song candidates are essentially tied, prefer the one that was ready
    # earliest. This is deliberately applied only after tempo and meter filtering.
    if not meter_ambiguous and len(ranked) > 1 and margin < 0.025:
        startup_ranked = sorted(ranked, key=lambda item: (-item.startup_quality, -item.score, item.model))
        startup_best = startup_ranked[0]
        if startup_best.startup_quality - best.startup_quality >= 0.035:
            best = startup_best
            selection_reason = "startup_tiebreak"
            runner_up = next((item for item in ranked if item.model != best.model), None)
            margin = best.score - runner_up.score if runner_up else best.score

    if meter_ambiguous:
        recommended_model = None
        confidence = "low"
        selection_reason = "meter_ambiguous"
    else:
        recommended_model = best.model
        if meter_resolution == "audio_accent":
            confidence = "medium"
        elif best.score >= 0.88 and abs(margin) >= 0.04:
            confidence = "high"
        elif best.score >= 0.72:
            confidence = "medium"
        else:
            confidence = "low"

    return {
        "schema": "banjofy.bn_consensus.v6",
        "recommended_model": recommended_model,
        "confidence": confidence,
        "consensus_bpm": round(consensus_bpm, 3),
        "consensus_meter": f"{consensus_meter_value}/4" if consensus_meter_value else "AMBIGUOUS",
        "meter_votes": meter_counts,
        "tempo_family_models": candidate_models,
        "meter_ambiguous": meter_ambiguous,
        "meter_resolution": meter_resolution,
        "selection_reason": selection_reason,
        "meter_accent_scores": {str(m): round(float(accent_scores.get(m, 0.5)), 4) for m in candidate_models},
        "startup_lock_scores": {str(m): round(float(startup_lock[m]), 4) for m in candidate_models},
        "startup_audio_scores": {str(m): round(float(startup_audio.get(m, 0.5)), 4) for m in candidate_models},
        "score_margin": round(float(margin), 4),
        "models": [assessment.__dict__ for assessment in assessments],
    }
