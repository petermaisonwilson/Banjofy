from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback
import webbrowser
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import analysis_engine

APP_TITLE = "Banjofy Song Analysis Laboratory 001"
SETTINGS_FILENAME = "song_analysis_lab_settings.json"


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    folder = base / "Banjofy" / "SongAnalysisLab"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} is not a valid Banjofy song record")
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".working")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def resolve_record_audio(record: dict, record_path: Path) -> Path | None:
    raw = record.get("practice_audio_path")
    if not raw:
        return None
    candidate = Path(str(raw)).expanduser()
    if candidate.is_file():
        return candidate

    # A Library may have been moved after acquisition. Recover by filename
    # from the standard Library-root Media/Audio folder.
    library_root = record_path.parents[2]
    recovered = library_root / "Media" / "Audio" / candidate.name
    return recovered if recovered.is_file() else None


def discover_library_songs(library_root: Path) -> list[dict]:
    songs_folder = library_root / "Library" / "Songs"
    if not songs_folder.is_dir():
        return []

    songs: list[dict] = []
    for record_path in sorted(songs_folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = read_json(record_path)
            audio = resolve_record_audio(record, record_path)
        except Exception:
            continue
        if audio is None:
            continue
        songs.append({
            "record_path": record_path,
            "record": record,
            "audio_path": audio,
            "song_id": str(record.get("song_id") or record_path.stem),
            "title": str(record.get("title_requested") or audio.stem),
            "analysis_status": str(record.get("analysis_status") or "not_started"),
            "duration_seconds": float(record.get("duration_seconds") or 0.0),
        })
    return songs


def analysis_payload(result: analysis_engine.AnalysisResult) -> dict:
    payload = asdict(result)
    payload["engine_baseline"] = "Banjofy Chord Laboratory 016"
    payload["integration_laboratory"] = APP_TITLE
    payload["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return payload


def commit_analysis_to_library(
    library_root: Path,
    record_path: Path,
    result: analysis_engine.AnalysisResult,
) -> tuple[Path, Path]:
    record = read_json(record_path)
    song_id = str(record.get("song_id") or record_path.stem)
    output_folder = library_root / "Analysis" / song_id
    output_folder.mkdir(parents=True, exist_ok=True)

    payload = analysis_payload(result)
    analysis_path = output_folder / "song_analysis.json"
    write_json_atomic(analysis_path, payload)

    record["analysis_status"] = "completed"
    record["analysis_engine"] = "Banjofy Chord Laboratory 016"
    record["analysis_version"] = result.analysis_version
    record["analysis_path"] = str(analysis_path)
    record["analysis_completed_at"] = payload["completed_at"]
    record["analysis_summary"] = {
        "key": result.key,
        "key_confidence": round(float(result.key_confidence), 4),
        "raw_bpm": round(float(result.raw_bpm), 3),
        "practice_bpm": round(float(result.practice_bpm), 3),
        "meter": result.meter,
        "beat_count": int(result.beat_count),
        "main_chords": list(result.main_chords),
        "beginner_chords": list(result.beginner_chords),
        "intermediate_chords": list(result.intermediate_chords),
        "professional_chords": list(result.professional_chords),
        "chord_segment_count": len(result.segments),
        "musical_end_seconds": round(float(result.musical_end_s), 3),
    }
    write_json_atomic(record_path, record)
    return analysis_path, record_path


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


class SongAnalysisWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x720")
        self.minsize(850, 620)

        self.library_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose the Banjofy Library used by the acquisition stage")
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.songs: list[dict] = []
        self.selected_song: dict | None = None

        self._load_settings()
        self._build_ui()
        self.after(150, self._poll)
        if self.library_var.get():
            self.after(300, self._refresh_songs)

    def _load_settings(self) -> None:
        try:
            data = json.loads(settings_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.library_var.set(str(data.get("library_root", "")))

    def _save_settings(self) -> None:
        settings_path().write_text(
            json.dumps({"library_root": self.library_var.get().strip()}, indent=2),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "This build proves the handover from the acquisition Library into the proven "
                "Chord Laboratory 016 analysis engine. It reads the saved Practice audio and "
                "writes the analysis back into the same song record."
            ),
            wraplength=920,
        ).pack(anchor="w", pady=(5, 12))

        library_box = ttk.LabelFrame(outer, text="1. Open the Banjofy Library")
        library_box.pack(fill="x", pady=5)
        ttk.Entry(library_box, textvariable=self.library_var).grid(
            row=0, column=0, sticky="ew", padx=10, pady=8
        )
        ttk.Button(library_box, text="Choose Library folder", command=self._choose_library).grid(
            row=0, column=1, padx=10, pady=8
        )
        ttk.Button(library_box, text="Refresh songs", command=self._refresh_songs).grid(
            row=0, column=2, padx=(0, 10), pady=8
        )
        library_box.columnconfigure(0, weight=1)

        songs_box = ttk.LabelFrame(outer, text="2. Select a Library song")
        songs_box.pack(fill="both", expand=True, pady=5)
        columns = ("title", "duration", "status", "audio")
        self.tree = ttk.Treeview(songs_box, columns=columns, show="headings", height=10, selectmode="browse")
        self.tree.heading("title", text="Song")
        self.tree.heading("duration", text="Length")
        self.tree.heading("status", text="Analysis")
        self.tree.heading("audio", text="Practice audio")
        self.tree.column("title", width=330, anchor="w")
        self.tree.column("duration", width=70, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("audio", width=380, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._song_selected)
        self.tree.bind("<Double-1>", lambda _event: self._start_analysis())

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        self.analyse_button = ttk.Button(
            controls,
            text="Analyse Selected Library Song",
            command=self._start_analysis,
            state="disabled",
        )
        self.analyse_button.pack(side="left")
        ttk.Button(controls, text="Open Analysis Folder", command=self._open_analysis_folder).pack(
            side="right"
        )

        status_box = ttk.LabelFrame(outer, text="Analysis status")
        status_box.pack(fill="both", expand=True, pady=5)
        ttk.Label(status_box, textvariable=self.status_var, wraplength=920).pack(
            anchor="w", padx=10, pady=8
        )
        self.output = tk.Text(status_box, height=12, wrap="word", state="disabled", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _choose_library(self) -> None:
        chosen = filedialog.askdirectory(title="Choose the Banjofy Library folder")
        if chosen:
            self.library_var.set(chosen)
            self._save_settings()
            self._refresh_songs()

    def _library_root(self) -> Path | None:
        text = self.library_var.get().strip()
        if not text:
            messagebox.showerror(APP_TITLE, "Choose the Banjofy Library folder first.")
            return None
        root = Path(text).expanduser()
        if not root.is_dir():
            messagebox.showerror(APP_TITLE, f"The selected Library folder does not exist:\n{root}")
            return None
        return root

    def _refresh_songs(self) -> None:
        root = self._library_root()
        if root is None:
            return
        self.songs = discover_library_songs(root)
        self.selected_song = None
        self.analyse_button.configure(state="disabled")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, song in enumerate(self.songs):
            self.tree.insert(
                "", "end", iid=str(index),
                values=(
                    song["title"],
                    format_duration(song["duration_seconds"]),
                    song["analysis_status"],
                    song["audio_path"].name,
                ),
            )
        if self.songs:
            self.status_var.set(f"Found {len(self.songs)} Library song(s) with saved Practice audio")
            self._append(f"Library scan found {len(self.songs)} analysable song(s)")
        else:
            self.status_var.set("No Library song with a valid saved Practice-audio file was found")
            self._append("No analysable Library songs were found")

    def _song_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            self.selected_song = None
            self.analyse_button.configure(state="disabled")
            return
        self.selected_song = self.songs[int(selected[0])]
        self.analyse_button.configure(state="normal")
        self.status_var.set(f"Selected: {self.selected_song['title']}")

    def _start_analysis(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select a Library song first.")
            return
        root = self._library_root()
        if root is None:
            return

        song = self.selected_song
        audio_path = Path(song["audio_path"])
        record_path = Path(song["record_path"])
        if not audio_path.is_file():
            messagebox.showerror(APP_TITLE, f"The Practice audio can no longer be found:\n{audio_path}")
            return

        output_folder = root / "Analysis" / song["song_id"]
        self.analyse_button.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.status_var.set("Starting the proven Laboratory 016 analysis engine...")
        self._append(f"Song record: {record_path}")
        self._append(f"Practice audio: {audio_path}")

        def worker() -> None:
            try:
                result = analysis_engine.analyse_audio(
                    audio_path,
                    output_folder,
                    lambda message: self.messages.put(("status", message)),
                )
                analysis_path, updated_record = commit_analysis_to_library(
                    root, record_path, result
                )
                self.messages.put(("done", {
                    "result": result,
                    "analysis_path": analysis_path,
                    "record_path": updated_record,
                }))
            except Exception as exc:
                self.messages.put(("error", f"{exc}\n\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "status":
                self.status_var.set(str(payload))
                self._append(str(payload))
            elif kind == "error":
                self.analyse_button.configure(state="normal")
                self.status_var.set("Analysis failed")
                self._append(str(payload))
                messagebox.showerror(
                    APP_TITLE,
                    "Analysis failed. The exact error is displayed in the laboratory window.",
                )
            elif kind == "done":
                result = payload["result"]
                self.status_var.set("Song analysis and Library update successful")
                self._append("")
                self._append(f"Likely key: {result.key} ({result.key_confidence:.0%})")
                self._append(f"Raw tempo: {result.raw_bpm:.1f} BPM")
                self._append(f"Suggested Practice tempo: {result.practice_bpm:.1f} BPM")
                self._append(f"Detected beats: {result.beat_count}")
                self._append(f"Main chords: {', '.join(result.main_chords)}")
                self._append(f"Chord timeline segments: {len(result.segments)}")
                self._append(f"Analysis JSON: {payload['analysis_path']}")
                self._append(f"Updated Library record: {payload['record_path']}")
                self.analyse_button.configure(state="normal")
                self._refresh_songs()
                messagebox.showinfo(
                    APP_TITLE,
                    "The saved Practice audio was analysed and the results were written "
                    "back into the Banjofy Library record.",
                )

        self.after(150, self._poll)

    def _open_analysis_folder(self) -> None:
        root = self._library_root()
        if root is None:
            return
        folder = root / "Analysis"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(folder.as_uri())


def main() -> int:
    analysis_engine.ensure_safe_console_streams()
    SongAnalysisWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
