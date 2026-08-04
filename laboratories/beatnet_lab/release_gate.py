from pathlib import Path
import ast
root=Path(__file__).resolve().parent
repo=root.parents[1]
wf=(repo/'.github/workflows/song-analysis-lab.yml').read_text(encoding='utf-8')
main=(root/'main.py').read_text(encoding='utf-8')
smoke=(root/'offline_smoke_test.py').read_text(encoding='utf-8')
spec=(root/'beatnet_lab.spec').read_text(encoding='utf-8')
ast.parse(main); ast.parse(smoke)
assert 'Banjofy BeatNet Listening Laboratory 005' in main
assert 'BanjofyBeatNetLab005' in spec
assert 'Build Banjofy BeatNet Listening Laboratory 005' in wf
assert 'setuptools==80.9.0' in wf
assert 'wheel==0.45.1' in wf
assert 'python -m pip install --upgrade "pip<25" setuptools wheel' not in wf
for token in ('madmom==0.16.1 --no-build-isolation','pyaudio==0.2.14','torch==2.1.2','git+https://github.com/mjhydri/BeatNet.git','Run real madmom and BeatNet offline audio proof'):
    assert token in wf, token
assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke
assert "inference_model='DBN'" in smoke
assert wf.index('setuptools==80.9.0') < wf.index('madmom==0.16.1')
assert wf.index('madmom import passed') < wf.index('BeatNet import passed')
assert wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Install packaging tools')
print('Banjofy BeatNet Listening Laboratory 005 release gate: passed')
