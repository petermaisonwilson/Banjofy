from __future__ import annotations
import ast, sys
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 021 — Timing Evidence and Comparison"' in main_text
assert 'name="BanjofySongAnalysisLab021"' in spec_text
assert 'Create Timing Evidence Report' in main_text
assert 'def _create_timing_evidence_report(' in main_text
assert 'timing_evidence_021.json' in main_text
assert 'timing_evidence_021.txt' in main_text

for required in (
    "def build_timing_evidence_report(",
    "def format_timing_evidence_text(",
    "all_ranked_candidates",
    "winner_minus_verified_components",
    "scoring_weights_changed",
    "timing_data_changed",
):
    assert required in engine_text

for exact_weight in (
    "0.23 * stability",
    "0.20 * beat_support",
    "0.05 * chord_grid_support",
    "0.27 * repeating_accent",
    "0.18 * bar_consistency",
    "0.05 * lead_in_rise",
    "0.02 * meter_prior",
):
    assert exact_weight in engine_text

assert "wav = prepare_wav(audio_path, Path(temporary))" in engine_text
assert "librosa.load(audio_path" not in engine_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text

sys.path.insert(0, str(root))
import structure_engine

truth = structure_engine._saved_manual_truth(
    {
        "confirmed_meter": "4/4",
        "confirmed_beat_grid_method": "standard",
        "confirmed_phase_number": 3,
    },
    {},
)
assert truth["complete"] is True
assert truth["meter"] == "4/4"
assert truth["beat_grid_method"] == "standard"
assert truth["phase_number"] == 3

sample = {
    "song_title": "Proof Song",
    "candidate_count": 1,
    "chord_change_count_in_preview": 4,
    "winner": {
        "meter": "4/4", "label": "Standard full mix",
        "method": "standard", "phase_number": 2, "score": 0.8,
    },
    "winner_margin": 0.0,
    "verified_candidate": {
        "meter": "4/4", "beat_grid_method": "standard",
        "phase_number": 3, "complete": True, "rank": 2,
        "score_gap_from_winner": 0.1,
        "winner_minus_verified_components": {"stability": 0.0},
    },
    "all_ranked_candidates": [{
        "rank": 1, "score": 0.8, "meter": "4/4", "method": "standard",
        "phase_number": 2, "stability": 1.0, "beat_support": 0.7,
        "chord_grid_support": 0.4, "repeating_accent_score": 0.8,
        "bar_pattern_consistency": 0.7, "lead_in_rise_score": 0.5,
    }],
}
text = structure_engine.format_timing_evidence_text(sample)
assert "AUTOMATIC WINNER" in text
assert "SAVED MANUAL RESULT" in text
assert "WHY THE WINNER BEAT THE SAVED RESULT" in text
assert "ALL CANDIDATES" in text

print("Banjofy Song Analysis Laboratory 021 complete release gate: passed")
