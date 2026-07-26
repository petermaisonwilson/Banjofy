from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
main_text = (root / "main.py").read_text(encoding="utf-8")
engine_text = (root / "analysis_engine.py").read_text(encoding="utf-8")
spec_text = (root / "song_analysis_lab.spec").read_text(encoding="utf-8")

ast.parse(main_text)
ast.parse(engine_text)

required_main = [
    'APP_TITLE = "Banjofy Song Analysis Laboratory 001"',
    'def discover_library_songs(library_root: Path)',
    'def resolve_record_audio(record: dict, record_path: Path)',
    'def commit_analysis_to_library(',
    'analysis_engine.analyse_audio(',
    '"analysis_status"] = "completed"',
    '"analysis_summary"] = {',
    'text="Analyse Selected Library Song"',
]
for text in required_main:
    assert text in main_text, f"Missing integration implementation: {text}"

required_engine = [
    'ANALYSIS_VERSION = 16',
    'class AnalysisResult:',
    'def analyse_audio(',
    'def detect_beats(',
    'def infer_key(',
    'def run_internal_self_audit()',
]
for text in required_engine:
    assert text in engine_text, f"Missing proven engine implementation: {text}"

assert 'name="BanjofySongAnalysisLab001"' in spec_text
assert 'datas = [(str(chordmini), "ChordMini")]' in spec_text

sys.path.insert(0, str(root))
import analysis_engine
import main

with tempfile.TemporaryDirectory(prefix="banjofy_sal001_gate_") as temporary:
    library = Path(temporary)
    audio = library / "Media" / "Audio" / "proof.m4a"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"proof-audio-placeholder")

    record_path = library / "Library" / "Songs" / "proof-song.json"
    record_path.parent.mkdir(parents=True)
    record_path.write_text(json.dumps({
        "song_id": "proof-song",
        "title_requested": "Proof Song",
        "practice_audio_path": str(audio),
        "duration_seconds": 12.0,
        "analysis_status": "not_started",
    }), encoding="utf-8")

    songs = main.discover_library_songs(library)
    assert len(songs) == 1
    assert songs[0]["audio_path"] == audio

    result = analysis_engine.AnalysisResult(
        source_audio=str(audio),
        model=analysis_engine.MODEL_NAME,
        analysis_version=16,
        key="G major",
        key_confidence=0.91,
        bpm=100.0,
        raw_bpm=100.0,
        practice_bpm=100.0,
        meter="Unknown",
        meter_confidence=0.0,
        beat_count=20,
        main_chords=["G", "C", "D"],
        beginner_chords=["G", "C", "D"],
        intermediate_chords=["G", "C", "D"],
        professional_chords=["G", "C", "D"],
        musical_end_s=12.0,
        raw_segment_count=3,
        cleaned_segment_count=3,
        duration_s=12.0,
        segments=[
            analysis_engine.ChordSegment(0.0, 4.0, "G", 4.0),
            analysis_engine.ChordSegment(4.0, 8.0, "C", 4.0),
            analysis_engine.ChordSegment(8.0, 12.0, "D", 4.0),
        ],
        diagnostics=["integration proof"],
        detector_disagreements=[],
        chord_importance=[],
    )
    analysis_path, updated_path = main.commit_analysis_to_library(library, record_path, result)
    assert analysis_path.is_file()
    updated = json.loads(updated_path.read_text(encoding="utf-8"))
    assert updated["analysis_status"] == "completed"
    assert updated["analysis_summary"]["key"] == "G major"
    assert updated["analysis_summary"]["practice_bpm"] == 100.0
    assert updated["analysis_summary"]["main_chords"] == ["G", "C", "D"]

print("Banjofy Song Analysis Laboratory 001 release gate: passed")
