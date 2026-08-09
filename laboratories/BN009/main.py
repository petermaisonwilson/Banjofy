from __future__ import annotations

import csv
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
import wave
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

from consensus import analyse_consensus

APP_TITLE = "Banjofy BN Consensus Lab 009"
SUPPORTED_AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}


def bundled_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).is_file():
            return path
    except Exception:
        pass
    local = bundled_path("ffmpeg.exe")
    if local.is_file():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("The bundled FFmpeg executable could not be found.")


def convert_to_wav(source: Path, destination: Path) -> None:
    cmd = [
        ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le",
        str(destination),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"FFmpeg conversion failed:\n{result.stderr.strip()}")


def normalise_output(raw) -> np.ndarray:
    data = np.asarray(raw, dtype=float)
    if data.ndim != 2 or data.shape[1] < 2:
        raise RuntimeError(f"BeatNet returned an unexpected result shape: {data.shape}")
    data = data[:, :2]
    data = data[np.isfinite(data).all(axis=1)]
    data = data[data[:, 0] >= 0]
    if len(data) < 4:
        raise RuntimeError("BeatNet returned fewer than four usable beats.")
    data = data[np.argsort(data[:, 0])]
    return data


def estimate_summary(data: np.ndarray) -> dict:
    times = data[:, 0]
    beat_numbers = np.rint(data[:, 1]).astype(int)
    diffs = np.diff(times)
    diffs = diffs[(diffs > 0.12) & (diffs < 3.0)]
    bpm = float(60.0 / np.median(diffs)) if len(diffs) else 0.0
    positive = beat_numbers[beat_numbers > 0]
    meter = int(np.max(positive)) if len(positive) else 0
    downbeats = times[beat_numbers == 1]
    return {
        "bpm": round(bpm, 3),
        "meter": f"{meter}/4" if meter else "unknown",
        "beat_count": int(len(times)),
        "downbeat_count": int(len(downbeats)),
        "first_downbeat_s": round(float(downbeats[0]), 6) if len(downbeats) else None,
    }


def create_click_wav(data: np.ndarray, duration_s: float, destination: Path) -> None:
    rate = 22050
    total = max(1, int((duration_s + 0.5) * rate))
    audio = np.zeros(total, dtype=np.float32)
    click_length = int(0.055 * rate)
    t = np.arange(click_length, dtype=np.float32) / rate
    envelope = np.exp(-55.0 * t)

    for timestamp, beat_value in data:
        beat_number = int(round(beat_value))
        frequency = 1760.0 if beat_number == 1 else 880.0
        amplitude = 0.82 if beat_number == 1 else 0.38
        click = amplitude * np.sin(2.0 * np.pi * frequency * t) * envelope
        start = int(float(timestamp) * rate)
        end = min(total, start + click_length)
        if start < 0 or start >= total:
            continue
        audio[start:end] += click[:end-start]

    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0.98:
        audio *= 0.98 / peak
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def meter_accent_score(data: np.ndarray, song_wav: Path) -> float:
    """Estimate whether proposed Beat-1 positions are more accented than other beats.

    The input WAV is the same mono 22.05 kHz PCM file already prepared for BeatNet.
    This does not change BeatNet output; it supplies independent audio evidence only
    when the candidate models agree on tempo but disagree on meter.
    """
    with wave.open(str(song_wav), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if channels != 1 or width != 2 or not frames:
        return 0.5

    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if len(samples) < rate:
        return 0.5
    transient = np.abs(np.diff(samples, prepend=samples[0]))
    duration = len(samples) / float(rate)
    start_limit = max(5.0, duration * 0.05)
    end_limit = duration * 0.95
    pre = int(0.035 * rate)
    post = int(0.105 * rate)

    downbeat_strengths = []
    other_strengths = []
    for timestamp, beat_value in data:
        timestamp = float(timestamp)
        if timestamp < start_limit or timestamp > end_limit:
            continue
        centre = int(timestamp * rate)
        left = max(0, centre - pre)
        right = min(len(transient), centre + post)
        if right <= left:
            continue
        window = transient[left:right]
        if not len(window):
            continue
        # Median of the loudest quarter emphasises attacks while resisting isolated noise.
        cut = max(1, len(window) // 4)
        strength = float(np.mean(np.partition(window, -cut)[-cut:]))
        if int(round(float(beat_value))) == 1:
            downbeat_strengths.append(strength)
        else:
            other_strengths.append(strength)

    if len(downbeat_strengths) < 4 or len(other_strengths) < 8:
        return 0.5
    down = float(np.median(downbeat_strengths))
    other = float(np.median(other_strengths))
    total = down + other
    if total <= 1e-9:
        return 0.5
    return float(np.clip(down / total, 0.0, 1.0))


def mix_clicked_song(song_wav: Path, clicks_wav: Path, destination: Path) -> None:
    cmd = [
        ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(song_wav), "-i", str(clicks_wav),
        "-filter_complex", "[0:a]volume=0.82[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0",
        "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(destination),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"FFmpeg click mixing failed:\n{result.stderr.strip()}")


def write_model_outputs(output_dir: Path, source: Path, model: int, data: np.ndarray, summary: dict, song_wav: Path) -> dict:
    prefix = output_dir / f"{source.stem}__BN_M{model}"
    csv_path = prefix.with_suffix(".csv")
    json_path = prefix.with_suffix(".json")
    clicks_path = output_dir / f"{prefix.name}__clicks.wav"
    mixed_path = output_dir / f"{prefix.name}__CLICKED.wav"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_seconds", "beat_number", "is_downbeat"])
        for timestamp, beat_value in data:
            beat = int(round(beat_value))
            writer.writerow([f"{timestamp:.6f}", beat, "YES" if beat == 1 else "NO"])

    payload = {
        "schema": "banjofy.bn009.model.v1",
        "source_audio": str(source),
        "beatnet_model": model,
        "mode": "offline",
        "inference_model": "DBN",
        "truth_used": False,
        "summary": summary,
        "beats": [
            {"time_s": round(float(t), 6), "beat_number": int(round(b)), "downbeat": int(round(b)) == 1}
            for t, b in data
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    create_click_wav(data, wav_duration(song_wav), clicks_path)
    mix_clicked_song(song_wav, clicks_path, mixed_path)
    return {
        "model": model,
        "summary": summary,
        "clicked_song": str(mixed_path),
        "json": str(json_path),
    }


def write_consensus_outputs(output_dir: Path, source: Path, consensus: dict, model_results: list[dict]) -> dict:
    json_path = output_dir / f"{source.stem}__BN009_CONSENSUS.json"
    txt_path = output_dir / f"{source.stem}__BN009_CONSENSUS.txt"

    payload = dict(consensus)
    payload["source_audio"] = str(source)
    payload["truth_used"] = False
    payload["note"] = "Consensus compares unchanged outputs from BeatNet trained models 1, 2 and 3."
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    recommended_model = consensus["recommended_model"]
    recommended_path = None
    if recommended_model is not None:
        recommended_model = int(recommended_model)
        selected = next(result for result in model_results if result["model"] == recommended_model)
        recommended_path = output_dir / f"{source.stem}__BN009_RECOMMENDED_CLICKED.wav"
        shutil.copy2(selected["clicked_song"], recommended_path)

    lines = [
        "BANJOFY BN CONSENSUS LAB 009",
        "",
        f"Song: {source.name}",
        f"Recommended model: {recommended_model if recommended_model is not None else 'NONE - AMBIGUOUS'}",
        f"Confidence: {consensus['confidence']}",
        f"Consensus BPM: {consensus['consensus_bpm']}",
        f"Consensus meter: {consensus['consensus_meter']}",
        f"Tempo family models: {consensus['tempo_family_models']}",
        f"Meter votes: {consensus['meter_votes']}",
        f"Meter resolution: {consensus['meter_resolution']}",
        f"Meter accent scores: {consensus['meter_accent_scores']}",
        "",
        "MODEL SCORES",
    ]
    for item in consensus["models"]:
        lines.append(
            f"Model {item['model']}: score={item['score']:.4f}, bpm={item['bpm']}, meter={item['meter']}/4, "
            f"tempo support={item['tempo_support']}, accent={item['meter_accent_score']:.4f}, "
            f"beat agreement={item['beat_agreement']:.4f}, downbeat agreement={item['downbeat_agreement']:.4f}"
        )
    lines.append("")
    if recommended_path is not None:
        lines += [
            f"Listen first to: {recommended_path.name}",
            "High click = Beat 1. Lower click = other beats.",
        ]
    else:
        lines += [
            "NO RECOMMENDED CLICKED WAV WAS CREATED.",
            "BN009 found a supported tempo family but could not safely resolve the meter.",
            "Listen only to the individual candidate-model WAVs if investigation is needed.",
        ]
    lines.append("Low confidence means BN009 detected meaningful disagreement and is not claiming certainty.")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(json_path),
        "report": str(txt_path),
        "recommended_clicked_song": str(recommended_path) if recommended_path is not None else None,
    }


def run_bn009(source: Path, output_dir: Path, progress) -> dict:
    from BeatNet.BeatNet import BeatNet

    output_dir.mkdir(parents=True, exist_ok=True)
    model_results = []
    model_outputs: dict[int, np.ndarray] = {}

    with tempfile.TemporaryDirectory(prefix="banjofy_bn009_") as temp_name:
        wav_path = Path(temp_name) / "input.wav"
        progress("Converting selected audio to BeatNet WAV format…")
        convert_to_wav(source, wav_path)

        # PROVEN BN008 ANALYSIS PATH: do not change these BeatNet settings.
        for model in (1, 2, 3):
            progress(f"BeatNet model {model} is listening to the whole song…")
            estimator = BeatNet(
                model,
                mode="offline",
                inference_model="DBN",
                plot=[],
                thread=False,
                device="cpu",
            )
            raw = estimator.process(str(wav_path))
            data = normalise_output(raw)
            model_outputs[model] = data
            summary = estimate_summary(data)
            progress(f"Model {model}: {summary['bpm']} BPM, {summary['meter']}, {summary['downbeat_count']} downbeats.")
            model_results.append(write_model_outputs(output_dir, source, model, data, summary, wav_path))

        progress("Measuring source-audio accents at each model's proposed Beat 1 positions…")
        meter_accent_scores = {model: meter_accent_score(data, wav_path) for model, data in model_outputs.items()}
        for model in sorted(meter_accent_scores):
            progress(f"Model {model} Beat-1 accent score: {meter_accent_scores[model]:.4f}")
        progress("Comparing Models 1, 2 and 3…")
        consensus = analyse_consensus(model_outputs, meter_accent_scores=meter_accent_scores)

    consensus_files = write_consensus_outputs(output_dir, source, consensus, model_results)
    return {"models": model_results, "consensus": consensus, "files": consensus_files}


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x760")
        self.minsize(920, 640)
        self.messages: queue.Queue = queue.Queue()
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a song to begin.")
        self._build()
        self.after(100, self._poll)
        self._startup_probe()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=("Runs the proven BeatNet offline DBN path through trained Models 1, 2 and 3, then compares their "
                  "beat/downbeat outputs to recommend one Banjofy timing source when the evidence is strong enough. "
                  "No verified song answers are used."),
            wraplength=1060,
        ).pack(anchor="w", pady=(5, 16))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Audio file:", width=16).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="Choose audio file", command=self._choose_audio).grid(row=0, column=2)
        ttk.Label(form, text="Output folder:", width=16).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="Choose output folder", command=self._choose_output).grid(row=1, column=2)
        form.columnconfigure(1, weight=1)

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=14)
        self.run_button = ttk.Button(row, text="Run BN Consensus Test", command=self._run)
        self.run_button.pack(side="left")
        ttk.Label(row, textvariable=self.status_var, wraplength=800).pack(side="left", padx=14)

        guide = ttk.LabelFrame(outer, text="What BN009 will produce", padding=10)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(
            guide,
            text=("You always get all three model clicked WAVs and a consensus report. When the evidence is strong enough, "
                  "BN009 also creates one RECOMMENDED_CLICKED WAV. If tempo or meter remains genuinely ambiguous, it says so "
                  "instead of manufacturing a recommendation."),
            wraplength=1040,
        ).pack(anchor="w")

        log_frame = ttk.LabelFrame(outer, text="Progress and consensus result", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, wrap="word", height=22)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _choose_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a song",
            filetypes=[("Audio files", "*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.wma"), ("All files", "*.*")],
        )
        if path:
            self.source_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).parent / "BN009 Results"))

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    def _append(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _run(self) -> None:
        source = Path(self.source_var.get().strip())
        output_text = self.output_var.get().strip()
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO:
            messagebox.showerror(APP_TITLE, "Choose a valid audio file first.")
            return
        if not output_text:
            messagebox.showerror(APP_TITLE, "Choose an output folder first.")
            return
        output = Path(output_text)
        self.run_button.configure(state="disabled")
        self._append("")
        self._append(f"Song: {source}")
        self._append("Models: 1, 2, 3")
        self.status_var.set("BN009 started…")

        def progress(text: str) -> None:
            self.messages.put(("progress", text))

        def worker() -> None:
            try:
                result = run_bn009(source, output, progress)
                self.messages.put(("done", result))
            except Exception as exc:
                self.messages.put(("error", f"{exc}\n\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "progress":
                    self.status_var.set(str(payload))
                    self._append(str(payload))
                elif kind == "done":
                    self.run_button.configure(state="normal")
                    consensus = payload["consensus"]
                    self.status_var.set("BN009 consensus complete.")
                    self._append("")
                    for result in payload["models"]:
                        s = result["summary"]
                        self._append(f"Model {result['model']}: {s['bpm']} BPM, {s['meter']}")
                    self._append("")
                    recommended = consensus["recommended_model"]
                    if recommended is None:
                        self._append("RECOMMENDED MODEL: NONE - AMBIGUOUS")
                    else:
                        self._append(f"RECOMMENDED MODEL: {recommended}")
                    self._append(f"CONFIDENCE: {consensus['confidence'].upper()}")
                    self._append(f"CONSENSUS BPM: {consensus['consensus_bpm']}")
                    self._append(f"CONSENSUS METER: {consensus['consensus_meter']}")
                    self._append(f"TEMPO FAMILY MODELS: {consensus['tempo_family_models']}")
                    self._append(f"METER RESOLUTION: {consensus['meter_resolution']}")
                    self._append(f"METER ACCENT SCORES: {consensus['meter_accent_scores']}")
                    recommended_file = payload["files"]["recommended_clicked_song"]
                    if recommended_file:
                        self._append(f"Recommended clicked song: {recommended_file}")
                        messagebox.showinfo(
                            APP_TITLE,
                            f"BN009 recommends Model {recommended} with {consensus['confidence']} confidence.\n\n"
                            "Listen to the RECOMMENDED_CLICKED WAV first.",
                        )
                    else:
                        self._append("No recommended clicked song created because meter is unresolved.")
                        messagebox.showwarning(
                            APP_TITLE,
                            "BN009 found a supported tempo family but could not safely resolve the meter.\n\n"
                            "No automatic recommendation has been created.",
                        )
                elif kind == "error":
                    self.run_button.configure(state="normal")
                    self.status_var.set("BN009 failed.")
                    self._append(str(payload))
                    messagebox.showerror(APP_TITLE, "BN009 failed. The exact error is shown in the window.")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _startup_probe(self) -> None:
        probe = os.environ.get("BANJOFY_BEATNET_STARTUP_PROBE_FILE")
        if probe:
            Path(probe).write_text(json.dumps({"status": "ready", "app": APP_TITLE}), encoding="utf-8")
            self.after(100, self.destroy)


if __name__ == "__main__":
    Application().mainloop()
