from pathlib import Path
import json
import numpy as np
import soundfile as sf

def make_click_track(path: Path, sr: int = 22050) -> None:
    duration = 12.0
    audio = np.zeros(int(duration * sr), dtype=np.float32)
    beat_times = np.arange(0.5, duration - 0.1, 0.5)  # 120 BPM
    for i, t in enumerate(beat_times):
        start = int(t * sr)
        length = int(0.05 * sr)
        tt = np.arange(length, dtype=np.float32) / sr
        freq = 1800.0 if i % 4 == 0 else 900.0
        env = np.exp(-tt * 55.0)
        click = 0.8 * np.sin(2 * np.pi * freq * tt) * env
        end = min(len(audio), start + length)
        audio[start:end] += click[:end-start]
    sf.write(path, audio, sr)

def main() -> None:
    root = Path(__file__).resolve().parent
    wav = root / "beatnet_smoke_120bpm_4_4.wav"
    make_click_track(wav)

    from BeatNet.BeatNet import BeatNet

    estimator = BeatNet(
        1,
        mode="offline",
        inference_model="DBN",
        plot=[],
        thread=False,
    )
    output = estimator.process(str(wav))
    rows = np.asarray(output)
    if rows.ndim != 2 or rows.shape[0] < 8 or rows.shape[1] < 2:
        raise RuntimeError(f"BeatNet returned an invalid result shape: {rows.shape}")

    times = rows[:, 0].astype(float)
    beat_numbers = rows[:, 1].astype(int)
    if not np.all(np.diff(times) > 0):
        raise RuntimeError("BeatNet beat times are not strictly increasing.")
    if 1 not in set(beat_numbers.tolist()):
        raise RuntimeError("BeatNet returned no downbeats.")

    result = {
        "status": "passed",
        "detected_events": int(rows.shape[0]),
        "first_events": rows[:12].tolist(),
        "contains_downbeats": True,
    }
    (root / "beatnet_offline_smoke_test.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
