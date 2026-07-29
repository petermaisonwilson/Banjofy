from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 020 — Repeating-Pattern Downbeat Recommendation"' in main_text
assert 'name="BanjofySongAnalysisLab020"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text

for forbidden in ('"2/4"', "'2/4'", '"6/8"', "'6/8'", "Build 013"):
    assert forbidden not in main_text

for required in (
    "Recommend Meter, Beat Grid and Phase",
    "def _recommend_timing(",
    "timing_recommendation_020.json",
    "automatic_scoring_v2_repeating_pattern",
):
    assert required in main_text

for required in (
    "def _phase_pattern_metrics(",
    "def score_timing_candidates(",
    "def recommend_timing_structure(",
    "repeating_accent_score",
    "bar_pattern_consistency",
    "lead_in_rise_score",
    '"phase_chord_weight": 0.0',
):
    assert required in engine_text

assert "wav = prepare_wav(audio_path, Path(temporary))" in engine_text
assert "librosa.load(audio_path" not in engine_text

sys.path.insert(0, str(root))
import structure_engine

# Synthetic 3/4 example:
# the true Beat 1 is candidate Phase 3, while chord changes deliberately occur
# on other beats. The scorer must still choose Phase 3.
frame_times = np.arange(0.0, 48.0, 0.05)
full = np.zeros_like(frame_times)
low = np.zeros_like(frame_times)
beats = [0.30 + index * 0.60 for index in range(72)]

# Phase numbering is offset from beat index zero. Phase 3 means indices 2,5,8...
for index, beat in enumerate(beats):
    frame_index = int(np.argmin(np.abs(frame_times - beat)))
    position = index % 3
    if position == 2:
        full[frame_index] = 0.82
        low[frame_index] = 1.00
    elif position == 0:
        full[frame_index] = 0.50
        low[frame_index] = 0.54
    else:
        full[frame_index] = 0.34
        low[frame_index] = 0.40

# Chord changes are mostly on positions 0 and 1, not on the true downbeat.
chord_changes = [
    beats[index] for index in (3, 7, 12, 16, 21, 25, 31, 34, 40, 46, 49, 55)
]

candidates = {
    "low_frequency": {
        "label": "Low-frequency rhythm",
        "bpm": 100.0,
        "beat_times": beats,
    },
    "standard": {
        "label": "Standard full mix",
        "bpm": 120.0,
        "beat_times": [0.20 + index * 0.50 for index in range(82)],
    },
}

rows = structure_engine.score_timing_candidates(
    candidates,
    full,
    low,
    frame_times,
    chord_changes,
)
assert rows
winner = rows[0]
assert winner["meter"] == "3/4", winner
assert winner["method"] == "low_frequency", winner
assert winner["phase_number"] == 3, winner
assert winner["phase_chord_weight"] == 0.0
assert "repeating_accent_score" in winner
assert "bar_pattern_consistency" in winner
assert "bar_position_profile" in winner

# Every supported phase must still be scored.
assert {row["meter"] for row in rows} == {"3/4", "4/4"}
assert all(
    1 <= row["phase_number"] <= (3 if row["meter"] == "3/4" else 4)
    for row in rows
)

print("Banjofy Song Analysis Laboratory 020 complete release gate: passed")
