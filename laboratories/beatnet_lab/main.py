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

APP_TITLE = "Banjofy BeatNet Listening Laboratory 005"
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


def write_outputs(output_dir: Path, source: Path, model: int, data: np.ndarray, summary: dict, song_wav: Path) -> dict:
    stem = source.stem
    prefix = output_dir / f"{stem}__BeatNet_Model_{model}"
    csv_path = prefix.with_suffix(".csv")
    json_path = prefix.with_suffix(".json")
    txt_path = prefix.with_suffix(".txt")
    clicks_path = output_dir / f"{prefix.name}__clicks_only.wav"
    mixed_path = output_dir / f"{prefix.name}__CLICKED_SONG.wav"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_seconds", "beat_number", "is_downbeat"])
        for timestamp, beat_value in data:
            beat = int(round(beat_value))
            writer.writerow([f"{timestamp:.6f}", beat, "YES" if beat == 1 else "NO"])

    payload = {
        "schema": "banjofy.beatnet_listening_test.v1",
        "laboratory": "BeatNet Listening Laboratory 005",
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

    lines = [
        "BANJOFY BEATNET LISTENING LABORATORY 001",
        "",
        f"Song: {source.name}",
        f"BeatNet trained model: {model}",
        "Mode: offline DBN",
        "Verified answers used during analysis: NO",
        "",
        f"Detected BPM: {summary['bpm']}",
        f"Detected meter: {summary['meter']}",
        f"Detected beats: {summary['beat_count']}",
        f"Detected downbeats: {summary['downbeat_count']}",
        f"First downbeat: {summary['first_downbeat_s']} seconds",
        "",
        "LISTENING TEST",
        f"Open: {mixed_path.name}",
        "The high click is Beat 1. The lower click marks the other beats.",
        "Judge whether Beat 1 remains correct from the beginning to the end.",
    ]
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    create_click_wav(data, wav_duration(song_wav), clicks_path)
    mix_clicked_song(song_wav, clicks_path, mixed_path)
    return {"model": model, "summary": summary, "clicked_song": str(mixed_path), "report": str(txt_path)}


def run_beatnet(source: Path, output_dir: Path, models: list[int], progress) -> list[dict]:
    from BeatNet.BeatNet import BeatNet

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="banjofy_beatnet_") as temp_name:
        wav_path = Path(temp_name) / "input.wav"
        progress("Converting the selected audio to BeatNet's WAV format…")
        convert_to_wav(source, wav_path)

        for model in models:
            progress(f"BeatNet trained model {model} is listening to the whole song…")
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
            summary = estimate_summary(data)
            progress(
                f"Model {model}: {summary['bpm']} BPM, {summary['meter']}, "
                f"{summary['downbeat_count']} downbeats. Creating clicked song…"
            )
            results.append(write_outputs(output_dir, source, model, data, summary, wav_path))
    return results


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x720")
        self.minsize(920, 620)
        self.messages: queue.Queue = queue.Queue()
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.model_var = tk.StringVar(value="All three trained models")
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
            text=("A completely separate test of BeatNet's trained beat, downbeat, BPM and meter detection. "
                  "No Banjofy timing scores or verified answers are used."),
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
        ttk.Label(form, text="BeatNet model:", width=16).grid(row=2, column=0, sticky="w", pady=5)
        combo = ttk.Combobox(
            form, textvariable=self.model_var, state="readonly",
            values=("All three trained models", "Model 1", "Model 2", "Model 3"),
        )
        combo.grid(row=2, column=1, sticky="w", padx=6)
        form.columnconfigure(1, weight=1)

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=14)
        self.run_button = ttk.Button(row, text="Run BeatNet Listening Test", command=self._run)
        self.run_button.pack(side="left")
        ttk.Label(row, textvariable=self.status_var, wraplength=800).pack(side="left", padx=14)

        guide = ttk.LabelFrame(outer, text="What to listen for", padding=10)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(
            guide,
            text=("Each model creates a CLICKED_SONG WAV. The high click is Beat 1; lower clicks are the other beats. "
                  "A result passes only when the high click marks the real start of every bar and stays locked for the whole song."),
            wraplength=1040,
        ).pack(anchor="w")

        log_frame = ttk.LabelFrame(outer, text="Progress and results", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, wrap="word", height=20)
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
                self.output_var.set(str(Path(path).parent / "BeatNet Test Results"))

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    def _append(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _run(self) -> None:
        source = Path(self.source_var.get().strip())
        output = Path(self.output_var.get().strip())
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO:
            messagebox.showerror(APP_TITLE, "Choose a valid audio file first.")
            return
        if not str(output):
            messagebox.showerror(APP_TITLE, "Choose an output folder first.")
            return
        selected = self.model_var.get()
        models = [1, 2, 3] if selected.startswith("All") else [int(selected[-1])]
        self.run_button.configure(state="disabled")
        self._append("")
        self._append(f"Song: {source}")
        self._append(f"Models: {models}")
        self.status_var.set("BeatNet test started…")

        def progress(text: str) -> None:
            self.messages.put(("progress", text))

        def worker() -> None:
            try:
                results = run_beatnet(source, output, models, progress)
                self.messages.put(("done", results))
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
                    self.status_var.set("BeatNet listening test complete.")
                    self._append("")
                    for result in payload:
                        s = result["summary"]
                        self._append(f"Model {result['model']}: {s['bpm']} BPM, {s['meter']}")
                        self._append(f"Clicked song: {result['clicked_song']}")
                    messagebox.showinfo(APP_TITLE, "BeatNet finished. Open each CLICKED_SONG WAV and listen to the strong Beat 1 clicks.")
                elif kind == "error":
                    self.run_button.configure(state="normal")
                    self.status_var.set("BeatNet test failed.")
                    self._append(str(payload))
                    messagebox.showerror(APP_TITLE, "BeatNet failed. The exact error is shown in the window.")
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
