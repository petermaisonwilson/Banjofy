from pathlib import Path
import json
import numpy as np
import soundfile as sf


def make_test_audio(path: Path, sr: int = 44100) -> None:
    duration = 16.0
    audio = np.zeros(int(duration * sr), dtype=np.float32)
    beat_times = np.arange(0.5, duration - 0.1, 0.5)
    for i, t in enumerate(beat_times):
        start = int(t * sr)
        length = int(0.075 * sr)
        tt = np.arange(length, dtype=np.float32) / sr
        downbeat = i % 4 == 0
        freq = 1500.0 if downbeat else 850.0
        amp = 0.95 if downbeat else 0.55
        click = amp * np.sin(2 * np.pi * freq * tt) * np.exp(-tt * 45.0)
        bass = (0.40 if downbeat else 0.18) * np.sin(2 * np.pi * 95.0 * tt) * np.exp(-tt * 30.0)
        event = click + bass
        end = min(len(audio), start + length)
        audio[start:end] += event[:end-start]
    peak=float(np.max(np.abs(audio)))
    if peak>0: audio=0.92*audio/peak
    sf.write(path,audio,sr,subtype='PCM_16')


def main() -> None:
    root=Path(__file__).resolve().parent
    wav=root/'beatnet_smoke_120bpm_4_4.wav'
    make_test_audio(wav)
    import madmom
    from madmom.features.beats import RNNBeatProcessor
    activation=np.asarray(RNNBeatProcessor()(str(wav)))
    if activation.size < 10:
        raise RuntimeError('madmom produced no usable beat activation sequence.')
    from BeatNet.BeatNet import BeatNet
    model_results={}
    for model_number in (1,2,3):
        estimator=BeatNet(model_number,mode='offline',inference_model='DBN',plot=[],thread=False)
        rows=np.asarray(estimator.process(str(wav)))
        if rows.ndim != 2 or rows.shape[0] < 8 or rows.shape[1] < 2:
            raise RuntimeError(f'BeatNet model {model_number} returned invalid shape {rows.shape}')
        times=rows[:,0].astype(float); nums=rows[:,1].astype(int)
        if not np.all(np.isfinite(times)): raise RuntimeError(f'BeatNet model {model_number} returned non-finite beat times.')
        if not np.all(np.diff(times)>0): raise RuntimeError(f'BeatNet model {model_number} beat times are not increasing.')
        if 1 not in set(nums.tolist()): raise RuntimeError(f'BeatNet model {model_number} returned no downbeats.')
        model_results[str(model_number)]={'events':int(rows.shape[0]),'first_events':rows[:12].tolist(),'beat_numbers_seen':sorted(set(nums.tolist()))}
    result={'status':'passed','madmom_activation_frames':int(activation.size),'beatnet_models':model_results}
    (root/'beatnet_offline_smoke_test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
