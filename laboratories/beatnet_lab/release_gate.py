from pathlib import Path
import ast
root=Path(__file__).resolve().parent
repo=root.parents[1]
wf=(repo/'.github/workflows/song-analysis-lab.yml').read_text(encoding='utf-8')
main=(root/'main.py').read_text(encoding='utf-8')
smoke=(root/'offline_smoke_test.py').read_text(encoding='utf-8')
spec=(root/'beatnet_lab.spec').read_text(encoding='utf-8')
ast.parse(main); ast.parse(smoke)
assert 'Banjofy BeatNet Listening Laboratory 006' in main
assert 'BanjofyBeatNetLab006' in spec
assert 'Build Banjofy BeatNet Listening Laboratory 006' in wf
assert 'setuptools==80.9.0' in wf
assert 'wheel==0.45.1' in wf
for token in ('madmom==0.16.1 --no-build-isolation','pyaudio==0.2.14','torch==2.1.2','git+https://github.com/mjhydri/BeatNet.git','Run real madmom and BeatNet offline audio proof'):
    assert token in wf, token
assert 'imageio-ffmpeg==0.4.9' in wf
assert 'import imageio_ffmpeg' in wf
assert 'imageio_ffmpeg.get_ffmpeg_exe()' in wf
assert 'import imageio_ffmpeg' in spec
assert 'ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()' in spec
assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke
assert "inference_model='DBN'" in smoke
assert wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Install packaging tools')
assert wf.index('imageio-ffmpeg==0.4.9') < wf.index('Build Windows application')
assert wf.index('imageio_ffmpeg.get_ffmpeg_exe()') < wf.index('Build Windows application')
print('Banjofy BeatNet Listening Laboratory 006 release gate: passed')
