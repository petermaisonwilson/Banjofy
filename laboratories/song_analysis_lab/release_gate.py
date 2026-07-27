from __future__ import annotations

import ast
import json
import os
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

ast.parse(main_text)
ast.parse(engine_text)

# Exact release identity.
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 007 — Meter, Bars and Downbeats"' in main_text
assert 'name="BanjofySongAnalysisLab007"' in spec_text

# Tkinter reserved-name collision must never return.
assert "def _root(" not in main_text
assert "self._root()" not in main_text
assert "def _library_root(self) -> Path | None:" in main_text
assert main_text.count("self._library_root()") == 3

# Variables precede settings.
assert main_text.index("self.library_var = tk.StringVar") < main_text.index("self._load_settings()")

# Safe automatic refresh.
for required in (
    'saved_library = self.library_var.get().strip()',
    'Path(saved_library).is_dir() and not startup_probe',
    'elif saved_library and not Path(saved_library).is_dir():',
    '"The remembered Library folder is currently unavailable.',
):
    assert required in main_text, f"Missing safe saved-Library startup behaviour: {required}"

# Positive startup handshake.
for required in (
    'BANJOFY_STARTUP_PROBE_FILE',
    '"status": "ready"',
    '"library_setting": app.library_var.get()',
    "app.after(300, app.destroy)",
):
    assert required in main_text, f"Missing startup handshake: {required}"

# Required application integration.
for required in (
    "def load_library_setting(path: Path | None = None) -> str:",
    "def discover_analysed_songs(library_root: Path)",
    "def commit_structure(",
    'text="Detect Meter, Bars and Downbeats"',
):
    assert required in main_text, f"Missing application behaviour: {required}"

# Required structure engine.
for required in (
    'SUPPORTED_METERS = ((2, "2/4"), (3, "3/4"), (4, "4/4"))',
    "def infer_meter(accents: np.ndarray)",
    "def build_bar_grid(",
    "def analyse_structure(",
    "bar_aligned_chords",
):
    assert required in engine_text, f"Missing structure behaviour: {required}"

sys.path.insert(0, str(root))
import main
import structure_engine

# Settings parser: missing, valid, malformed and wrong shape.
with tempfile.TemporaryDirectory(prefix="banjofy_sal007_settings_") as temporary:
    folder = Path(temporary)
    settings = folder / "song_analysis_lab_settings.json"

    assert main.load_library_setting(settings) == ""

    expected = r"C:\Existing Banjofy Library"
    settings.write_text(json.dumps({"library_root": expected}), encoding="utf-8")
    assert main.load_library_setting(settings) == expected

    settings.write_text("{broken", encoding="utf-8")
    assert main.load_library_setting(settings) == ""

    settings.write_text(json.dumps(["wrong", "shape"]), encoding="utf-8")
    assert main.load_library_setting(settings) == ""

# Deterministic meter proofs.
for beats_per_bar, expected_meter, phase in (
    (2, "2/4", 1),
    (3, "3/4", 1),
    (4, "4/4", 1),
):
    accents = np.asarray(
        [3.0 if index % beats_per_bar == phase else 0.2 for index in range(72)],
        dtype=float,
    )
    best, _ = structure_engine.infer_meter(accents)
    assert best.meter == expected_meter, (expected_meter, best)
    assert best.beats_per_bar == beats_per_bar
    assert best.phase == phase

# Beat/bar/chord grid.
beats = [index * 0.5 for index in range(36)]
segments = [
    {"start_s": 0.0, "end_s": 6.0, "chord": "G"},
    {"start_s": 6.0, "end_s": 12.0, "chord": "C"},
    {"start_s": 12.0, "end_s": 18.5, "chord": "D"},
]
beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
    beats, 4, 1, segments
)
assert len(bars) >= 8
assert beat_grid[1]["is_downbeat"] is True
assert aligned and aligned[0]["chords"]
assert len(downbeats) == len(bars)

# Real temporary Library and atomic updates.
with tempfile.TemporaryDirectory(prefix="banjofy_sal007_library_") as temporary:
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

    assert structure_path.name == "song_structure.json"
    assert updated_record.name == "proof.json"
    assert updated_analysis.name == "song_analysis.json"

    record = json.loads(updated_record.read_text(encoding="utf-8"))
    analysis = json.loads(updated_analysis.read_text(encoding="utf-8"))
    structure = json.loads(structure_path.read_text(encoding="utf-8"))

    assert record["structure_status"] == "completed"
    assert record["structure_summary"]["meter"] == "4/4"
    assert analysis["bar_count"] == len(bars)
    assert analysis["bar_aligned_chords"]
    assert structure["meter"] == "4/4"

print("Banjofy Song Analysis Laboratory 007 complete release gate: passed")
