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
assert "analyse_consensus(model_outputs, meter_accent_scores=meter_accent_scores)" in main
assert "BN009_RECOMMENDED_CLICKED" in main
assert "NONE - AMBIGUOUS" in main
assert "tempo_family_models" in main
assert "meter_accent_score" in main
assert "Measuring source-audio accents" in main

for token in [
    "_tempo_support",
    "tempo_family",
    "candidate_models",
    "meter_accent_scores",
    'meter_resolution = "audio_accent"',
    'recommended_model = None',
    '"meter_accent_scores"',
]:
    assert token in consensus, token

# No song-specific truth or hard-coded model choice is allowed in the consensus engine.
for forbidden in ["Hotel California", "Tennessee Waltz", "Folsom", "AC/DC", "Dylan"]:
    assert forbidden not in consensus, forbidden

# Self-tests must prove: tempo outlier rejection, preserved ambiguity without audio
# evidence, resolution only with strong accent evidence, and refusal on weak evidence.
for token in [
    "130.435",
    "68.182",
    'result2["recommended_model"] is None',
    'result2["tempo_family_models"] == [2, 3]',
    'meter_accent_scores={2: 0.51, 3: 0.62}',
    'result4["recommended_model"] == 3',
    'result4["consensus_meter"] == "3/4"',
    'result4["meter_resolution"] == "audio_accent"',
    'meter_accent_scores={2: 0.54, 3: 0.56}',
    'result5["recommended_model"] is None',
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
