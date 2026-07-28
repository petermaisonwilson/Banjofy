from __future__ import annotations

import ast
import copy
import json
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 014 — Confirm Downbeat Phase"' in main_text
assert 'name="BanjofySongAnalysisLab014"' in spec_text

# Agreed scope remains exact.
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'", '"6/8"', "'6/8'"):
    assert forbidden not in engine_text
    assert forbidden not in main_text

# Build 013 audition remains.
for required in (
    "downbeat_phase_audition_paths",
    "def _set_visual_phase(",
    "def _phase_downbeat_times(",
    "audible_phase_",
    "AUDIBLE_PREVIEW_SECONDS = 180.0",
):
    assert required in main_text or required in engine_text

# Build 014 confirmation requirements.
for required in (
    "def build_confirmed_phase_updates(",
    'text="Confirm Selected Phase"',
    "def _confirm_selected_phase(",
    '"downbeat_phase_status": "confirmed"',
    '"confirmed_phase_number"',
    '"confirmed_phase_offset"',
    '"detected_first_downbeat_beat_index"',
    '"confirmed_first_downbeat_beat_index"',
    '"downbeat_phase_confirmed_by": "manual_audition"',
    "structure_engine.build_bar_grid(",
):
    assert required in main_text

# Confirmation must preserve detector data and must not alter chord segments/BPM.
helper_start = main_text.index("def build_confirmed_phase_updates(")
helper_end = main_text.index("def commit_structure(", helper_start)
helper = main_text[helper_start:helper_end]
assert 'analysis.get("segments", [])' in helper
assert 'analysis.get("beat_times", [])' in helper
for forbidden_assignment in (
    'updated_analysis["segments"] =',
    'updated_analysis["raw_bpm"] =',
    'updated_analysis["best_meter_candidate"] =',
):
    assert forbidden_assignment not in helper

# Central M4A route and Tk safety remain.
assert "wav_source = prepare_wav(audio_path, Path(temporary_folder))" in engine_text
assert "librosa.load(audio_path" not in engine_text
assert "def _root(" not in main_text
assert "def _library_root(self) -> Path | None:" in main_text

import sys
sys.path.insert(0, str(root))
import main

segments = [
    {"start_s": 0.0, "end_s": 2.0, "chord": "Am"},
    {"start_s": 2.0, "end_s": 4.0, "chord": "E7"},
    {"start_s": 4.0, "end_s": 8.5, "chord": "G"},
]
beat_times = [index * 0.5 for index in range(16)]
record = {
    "song_id": "proof",
    "structure_summary": {
        "first_downbeat_beat_index": 2,
        "bar_count": 3,
    },
}
analysis = {
    "segments": copy.deepcopy(segments),
    "beat_times": list(beat_times),
    "beats_per_bar": 4,
    "first_downbeat_beat_index": 2,
    "best_meter_candidate": "4/4",
    "raw_bpm": 120.0,
}

updated_record, updated_analysis, structure_updates = (
    main.build_confirmed_phase_updates(
        record,
        analysis,
        selected_phase_number=3,
        confirmed_at="2026-07-28 15:00:00",
    )
)

# Hotel California proof: detected index 2 + Phase 3 offset 2 = confirmed index 0.
assert updated_analysis["detected_first_downbeat_beat_index"] == 2
assert updated_analysis["confirmed_phase_number"] == 3
assert updated_analysis["confirmed_phase_offset"] == 2
assert updated_analysis["confirmed_first_downbeat_beat_index"] == 0
assert updated_analysis["first_downbeat_beat_index"] == 0
assert updated_analysis["downbeat_phase_status"] == "confirmed"
assert updated_analysis["downbeat_phase_confirmed_by"] == "manual_audition"

# Bars and aligned chords must be rebuilt from index 0.
assert updated_analysis["downbeat_times"][0] == 0.0
assert updated_analysis["bar_count"] == 4
assert updated_analysis["bars"][0]["bar_number"] == 1
assert updated_analysis["bar_aligned_chords"]
assert updated_record["structure_summary"]["confirmed_phase_number"] == 3
assert structure_updates["confirmed_first_downbeat_beat_index"] == 0

# Proven musical data must remain byte-for-byte equivalent as Python values.
assert updated_analysis["segments"] == segments
assert updated_analysis["beat_times"] == beat_times
assert updated_analysis["best_meter_candidate"] == "4/4"
assert updated_analysis["raw_bpm"] == 120.0

# Direct 3/4 proof too.
analysis_34 = dict(analysis)
analysis_34["beats_per_bar"] = 3
analysis_34["first_downbeat_beat_index"] = 1
record_34, result_34, structure_34 = main.build_confirmed_phase_updates(
    record,
    analysis_34,
    selected_phase_number=3,
    confirmed_at="2026-07-28 15:00:00",
)
assert result_34["confirmed_first_downbeat_beat_index"] == 0
assert result_34["confirmed_phase_number"] == 3

print("Banjofy Song Analysis Laboratory 014 complete release gate: passed")
