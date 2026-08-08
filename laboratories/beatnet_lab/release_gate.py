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
spec_tree = ast.parse(spec, filename='beatnet_lab.spec', mode='exec')

# Build-008 packaging gate only. Do not alter the proven BeatNet analysis path.
assert 'Banjofy BeatNet Listening Laboratory 007' in main
assert 'Build Banjofy BeatNet 008' in wf
assert 'BN008' in wf

# Check the PyInstaller EXE/COLLECT names structurally so quote style cannot break the gate.
bn008_names = 0
for node in ast.walk(spec_tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'EXE', 'COLLECT'}:
        for keyword in node.keywords:
            if keyword.arg == 'name' and isinstance(keyword.value, ast.Constant) and keyword.value.value == 'BN008':
                bn008_names += 1
assert bn008_names >= 2, f'Expected BN008 name on EXE and COLLECT, found {bn008_names}'

# Prevent another spec-relative path regression. The spec must resolve both
# files from PyInstaller's SPECPATH instead of embedding the repository path.
for token in [
    'spec_root = Path(SPECPATH).resolve()',
    'main_script = spec_root / "main.py"',
    'dll_hook = spec_root / "dll_hook.py"',
    '[str(main_script)]',
    'runtime_hooks=[str(dll_hook)]',
    'pathex=[str(spec_root)]',
    'collect_all(package)',
    'collect_dynamic_libs(package)',
    'collect_submodules(package)',
    'collect_submodules("BeatNet")',
    'imageio_ffmpeg',
    'imageio_ffmpeg.get_ffmpeg_exe()',
    'pkg_resources',
]:
    assert token in spec, token

# Runtime startup preflight must exercise the compiled and dynamically used
# pieces before main.py can write GitHub's ready proof.
for token in [
    'numpy.libs',
    'scipy.libs',
    'os.add_dll_directory',
    'import numpy',
    'import scipy',
    'import madmom',
    'import torch',
    'import imageio_ffmpeg',
    'from BeatNet.BeatNet import BeatNet',
    'get_ffmpeg_exe()',
]:
    assert token in hook, token

assert 'Full clean rebuild preparation' in wf
assert 'Audit compiled package contents' in wf
assert 'Launch actual packaged EXE and require ready proof' in wf
assert 'BANJOFY_BEATNET_STARTUP_PROBE_FILE' in wf
assert 'Start-Process' in wf
assert 'BN008.exe' in wf
assert 'dist/BN008/BN008.exe' in wf
assert 'artifact/BN008' in wf
assert 'B008.txt' in wf
assert 'beatnet_offline_smoke_test.json' in wf
assert wf.index('Run real madmom and BeatNet offline audio proof') < wf.index('Build Windows application')
assert wf.index('Build Windows application') < wf.index('Audit compiled package contents')
assert wf.index('Audit compiled package contents') < wf.index('Launch actual packaged EXE and require ready proof')
assert wf.index('Launch actual packaged EXE and require ready proof') < wf.index('Assemble artifact')
assert wf.index('Assemble artifact') < wf.index('Upload Windows artifact')

assert 'for model_number in (1,2,3):' in smoke
assert "mode='offline'" in smoke
assert "inference_model='DBN'" in smoke

print('Banjofy BeatNet Build 008 release gate: passed')
