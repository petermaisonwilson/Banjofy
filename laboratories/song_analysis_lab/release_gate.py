from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 012 — Visual Chord and Bar Alignment Check"' in main_text
assert 'name="BanjofySongAnalysisLab012"' in spec_text

# Confirm the passed Build 011 meter rules remain untouched.
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
assert 'best, meter_candidate_agreement = choose_primary_meter(full_best, rhythmic_best)' in engine_text
assert 'best_meter_candidate=best.meter' in engine_text
assert 'beats_per_bar=best.beats_per_bar' in engine_text
assert 'meter_candidate_agreement=meter_candidate_agreement' in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'", '"6/8"', "'6/8'"):
    assert forbidden not in engine_text
    assert forbidden not in main_text

# Confirm central media loading and existing long audible proof remain.
assert 'AUDIBLE_PREVIEW_SECONDS = 180.0' in engine_text
assert 'wav_source = prepare_wav(audio_path, Path(temporary_folder))' in engine_text
assert 'librosa.load(audio_path' not in engine_text

# Build 012 must consume, not regenerate, saved chord segments.
for required in (
    'raw_segments = analysis.get("segments", [])',
    'self.visual_chord_segments',
    'def _chord_display_at(self, elapsed: float)',
    'textvariable=self.visual_current_chord_var',
    'textvariable=self.visual_next_chord_var',
    'textvariable=self.visual_change_var',
    'Current chord',
    'Next chord:',
    'Change in:',
):
    assert required in main_text

# No new chord-analysis call is permitted in the playback route.
playback = main_text[main_text.index('    def _play_audible_check'):main_text.index('    def _open_folder')]
assert 'analyse_structure(' not in playback
assert 'write_json_atomic(' not in playback

# Direct chord-timeline boundary proof without a graphical proxy.
sys.path.insert(0, str(root))
import main
app = object.__new__(main.App)
app.visual_chord_segments = [
    {"start_s": 1.0, "end_s": 3.0, "chord": "Am"},
    {"start_s": 3.0, "end_s": 5.5, "chord": "E7"},
    {"start_s": 5.5, "end_s": 9.0, "chord": "G"},
]
assert app._chord_display_at(0.5) == ("—", "Am", 0.5)
assert app._chord_display_at(1.0) == ("Am", "E7", 2.0)
assert app._chord_display_at(2.25) == ("Am", "E7", 0.75)
assert app._chord_display_at(3.0) == ("E7", "G", 2.5)
assert app._chord_display_at(8.0) == ("G", "—", None)
assert app._chord_display_at(10.0) == ("—", "—", None)

print("Banjofy Song Analysis Laboratory 012 complete release gate: passed")
