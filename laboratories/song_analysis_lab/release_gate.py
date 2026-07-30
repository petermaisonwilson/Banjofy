from pathlib import Path
import ast, sys
root = Path(__file__).resolve().parent
m = (root/"main.py").read_text(encoding="utf-8")
e = (root/"structure_engine.py").read_text(encoding="utf-8")
s = (root/"song_analysis_lab.spec").read_text(encoding="utf-8")
ast.parse(m); ast.parse(e)
assert "Laboratory 024 — Automated Truth Validation" in m
assert "BanjofySongAnalysisLab024" in s
assert "Validate Automatic Timing" in m
assert "timing_validation_024.txt" in m
for w in ("0.23 * stability","0.20 * beat_support","0.05 * chord_grid_support","0.27 * repeating_accent","0.18 * bar_consistency","0.05 * lead_in_rise","0.02 * meter_prior"):
    assert w in e
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in e
sys.path.insert(0, str(root))
import structure_engine
truth={"schema":"banjofy.manual_truth.v2","verified_by_user":True,"complete":True,"meter":"4/4","beat_grid_method":"standard","phase_number":3}
analysis={"timing_recommendation":{"ranked_candidates":[{"meter":"4/4","beat_grid_method":"standard","phase_number":2,"score":0.8}]}}
r=structure_engine.validate_automatic_timing("Hotel",analysis,truth,Path("a"),Path("t"))
assert r["checks"]["meter"]["pass"]
assert r["checks"]["beat_grid_method"]["pass"]
assert not r["checks"]["phase_number"]["pass"]
assert not r["overall_pass"]
truth["phase_number"]=2
r2=structure_engine.validate_automatic_timing("Pass",analysis,truth,Path("a"),Path("t"))
assert r2["overall_pass"]
assert "Overall: PASS" in structure_engine.format_timing_validation(r2)
print("Banjofy Song Analysis Laboratory 024 complete release gate: passed")
