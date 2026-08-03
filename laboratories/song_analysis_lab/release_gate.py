from pathlib import Path
import ast,sys
root=Path(__file__).resolve().parent
m=(root/'main.py').read_text(encoding='utf-8')
e=(root/'structure_engine.py').read_text(encoding='utf-8')
s=(root/'song_analysis_lab.spec').read_text(encoding='utf-8')
ast.parse(m);ast.parse(e)
assert 'Laboratory 028 — Musical Tempo Selector' in m
assert 'BanjofySongAnalysisLab028' in s
assert 'Run Musical Tempo Selector' in m
for token in ('def _harmonic_cycle_quality(','def _tempo_level_preference(','harmonic_cycle_quality','tempo_level_preference'):
    assert token in e
sys.path.insert(0,str(root))
import structure_engine
compact=['Bm','F#7','A','E','G','D','Em','F#7']*4
duped=[]
for chord in compact: duped.extend([chord,chord])
c=structure_engine._harmonic_cycle_quality(compact)
d=structure_engine._harmonic_cycle_quality(duped)
assert c['median_run_bars']==1.0
assert d['median_run_bars']==2.0
assert c['compactness']>d['compactness']
assert structure_engine._tempo_level_preference(74.0,1.0,c)>structure_engine._tempo_level_preference(148.0,2.0,d)
held=['G','G','C','C','D','D','G','G']*3
assert structure_engine._harmonic_cycle_quality(held)['score']>0
for w in ('0.23 * stability','0.20 * beat_support','0.05 * chord_grid_support','0.27 * repeating_accent','0.18 * bar_consistency','0.05 * lead_in_rise','0.02 * meter_prior'):
    assert w in e
print('Banjofy Song Analysis Laboratory 028 complete release gate: passed')
