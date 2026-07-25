from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import imageio_ffmpeg
import yt_dlp

APP_TITLE = "Banjofy Firefox Acquisition Laboratory 004"
SUPPORTED_MEDIA = {".mp4", ".webm", ".m4a", ".mp3", ".wav", ".ogg", ".mkv"}
PARTIAL_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}
POLL_SECONDS = 1.0
STABLE_SCANS_REQUIRED = 3
SETTINGS_FILENAME = "firefox_acquisition_lab_settings.json"
OFFICIAL_ADDON_URL = "https://addons.mozilla.org/firefox/addon/easy-youtube-video-download/"
SEARCH_LIMIT = 8


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    folder = base / "Banjofy" / "FirefoxAcquisitionLab"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def normalise_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    ignored = {"official", "video", "audio", "lyrics", "lyric", "music", "hd", "hq"}
    return {word for word in words if len(word) >= 2 and word not in ignored}


def safe_stem(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:150] or "Banjofy Song"


def detect_firefox() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla Firefox" / "firefox.exe",
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def default_downloads_folder() -> Path:
    return Path.home() / "Downloads"


def ffmpeg_exe() -> Path:
    path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not path.is_file():
        raise FileNotFoundError("The bundled FFmpeg executable was not found")
    return path


def inspect_media(path: Path) -> dict[str, object]:
    command = [str(ffmpeg_exe()), "-hide_banner", "-i", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (completed.stderr or "") + "\n" + (completed.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if not match:
        raise RuntimeError("FFmpeg could not read a valid duration from the downloaded media")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0.5:
        raise RuntimeError("The downloaded media is too short to be a usable song")
    audio_present = "Audio:" in output
    video_present = "Video:" in output
    if not audio_present:
        raise RuntimeError("The downloaded file does not contain an audio stream")
    return {
        "duration_seconds": round(duration, 3),
        "audio_present": audio_present,
        "video_present": video_present,
        "ffmpeg_evidence": output[-3000:],
    }


def extract_practice_audio(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.stem}.working{target.suffix}")
    temporary.unlink(missing_ok=True)
    command = [
        str(ffmpeg_exe()), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vn", "-c:a", "aac", "-b:a", "192k", str(temporary),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(f"Practice audio extraction failed: {detail[-900:]}")
    temporary.replace(target)


def format_duration(seconds: object) -> str:
    try:
        total = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        return "—"
    return f"{total // 60}:{total % 60:02d}" if total else "—"


def build_search_results(info: dict[str, object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for entry in info.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        if not video_id or not title:
            continue
        url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={video_id}"
        results.append({
            "id": video_id,
            "title": title,
            "channel": str(entry.get("channel") or entry.get("uploader") or "").strip(),
            "duration": entry.get("duration"),
            "url": url,
        })
    return results[:SEARCH_LIMIT]


def search_youtube(query: str) -> list[dict[str, object]]:
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": SEARCH_LIMIT,
        "socket_timeout": 20,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{SEARCH_LIMIT}:{query}", download=False)
    if not isinstance(info, dict):
        return []
    return build_search_results(info)


@dataclass
class CandidateState:
    size: int = -1
    stable_scans: int = 0


class AcquisitionWatcher(threading.Thread):
    def __init__(self, downloads: Path, staging: Path, expected_title: str, armed_at: float,
                 events: queue.Queue, stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self.downloads = downloads
        self.staging = staging
        self.expected_words = normalise_words(expected_title)
        self.armed_at = armed_at
        self.events = events
        self.stop_event = stop_event
        self.states: dict[Path, CandidateState] = {}

    def emit(self, kind: str, message: str, **extra: object) -> None:
        self.events.put({"kind": kind, "message": message, **extra})

    def score(self, path: Path) -> tuple[int, int]:
        file_words = normalise_words(path.stem)
        return len(self.expected_words & file_words), -len(self.expected_words - file_words)

    def eligible(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_MEDIA:
            return False
        if any(path.name.lower().endswith(suffix) for suffix in PARTIAL_SUFFIXES):
            return False
        try:
            return path.stat().st_mtime >= self.armed_at - 2.0
        except OSError:
            return False

    def unique_destination(self, source: Path) -> Path:
        target = self.staging / source.name
        if not target.exists():
            return target
        return self.staging / f"{source.stem} ({time.strftime('%Y%m%d-%H%M%S')}){source.suffix}"

    def run(self) -> None:
        self.emit("status", f"Watching {self.downloads}")
        while not self.stop_event.is_set():
            try:
                candidates = [p for p in self.downloads.iterdir() if self.eligible(p)]
            except OSError as exc:
                self.emit("error", f"Cannot read Downloads folder: {exc}")
                return
            ranked = [(self.score(p), p) for p in candidates if not self.expected_words or self.score(p)[0] > 0]
            ranked.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
            for _, path in ranked:
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                state = self.states.setdefault(path, CandidateState())
                if size > 0 and size == state.size:
                    state.stable_scans += 1
                else:
                    state.size, state.stable_scans = size, 0
                self.emit("candidate", f"Candidate found: {path.name} — waiting for completion")
                if state.stable_scans < STABLE_SCANS_REQUIRED:
                    continue
                try:
                    with path.open("rb") as handle:
                        handle.read(16)
                except OSError:
                    continue
                self.staging.mkdir(parents=True, exist_ok=True)
                target = self.unique_destination(path)
                try:
                    shutil.move(str(path), str(target))
                except OSError as exc:
                    self.emit("error", f"The completed file could not be moved: {exc}")
                    return
                self.emit("processing", f"Validating media: {target.name}", target=str(target))
                try:
                    media = inspect_media(target)
                except Exception as exc:
                    self.emit("error", f"Media validation failed: {exc}", target=str(target))
                    return
                self.emit("media_ready", f"Validated {target.name}", target=str(target), media=media)
                return
            time.sleep(POLL_SECONDS)
        self.emit("stopped", "Waiting stopped")


class StorageChoiceDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, filename: str, duration: float, remembered: str | None = None) -> None:
        super().__init__(parent)
        self.title("Keep this song for offline Practice?")
        self.resizable(False, False)
        self.result: tuple[str, bool] | None = None
        self.choice = tk.StringVar(value=remembered or "audio")
        self.remember = tk.BooleanVar(value=False)
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Keep this song for offline Practice?", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{filename}\nDuration: {duration/60:.1f} minutes", wraplength=520).pack(anchor="w", pady=(5, 12))
        options = [
            ("audio", "Keep audio only — Recommended", "Offline Practice, exact repeats and speed control, with modest storage."),
            ("both", "Keep video and audio", "Keeps the original video and a separate Practice audio file."),
            ("online", "Online playback only", "Keeps the Library record but removes downloaded media."),
        ]
        for value, title, detail in options:
            box = ttk.Frame(frame); box.pack(fill="x", pady=4)
            ttk.Radiobutton(box, text=title, variable=self.choice, value=value).pack(anchor="w")
            ttk.Label(box, text=detail, wraplength=500).pack(anchor="w", padx=(24, 0))
        ttk.Checkbutton(frame, text="Remember my choice", variable=self.remember).pack(anchor="w", pady=(12, 8))
        buttons = ttk.Frame(frame); buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Continue", command=self._accept).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_visibility(); self.focus_force()

    def _accept(self) -> None:
        self.result = (self.choice.get(), self.remember.get()); self.destroy()

    def _cancel(self) -> None:
        self.result = None; self.destroy()


class LaboratoryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("940x760")
        self.minsize(860, 680)
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.watcher: AcquisitionWatcher | None = None
        self.library_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.expected_var = tk.StringVar()
        self.youtube_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready to search for a song inside Banjofy")
        self.firefox_var = tk.StringVar()
        self.remembered_storage: str | None = None
        self.search_results: list[dict[str, object]] = []
        self._load_settings()
        self._build_ui()
        self._refresh_firefox_status()
        self.after(200, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _load_settings(self) -> None:
        try:
            data = json.loads(settings_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.library_var.set(str(data.get("library_root", "")))
        value = data.get("storage_choice")
        self.remembered_storage = value if value in {"audio", "both", "online"} else None

    def _save_settings(self, storage_choice: str | None = None) -> None:
        data: dict[str, object] = {"library_root": self.library_var.get().strip()}
        if storage_choice in {"audio", "both", "online"}:
            data["storage_choice"] = storage_choice
            self.remembered_storage = storage_choice
        elif self.remembered_storage:
            data["storage_choice"] = self.remembered_storage
        settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text=("Search for a song inside Banjofy, choose the exact recording, open it in Firefox, "
                               "then use the proven downloader. Banjofy takes over when the file arrives."),
                  wraplength=880).pack(anchor="w", pady=(5, 10))

        status_box = ttk.LabelFrame(outer, text="1. Firefox and downloader"); status_box.pack(fill="x", pady=4)
        ttk.Label(status_box, textvariable=self.firefox_var).grid(row=0, column=0, sticky="w", padx=10, pady=7)
        ttk.Button(status_box, text="Open approved downloader page", command=self._open_addon).grid(row=0, column=1, padx=10, pady=7)
        status_box.columnconfigure(0, weight=1)

        library_box = ttk.LabelFrame(outer, text="2. Select the Banjofy Library location"); library_box.pack(fill="x", pady=4)
        ttk.Entry(library_box, textvariable=self.library_var).grid(row=0, column=0, sticky="ew", padx=10, pady=7)
        ttk.Button(library_box, text="Choose folder", command=self._choose_library).grid(row=0, column=1, padx=10, pady=7)
        library_box.columnconfigure(0, weight=1)

        search_box = ttk.LabelFrame(outer, text="3. Search for a song inside Banjofy"); search_box.pack(fill="both", expand=True, pady=4)
        top = ttk.Frame(search_box); top.pack(fill="x", padx=10, pady=(8, 5))
        entry = ttk.Entry(top, textvariable=self.search_var); entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _event: self._begin_search())
        self.search_button = ttk.Button(top, text="Search YouTube", command=self._begin_search); self.search_button.pack(side="left", padx=(8, 0))
        columns = ("title", "channel", "duration")
        self.results_tree = ttk.Treeview(search_box, columns=columns, show="headings", height=7, selectmode="browse")
        self.results_tree.heading("title", text="Recording")
        self.results_tree.heading("channel", text="Channel")
        self.results_tree.heading("duration", text="Length")
        self.results_tree.column("title", width=500, anchor="w")
        self.results_tree.column("channel", width=220, anchor="w")
        self.results_tree.column("duration", width=70, anchor="center")
        self.results_tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.results_tree.bind("<Double-1>", lambda _event: self._select_result())
        choose = ttk.Frame(search_box); choose.pack(fill="x", padx=10, pady=(3, 8))
        ttk.Button(choose, text="Use selected recording", command=self._select_result).pack(side="left")
        ttk.Label(choose, text="Double-clicking a result does the same.").pack(side="left", padx=10)

        selected_box = ttk.LabelFrame(outer, text="4. Selected recording"); selected_box.pack(fill="x", pady=4)
        ttk.Label(selected_box, text="Title:").grid(row=0, column=0, sticky="w", padx=10, pady=(7, 2))
        ttk.Entry(selected_box, textvariable=self.expected_var, state="readonly").grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        ttk.Label(selected_box, text="YouTube address:").grid(row=2, column=0, sticky="w", padx=10, pady=(2, 2))
        ttk.Entry(selected_box, textvariable=self.youtube_var, state="readonly").grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 7))
        ttk.Button(selected_box, text="Open selected recording in Firefox", command=self._open_youtube).grid(row=1, column=1, rowspan=3, padx=10, pady=7)
        selected_box.columnconfigure(0, weight=1)

        action = ttk.Frame(outer); action.pack(fill="x", pady=10)
        self.start_button = ttk.Button(action, text="Start waiting for selected song", command=self._start); self.start_button.pack(side="left")
        self.stop_button = ttk.Button(action, text="Stop waiting", command=self._stop, state="disabled"); self.stop_button.pack(side="left", padx=8)
        ttk.Button(action, text="Open Library folder", command=self._open_library).pack(side="right")

        result_box = ttk.LabelFrame(outer, text="Test status"); result_box.pack(fill="both", expand=True, pady=4)
        ttk.Label(result_box, textvariable=self.status_var, wraplength=870).pack(anchor="w", padx=10, pady=6)
        self.log = tk.Text(result_box, height=6, state="disabled", wrap="word"); self.log.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ttk.Label(outer, text=f"Firefox remains unchanged. Watched folder: {default_downloads_folder()}").pack(anchor="w", pady=(5, 0))

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log.see("end"); self.log.configure(state="disabled")

    def _refresh_firefox_status(self) -> None:
        firefox = detect_firefox()
        try:
            ffmpeg_text = f" | FFmpeg ready: {ffmpeg_exe().name}"
        except Exception as exc:
            ffmpeg_text = f" | FFmpeg unavailable: {exc}"
        self.firefox_var.set((f"Firefox found: {firefox}" if firefox else "Firefox was not found") + ffmpeg_text)

    def _open_addon(self) -> None:
        webbrowser.open(OFFICIAL_ADDON_URL)

    def _choose_library(self) -> None:
        selected = filedialog.askdirectory(title="Choose the Banjofy Library location")
        if selected:
            self.library_var.set(selected); self._save_settings()

    def _begin_search(self) -> None:
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo(APP_TITLE, "Enter a song title or artist to search for."); return
        self.search_button.configure(state="disabled")
        self.status_var.set(f"Searching YouTube for: {query}")
        self._append_log(f"Search started: {query}")
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str) -> None:
        try:
            results = search_youtube(query)
            if not results:
                raise RuntimeError("No usable YouTube results were returned")
            self.events.put({"kind": "search_ready", "message": f"Found {len(results)} recordings", "results": results})
        except Exception as exc:
            self.events.put({"kind": "search_error", "message": f"Song search failed: {exc}"})

    def _show_search_results(self, results: list[dict[str, object]]) -> None:
        self.search_results = results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        for index, result in enumerate(results):
            self.results_tree.insert("", "end", iid=str(index), values=(
                result["title"], result["channel"], format_duration(result["duration"])
            ))
        first = self.results_tree.get_children()
        if first:
            self.results_tree.selection_set(first[0]); self.results_tree.focus(first[0])

    def _select_result(self) -> None:
        selected = self.results_tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Select one recording from the search results first."); return
        result = self.search_results[int(selected[0])]
        self.expected_var.set(str(result["title"]))
        self.youtube_var.set(str(result["url"]))
        self.status_var.set("Recording selected. Open it in Firefox, then start waiting before downloading.")
        self._append_log(f"Selected: {result['title']} — {result['channel']}")

    def _open_youtube(self) -> None:
        address = self.youtube_var.get().strip()
        if not address:
            messagebox.showinfo(APP_TITLE, "Search and select a recording first."); return
        firefox = detect_firefox()
        try:
            subprocess.Popen([str(firefox), address]) if firefox else webbrowser.open(address)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not open Firefox: {exc}")

    def _validate(self) -> tuple[Path, Path, str] | None:
        if not detect_firefox():
            messagebox.showerror(APP_TITLE, "Firefox was not found."); return None
        downloads = default_downloads_folder()
        if not downloads.is_dir():
            messagebox.showerror(APP_TITLE, f"Downloads folder was not found:\n{downloads}"); return None
        root_text = self.library_var.get().strip()
        if not root_text:
            messagebox.showerror(APP_TITLE, "Choose the Banjofy Library location first."); return None
        root = Path(root_text).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
            test = root / ".banjofy_write_test"; test.write_text("write test", encoding="utf-8"); test.unlink()
            ffmpeg_exe()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Setup validation failed:\n{exc}"); return None
        expected = self.expected_var.get().strip()
        if not normalise_words(expected) or not self.youtube_var.get().strip():
            messagebox.showerror(APP_TITLE, "Search and select the exact recording first."); return None
        return downloads, root / "Working" / "Incoming", expected

    def _start(self) -> None:
        validated = self._validate()
        if validated is None:
            return
        downloads, staging, expected = validated
        self._save_settings()
        self.stop_event = threading.Event()
        self.watcher = AcquisitionWatcher(downloads, staging, expected, time.time(), self.events, self.stop_event)
        self.watcher.start()
        self.start_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.status_var.set("Waiting. Download the selected recording with the Firefox extension.")
        self._append_log(f"Armed for selected recording: {expected}")
        self._append_log(f"Only new matching media in {downloads} will be considered")

    def _stop(self) -> None:
        self.stop_event.set(); self.start_button.configure(state="normal"); self.stop_button.configure(state="disabled")

    def _open_library(self) -> None:
        root_text = self.library_var.get().strip()
        if not root_text:
            messagebox.showinfo(APP_TITLE, "Choose the Library location first."); return
        path = Path(root_text); path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(path.as_uri())

    def _process_storage_choice(self, source: Path, media: dict[str, object]) -> None:
        root = Path(self.library_var.get().strip())
        duration = float(media["duration_seconds"])
        dialog = StorageChoiceDialog(self, source.name, duration, self.remembered_storage)
        self.wait_window(dialog)
        if dialog.result is None:
            self.status_var.set("Storage choice cancelled. Download remains safely in Working\\Incoming.")
            self._append_log("Storage choice cancelled; source retained in staging"); return
        choice, remember = dialog.result
        if remember:
            self._save_settings(choice)
        song_id = time.strftime("%Y%m%d-%H%M%S") + "-" + safe_stem(self.expected_var.get()).lower().replace(" ", "-")[:60]
        audio_target = root / "Media" / "Audio" / f"{safe_stem(source.stem)}.m4a"
        video_target = root / "Media" / "Video" / source.name
        record_path = root / "Library" / "Songs" / f"{song_id}.json"
        try:
            self.status_var.set("Extracting Practice audio…")
            self._append_log("Extracting 192 kbps AAC Practice audio")
            if choice in {"audio", "both"}:
                extract_practice_audio(source, audio_target); inspect_media(audio_target)
            if choice == "both":
                video_target.parent.mkdir(parents=True, exist_ok=True)
                if video_target.exists():
                    video_target = video_target.with_name(f"{video_target.stem} ({time.strftime('%H%M%S')}){video_target.suffix}")
                shutil.move(str(source), str(video_target))
            else:
                source.unlink(missing_ok=True)
            record = {
                "record_version": 2,
                "laboratory": APP_TITLE,
                "song_id": song_id,
                "title_requested": self.expected_var.get().strip(),
                "youtube_url": self.youtube_var.get().strip(),
                "original_download_name": source.name,
                "duration_seconds": duration,
                "storage_choice": choice,
                "practice_audio_path": str(audio_target) if choice in {"audio", "both"} else None,
                "video_path": str(video_target) if choice == "both" else None,
                "analysis_status": "not_started",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "media_validation": {k: v for k, v in media.items() if k != "ffmpeg_evidence"},
            }
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            evidence = root / "Diagnostics" / f"{song_id}-media-validation.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(str(media.get("ffmpeg_evidence", "")), encoding="utf-8")
        except Exception as exc:
            self.status_var.set(f"Processing failed: {exc}")
            self._append_log(f"Processing failed: {exc}")
            messagebox.showerror(APP_TITLE, f"The media was imported but final processing failed.\n\n{exc}\n\nThe source is retained where possible.")
            return
        self.status_var.set("Search, handover and Library media test successful")
        self._append_log(f"Storage choice completed: {choice}")
        self._append_log(f"Library record: {record_path}")
        messagebox.showinfo(APP_TITLE, "The in-Banjofy search, Firefox handover, audio preparation and Library save all succeeded.\n\n"
                            f"Library record:\n{record_path}")

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind, message = str(event.get("kind", "status")), str(event.get("message", ""))
            self.status_var.set(message)
            if kind != "candidate" or not self.log.get("end-2l", "end-1l").strip().endswith(message):
                self._append_log(message)
            if kind in {"media_ready", "error", "stopped"}:
                self.start_button.configure(state="normal"); self.stop_button.configure(state="disabled")
            if kind in {"search_ready", "search_error"}:
                self.search_button.configure(state="normal")
            if kind == "search_ready":
                self._show_search_results(list(event["results"]))
            elif kind == "search_error":
                messagebox.showerror(APP_TITLE, message + "\n\nThe proven Firefox downloader and existing Library remain unaffected.")
            elif kind == "media_ready":
                self._process_storage_choice(Path(str(event["target"])), dict(event["media"]))
            elif kind == "error":
                messagebox.showerror(APP_TITLE, message)
        self.after(200, self._poll_events)

    def _close(self) -> None:
        self.stop_event.set(); self.destroy()


def main() -> int:
    LaboratoryApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
