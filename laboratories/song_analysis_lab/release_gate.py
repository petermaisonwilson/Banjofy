from pathlib import Path
import ast, sys

root = Path(__file__).resolve().parent
m = (root / "main.py").read_text(encoding="utf-8")
e = (root / "structure_engine.py").read_text(encoding="utf-8")
s = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(m)
ast.parse(e)

assert "Laboratory 027 — Whole-Song Interpreter" in m
assert "BanjofySongAnalysisLab027" in s
assert "Run Whole-Song Interpreter" in m
assert "whole_song_interpreter_027.txt" in m

for token in (
    "def _candidate_pulse_variants(",
    "def _pattern_repetition_score(",
    "def _chord_change_integer_beat_score(",
    "def _bar_timeline(",
    "def interpret_song_whole_song(",
    "def interpret_verified_library_whole_song(",
    "def format_whole_song_library_report(",
    "decision_made_before_truth",
    "truth_used_for_candidate_selection",
):
    assert token in e

# Existing Build 020 score remains exactly available.
for weight in (
    "0.23 * stability",
    "0.20 * beat_support",
    "0.05 * chord_grid_support",
    "0.27 * repeating_accent",
    "0.18 * bar_consistency",
    "0.05 * lead_in_rise",
    "0.02 * meter_prior",
):
    assert weight in e

assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in e

sys.path.insert(0, str(root))
import structure_engine

# Pulse candidate proof.
beats = [float(i) for i in range(24)]
variants = structure_engine._candidate_pulse_variants(beats)
names = {row["pulse_variant"] for row in variants}
assert "as_detected" in names
assert "half_time_offset_0" in names
assert "half_time_offset_1" in names
assert "double_time_interpolated" in names

# Harmonic repetition proof.
seq = ["Bm","F#","A","E","G","D","Em","F#"] * 4
assert structure_engine._pattern_repetition_score(seq) > 0.5

# Timeline proof.
segments = [
    {"start_s": 0.0, "end_s": 4.0, "chord": "G"},
    {"start_s": 4.0, "end_s": 8.0, "chord": "C"},
]
timeline = structure_engine._bar_timeline(
    [float(i) for i in range(12)],
    "4/4",
    1,
    segments,
)
assert timeline[0]["bar"] == 1
assert timeline[0]["beats"][0]["beat"] == 1
assert timeline[0]["beats"][0]["chord"] == "G"
assert timeline[1]["beats"][0]["chord"] == "C"

# Truth validation must be separate from interpretation.
interpretation = {
    "winner": {
        "meter": "4/4",
        "beat_grid_method": "standard",
        "phase_number": 3,
    }
}
truth = {
    "meter": "4/4",
    "beat_grid_method": "standard",
    "phase_number": 3,
}
validation = structure_engine._truth_match_after_decision(interpretation, truth)
assert validation["exact_match"] is True

sample = {
    "verified_song_count": 1,
    "exact_whole_song_matches": 1,
    "exact_accuracy": 1.0,
    "truth_used_for_candidate_selection": False,
    "songs": [{
        "song_title": "Proof Song",
        "interpretation": {
            "winner": {
                "meter": "4/4",
                "beat_grid_method": "standard",
                "phase_number": 3,
                "bpm": 72.0,
                "pulse_variant": "half_time_offset_0",
                "coherence_score": 0.91,
                "confidence_class": "strong",
                "runner_up_margin": 0.1,
            },
            "key_from_existing_analysis": "Bm",
            "ranked_candidates": [{
                "rank": 1,
                "meter": "4/4",
                "grid_method": "standard",
                "phase_number": 3,
                "bpm": 72.0,
                "pulse_variant": "half_time_offset_0",
                "coherence_score": 0.91,
            }],
            "bar_timeline": [{
                "bar": 1,
                "beats": [
                    {"beat": 1, "time_s": 1.0, "chord": "Bm"},
                    {"beat": 2, "time_s": 1.8, "chord": "Bm"},
                    {"beat": 3, "time_s": 2.6, "chord": "Bm"},
                    {"beat": 4, "time_s": 3.4, "chord": "Bm"},
                ],
            }],
        },
        "post_decision_validation": {
            "verified_truth": {
                "meter": "4/4",
                "beat_grid_method": "standard",
                "phase_number": 3,
            },
            "checks": {
                "meter": "PASS",
                "beat_grid_method": "PASS",
                "phase_number": "PASS",
            },
            "exact_match": True,
        },
    }],
    "next_gate": "Expand only after generalisation proof.",
}
text = structure_engine.format_whole_song_library_report(sample)
assert "Truth used for candidate selection: NO" in text
assert "Exact PASS" in text
assert "First 8 constructed bars" in text

print("Banjofy Song Analysis Laboratory 027 complete release gate: passed")
