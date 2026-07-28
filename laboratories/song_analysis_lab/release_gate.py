from __future__ import annotations
import ast, sys, tempfile, subprocess
from pathlib import Path
import numpy as np, soundfile as sf, imageio_ffmpeg
root=Path(__file__).resolve().parent
main_text=(root/'main.py').read_text(encoding='utf-8'); engine_text=(root/'structure_engine.py').read_text(encoding='utf-8'); spec_text=(root/'song_analysis_lab.spec').read_text(encoding='utf-8')
ast.parse(main_text); ast.parse(engine_text)
assert 'APP_TITLE = "Banjofy Song Analysis Laboratory 017 — Alternative Beat-Grid Audition"' in main_text
assert 'name="BanjofySongAnalysisLab017"' in spec_text
assert 'SUPPORTED_METERS = ((3, "3/4"), (4, "4/4"))' in engine_text
for bad in ('"2/4"', "'2/4'", '"6/8"', "'6/8'", 'Build 013'):
    assert bad not in main_text
for req in ('generate_alternative_beat_grids','create_audible_beat_grid_check','Standard full mix','Percussion focused','Low-frequency rhythm','Steady slow pulse'):
    assert req in engine_text
for req in ('Create Alternative Beat Grids','Play Alternative Beat Grids','def _play_alternative_beat_grids','def _update_alternative_marker'):
    assert req in main_text
assert 'wav_source = prepare_wav(audio_path, Path(temporary_folder))' in engine_text
assert 'def _root(' not in main_text
sys.path.insert(0,str(root)); import structure_engine
with tempfile.TemporaryDirectory(prefix='sal017_') as td:
    td=Path(td); sr=22050; duration=18.0; y=np.zeros(int(sr*duration),dtype=np.float32)
    for t in np.arange(.5,duration,.75):
        s=int(t*sr); y[s:s+500]+=np.hanning(500).astype(np.float32)*.7
    wav=td/'source.wav'; m4a=td/'source.m4a'; sf.write(wav,y,sr)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-hide_banner','-loglevel','error','-i',str(wav),'-c:a','aac','-b:a','192k',str(m4a)],check=True)
    grids=structure_engine.generate_alternative_beat_grids(m4a)
    assert set(grids)=={'standard','percussive','low_frequency','steady_pulse'}
    for key,item in grids.items():
        assert len(item['beat_times'])>=8
        out=td/f'{key}.wav'; structure_engine.create_audible_beat_grid_check(m4a,item['beat_times'],out,preview_seconds=18.0)
        assert out.is_file() and out.stat().st_size>1000
print('Banjofy Song Analysis Laboratory 017 complete release gate: passed')
