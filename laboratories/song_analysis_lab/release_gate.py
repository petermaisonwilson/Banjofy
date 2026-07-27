from pathlib import Path
import ast, sys, numpy as np
root=Path(__file__).resolve().parent
main=(root/"main.py").read_text(); eng=(root/"structure_engine.py").read_text(); spec=(root/"song_analysis_lab.spec").read_text()
ast.parse(main); ast.parse(eng)
assert 'Laboratory 010' in main
assert 'name="BanjofySongAnalysisLab010"' in spec
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in eng
assert '2/4' not in eng and '2/4' not in main
assert 'AUDIBLE_PREVIEW_SECONDS = 180.0' in eng
assert 'def select_strongest_rhythmic_window' in eng
assert 'def _open_visual_window' in main and 'winsound.PlaySound' in main
sys.path.insert(0,str(root)); import structure_engine as s
a=np.concatenate([np.zeros(40),np.array([3.0 if i%4==1 else .2 for i in range(96)])]); t=[i*.5 for i in range(len(a))]
w,b,e,bs,es=s.select_strongest_rhythmic_window(a,t); assert b>=35; r,_=s.infer_meter(w); assert r.meter=='4/4'
for n,m in ((3,'3/4'),(4,'4/4')):
 v=np.array([3.0 if i%n==1 else .2 for i in range(96)]); r,_=s.infer_meter(v); assert r.meter==m
print('Banjofy Song Analysis Laboratory 010 complete release gate: passed')
