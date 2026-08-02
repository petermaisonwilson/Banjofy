from pathlib import Path
import ast, sys
root=Path(__file__).resolve().parent
m=(root/"main.py").read_text(encoding="utf-8")
e=(root/"structure_engine.py").read_text(encoding="utf-8")
s=(root/"song_analysis_lab.spec").read_text(encoding="utf-8")
ast.parse(m); ast.parse(e)
assert "Laboratory 026 — Timing Engine Benchmark" in m
assert "BanjofySongAnalysisLab026" in s
assert "Benchmark All Verified Songs" in m
assert "timing_engine_benchmark_026.txt" in m
for token in (
    "TIMING_BENCHMARK_ENGINES",
    "def _plp_grid(",
    "def benchmark_library_timing_engines(",
    "def format_timing_engine_benchmark(",
    "librosa_full_mix_dp",
    "librosa_percussive_dp",
    "librosa_low_frequency_dp",
    "librosa_plp",
):
    assert token in e
for w in ("0.23 * stability","0.20 * beat_support","0.05 * chord_grid_support","0.27 * repeating_accent","0.18 * bar_consistency","0.05 * lead_in_rise","0.02 * meter_prior"):
    assert w in e
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in e
sys.path.insert(0,str(root))
import structure_engine
assert len(structure_engine.TIMING_BENCHMARK_ENGINES)==5
sample={
 "verified_song_count":1,
 "leaderboard":[{
   "label":"Proof","songs_tested":1,"meter_matches":1,"grid_matches":1,
   "phase_matches":1,"exact_matches":1,"ranking_score":1.0,"errors":0
 }],
 "songs":[{
   "song_title":"Proof Song",
   "truth":{"meter":"4/4","beat_grid_method":"standard","phase_number":1},
   "engines":[{
      "label":"Proof","meter":"4/4","beat_grid_method":"standard","phase_number":1,
      "checks":{"meter":"PASS","beat_grid":"PASS","phase":"PASS","exact":"PASS"}
   }]
 }],
 "benchmark_limitations":["Proof limitation"],
}
text=structure_engine.format_timing_engine_benchmark(sample)
assert "LEADERBOARD" in text and "Proof Song" in text
print("Banjofy Song Analysis Laboratory 026 complete release gate: passed")
