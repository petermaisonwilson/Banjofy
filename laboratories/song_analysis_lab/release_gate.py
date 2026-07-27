from __future__ import annotations

import ast
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 013 — Downbeat Phase Audition"' in main_text
assert 'name="BanjofySongAnalysisLab013"' in spec_text

assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'", '"6/8"', "'6/8'"):
    assert forbidden not in engine_text
    assert forbidden not in main_text

for required in (
    "downbeat_phase_audition_paths",
    "audible_phase_",
    "def _set_visual_phase(",
    "def _effective_first_downbeat_index(",
    "def _phase_downbeat_times(",
    "Choose a phase; playback restarts from the beginning:",
    "DOWNBEAT — selected phase",
):
    assert required in main_text

assert "for phase_offset in range(beats_per_bar):" in main_text
assert "int(result.first_downbeat_beat_index) + phase_offset" in main_text
assert "AUDIBLE_PREVIEW_SECONDS = 180.0" in engine_text
assert "wav_source = prepare_wav(audio_path, Path(temporary_folder))" in engine_text
assert "librosa.load(audio_path" not in engine_text
assert "def _root(" not in main_text
assert "def _library_root(self) -> Path | None:" in main_text

phase_start = main_text.index("def _set_visual_phase(")
phase_end = main_text.index("def _effective_first_downbeat_index(", phase_start)
phase_block = main_text[phase_start:phase_end]
for forbidden_write in ("write_json_atomic", "commit_structure", "updated_analysis"):
    assert forbidden_write not in phase_block

print("Banjofy Song Analysis Laboratory 013 complete release gate: passed")
