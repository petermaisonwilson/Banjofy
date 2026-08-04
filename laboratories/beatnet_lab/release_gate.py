from pathlib import Path
import ast
root=Path(__file__).resolve().parent
repo=root.parents[1]
wf=(repo/'.github/workflows/song-analysis-lab.yml').read_text(encoding='utf-8')
main=(root/'main.py').read_text(encoding='utf-8')
smoke=(root/'offline_smoke_test.py').read_text(encoding='utf-8')
spec=(root/'beatnet_lab.spec').read_text(encoding='utf-8')
ast.parse(main); ast.parse(smoke)
assert 'Banjofy BeatNet Listening Laboratory 004' in main and 'BanjofyBeatNetLab004' in spec
for token in ['numpy==1.23.5','scipy==1.10.1','Cython==0.29.36','mido==1.3.2','madmom==0.16.1 --no-build-isolation','librosa==0.10.1','pyaudio==0.2.14','torch==2.1.2','matplotlib==3.7.5','tensorboard==2.15.2','PyYAML==6.0.2','pytest==8.3.5','git+https://github.com/mjhydri/BeatNet.git']:
    assert token in wf, token
assert wf.count('git+https://github.com/mjhydri/BeatNet.git')==1
assert wf.count('from BeatNet.BeatNet import BeatNet')==1
assert 'Install current BeatNet source and bundled trained models' not in wf
assert wf.index('madmom==0.16.1') < wf.index('madmom import passed') < wf.index('pyaudio==0.2.14') < wf.index('PyAudio import passed') < wf.index('git+https://github.com/mjhydri/BeatNet.git') < wf.index('BeatNet import passed') < wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Install packaging tools')
assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke and "inference_model='DBN'" in smoke and 'RNNBeatProcessor' in smoke
print('Banjofy BeatNet Listening Laboratory 004 release gate: passed')
