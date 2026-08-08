from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

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


def analyse_consensus(outputs: Dict[int, np.ndarray]) -> dict:
    """Compare unchanged BeatNet model outputs and recommend a timing source.

    This function does not run BeatNet and does not alter any model output. It only
    measures agreement and regularity after all requested models have completed.
    """
    if not outputs:
        raise ValueError("No BeatNet outputs supplied")

    prepared = {int(model): _normalise(data) for model, data in outputs.items()}
    summaries = {model: _summary(data) for model, data in prepared.items()}

    meters = [meter for _, meter, _ in summaries.values() if meter > 0]
    meter_counts = {meter: meters.count(meter) for meter in sorted(set(meters))}
    consensus_meter = max(meter_counts, key=meter_counts.get) if meter_counts else 0
    meter_votes = meter_counts.get(consensus_meter, 0)

    bpms = np.asarray([bpm for bpm, _, _ in summaries.values() if bpm > 0], dtype=float)
    consensus_bpm = float(np.median(bpms)) if len(bpms) else 0.0

    assessments = []
    for model in sorted(prepared):
        data = prepared[model]
        bpm, meter, mad = summaries[model]
        beat_agreement = _agreement_for(model, prepared, downbeats=False)
        downbeat_agreement = _agreement_for(model, prepared, downbeats=True)

        # Transparent score: model-to-model timing agreement carries most weight.
        # Meter agreement is useful when two or more models independently agree,
        # while interval regularity is deliberately a smaller contribution because
        # real performances can push and pull tempo naturally.
        meter_score = 1.0 if meter and meter == consensus_meter and meter_votes >= 2 else 0.5
        stability_score = max(0.0, 1.0 - min(mad / 0.10, 1.0))
        score = (
            0.45 * beat_agreement
            + 0.30 * downbeat_agreement
            + 0.15 * meter_score
            + 0.10 * stability_score
        )

        beat_numbers = np.rint(data[:, 1]).astype(int)
        assessments.append(
            ModelAssessment(
                model=model,
                bpm=round(float(bpm), 3),
                meter=meter,
                beat_count=int(len(data)),
                downbeat_count=int(np.sum(beat_numbers == 1)),
                interval_mad_s=round(float(mad), 6),
                beat_agreement=round(float(beat_agreement), 4),
                downbeat_agreement=round(float(downbeat_agreement), 4),
                score=round(float(score), 4),
            )
        )

    ranked = sorted(assessments, key=lambda item: (-item.score, item.model))
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = best.score - runner_up.score if runner_up else best.score

    if best.score >= 0.88 and margin >= 0.04:
        confidence = "high"
    elif best.score >= 0.75:
        confidence = "medium"
    else:
        confidence = "low"

    # A meter split such as 2/4 vs 4/4 vs 3/4 is musically significant. Do not
    # pretend the consensus is certain simply because one model has the top score.
    if len(meter_counts) > 1 and meter_votes < 2:
        confidence = "low"

    return {
        "schema": "banjofy.bn_consensus.v1",
        "recommended_model": best.model,
        "confidence": confidence,
        "consensus_bpm": round(consensus_bpm, 3),
        "consensus_meter": f"{consensus_meter}/4" if consensus_meter else "unknown",
        "meter_votes": meter_counts,
        "score_margin": round(float(margin), 4),
        "models": [assessment.__dict__ for assessment in assessments],
    }
