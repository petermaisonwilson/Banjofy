from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 016 — Pulse, Meter and Phase Validation"' in main_text
assert 'name="BanjofySongAnalysisLab016"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text

for forbidden in ('"2/4"', "'2/4'", '"6/8"', "'6/8'", "Build 013"):
    assert forbidden not in main_text

for required in (
    "def pulse_times_for_mode(",
    "def build_confirmed_pulse_updates(",
    "def create_phase_auditions(",
    "def persist_phase_audition_paths(",
    "Half pulse A",
    "Half pulse B",
    "Apply Pulse and Rebuild Phase Auditions",
    "Rebuilding missing or mismatched phase audition files in Build 016",
    "Reset confirmed timing and continue?",
):
    assert required in main_text

assert "detected_beat_times" in main_text
assert "pulse_interpretation" in main_text
assert "pulse_confirmation_status" in main_text
assert "wav_source = prepare_wav(audio_path, Path(temporary_folder))" in engine_text
assert "librosa.load(audio_path" not in engine_text
assert "def _root(" not in main_text

sys.path.insert(0, str(root))
import main

segments = [
    {"start_s": 0.0, "end_s": 4.0, "chord": "C"},
    {"start_s": 4.0, "end_s": 8.0, "chord": "G"},
]
detected = [index * 0.25 for index in range(48)]
analysis = {
    "segments": copy.deepcopy(segments),
    "beat_times": list(detected),
    "detected_beat_times": list(detected),
    "beats_per_bar": 3,
    "meter": "3/4",
    "confirmed_meter": "3/4",
    "first_downbeat_beat_index": 0,
    "detected_first_downbeat_beat_index": 0,
    "raw_bpm": 120.0,
    "best_meter_candidate": "4/4",
}
record = {"song_id": "tennessee-proof", "structure_summary": {}}

assert main.pulse_times_for_mode(analysis, "detected") == detected
assert main.pulse_times_for_mode(analysis, "half_a") == detected[0::2]
assert main.pulse_times_for_mode(analysis, "half_b") == detected[1::2]

record2, analysis2, structure2 = main.build_confirmed_pulse_updates(
    record,
    analysis,
    "half_a",
    "2026-07-28 16:00:00",
)
assert analysis2["detected_beat_times"] == detected
assert analysis2["beat_times"] == detected[0::2]
assert analysis2["pulse_interpretation"] == "half_a"
assert analysis2["pulse_confirmation_status"] == "confirmed"
assert analysis2["downbeat_phase_status"] == "unconfirmed"
assert analysis2["segments"] == segments
assert analysis2["raw_bpm"] == 120.0
assert analysis2["best_meter_candidate"] == "4/4"
assert analysis2["beats_per_bar"] == 3
assert analysis2["bar_aligned_chords"]
assert record2["structure_summary"]["pulse_interpretation"] == "half_a"

# Reapplying detected pulse must restore the original beat list.
_, restored, _ = main.build_confirmed_pulse_updates(
    record2,
    analysis2,
    "detected",
    "2026-07-28 16:01:00",
)
assert restored["beat_times"] == detected

print("Banjofy Song Analysis Laboratory 016 complete release gate: passed")
