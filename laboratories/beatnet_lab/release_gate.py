from pathlib import Path
import ast
root=Path(__file__).resolve().parent
repo=root.parents[1]
wf=(repo/'.github/workflows/song-analysis-lab.yml').read_text(encoding='utf-8')
main=(root/'main.py').read_text(encoding='utf-8')
spec=(root/'beatnet_lab.spec').read_text(encoding='utf-8')
smoke=(root/'offline_smoke_test.py').read_text(encoding='utf-8')

ast.parse(main)
ast.parse(smoke)
compile(spec,'beatnet_lab.spec','exec')

assert 'APP_TITLE = "Banjofy BeatNet Listening Laboratory 007"' in main
assert "name='BanjofyBeatNetLab007'" in spec
assert 'Build Banjofy BeatNet Listening Laboratory 007' in wf
assert 'Banjofy-BeatNet-Listening-Laboratory-007-Windows' in wf

for token in [
    'collect_all(package)',
    'collect_dynamic_libs(package)',
    'collect_submodules(package)',
    "collect_submodules('BeatNet')",
    'imageio_ffmpeg.get_ffmpeg_exe()'
]:
    assert token in spec, token

assert 'Launch packaged Windows application smoke test' in wf
assert 'Start-Process' in wf
assert 'BanjofyBeatNetLab007.exe' in wf
assert wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Build Windows application')
assert wf.index('Build Windows application') < wf.index('Launch packaged Windows application smoke test')
assert wf.index('Launch packaged Windows application smoke test') < wf.index('Assemble artifact')
assert wf.index('Assemble artifact') < wf.index('Upload Windows artifact')

assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke
assert "inference_model='DBN'" in smoke

print('Banjofy BeatNet Listening Laboratory 007 release gate: passed')
