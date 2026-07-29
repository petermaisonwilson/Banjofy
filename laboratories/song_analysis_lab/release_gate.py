from __future__ import annotations
import ast, sys
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 023 — Verified Timing Truth"' in main_text
assert 'name="BanjofySongAnalysisLab023"' in spec_text
assert 'Review / Save Verified Truth' in main_text
assert 'Save Verified Truth' in main_text
assert 'manual_truth_023.json' in main_text
assert 'manual_truth_023.txt' in main_text

for token in (
    "def recover_verified_truth(",
    "def build_verified_truth_record(",
    "def format_verified_truth_record(",
    "timing_recommendation",
    "ranked_candidates",
    "candidate_meters",
):
    assert token in engine_text

# Frozen Build 020 scoring model.
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

assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text

sys.path.insert(0, str(root))
import structure_engine

# Explicit confirmations override and candidates are excluded.
analysis = {
    "confirmed_meter": "3/4",
    "confirmed_beat_grid_method": "low_frequency",
    "timing_recommendation": {
        "ranked_candidates": [
            {"meter": "4/4", "beat_grid_method": "standard", "phase_number": 2}
        ]
    },
}
result = structure_engine.recover_verified_truth(
    {}, analysis, {}, "Tennessee",
    Path("record.json"), Path("song_analysis.json"), Path("song_structure.json"),
)
c = result["canonical_record"]
assert c["meter"] == "3/4"
assert c["beat_grid_method"] == "low_frequency"
assert c["phase_number"] is None
assert "No explicit confirmed phase exists" in " ".join(c["notes"])
assert not any(
    "ranked_candidates" in str(row.get("json_path"))
    for row in c["explicit_values"]
)

# Historical song inference.
analysis2 = {
    "best_meter_candidate": "4/4",
    "confirmed_phase_number": 3,
}
r2 = structure_engine.recover_verified_truth(
    {}, analysis2, {}, "Hotel",
    Path("record.json"), Path("song_analysis.json"), Path("song_structure.json"),
)
c2 = r2["canonical_record"]
assert c2["meter"] == "4/4"
assert c2["beat_grid_method"] == "standard"
assert c2["phase_number"] == 3
assert any("inferred" in note for note in c2["notes"])

verified = structure_engine.build_verified_truth_record(
    c2, meter="4/4", beat_grid_method="standard", phase_number=3
)
assert verified["complete"] is True
assert verified["verified_by_user"] is True
assert "VERIFIED TIMING TRUTH" in structure_engine.format_verified_truth_record(verified)

try:
    structure_engine.build_verified_truth_record(
        c2, meter="3/4", beat_grid_method="standard", phase_number=4
    )
except ValueError:
    pass
else:
    raise AssertionError("Invalid 3/4 Phase 4 was accepted.")

print("Banjofy Song Analysis Laboratory 023 complete release gate: passed")
