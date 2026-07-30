from pathlib import Path
import ast, sys
root=Path(__file__).resolve().parent
m=(root/"main.py").read_text(encoding="utf-8")
e=(root/"structure_engine.py").read_text(encoding="utf-8")
s=(root/"song_analysis_lab.spec").read_text(encoding="utf-8")
ast.parse(m); ast.parse(e)
assert "Laboratory 025 — Phase Challenger" in m
assert "BanjofySongAnalysisLab025" in s
assert "Test Phase Challenger" in m
assert "controls_top" in m and "controls_bottom" in m
assert "phase_challenger_025.txt" in m
for w in ("0.23 * stability","0.20 * beat_support","0.05 * chord_grid_support","0.27 * repeating_accent","0.18 * bar_consistency","0.05 * lead_in_rise","0.02 * meter_prior"):
    assert w in e
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in e
for token in ("def _phase_boundary_score(","def test_phase_challenger(","def format_phase_challenger(","meter_changed\": False","beat_grid_changed\": False"):
    assert token in e
sys.path.insert(0,str(root))
import structure_engine

analysis={
 "alternative_beat_grids":{"standard":{"beat_times":[float(i) for i in range(24)]}},
 "segments":[
   {"start_s":2.0,"end_s":6.0},
   {"start_s":6.0,"end_s":10.0},
   {"start_s":10.0,"end_s":14.0},
   {"start_s":14.0,"end_s":18.0},
 ],
 "timing_recommendation":{"ranked_candidates":[
   {"meter":"4/4","method":"standard","phase_number":2,"score":0.60},
   {"meter":"4/4","method":"standard","phase_number":3,"score":0.55},
   {"meter":"4/4","method":"standard","phase_number":4,"score":0.52},
   {"meter":"4/4","method":"standard","phase_number":1,"score":0.50},
 ]}
}
truth={"schema":"banjofy.manual_truth.v2","verified_by_user":True,"complete":True,"meter":"4/4","beat_grid_method":"standard","phase_number":3}
r=structure_engine.test_phase_challenger("Proof",analysis,truth,Path("a"),Path("t"))
assert r["frozen_meter"]=="4/4"
assert r["frozen_beat_grid_method"]=="standard"
assert r["challenger_phase_number"]==3
assert r["old_phase_number"]==2
assert r["improved"] is True
assert r["meter_changed"] is False
assert r["beat_grid_changed"] is False
text=structure_engine.format_phase_challenger(r)
assert "Challenger phase: 3 — PASS" in text
assert "Meter changed: NO" in text
print("Banjofy Song Analysis Laboratory 025 complete release gate: passed")
