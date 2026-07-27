from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 008 — 3/4 and 4/4 Meter Check"' in main_text
assert 'name="BanjofySongAnalysisLab008"' in spec_text

# Agreed scope lock: 3/4 and 4/4 only.
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'"):
    assert forbidden not in engine_text, f"Forbidden meter returned: {forbidden}"
    assert forbidden not in main_text, f"Forbidden meter returned in UI: {forbidden}"

# Uncertainty handling.
for required in (
    "METER_CONFIDENCE_THRESHOLD = 0.55",
    'reported_meter = best.meter if meter_status == "confirmed" else "Uncertain"',
    'best_meter_candidate=best.meter',
    'meter_status=meter_status',
):
    assert required in engine_text, f"Missing uncertainty behaviour: {required}"

# Audible check.
for required in (
    "def create_audible_bar_check(",
    'audible_check_path = folder / "audible_bar_check.wav"',
    'text="Play Audible Bar Check"',
    '"audible_bar_check_path"',
):
    assert required in engine_text or required in main_text, f"Missing audible-check behaviour: {required}"

# Tkinter safety remains.
assert "def _root(" not in main_text
assert "self._root()" not in main_text
assert "def _library_root(self) -> Path | None:" in main_text
assert main_text.index("self.library_var = tk.StringVar") < main_text.index("self._load_settings()")

sys.path.insert(0, str(root))
import main
import structure_engine

# Deterministic 3/4 and 4/4 only.
for beats_per_bar, expected_meter, phase in (
    (3, "3/4", 1),
    (4, "4/4", 1),
):
    accents = np.asarray(
        [3.0 if index % beats_per_bar == phase else 0.2 for index in range(96)],
        dtype=float,
    )
    best, candidates = structure_engine.infer_meter(accents)
    assert best.meter == expected_meter, (expected_meter, best)
    assert best.beats_per_bar == beats_per_bar
    assert best.phase == phase
    assert {item.meter for item in candidates} <= {"3/4", "4/4"}

# Weak evidence must become Uncertain.
weak = np.zeros(96, dtype=float)
best, _ = structure_engine.infer_meter(weak)
status = "confirmed" if best.confidence >= structure_engine.METER_CONFIDENCE_THRESHOLD else "uncertain"
reported = best.meter if status == "confirmed" else "Uncertain"
assert reported == "Uncertain"

# Bar grid and audible WAV proof.
beats = [index * 0.5 for index in range(48)]
segments = [
    {"start_s": 0.0, "end_s": 8.0, "chord": "G"},
    {"start_s": 8.0, "end_s": 16.0, "chord": "C"},
    {"start_s": 16.0, "end_s": 24.5, "chord": "D"},
]
beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(beats, 4, 1, segments)
assert len(bars) >= 10
assert aligned and downbeats

with tempfile.TemporaryDirectory(prefix="banjofy_sal008_") as temporary:
    folder = Path(temporary)
    sr = 22050
    duration = 24.0
    times = np.arange(0.0, duration, 1.0 / sr)
    audio_data = (0.08 * np.sin(2 * np.pi * 220.0 * times)).astype(np.float32)
    audio = folder / "proof.wav"
    sf.write(audio, audio_data, sr)

    check = folder / "audible_bar_check.wav"
    structure_engine.create_audible_bar_check(
        audio, beats, downbeats, check, preview_seconds=20.0
    )
    assert check.is_file() and check.stat().st_size > 1000

    library = folder / "LibraryRoot"
    saved_audio = library / "Media" / "Audio" / "proof.wav"
    saved_audio.parent.mkdir(parents=True)
    saved_audio.write_bytes(audio.read_bytes())

    record_path = library / "Library" / "Songs" / "proof.json"
    record_path.parent.mkdir(parents=True)
    analysis_path = library / "Analysis" / "proof" / "song_analysis.json"
    analysis_path.parent.mkdir(parents=True)

    record_path.write_text(json.dumps({
        "song_id": "proof",
        "title_requested": "Proof Song",
        "practice_audio_path": str(saved_audio),
        "analysis_path": str(analysis_path),
        "analysis_status": "completed",
    }), encoding="utf-8")
    analysis_path.write_text(json.dumps({"segments": segments}), encoding="utf-8")

    result = structure_engine.StructureResult(
        structure_version=3,
        source_audio=str(saved_audio),
        raw_bpm=120.0,
        beat_times=beats,
        beat_count=len(beats),
        meter="4/4",
        meter_status="confirmed",
        best_meter_candidate="4/4",
        beats_per_bar=4,
        meter_confidence=0.90,
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

    paths = main.commit_structure(library, record_path, analysis_path, result)
    structure_path, updated_record, updated_analysis, audible_path = paths
    assert structure_path.is_file()
    assert audible_path.is_file() and audible_path.name == "audible_bar_check.wav"

    record = json.loads(updated_record.read_text(encoding="utf-8"))
    analysis = json.loads(updated_analysis.read_text(encoding="utf-8"))
    assert record["structure_summary"]["meter_status"] == "confirmed"
    assert record["structure_summary"]["best_meter_candidate"] == "4/4"
    assert Path(record["audible_bar_check_path"]).is_file()
    assert analysis["best_meter_candidate"] == "4/4"
    assert analysis["audible_bar_check_path"]

print("Banjofy Song Analysis Laboratory 008 complete release gate: passed")
