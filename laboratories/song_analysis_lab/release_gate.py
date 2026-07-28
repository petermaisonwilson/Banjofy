from __future__ import annotations
import ast, copy, sys
from pathlib import Path
root=Path(__file__).resolve().parent
main_text=(root/'main.py').read_text(encoding='utf-8')
engine_text=(root/'structure_engine.py').read_text(encoding='utf-8')
spec_text=(root/'song_analysis_lab.spec').read_text(encoding='utf-8')
ast.parse(main_text); ast.parse(engine_text)
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 015 — Confirm Meter and Downbeat Phase"' in main_text
assert 'name="BanjofySongAnalysisLab015"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('(2, "2/4")','"2/4"',"'2/4'",'"6/8"',"'6/8'"):
    assert forbidden not in engine_text
for required in (
    'def build_confirmed_meter_updates(',
    'Apply Meter and Rebuild Phase Auditions',
    'def _confirm_selected_meter(',
    'meter_confirmation_status',
    'detected_meter_candidate',
    'confirmed_meter',
    'meter_confirmed_by',
    'meter_confirmed_at',
    'remove_phase_confirmation_keys',
    'def build_confirmed_phase_updates(',
    'Confirm Selected Phase',
): assert required in main_text
assert 'wav_source = prepare_wav(audio_path, Path(temporary_folder))' in engine_text
assert 'librosa.load(audio_path' not in engine_text
assert 'def _root(' not in main_text
sys.path.insert(0,str(root)); import main
segments=[{'start_s':0.0,'end_s':2.0,'chord':'C'},{'start_s':2.0,'end_s':4.0,'chord':'F'},{'start_s':4.0,'end_s':8.0,'chord':'G'}]
beats=[i*.5 for i in range(18)]
record={'song_id':'proof','structure_summary':{'beats_per_bar':4}}
analysis={'segments':copy.deepcopy(segments),'beat_times':list(beats),'beats_per_bar':4,'first_downbeat_beat_index':2,'best_meter_candidate':'4/4','meter':'Uncertain','raw_bpm':120.0,'confirmed_phase_number':3,'confirmed_phase_offset':2,'confirmed_first_downbeat_beat_index':0,'downbeat_phase_status':'confirmed'}
r,a,s=main.build_confirmed_meter_updates(record,analysis,'3/4','2026-07-28 16:00:00')
assert a['detected_meter_candidate']=='4/4'
assert a['confirmed_meter']=='3/4'
assert a['meter']=='3/4' and a['meter_status']=='confirmed'
assert a['beats_per_bar']==3
assert a['meter_confirmation_status']=='confirmed'
assert a['downbeat_phase_status']=='unconfirmed'
assert 'confirmed_phase_number' not in a
assert len(a['downbeat_times'])>0 and a['bar_aligned_chords']
assert a['segments']==segments and a['beat_times']==beats and a['raw_bpm']==120.0 and a['best_meter_candidate']=='4/4'
r2,a2,s2=main.build_confirmed_meter_updates(record,analysis,'4/4','2026-07-28 16:00:00')
assert a2['confirmed_meter']=='4/4' and a2['beats_per_bar']==4
try:
    main.build_confirmed_meter_updates(record,analysis,'6/8','x')
    raise AssertionError('6/8 accepted')
except RuntimeError: pass
print('Banjofy Song Analysis Laboratory 015 complete release gate: passed')
