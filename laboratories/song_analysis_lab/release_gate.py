from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "structure_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 009 — 3/4 and 4/4 Meter Check"' in main_text
assert 'name="BanjofySongAnalysisLab009"' in spec_text

# Agreed scope: exactly 3/4 and 4/4.
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
assert "Comparing 3/4 and 4/4 bar patterns" in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'", "Comparing 2/4"):
    assert forbidden not in engine_text
    assert forbidden not in main_text

# Safe Tkinter startup remains.
assert "def _root(" not in main_text
assert "self._root()" not in main_text
assert "def _library_root(self) -> Path | None:" in main_text

# M4A/MP4 audible route must use FFmpeg-prepared WAV only.
assert "wav_source = prepare_wav(audio_path, Path(temporary_folder))" in engine_text
assert "librosa.load(\n            wav_source," in engine_text
assert "librosa.load(audio_path" not in engine_text

# Audible output must precede any JSON commit.
audible_call = main_text.index("structure_engine.create_audible_bar_check(")
assert audible_call < main_text.index("write_json_atomic(structure_path")
assert audible_call < main_text.index("write_json_atomic(record_path")
assert audible_call < main_text.index("write_json_atomic(analysis_path")

sys.path.insert(0, str(root))
import main
import structure_engine

# Deterministic 3/4 and 4/4.
for beats_per_bar, expected, phase in ((3, "3/4", 1), (4, "4/4", 1)):
    accents = np.asarray(
        [3.0 if index % beats_per_bar == phase else 0.2 for index in range(96)],
        dtype=float,
    )
    best, candidates = structure_engine.infer_meter(accents)
    assert best.meter == expected
    assert best.beats_per_bar == beats_per_bar
    assert {item.meter for item in candidates} <= {"3/4", "4/4"}

# Real AAC/M4A to audible WAV, through application helper.
with tempfile.TemporaryDirectory(prefix="banjofy_sal009_m4a_") as temporary:
    folder = Path(temporary)
    sr = 22050
    duration = 8.0
    samples = np.zeros(int(sr * duration), dtype=np.float32)
    for beat in np.arange(0.5, duration, 0.5):
        start = int(beat * sr)
        samples[start:start + 250] += np.hanning(250).astype(np.float32) * 0.5

    wav = folder / "source.wav"
    m4a = folder / "source.m4a"
    audible = folder / "audible.wav"
    sf.write(wav, samples, sr)

    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(m4a),
    ], check=True)
    assert m4a.is_file() and m4a.stat().st_size > 1000

    structure_engine.create_audible_bar_check(
        m4a,
        [value for value in np.arange(0.5, duration, 0.5)],
        [0.5, 2.5, 4.5, 6.5],
        audible,
        preview_seconds=8.0,
    )
    assert audible.is_file() and audible.stat().st_size > 1000

# Atomic Library update using M4A source.
with tempfile.TemporaryDirectory(prefix="banjofy_sal009_library_") as temporary:
    library = Path(temporary)
    sr = 22050
    duration = 8.0
    wav = library / "source.wav"
    audio = library / "Media" / "Audio" / "proof.m4a"
    audio.parent.mkdir(parents=True)

    t = np.arange(int(sr * duration)) / sr
    sf.write(wav, (0.08 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr)
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(audio),
    ], check=True)

    record_path = library / "Library" / "Songs" / "proof.json"
    record_path.parent.mkdir(parents=True)
    analysis_path = library / "Analysis" / "proof" / "song_analysis.json"
    analysis_path.parent.mkdir(parents=True)

    segments = [{"start_s": 0.0, "end_s": duration, "chord": "G"}]
    record_path.write_text(json.dumps({
        "song_id": "proof",
        "title_requested": "Proof Song",
        "practice_audio_path": str(audio),
        "analysis_path": str(analysis_path),
        "analysis_status": "completed",
    }), encoding="utf-8")
    analysis_path.write_text(json.dumps({"segments": segments}), encoding="utf-8")

    beats = [value for value in np.arange(0.5, duration, 0.5)]
    beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
        beats, 4, 0, segments
    )
    result = structure_engine.StructureResult(
        structure_version=4,
        source_audio=str(audio),
        raw_bpm=120.0,
        beat_times=beats,
        beat_count=len(beats),
        meter="4/4",
        meter_status="confirmed",
        best_meter_candidate="4/4",
        beats_per_bar=4,
        meter_confidence=0.90,
        first_downbeat_beat_index=0,
        downbeat_times=downbeats,
        bar_start_times=downbeats,
        bar_count=len(bars),
        beat_grid=beat_grid,
        bars=bars,
        bar_aligned_chords=aligned,
        candidate_meters=[],
        diagnostics=["proof"],
    )
    structure_path, updated_record, updated_analysis, audible_path = main.commit_structure(
        library, record_path, analysis_path, result
    )
    assert audible_path.is_file()
    assert structure_path.is_file()
    assert json.loads(updated_record.read_text(encoding="utf-8"))["audible_bar_check_path"]
    assert json.loads(updated_analysis.read_text(encoding="utf-8"))["audible_bar_check_path"]

print("Banjofy Song Analysis Laboratory 009 complete release gate: passed")
