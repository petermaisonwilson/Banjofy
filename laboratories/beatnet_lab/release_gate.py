from pathlib import Path
import ast

root = Path(__file__).resolve().parent
repo = root.parents[1]
wf = (repo / '.github/workflows/song-analysis-lab.yml').read_text(encoding='utf-8')
main = (root / 'main.py').read_text(encoding='utf-8')
spec = (root / 'beatnet_lab.spec').read_text(encoding='utf-8')
smoke = (root / 'offline_smoke_test.py').read_text(encoding='utf-8')
hook = (root / 'dll_hook.py').read_text(encoding='utf-8')

ast.parse(main)
ast.parse(smoke)
ast.parse(hook)
compile(spec, 'beatnet_lab.spec', 'exec')

# Build-008 packaging gate only. Do not alter the proven BeatNet analysis path.
assert 'Banjofy BeatNet Listening Laboratory 007' in main
assert "name='BN008'" in spec
assert 'Build Banjofy BeatNet 008' in wf
assert 'BN008' in wf

for token in [
    'collect_all(package)',
    'collect_dynamic_libs(package)',
    'collect_submodules(package)',
    "collect_submodules('BeatNet')",
    'imageio_ffmpeg.get_ffmpeg_exe()',
    'runtime_hooks=',
    'dll_hook.py',
]:
    assert token in spec, token

for token in [
    'numpy.libs',
    'scipy.libs',
    'os.add_dll_directory',
]:
    assert token in hook, token

assert 'Full clean rebuild preparation' in wf
assert 'Audit compiled package contents' in wf
assert 'Launch actual packaged EXE and require ready proof' in wf
assert 'BANJOFY_BEATNET_STARTUP_PROBE_FILE' in wf
assert 'Start-Process' in wf
assert 'BN008.exe' in wf
assert wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Build Windows application')
assert wf.index('Build Windows application') < wf.index('Audit compiled package contents')
assert wf.index('Audit compiled package contents') < wf.index('Launch actual packaged EXE and require ready proof')
assert wf.index('Launch actual packaged EXE and require ready proof') < wf.index('Assemble artifact')
assert wf.index('Assemble artifact') < wf.index('Upload Windows artifact')

assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke
assert "inference_model='DBN'" in smoke

print('Banjofy BeatNet Build 008 release gate: passed')
