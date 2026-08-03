from pathlib import Path
import ast

root = Path(__file__).resolve().parent
repo = root.parents[1]
wf = (repo / ".github/workflows/song-analysis-lab.yml").read_text(encoding="utf-8")
main = (root / "main.py").read_text(encoding="utf-8")
smoke = (root / "offline_smoke_test.py").read_text(encoding="utf-8")

ast.parse(main)
ast.parse(smoke)

assert "Banjofy BeatNet Listening Laboratory 003" in main
assert "Build Banjofy BeatNet Listening Laboratory 003" in wf
assert "Install current BeatNet source and bundled trained models" not in wf
assert wf.count("pyaudio==0.2.14") == 1
assert wf.count("git+https://github.com/mjhydri/BeatNet.git") == 1
assert wf.count("from BeatNet.BeatNet import BeatNet") == 1

a = wf.index("pyaudio==0.2.14")
b = wf.index('python -c "import pyaudio; print')
c = wf.index('git+https://github.com/mjhydri/BeatNet.git')
d = wf.index('python -c "from BeatNet.BeatNet import BeatNet; print')
e = wf.index("offline_smoke_test.py")
assert a < b < c < d < e

print("Banjofy BeatNet Listening Laboratory 003 release gate: passed")
