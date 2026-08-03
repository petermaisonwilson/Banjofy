from pathlib import Path
import ast, sys, numpy as np
root=Path(__file__).resolve().parent
m=(root/'main.py').read_text(encoding='utf-8')
ast.parse(m)
assert 'Banjofy BeatNet Listening Laboratory 001' in m
assert 'from BeatNet.BeatNet import BeatNet' in m
assert 'mode="offline"' in m
assert 'inference_model="DBN"' in m
assert 'truth_used' in m
assert 'CLICKED_SONG' in m
assert '1760.0 if beat_number == 1 else 880.0' in m
sys.path.insert(0,str(root))
import main
sample=np.array([[0.5,1],[1.0,2],[1.5,3],[2.0,4],[2.5,1]],dtype=float)
s=main.estimate_summary(sample)
assert s['meter']=='4/4'
assert s['downbeat_count']==2
assert abs(s['bpm']-120.0)<0.01
print('Banjofy BeatNet Listening Laboratory 001 source release gate: passed')
