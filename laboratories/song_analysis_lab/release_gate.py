from __future__ import annotations
import ast, sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
main_text=(root/'main.py').read_text(encoding='utf-8')
engine_text=(root/'structure_engine.py').read_text(encoding='utf-8')
spec_text=(root/'song_analysis_lab.spec').read_text(encoding='utf-8')
ast.parse(main_text); ast.parse(engine_text)
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 019 — Automatic Timing Recommendation"' in main_text
assert 'name="BanjofySongAnalysisLab019"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for forbidden in ('"2/4"',"'2/4'",'"6/8"',"'6/8'",'Build 013'):
    assert forbidden not in main_text
for required in (
    'Recommend Meter, Beat Grid and Phase',
    'def _recommend_timing(',
    'timing_recommendation_019.json',
): assert required in main_text
assert 'recommendation_applied' in engine_text
for required in (
    'def score_timing_candidates(',
    'def recommend_timing_structure(',
    'recommended_meter',
    'recommended_beat_grid_method',
    'recommended_phase_number',
): assert required in engine_text
assert 'wav = prepare_wav(audio_path, Path(temporary))' in engine_text
assert 'librosa.load(audio_path' not in engine_text
sys.path.insert(0,str(root)); import structure_engine
frames=np.arange(0.0,20.0,0.1)
full=np.zeros_like(frames); low=np.zeros_like(frames)
beats=[0.2+i*0.6 for i in range(30)]
for i,t in enumerate(beats):
    idx=int(np.argmin(np.abs(frames-t)))
    full[idx]=0.8
    low[idx]=1.0 if i%3==2 else 0.45
candidates={
 'low_frequency':{'label':'Low-frequency rhythm','bpm':100.0,'beat_times':beats},
 'standard':{'label':'Standard full mix','bpm':120.0,'beat_times':[0.1+i*0.5 for i in range(35)]},
}
rows=structure_engine.score_timing_candidates(candidates,full,low,frames,[2.0,5.6,9.2,12.8])
assert rows and {row['meter'] for row in rows}=={'3/4','4/4'}
assert all(1 <= row['phase_number'] <= (3 if row['meter']=='3/4' else 4) for row in rows)
print('Banjofy Song Analysis Laboratory 019 complete release gate: passed')
