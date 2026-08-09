from pathlib import Path
import ast

root = Path(__file__).resolve().parent
repo = root.parents[1]
wf = (repo / ".github/workflows/bn009.yml").read_text(encoding="utf-8")
main = (root / "main.py").read_text(encoding="utf-8")
consensus = (root / "consensus.py").read_text(encoding="utf-8")
self_test = (root / "self_test.py").read_text(encoding="utf-8")
spec = (root / "BN009.spec").read_text(encoding="utf-8")
hook = (root / "dll_hook.py").read_text(encoding="utf-8")

for name, text in [("main.py", main), ("consensus.py", consensus), ("self_test.py", self_test), ("dll_hook.py", hook)]:
    ast.parse(text, filename=name)
ast.parse(spec, filename="BN009.spec", mode="exec")

assert "Banjofy BN Consensus Lab 009" in main
assert "from consensus import analyse_consensus" in main
assert "for model in (1, 2, 3):" in main
assert 'mode="offline"' in main
assert 'inference_model="DBN"' in main
assert 'device="cpu"' in main
assert "startup_audio_score" in main
assert "startup_audio_scores" in main
assert "startup_lock_scores" in main
assert "analyse_consensus(model_outputs, meter_accent_scores=meter_accent_scores, startup_audio_scores=startup_audio_scores)" in main
assert "BN009_RECOMMENDED_CLICKED" in main

for token in [
    "_tempo_support",
    "candidate_models",
    "meter_accent_scores",
    "startup_audio_scores",
    "_startup_lock_score",
    "startup_quality",
    'selection_reason = "startup_tiebreak"',
    '"startup_audio_scores"',
    '"startup_lock_scores"',
    'recommended_model = None',
]:
    assert token in consensus, token

for forbidden in ["Hotel California", "Tennessee Waltz", "Folsom", "AC/DC", "Dylan"]:
    assert forbidden not in consensus, forbidden

for token in [
    "130.435",
    "68.182",
    'result2["recommended_model"] is None',
    'result4["recommended_model"] == 3',
    'result4["meter_resolution"] == "audio_accent"',
    "shift_opening_downbeats",
    "startup_audio_scores={1: 0.92, 2: 0.68, 3: 0.72}",
    'result6["recommended_model"] == 1',
    'by_model[1]["startup_quality"] > by_model[2]["startup_quality"]',
]:
    assert token in self_test, token

assert "workflow_dispatch:" in wf
assert "\n  push:" not in wf
assert "Build BN Con Lab009" in wf
assert "BN009.exe" in wf
assert "include-hidden-files: true" in wf
assert "Full clean rebuild preparation" in wf
assert "Audit uploaded package inputs" in wf

for token in ["numpy.libs", "scipy.libs", "os.add_dll_directory"]:
    assert token in hook, token
for forbidden in ["import numpy", "import scipy", "import madmom", "import torch", "from BeatNet"]:
    assert forbidden not in hook, forbidden

for token in ["copy_metadata(\"madmom\")", "visible_libs", 'name="BN009"', 'name="BN9D"']:
    assert token in spec, token

print("BN Con Lab009 release gate: passed")
