from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert main_text.index("self.library_var = tk.StringVar") < main_text.index("self._load_settings()"), (
    "library_var must be created before settings are loaded"
)
assert 'def load_library_setting(path: Path | None = None) -> str:' in main_text
assert 'if hasattr(self, "library_var"):' in main_text

for required in [
    'APP_TITLE = "Banjofy Song Analysis Laboratory 004 — Meter, Bars and Downbeats"',
    'def discover_analysed_songs(library_root: Path)',
    'def commit_structure(',
    'text="Detect Meter, Bars and Downbeats"',
    '"The existing JSON filenames have not changed.',
]:
    assert required in main_text, f"Missing main implementation: {required}"

for required in [
    'SUPPORTED_METERS = ((2, "2/4"), (3, "3/4"), (4, "4/4"))',
    'def infer_meter(accents: np.ndarray)',
    'def build_bar_grid(',
    'def analyse_structure(',
    'bar_aligned_chords',
]:
    assert required in engine_text, f"Missing structure implementation: {required}"

assert 'name="BanjofySongAnalysisLab004"' in spec_text
assert '"torch"' in spec_text and 'excludes=' in spec_text

sys.path.insert(0, str(root))
import main
import structure_engine

with tempfile.TemporaryDirectory(prefix="banjofy_sal004_settings_") as saved:
    saved_path = Path(saved) / "song_analysis_lab_settings.json"
    saved_path.write_text(
        json.dumps({"library_root": r"C:\\Existing Banjofy Library"}),
        encoding="utf-8",
    )
    assert main.load_library_setting(saved_path) == r"C:\Existing Banjofy Library"
    saved_path.write_text("{broken", encoding="utf-8")
    assert main.load_library_setting(saved_path) == ""

# Direct deterministic meter proof: strong accent every four beats.
accents = np.asarray([3.0 if index % 4 == 1 else 0.2 for index in range(48)], dtype=float)
best, candidates = structure_engine.infer_meter(accents)
assert best.meter == "4/4", best
assert best.phase == 1, best

beats = [index * 0.5 for index in range(24)]
segments = [
    {"start_s": 0.0, "end_s": 4.0, "chord": "G"},
    {"start_s": 4.0, "end_s": 8.0, "chord": "C"},
    {"start_s": 8.0, "end_s": 12.5, "chord": "D"},
]
beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(beats, 4, 1, segments)
assert len(bars) >= 5
assert bars[0]["bar_number"] == 1
assert beat_grid[1]["is_downbeat"] is True
assert aligned[0]["chords"]

with tempfile.TemporaryDirectory(prefix="banjofy_sal002_gate_") as temporary:
    library = Path(temporary)
    audio = library / "Media" / "Audio" / "proof.m4a"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"placeholder")

    record_path = library / "Library" / "Songs" / "proof.json"
    record_path.parent.mkdir(parents=True)
    analysis_path = library / "Analysis" / "proof" / "song_analysis.json"
    analysis_path.parent.mkdir(parents=True)

    record_path.write_text(json.dumps({
        "song_id": "proof",
        "title_requested": "Proof Song",
        "practice_audio_path": str(audio),
        "analysis_path": str(analysis_path),
        "analysis_status": "completed",
    }), encoding="utf-8")
    analysis_path.write_text(json.dumps({"segments": segments, "meter": "Unknown"}), encoding="utf-8")

    songs = main.discover_analysed_songs(library)
    assert len(songs) == 1

    result = structure_engine.StructureResult(
        structure_version=2,
        source_audio=str(audio),
        raw_bpm=120.0,
        beat_times=beats,
        beat_count=len(beats),
        meter="4/4",
        beats_per_bar=4,
        meter_confidence=0.88,
        first_downbeat_beat_index=1,
        downbeat_times=downbeats,
        bar_start_times=downbeats,
        bar_count=len(bars),
        beat_grid=beat_grid,
        bars=bars,
        bar_aligned_chords=aligned,
        candidate_meters=[{"meter": "4/4", "score": 2.0}],
        diagnostics=["proof"],
    )
    structure_path, updated_record, updated_analysis = main.commit_structure(
        library, record_path, analysis_path, result
    )
    assert structure_path.is_file()
    record = json.loads(updated_record.read_text(encoding="utf-8"))
    analysis = json.loads(updated_analysis.read_text(encoding="utf-8"))
    assert record["structure_status"] == "completed"
    assert record["structure_summary"]["meter"] == "4/4"
    assert analysis["bar_count"] == len(bars)
    assert analysis["bar_aligned_chords"]

print("Banjofy Song Analysis Laboratory 004 release gate: passed")
