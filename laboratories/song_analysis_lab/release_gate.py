from __future__ import annotations

import ast
import json
import os
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
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 011 — Whole-Track Meter with Visual Check"' in main_text
assert 'name="BanjofySongAnalysisLab011"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('(2, "2/4")', '"2/4"', "'2/4'", '6/8'):
    assert forbidden not in engine_text
    assert forbidden not in main_text

# Build 010 regression must be structurally impossible.
assert 'def choose_primary_meter(' in engine_text
assert 'return full_best, agreement' in engine_text
assert 'global_phase = (rhythmic_best.phase + rhythmic_start)' not in engine_text
assert 'best, meter_candidate_agreement = choose_primary_meter(full_best, rhythmic_best)' in engine_text
assert 'beat_times, best.beats_per_bar, best.phase' in engine_text
assert 'meter_candidate_agreement' in engine_text
assert 'rhythmic_window_candidate' in engine_text
assert 'rhythmic_window_meter_confidence' in engine_text

# Build 010 visual and extended M4A proof remain.
assert 'AUDIBLE_PREVIEW_SECONDS = 180.0' in engine_text
assert 'wav_source = prepare_wav(audio_path, Path(temporary_folder))' in engine_text
assert 'librosa.load(audio_path' not in engine_text
assert 'text="Play 180-Second Audible + Visual Check"' in main_text
assert 'def _open_visual_window' in main_text
assert 'def _update_visual_marker' in main_text
assert 'winsound.PlaySound' in main_text
assert 'def _root(' not in main_text

sys.path.insert(0, str(root))
import structure_engine as s

# Direct disagreement rule: whole-track 4/4 cannot be overturned by window 3/4.
full = s.MeterCandidate('4/4', 4, 2, 0.3, 0.21)
window = s.MeterCandidate('3/4', 3, 0, 0.4, 0.23)
primary, agreement = s.choose_primary_meter(full, window)
assert primary is full
assert primary.meter == '4/4'
assert primary.beats_per_bar == 4
assert primary.phase == 2
assert agreement is False

# Agreement case remains available.
window4 = s.MeterCandidate('4/4', 4, 1, 0.8, 0.70)
primary2, agreement2 = s.choose_primary_meter(full, window4)
assert primary2 is full and agreement2 is True

# Direct 3/4 and 4/4 inference proofs.
for count, expected in ((3, '3/4'), (4, '4/4')):
    accents = np.asarray([3.0 if i % count == 1 else 0.2 for i in range(96)], dtype=float)
    best, candidates = s.infer_meter(accents)
    assert best.meter == expected
    assert {c.meter for c in candidates} == {'3/4', '4/4'}

# Real AAC/M4A through central FFmpeg route to audible WAV.
with tempfile.TemporaryDirectory(prefix='sal011_m4a_') as temporary:
    folder = Path(temporary)
    sr = 22050
    duration = 12.0
    t = np.arange(int(sr * duration)) / sr
    wav = folder / 'source.wav'
    m4a = folder / 'source.m4a'
    audible = folder / 'audible.wav'
    sf.write(wav, (0.08 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr)
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-hide_banner', '-loglevel', 'error',
        '-i', str(wav), '-c:a', 'aac', '-b:a', '192k', str(m4a)
    ], check=True)
    s.create_audible_bar_check(
        m4a,
        [float(v) for v in np.arange(0.5, duration, 0.5)],
        [float(v) for v in np.arange(0.5, duration, 2.0)],
        audible,
    )
    assert audible.is_file() and audible.stat().st_size > 1000

print('Banjofy Song Analysis Laboratory 011 complete release gate: passed')
