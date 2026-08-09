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
    tempo_support: int
    meter_evidence: float
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


def _phase_support(candidate: int, candidate_models: list[int], prepared: Dict[int, np.ndarray]) -> float:
    """Measure whether a candidate's downbeats are supported by the shared beat pulse.

    This deliberately does not inspect audio or use song truth. It asks a narrower
    question: once models agree on tempo, do the candidate Beat-1 timestamps land on
    beat timestamps that the other tempo-family models also recognise? A false meter
    often places some downbeats between the common pulse positions.
    """
    own = prepared[candidate]
    own_numbers = np.rint(own[:, 1]).astype(int)
    own_downbeats = own[own_numbers == 1, 0]
    if not len(own_downbeats):
        return 0.0
    values = []
    for other_model in candidate_models:
        if other_model == candidate:
            continue
        other_times = prepared[other_model][:, 0]
        values.append(_nearest_fraction(own_downbeats, other_times, 0.10))
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

    tempo_support = {model: _tempo_support(model, summaries) for model in prepared}
    max_tempo_support = max(tempo_support.values()) if tempo_support else 0
    tempo_family = [model for model in sorted(prepared) if tempo_support[model] == max_tempo_support]

    if max_tempo_support >= 1:
        candidate_models = tempo_family
    else:
        candidate_models = sorted(prepared)

    candidate_bpms = np.asarray([summaries[m][0] for m in candidate_models if summaries[m][0] > 0], dtype=float)
    consensus_bpm = float(np.median(candidate_bpms)) if len(candidate_bpms) else 0.0

    candidate_meters = [summaries[m][1] for m in candidate_models if summaries[m][1] > 0]
    meter_counts = {meter: candidate_meters.count(meter) for meter in sorted(set(candidate_meters))}
    max_meter_votes = max(meter_counts.values()) if meter_counts else 0
    winning_meters = [meter for meter, count in meter_counts.items() if count == max_meter_votes]
    meter_ambiguous = len(winning_meters) != 1 or max_meter_votes < 2
    consensus_meter_value = winning_meters[0] if not meter_ambiguous else 0

    meter_evidence = {model: _phase_support(model, candidate_models, prepared) for model in candidate_models}
    meter_resolution = "vote"

    # If tempo is supported but meter is tied, use only cross-model timing evidence.
    # A winner must be materially better supported; otherwise ambiguity is preserved.
    if meter_ambiguous and len(candidate_models) >= 2:
        evidence_ranked = sorted(candidate_models, key=lambda m: (-meter_evidence[m], m))
        evidence_best = evidence_ranked[0]
        evidence_second = evidence_ranked[1]
        evidence_margin = meter_evidence[evidence_best] - meter_evidence[evidence_second]
        if meter_evidence[evidence_best] >= 0.85 and evidence_margin >= 0.08:
            consensus_meter_value = summaries[evidence_best][1]
            meter_ambiguous = False
            meter_resolution = "phase_evidence"
        else:
            meter_resolution = "ambiguous"

    assessments = []
    for model in sorted(prepared):
        data = prepared[model]
        bpm, meter, mad = summaries[model]
        beat_agreement = _agreement_for(model, prepared, downbeats=False)
        downbeat_agreement = _agreement_for(model, prepared, downbeats=True)
        support = tempo_support[model]
        evidence = meter_evidence.get(model, 0.0)

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
            0.35 * beat_agreement
            + 0.20 * downbeat_agreement
            + 0.20 * tempo_score
            + 0.10 * meter_score
            + 0.10 * evidence
            + 0.05 * stability_score
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
                tempo_support=int(support),
                meter_evidence=round(float(evidence), 4),
                score=round(float(score), 4),
            )
        )

    candidate_assessments = [item for item in assessments if item.model in candidate_models]
    if not meter_ambiguous:
        meter_matches = [item for item in candidate_assessments if item.meter == consensus_meter_value]
        if meter_matches:
            candidate_assessments = meter_matches
    ranked = sorted(candidate_assessments, key=lambda item: (-item.score, item.model))
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = best.score - runner_up.score if runner_up else best.score

    if meter_ambiguous:
        recommended_model = None
        confidence = "low"
    else:
        recommended_model = best.model
        if meter_resolution == "phase_evidence":
            confidence = "medium"
        elif best.score >= 0.88 and margin >= 0.04:
            confidence = "high"
        elif best.score >= 0.75:
            confidence = "medium"
        else:
            confidence = "low"

    return {
        "schema": "banjofy.bn_consensus.v3",
        "recommended_model": recommended_model,
        "confidence": confidence,
        "consensus_bpm": round(consensus_bpm, 3),
        "consensus_meter": f"{consensus_meter_value}/4" if consensus_meter_value else "AMBIGUOUS",
        "meter_votes": meter_counts,
        "tempo_family_models": candidate_models,
        "meter_ambiguous": meter_ambiguous,
        "meter_resolution": meter_resolution,
        "meter_evidence": {str(model): round(float(value), 4) for model, value in meter_evidence.items()},
        "score_margin": round(float(margin), 4),
        "models": [assessment.__dict__ for assessment in assessments],
    }
