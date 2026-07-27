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

import structure_engine

APP_TITLE = "Banjofy Song Analysis Laboratory 005 — Meter, Bars and Downbeats"
SETTINGS_FILENAME = "song_analysis_lab_settings.json"


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    folder = base / "Banjofy" / "SongAnalysisLab"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def load_library_setting(path: Path | None = None) -> str:
    target = path or settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("library_root") or "")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} is not a valid JSON object")
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".working")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def resolve_audio(record: dict, record_path: Path) -> Path | None:
    raw = record.get("practice_audio_path")
    if not raw:
        return None
    candidate = Path(str(raw)).expanduser()
    if candidate.is_file():
        return candidate
    library_root = record_path.parents[2]
    recovered = library_root / "Media" / "Audio" / candidate.name
    return recovered if recovered.is_file() else None


def resolve_analysis(record: dict, record_path: Path) -> Path | None:
    raw = record.get("analysis_path")
    if raw:
        candidate = Path(str(raw)).expanduser()
        if candidate.is_file():
            return candidate
    library_root = record_path.parents[2]
    song_id = str(record.get("song_id") or record_path.stem)
    recovered = library_root / "Analysis" / song_id / "song_analysis.json"
    return recovered if recovered.is_file() else None


def discover_analysed_songs(library_root: Path) -> list[dict]:
    folder = library_root / "Library" / "Songs"
    if not folder.is_dir():
        return []
    songs = []
    for record_path in sorted(folder.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            record = read_json(record_path)
            audio = resolve_audio(record, record_path)
            analysis = resolve_analysis(record, record_path)
        except Exception:
            continue
        if audio is None or analysis is None:
            continue
        songs.append({
            "record_path": record_path,
            "record": record,
            "audio_path": audio,
            "analysis_path": analysis,
            "song_id": str(record.get("song_id") or record_path.stem),
            "title": str(record.get("title_requested") or audio.stem),
            "structure_status": str(record.get("structure_status") or "not_started"),
        })
    return songs


def commit_structure(
    library_root: Path,
    record_path: Path,
    analysis_path: Path,
    result: structure_engine.StructureResult,
) -> tuple[Path, Path, Path]:
    record = read_json(record_path)
    analysis = read_json(analysis_path)
    song_id = str(record.get("song_id") or record_path.stem)
    folder = library_root / "Analysis" / song_id
    folder.mkdir(parents=True, exist_ok=True)

    structure_path = folder / "song_structure.json"
    payload = asdict(result)
    payload["integration_laboratory"] = APP_TITLE
    payload["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_json_atomic(structure_path, payload)

    summary = {
        "meter": result.meter,
        "meter_confidence": round(float(result.meter_confidence), 4),
        "beats_per_bar": int(result.beats_per_bar),
        "first_downbeat_beat_index": int(result.first_downbeat_beat_index),
        "beat_count": int(result.beat_count),
        "bar_count": int(result.bar_count),
        "bar_start_times": list(result.bar_start_times),
        "downbeat_times": list(result.downbeat_times),
    }

    record["structure_status"] = "completed"
    record["structure_version"] = result.structure_version
    record["structure_path"] = str(structure_path)
    record["structure_completed_at"] = payload["completed_at"]
    record["structure_summary"] = summary
    write_json_atomic(record_path, record)

    analysis["meter"] = result.meter
    analysis["meter_confidence"] = result.meter_confidence
    analysis["beats_per_bar"] = result.beats_per_bar
    analysis["beat_times"] = result.beat_times
    analysis["downbeat_times"] = result.downbeat_times
    analysis["bar_start_times"] = result.bar_start_times
    analysis["bar_count"] = result.bar_count
    analysis["beat_grid"] = result.beat_grid
    analysis["bars"] = result.bars
    analysis["bar_aligned_chords"] = result.bar_aligned_chords
    analysis["structure_version"] = result.structure_version
    write_json_atomic(analysis_path, analysis)

    return structure_path, record_path, analysis_path


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1020x760")
        self.minsize(880, 650)
        # Tk variables must exist before any persisted settings are read.
        self.library_var = tk.StringVar(master=self, value="")
        self.status_var = tk.StringVar(
            master=self,
            value="Choose the Library that passed Song Analysis Laboratory 001",
        )
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.songs: list[dict] = []
        self.selected_song: dict | None = None
        self._load_settings()
        self._build_ui()
        self.after(150, self._poll)
        if self.library_var.get():
            self.after(300, self._refresh)

    def _load_settings(self) -> None:
        # This method is deliberately safe when a settings file already exists.
        # GitHub now proves this exact persisted-settings startup path.
        library_value = load_library_setting()
        if hasattr(self, "library_var"):
            self.library_var.set(library_value)

    def _save_settings(self) -> None:
        write_json_atomic(settings_path(), {"library_root": self.library_var.get().strip()})

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "This build leaves the passed chord analysis unchanged. It estimates metre and "
                "downbeats from rhythmic accents, then adds numbered bars and a bar-aligned chord view."
            ),
            wraplength=950,
        ).pack(anchor="w", pady=(5, 12))

        library = ttk.LabelFrame(outer, text="1. Open the analysed Banjofy Library")
        library.pack(fill="x", pady=5)
        ttk.Entry(library, textvariable=self.library_var).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Button(library, text="Choose Library folder", command=self._choose).grid(row=0, column=1, padx=10, pady=8)
        ttk.Button(library, text="Refresh songs", command=self._refresh).grid(row=0, column=2, padx=(0, 10), pady=8)
        library.columnconfigure(0, weight=1)

        songs = ttk.LabelFrame(outer, text="2. Select a song that passed Laboratory 001")
        songs.pack(fill="both", expand=True, pady=5)
        columns = ("title", "analysis", "structure", "audio")
        self.tree = ttk.Treeview(songs, columns=columns, show="headings", height=10, selectmode="browse")
        for key, title, width in (
            ("title", "Song", 330),
            ("analysis", "Chord analysis", 120),
            ("structure", "Structure", 110),
            ("audio", "Practice audio", 380),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w" if key in {"title", "audio"} else "center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._selected)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        self.run_button = ttk.Button(
            controls, text="Detect Meter, Bars and Downbeats",
            command=self._start, state="disabled",
        )
        self.run_button.pack(side="left")
        ttk.Button(controls, text="Open Analysis Folder", command=self._open_folder).pack(side="right")

        status = ttk.LabelFrame(outer, text="Structure-analysis status")
        status.pack(fill="both", expand=True, pady=5)
        ttk.Label(status, textvariable=self.status_var, wraplength=950).pack(anchor="w", padx=10, pady=8)
        self.output = tk.Text(status, height=13, state="disabled", wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _choose(self) -> None:
        chosen = filedialog.askdirectory(title="Choose the analysed Banjofy Library root")
        if chosen:
            self.library_var.set(chosen)
            self._save_settings()
            self._refresh()

    def _root(self) -> Path | None:
        text = self.library_var.get().strip()
        if not text:
            messagebox.showerror(APP_TITLE, "Choose the Banjofy Library root first.")
            return None
        root = Path(text)
        if not root.is_dir():
            messagebox.showerror(APP_TITLE, f"The selected folder does not exist:\n{root}")
            return None
        return root

    def _refresh(self) -> None:
        root = self._root()
        if root is None:
            return
        self.songs = discover_analysed_songs(root)
        self.selected_song = None
        self.run_button.configure(state="disabled")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, song in enumerate(self.songs):
            self.tree.insert("", "end", iid=str(index), values=(
                song["title"],
                song["record"].get("analysis_status", "unknown"),
                song["structure_status"],
                song["audio_path"].name,
            ))
        self.status_var.set(
            f"Found {len(self.songs)} song(s) with both Practice audio and Laboratory 001 analysis"
            if self.songs else
            "No song with both Practice audio and Laboratory 001 analysis was found"
        )

    def _selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            self.selected_song = None
            self.run_button.configure(state="disabled")
            return
        self.selected_song = self.songs[int(selected[0])]
        self.run_button.configure(state="normal")
        self.status_var.set(f"Selected: {self.selected_song['title']}")

    def _start(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        root = self._root()
        if root is None:
            return

        song = self.selected_song
        self.run_button.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._append(f"Existing Library JSON filename: {song['record_path'].name}")
        self._append("That filename will remain unchanged; its contents will be updated.")

        def worker() -> None:
            try:
                analysis = read_json(song["analysis_path"])
                segments = analysis.get("segments")
                if not isinstance(segments, list) or not segments:
                    raise RuntimeError("The Laboratory 001 song_analysis.json contains no chord segments.")
                result = structure_engine.analyse_structure(
                    song["audio_path"], segments,
                    lambda text: self.messages.put(("status", text)),
                )
                paths = commit_structure(
                    root, song["record_path"], song["analysis_path"], result
                )
                self.messages.put(("done", {"result": result, "paths": paths}))
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
                self.run_button.configure(state="normal")
                self.status_var.set("Structure analysis failed")
                self._append(str(payload))
                messagebox.showerror(APP_TITLE, "Structure analysis failed. The exact error is shown in the window.")
            elif kind == "done":
                result = payload["result"]
                structure_path, record_path, analysis_path = payload["paths"]
                self.status_var.set("Meter, bars and downbeats saved successfully")
                self._append("")
                self._append(f"Estimated meter: {result.meter}")
                self._append(f"Meter confidence: {result.meter_confidence:.0%}")
                self._append(f"Beats per bar: {result.beats_per_bar}")
                self._append(f"Detected beats: {result.beat_count}")
                self._append(f"Estimated bars: {result.bar_count}")
                self._append(f"First downbeat beat index: {result.first_downbeat_beat_index}")
                self._append(f"New structure file: {structure_path}")
                self._append(f"Updated existing Library JSON: {record_path}")
                self._append(f"Updated existing song analysis JSON: {analysis_path}")
                self.run_button.configure(state="normal")
                self._refresh()
                messagebox.showinfo(
                    APP_TITLE,
                    "The structure pass completed.\n\n"
                    "The existing JSON filenames have not changed. Open them in Notepad "
                    "to inspect the new meter, bar and downbeat fields.",
                )
        self.after(150, self._poll)

    def _open_folder(self) -> None:
        root = self._root()
        if root is None:
            return
        folder = root / "Analysis"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(folder.as_uri())


def main() -> int:
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
