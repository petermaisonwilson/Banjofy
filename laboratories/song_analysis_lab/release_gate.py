from __future__ import annotations
import ast, sys
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 022 — Manual Truth Recovery"' in main_text
assert 'name="BanjofySongAnalysisLab022"' in spec_text
assert 'self.geometry("1550x820")' in main_text
assert 'Recover Manual Truth' in main_text
assert 'def _recover_manual_truth(' in main_text
assert 'manual_truth_recovery_022.txt' in main_text
assert 'manual_truth_022.json' in main_text

for required in (
    "TRUTH_FIELD_ALIASES",
    "def _walk_json_values(",
    "def _collect_truth_candidates(",
    "def recover_manual_truth(",
    "def format_manual_truth_recovery(",
    "confirmed_first_downbeat_beat_index",
    "detected_first_downbeat_beat_index",
):
    assert required in engine_text

# Scorer remains unchanged from Build 020/021.
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
assert "librosa.load(audio_path" not in engine_text

sys.path.insert(0, str(root))
import structure_engine

# Direct explicit truth recovery.
record = {
    "structure_summary": {
        "confirmed_meter": "4/4",
        "confirmed_phase_number": 3,
    }
}
analysis = {
    "confirmed_beat_grid_method": "standard",
    "meter": "Uncertain",
}
structure = {}
result = structure_engine.recover_manual_truth(
    record,
    analysis,
    structure,
    "Hotel Proof",
    Path("record.json"),
    Path("song_analysis.json"),
    Path("song_structure.json"),
)
canonical = result["canonical_record"]
assert canonical["meter"] == "4/4"
assert canonical["beat_grid_method"] == "standard"
assert canonical["phase_number"] == 3
assert canonical["complete"] is True

# Derived phase proof: detector index 2, confirmed index 0 in 4/4 => Phase 3.
record2 = {}
analysis2 = {
    "confirmed_meter": "4/4",
    "confirmed_beat_grid_method": "standard",
    "detected_first_downbeat_beat_index": 2,
    "confirmed_first_downbeat_beat_index": 0,
}
result2 = structure_engine.recover_manual_truth(
    record2,
    analysis2,
    {},
    "Derived Phase Proof",
    Path("record.json"),
    Path("song_analysis.json"),
    Path("song_structure.json"),
)
assert result2["canonical_record"]["phase_number"] == 3
assert result2["canonical_record"]["complete"] is True
assert result2["derived_values"]

# Conflict detection proof.
analysis3 = {
    "confirmed_meter": "3/4",
    "meter": "4/4",
}
result3 = structure_engine.recover_manual_truth(
    {},
    analysis3,
    {},
    "Conflict Proof",
    Path("record.json"),
    Path("song_analysis.json"),
    Path("song_structure.json"),
)
assert result3["canonical_record"]["meter"] == "3/4"
assert result3["conflicts"]

text = structure_engine.format_manual_truth_recovery(result2)
assert "SELECTED SOURCES" in text
assert "DERIVED VALUES" in text
assert "ALL LOCATED VALUES" in text
assert "Timing data changed: NO" in text

print("Banjofy Song Analysis Laboratory 022 complete release gate: passed")
