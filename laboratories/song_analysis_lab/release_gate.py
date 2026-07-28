from __future__ import annotations
import ast,copy,sys
from pathlib import Path
root=Path(__file__).resolve().parent
main_text=(root/'main.py').read_text(encoding='utf-8')
engine_text=(root/'structure_engine.py').read_text(encoding='utf-8')
spec_text=(root/'song_analysis_lab.spec').read_text(encoding='utf-8')
ast.parse(main_text); ast.parse(engine_text)
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 018 — Confirm Alternative Beat Grid"' in main_text
assert 'name="BanjofySongAnalysisLab018"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('"2/4"',"'2/4'",'"6/8"',"'6/8'",'Build 013'):
    assert forbidden not in main_text
for required in (
 'def build_confirmed_alternative_grid_updates(',
 'Confirm Selected Beat Grid and Rebuild Phases',
 'confirmed_beat_grid_method','beat_grid_confirmation_status',
 'alternative_grid','create_phase_auditions(',
 'Chord names and chord-change times will not be altered.',
): assert required in main_text
assert 'low_frequency' in engine_text
assert 'wav_source = prepare_wav(audio_path, Path(temporary_folder))' in engine_text
assert 'librosa.load(audio_path' not in engine_text
sys.path.insert(0,str(root)); import main
segments=[{'start_s':0.0,'end_s':4.0,'chord':'C'},{'start_s':4.0,'end_s':8.0,'chord':'G'}]
original=[i*.25 for i in range(48)]
low=[.1+i*.6 for i in range(20)]
analysis={
 'segments':copy.deepcopy(segments),'beat_times':list(original),'detected_beat_times':list(original),
 'confirmed_meter':'3/4','meter':'3/4','beats_per_bar':3,
 'detected_first_downbeat_beat_index':0,'raw_bpm':120.0,
 'alternative_beat_grids':{'low_frequency':{'label':'Low-frequency rhythm','bpm':100.0,'beat_times':low}}
}
record={'song_id':'tennessee-proof','structure_summary':{}}
r,a,s=main.build_confirmed_alternative_grid_updates(record,analysis,'low_frequency','2026-07-28 17:00:00')
assert a['detected_beat_times']==original
assert a['beat_times']==low
assert a['confirmed_beat_grid_method']=='low_frequency'
assert a['confirmed_beat_grid_label']=='Low-frequency rhythm'
assert a['beat_grid_confirmation_status']=='confirmed'
assert a['downbeat_phase_status']=='unconfirmed'
assert a['segments']==segments and a['raw_bpm']==120.0
assert a['beats_per_bar']==3 and a['bar_aligned_chords']
assert r['structure_summary']['confirmed_beat_grid_method']=='low_frequency'
print('Banjofy Song Analysis Laboratory 018 complete release gate: passed')
