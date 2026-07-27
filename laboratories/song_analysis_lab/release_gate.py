from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

root = Path(__file__).resolve().parent
main_path = root / "main.py"
engine_path = root / "structure_engine.py"
spec_path = root / "song_analysis_lab.spec"

main_text = main_path.read_text(encoding="utf-8")
engine_text = engine_path.read_text(encoding="utf-8")
spec_text = spec_path.read_text(encoding="utf-8")

# 1. Syntax and exact identity
ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 005 — Meter, Bars and Downbeats"' in main_text
assert 'name="BanjofySongAnalysisLab005"' in spec_text
assert 'SUPPORTED_METERS = ((2, "2/4"), (3, "3/4"), (4, "4/4"))' in engine_text

# 2. Exact initialization order
library_creation = main_text.index("self.library_var = tk.StringVar")
settings_load = main_text.index("self._load_settings()")
assert library_creation < settings_load, "library_var must exist before persisted settings are loaded"
assert 'def load_library_setting(path: Path | None = None) -> str:' in main_text
assert 'if hasattr(self, "library_var"):' in main_text

# 3. Required integration behaviour
for required in [
    "def discover_analysed_songs(library_root: Path)",
    "def commit_structure(",
    'text="Detect Meter, Bars and Downbeats"',
    '"The existing JSON filenames have not changed.',
    '"structure_status"] = "completed"',
    'analysis["bar_aligned_chords"] = result.bar_aligned_chords',
]:
    assert required in main_text, f"Missing main implementation: {required}"

for required in [
    "def infer_meter(accents: np.ndarray)",
    "def build_bar_grid(",
    "def analyse_structure(",
    "bar_aligned_chords",
    "downbeat_times",
]:
    assert required in engine_text, f"Missing structure implementation: {required}"

sys.path.insert(0, str(root))
import main
import structure_engine

# 4. Persisted settings: missing, valid, malformed, wrong JSON shape
with tempfile.TemporaryDirectory(prefix="banjofy_sal005_settings_") as temporary:
    folder = Path(temporary)
    settings = folder / "song_analysis_lab_settings.json"

    assert main.load_library_setting(settings) == ""

    expected_library = str(folder / "Existing Banjofy Library")
    settings.write_text(json.dumps({"library_root": expected_library}), encoding="utf-8")
    assert main.load_library_setting(settings) == expected_library

    settings.write_text("{broken", encoding="utf-8")
    assert main.load_library_setting(settings) == ""

    settings.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    assert main.load_library_setting(settings) == ""

# 5. Direct deterministic meter proofs: 2/4, 3/4 and 4/4
for beats_per_bar, label, phase in (
    (2, "2/4", 0),
    (3, "3/4", 1),
    (4, "4/4", 1),
):
    accents = np.asarray(
        [3.0 if index % beats_per_bar == phase else 0.2 for index in range(72)],
        dtype=float,
    )
    best, candidates = structure_engine.infer_meter(accents)
    assert best.meter == label, (label, best)
    assert best.beats_per_bar == beats_per_bar
    assert best.phase == phase
    assert candidates

# 6. Direct beat/bar/chord grid proof
beats = [index * 0.5 for index in range(32)]
segments = [
    {"start_s": 0.0, "end_s": 4.0, "chord": "G"},
    {"start_s": 4.0, "end_s": 8.0, "chord": "C"},
    {"start_s": 8.0, "end_s": 16.5, "chord": "D"},
]
beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
    beats, 4, 1, segments
)
assert beat_grid[1]["is_downbeat"] is True
assert len(bars) >= 7
assert len(downbeats) == len(bars)
assert aligned and aligned[0]["chords"]

# 7. Real temporary Library discovery and atomic JSON updates
with tempfile.TemporaryDirectory(prefix="banjofy_sal005_library_") as temporary:
    library = Path(temporary)
    audio = library / "Media" / "Audio" / "proof.m4a"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"placeholder")

    record_path = library / "Library" / "Songs" / "proof.json"
    record_path.parent.mkdir(parents=True)
    analysis_path = library / "Analysis" / "proof" / "song_analysis.json"
    analysis_path.parent.mkdir(parents=True)

    record_path.write_text(
        json.dumps({
            "song_id": "proof",
            "title_requested": "Proof Song",
            "practice_audio_path": str(audio),
            "analysis_path": str(analysis_path),
            "analysis_status": "completed",
        }),
        encoding="utf-8",
    )
    analysis_path.write_text(
        json.dumps({"segments": segments, "meter": "Unknown"}),
        encoding="utf-8",
    )

    songs = main.discover_analysed_songs(library)
    assert len(songs) == 1
    assert songs[0]["audio_path"] == audio
    assert songs[0]["analysis_path"] == analysis_path

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
        diagnostics=["full release-gate proof"],
    )

    structure_path, updated_record, updated_analysis = main.commit_structure(
        library, record_path, analysis_path, result
    )

    assert structure_path.is_file()
    assert updated_record.name == "proof.json"
    assert updated_analysis.name == "song_analysis.json"

    record = json.loads(updated_record.read_text(encoding="utf-8"))
    analysis = json.loads(updated_analysis.read_text(encoding="utf-8"))
    structure = json.loads(structure_path.read_text(encoding="utf-8"))

    assert record["structure_status"] == "completed"
    assert record["structure_summary"]["meter"] == "4/4"
    assert record["structure_summary"]["bar_count"] == len(bars)
    assert analysis["meter"] == "4/4"
    assert analysis["bar_count"] == len(bars)
    assert analysis["bar_aligned_chords"]
    assert structure["meter"] == "4/4"
    assert structure["downbeat_times"]

print("Banjofy Song Analysis Laboratory 005 full release gate: passed")
