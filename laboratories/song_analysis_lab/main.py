from __future__ import annotations

import bisect
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

APP_TITLE = "Banjofy Song Analysis Laboratory 013 — Downbeat Phase Audition"
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
) -> tuple[Path, Path, Path, Path]:
    record = read_json(record_path)
    analysis = read_json(analysis_path)
    song_id = str(record.get("song_id") or record_path.stem)
    folder = library_root / "Analysis" / song_id
    folder.mkdir(parents=True, exist_ok=True)

    audible_check_path = folder / "audible_bar_check.wav"
    structure_engine.create_audible_bar_check(
        Path(result.source_audio),
        result.beat_times,
        result.downbeat_times,
        audible_check_path,
    )
    if not audible_check_path.is_file() or audible_check_path.stat().st_size == 0:
        raise RuntimeError("The audible bar-check file was not created successfully.")

    # Create one full 180-second audition file for each possible phase.
    # Chord times and beat spacing are unchanged; only the strong downbeat click moves.
    phase_check_paths: list[str] = []
    beats_per_bar = int(result.beats_per_bar)
    for phase_offset in range(beats_per_bar):
        effective_phase = (
            int(result.first_downbeat_beat_index) + phase_offset
        ) % beats_per_bar
        phase_downbeats = [
            float(result.beat_times[index])
            for index in range(effective_phase, len(result.beat_times), beats_per_bar)
        ]
        phase_path = folder / f"audible_phase_{phase_offset + 1}.wav"
        structure_engine.create_audible_bar_check(
            Path(result.source_audio),
            result.beat_times,
            phase_downbeats,
            phase_path,
        )
        if not phase_path.is_file() or phase_path.stat().st_size == 0:
            raise RuntimeError(
                f"Downbeat phase audition file {phase_offset + 1} was not created."
            )
        phase_check_paths.append(str(phase_path))

    structure_path = folder / "song_structure.json"
    payload = asdict(result)
    payload["integration_laboratory"] = APP_TITLE
    payload["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    payload["audible_bar_check_path"] = str(audible_check_path)
    payload["downbeat_phase_audition_paths"] = phase_check_paths

    summary = {
        "meter": result.meter,
        "meter_status": result.meter_status,
        "best_meter_candidate": result.best_meter_candidate,
        "meter_confidence": round(float(result.meter_confidence), 4),
        "full_track_meter_confidence": round(float(result.full_track_meter_confidence), 4),
        "rhythmic_window_candidate": result.rhythmic_window_candidate,
        "rhythmic_window_meter_confidence": round(float(result.rhythmic_window_meter_confidence), 4),
        "meter_candidate_agreement": bool(result.meter_candidate_agreement),
        "rhythmic_window_start_beat": int(result.rhythmic_window_start_beat),
        "rhythmic_window_end_beat": int(result.rhythmic_window_end_beat),
        "rhythmic_window_start_s": float(result.rhythmic_window_start_s),
        "rhythmic_window_end_s": float(result.rhythmic_window_end_s),
        "beats_per_bar": int(result.beats_per_bar),
        "first_downbeat_beat_index": int(result.first_downbeat_beat_index),
        "beat_count": int(result.beat_count),
        "bar_count": int(result.bar_count),
        "bar_start_times": list(result.bar_start_times),
        "downbeat_times": list(result.downbeat_times),
    }

    updated_record = dict(record)
    updated_record["structure_status"] = "completed"
    updated_record["structure_version"] = result.structure_version
    updated_record["structure_path"] = str(structure_path)
    updated_record["structure_completed_at"] = payload["completed_at"]
    updated_record["structure_summary"] = summary
    updated_record["audible_bar_check_path"] = str(audible_check_path)
    updated_record["downbeat_phase_audition_paths"] = phase_check_paths

    updated_analysis = dict(analysis)
    updated_analysis["meter"] = result.meter
    updated_analysis["meter_status"] = result.meter_status
    updated_analysis["best_meter_candidate"] = result.best_meter_candidate
    updated_analysis["meter_confidence"] = result.meter_confidence
    updated_analysis["full_track_meter_confidence"] = result.full_track_meter_confidence
    updated_analysis["rhythmic_window_candidate"] = result.rhythmic_window_candidate
    updated_analysis["rhythmic_window_meter_confidence"] = result.rhythmic_window_meter_confidence
    updated_analysis["meter_candidate_agreement"] = result.meter_candidate_agreement
    updated_analysis["rhythmic_window_start_beat"] = result.rhythmic_window_start_beat
    updated_analysis["rhythmic_window_end_beat"] = result.rhythmic_window_end_beat
    updated_analysis["rhythmic_window_start_s"] = result.rhythmic_window_start_s
    updated_analysis["rhythmic_window_end_s"] = result.rhythmic_window_end_s
    updated_analysis["beats_per_bar"] = result.beats_per_bar
    updated_analysis["first_downbeat_beat_index"] = result.first_downbeat_beat_index
    updated_analysis["beat_times"] = result.beat_times
    updated_analysis["downbeat_times"] = result.downbeat_times
    updated_analysis["bar_start_times"] = result.bar_start_times
    updated_analysis["bar_count"] = result.bar_count
    updated_analysis["beat_grid"] = result.beat_grid
    updated_analysis["bars"] = result.bars
    updated_analysis["bar_aligned_chords"] = result.bar_aligned_chords
    updated_analysis["structure_version"] = result.structure_version
    updated_analysis["audible_bar_check_path"] = str(audible_check_path)
    updated_analysis["downbeat_phase_audition_paths"] = phase_check_paths

    write_json_atomic(structure_path, payload)
    write_json_atomic(record_path, updated_record)
    write_json_atomic(analysis_path, updated_analysis)

    return structure_path, record_path, analysis_path, audible_check_path


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
        self.visual_window: tk.Toplevel | None = None
        self.visual_started_at: float | None = None
        self.visual_beat_times: list[float] = []
        self.visual_downbeat_times: list[float] = []
        self.visual_chord_segments: list[dict] = []
        self.visual_beats_per_bar: int = 4
        self.visual_duration: float = 0.0
        self.visual_phase_offset: int = 0
        self.visual_base_first_downbeat_index: int = 0
        self.visual_phase_paths: list[Path] = []
        self.visual_phase_buttons: list[ttk.Button] = []
        self._load_settings()
        self._build_ui()
        self.after(150, self._poll)

        saved_library = self.library_var.get().strip()
        startup_probe = bool(os.environ.get("BANJOFY_STARTUP_PROBE_FILE", "").strip())
        if saved_library and Path(saved_library).is_dir() and not startup_probe:
            self.after(300, self._refresh)
        elif saved_library and not Path(saved_library).is_dir():
            self.status_var.set(
                "The remembered Library folder is currently unavailable. "
                "Choose the correct top-level Library folder."
            )

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
            controls, text="Detect 3/4 or 4/4 and Create Audible Check",
            command=self._start, state="disabled",
        )
        self.run_button.pack(side="left")
        self.play_button = ttk.Button(
            controls,
            text="Play 180-Second Chord + Downbeat Phase Check",
            command=self._play_audible_check,
            state="disabled",
        )
        self.play_button.pack(side="left", padx=8)
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

    def _library_root(self) -> Path | None:
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
        root = self._library_root()
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

        existing_check = self.selected_song["record"].get("audible_bar_check_path")
        if existing_check and Path(str(existing_check)).is_file():
            self.play_button.configure(state="normal")
        else:
            self.play_button.configure(state="disabled")

        self.status_var.set(f"Selected: {self.selected_song['title']}")

    def _start(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        root = self._library_root()
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
                structure_path, record_path, analysis_path, audible_check_path = payload["paths"]
                self.status_var.set("Meter, bars and downbeats saved successfully")
                self._append("")
                self._append(f"Meter result: {result.meter}")
                self._append(f"Best candidate: {result.best_meter_candidate}")
                self._append(f"Meter status: {result.meter_status}")
                self._append(f"Whole-track confidence: {result.full_track_meter_confidence:.0%}")
                self._append(f"Rhythmic-window candidate: {result.rhythmic_window_candidate}")
                self._append(f"Rhythmic-window confidence: {result.rhythmic_window_meter_confidence:.0%}")
                self._append(f"Candidate agreement: {'Yes' if result.meter_candidate_agreement else 'No'}")
                self._append(f"Supporting window: {result.rhythmic_window_start_s:.1f}s to {result.rhythmic_window_end_s:.1f}s")
                self._append(f"Beats per bar: {result.beats_per_bar}")
                self._append(f"Detected beats: {result.beat_count}")
                self._append(f"Estimated bars: {result.bar_count}")
                self._append(f"First downbeat beat index: {result.first_downbeat_beat_index}")
                self._append(f"New structure file: {structure_path}")
                self._append(f"Updated existing Library JSON: {record_path}")
                self._append(f"Updated existing song analysis JSON: {analysis_path}")
                self._append(f"Audible bar check: {audible_check_path}")
                self.play_button.configure(state="normal")
                self.run_button.configure(state="normal")
                self._refresh()
                messagebox.showinfo(
                    APP_TITLE,
                    "The 3/4 or 4/4 structure pass completed.\n\n"
                    "The existing JSON filenames have not changed. Open them in Notepad "
                    "to inspect the new meter, bar and downbeat fields.",
                )
        self.after(150, self._poll)

    def _play_audible_check(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select a Library song first.")
            return

        record = read_json(self.selected_song["record_path"])
        analysis = read_json(self.selected_song["analysis_path"])

        raw_phase_paths = (
            record.get("downbeat_phase_audition_paths")
            or analysis.get("downbeat_phase_audition_paths")
            or []
        )
        self.visual_phase_paths = [
            Path(str(value))
            for value in raw_phase_paths
            if isinstance(value, str) and Path(str(value)).is_file()
        ]

        self.visual_beat_times = [float(v) for v in analysis.get("beat_times", [])]
        self.visual_downbeat_times = [float(v) for v in analysis.get("downbeat_times", [])]
        raw_segments = analysis.get("segments", [])
        self.visual_chord_segments = [
            segment for segment in raw_segments
            if isinstance(segment, dict)
            and isinstance(segment.get("start_s"), (int, float))
            and isinstance(segment.get("end_s"), (int, float))
        ] if isinstance(raw_segments, list) else []
        self.visual_chord_segments.sort(key=lambda item: float(item.get("start_s", 0.0)))

        self.visual_beats_per_bar = int(analysis.get("beats_per_bar") or 4)
        self.visual_base_first_downbeat_index = int(
            analysis.get("first_downbeat_beat_index")
            or record.get("structure_summary", {}).get("first_downbeat_beat_index")
            or 0
        )
        self.visual_phase_offset = 0

        if not self.visual_beat_times or not self.visual_downbeat_times:
            messagebox.showerror(APP_TITLE, "Beat or downbeat data is missing.")
            return
        if not self.visual_chord_segments:
            messagebox.showerror(
                APP_TITLE,
                "The saved song analysis contains no chord segments to display.",
            )
            return
        if len(self.visual_phase_paths) != self.visual_beats_per_bar:
            messagebox.showerror(
                APP_TITLE,
                "The downbeat phase audition files are missing. "
                "Run the structure analysis once in Build 013.",
            )
            return

        self.visual_duration = min(
            structure_engine.AUDIBLE_PREVIEW_SECONDS,
            self.visual_beat_times[-1],
        )
        self._open_visual_window()
        self._start_selected_phase()

    def _start_selected_phase(self) -> None:
        if not self.visual_phase_paths:
            return
        path = self.visual_phase_paths[self.visual_phase_offset]
        if not path.is_file():
            messagebox.showerror(APP_TITLE, f"The selected phase file is missing:\n{path}")
            return
        try:
            import winsound
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not start the phase audition:\n{exc}")
            return
        self.visual_started_at = time.monotonic()
        self._refresh_phase_display()
        self._update_visual_marker()

    def _set_visual_phase(self, phase_offset: int) -> None:
        if self.visual_beats_per_bar <= 0:
            return
        self.visual_phase_offset = int(phase_offset) % self.visual_beats_per_bar
        self._start_selected_phase()

    def _effective_first_downbeat_index(self) -> int:
        return (
            self.visual_base_first_downbeat_index + self.visual_phase_offset
        ) % max(1, self.visual_beats_per_bar)

    def _phase_downbeat_times(self) -> list[float]:
        effective = self._effective_first_downbeat_index()
        return [
            float(self.visual_beat_times[index])
            for index in range(
                effective,
                len(self.visual_beat_times),
                self.visual_beats_per_bar,
            )
        ]

    def _refresh_phase_display(self) -> None:
        if hasattr(self, "visual_phase_var"):
            self.visual_phase_var.set(
                f"Selected Phase {self.visual_phase_offset + 1} · "
                f"first downbeat beat index {self._effective_first_downbeat_index()}"
            )
        for index, button in enumerate(self.visual_phase_buttons):
            button.state(
                ["disabled"]
                if index == self.visual_phase_offset
                else ["!disabled"]
            )

    def _open_visual_window(self) -> None:
        if self.visual_window is not None and self.visual_window.winfo_exists():
            self.visual_window.destroy()

        self.visual_window = tk.Toplevel(self)
        self.visual_window.title("Banjofy Downbeat Phase Audition")
        self.visual_window.geometry("960x620")
        self.visual_window.minsize(840, 560)

        frame = ttk.Frame(self.visual_window, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Chord, Beat and Downbeat Phase Audition",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="center")
        ttk.Label(
            frame,
            text=(
                "The chord names and beat spacing remain unchanged. "
                "Choose each phase in turn; playback restarts from the beginning "
                "and only the strong downbeat click moves."
            ),
            wraplength=900,
        ).pack(anchor="center", pady=(4, 14))

        self.visual_bar_var = tk.StringVar(value="Bar —")
        self.visual_beat_var = tk.StringVar(value="Beat —")
        self.visual_time_var = tk.StringVar(value="0:00 / 3:00")
        self.visual_status_var = tk.StringVar(value="Starting…")
        self.visual_current_chord_var = tk.StringVar(value="—")
        self.visual_next_chord_var = tk.StringVar(value="Next chord: —")
        self.visual_change_var = tk.StringVar(value="Change in: —")
        self.visual_phase_var = tk.StringVar(value="")

        timing = ttk.Frame(frame)
        timing.pack(fill="x", pady=(4, 12))
        ttk.Label(
            timing,
            textvariable=self.visual_bar_var,
            font=("Segoe UI", 26, "bold"),
        ).pack(side="left")
        ttk.Label(
            timing,
            textvariable=self.visual_beat_var,
            font=("Segoe UI", 26),
        ).pack(side="left", padx=24)
        ttk.Label(
            timing,
            textvariable=self.visual_time_var,
            font=("Segoe UI", 16),
        ).pack(side="right")

        phase_frame = ttk.LabelFrame(frame, text="Audition every possible Beat 1 phase")
        phase_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            phase_frame,
            text="Choose a phase; playback restarts from the beginning:",
        ).pack(side="left", padx=10, pady=10)
        self.visual_phase_buttons = []
        for phase in range(self.visual_beats_per_bar):
            button = ttk.Button(
                phase_frame,
                text=f"Phase {phase + 1}",
                command=lambda value=phase: self._set_visual_phase(value),
            )
            button.pack(side="left", padx=4, pady=8)
            self.visual_phase_buttons.append(button)
        ttk.Label(
            phase_frame,
            textvariable=self.visual_phase_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=10)

        chord_box = ttk.LabelFrame(frame, text="Current chord from saved timeline")
        chord_box.pack(fill="x", pady=(4, 14))
        ttk.Label(
            chord_box,
            textvariable=self.visual_current_chord_var,
            font=("Segoe UI", 42, "bold"),
            anchor="center",
        ).pack(fill="x", padx=12, pady=(8, 2))
        chord_details = ttk.Frame(chord_box)
        chord_details.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(
            chord_details,
            textvariable=self.visual_next_chord_var,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")
        ttk.Label(
            chord_details,
            textvariable=self.visual_change_var,
            font=("Segoe UI", 15),
        ).pack(side="right")

        self.visual_canvas = tk.Canvas(frame, height=90, highlightthickness=1)
        self.visual_canvas.pack(fill="x")
        self.visual_canvas.create_line(30, 45, 890, 45, width=3)
        self.visual_marker = self.visual_canvas.create_oval(22, 29, 38, 61)

        ttk.Label(
            frame,
            textvariable=self.visual_status_var,
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=10)
        ttk.Button(
            frame,
            text="Stop Test",
            command=self._stop_visual_test,
        ).pack(side="right")
        self.visual_window.protocol("WM_DELETE_WINDOW", self._stop_visual_test)
        self._refresh_phase_display()

    def _chord_display_at(self, elapsed: float) -> tuple[str, str, float | None]:
        current_index = None
        for index, segment in enumerate(self.visual_chord_segments):
            start = float(segment.get("start_s", 0.0))
            end = float(segment.get("end_s", start))
            if start <= elapsed < end:
                current_index = index
                break

        if current_index is None:
            next_segment = next(
                (
                    segment
                    for segment in self.visual_chord_segments
                    if float(segment.get("start_s", 0.0)) > elapsed
                ),
                None,
            )
            if next_segment is None:
                return "—", "—", None
            next_chord = str(next_segment.get("chord") or "N")
            return (
                "—",
                next_chord,
                max(0.0, float(next_segment.get("start_s", 0.0)) - elapsed),
            )

        current = self.visual_chord_segments[current_index]
        current_chord = str(current.get("chord") or "N")
        next_segment = (
            self.visual_chord_segments[current_index + 1]
            if current_index + 1 < len(self.visual_chord_segments)
            else None
        )
        if next_segment is None:
            return current_chord, "—", None
        next_chord = str(next_segment.get("chord") or "N")
        change_in = max(
            0.0,
            float(next_segment.get("start_s", 0.0)) - elapsed,
        )
        return current_chord, next_chord, change_in

    def _update_visual_marker(self) -> None:
        if (
            self.visual_started_at is None
            or self.visual_window is None
            or not self.visual_window.winfo_exists()
        ):
            return

        elapsed = time.monotonic() - self.visual_started_at
        if elapsed >= self.visual_duration:
            self._stop_visual_test()
            return

        phase_downbeats = self._phase_downbeat_times()
        if not phase_downbeats:
            return

        beat_index = max(
            0,
            bisect.bisect_right(self.visual_beat_times, elapsed) - 1,
        )
        down_index = max(
            0,
            bisect.bisect_right(phase_downbeats, elapsed) - 1,
        )
        down_time = phase_downbeats[down_index]
        first_beat = bisect.bisect_left(self.visual_beat_times, down_time)
        beat_in_bar = max(
            1,
            min(
                self.visual_beats_per_bar,
                beat_index - first_beat + 1,
            ),
        )
        is_down = abs(elapsed - down_time) < 0.16

        width = max(100, self.visual_canvas.winfo_width())
        x = 30 + (elapsed / max(1, self.visual_duration)) * (width - 60)
        size = 26 if is_down else 16
        self.visual_canvas.coords(
            self.visual_marker,
            x - size / 2,
            45 - size,
            x + size / 2,
            45 + size,
        )

        self.visual_bar_var.set(f"Bar {down_index + 1}")
        self.visual_beat_var.set(
            f"Beat {beat_in_bar} of {self.visual_beats_per_bar}"
        )
        self.visual_time_var.set(
            f"{int(elapsed)//60}:{int(elapsed)%60:02d} / 3:00"
        )
        self.visual_status_var.set(
            "DOWNBEAT — selected phase"
            if is_down
            else "Beat"
        )

        current_chord, next_chord, change_in = self._chord_display_at(elapsed)
        self.visual_current_chord_var.set(current_chord)
        self.visual_next_chord_var.set(f"Next chord: {next_chord}")
        self.visual_change_var.set(
            "Change in: —"
            if change_in is None
            else f"Change in: {change_in:.1f}s"
        )

        self.after(25, self._update_visual_marker)

    def _stop_visual_test(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self.visual_started_at = None
        if self.visual_window is not None and self.visual_window.winfo_exists():
            self.visual_window.destroy()
        self.visual_window = None

    def _open_folder(self) -> None:
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
    app = App()

    probe_file = os.environ.get("BANJOFY_STARTUP_PROBE_FILE", "").strip()
    if probe_file:
        probe_path = Path(probe_file)
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_text(
            json.dumps({
                "status": "ready",
                "application": APP_TITLE,
                "library_setting": app.library_var.get(),
            }, indent=2),
            encoding="utf-8",
        )
        app.after(300, app.destroy)

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
