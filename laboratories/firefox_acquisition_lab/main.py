from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Banjofy Firefox Acquisition Laboratory 001"
SUPPORTED_MEDIA = {".mp4", ".webm", ".m4a", ".mp3", ".wav", ".ogg"}
PARTIAL_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}
POLL_SECONDS = 1.0
STABLE_SCANS_REQUIRED = 3
SETTINGS_FILENAME = "firefox_acquisition_lab_settings.json"
OFFICIAL_ADDON_URL = "https://addons.mozilla.org/firefox/addon/easy-youtube-video-download/"


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


def detect_firefox() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla Firefox" / "firefox.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def default_downloads_folder() -> Path:
    # This laboratory deliberately does not change Firefox's default folder.
    return Path.home() / "Downloads"


@dataclass
class CandidateState:
    size: int = -1
    stable_scans: int = 0


class AcquisitionWatcher(threading.Thread):
    def __init__(
        self,
        downloads: Path,
        destination: Path,
        expected_title: str,
        armed_at: float,
        events: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.downloads = downloads
        self.destination = destination
        self.expected_title = expected_title
        self.expected_words = normalise_words(expected_title)
        self.armed_at = armed_at
        self.events = events
        self.stop_event = stop_event
        self.states: dict[Path, CandidateState] = {}

    def emit(self, kind: str, message: str, **extra: object) -> None:
        self.events.put({"kind": kind, "message": message, **extra})

    def score(self, path: Path) -> tuple[int, int]:
        file_words = normalise_words(path.stem)
        overlap = len(self.expected_words & file_words)
        missing = len(self.expected_words - file_words)
        return overlap, -missing

    def eligible(self, path: Path) -> bool:
        if not path.is_file():
            return False
        lower_name = path.name.lower()
        if any(lower_name.endswith(suffix) for suffix in PARTIAL_SUFFIXES):
            return False
        if path.suffix.lower() not in SUPPORTED_MEDIA:
            return False
        try:
            # Two seconds tolerance covers filesystem timestamp rounding.
            return path.stat().st_mtime >= self.armed_at - 2.0
        except OSError:
            return False

    def unique_destination(self, source: Path) -> Path:
        target = self.destination / source.name
        if not target.exists():
            return target
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return self.destination / f"{source.stem} ({stamp}){source.suffix}"

    def run(self) -> None:
        self.emit("status", f"Watching {self.downloads}")
        while not self.stop_event.is_set():
            try:
                candidates = [p for p in self.downloads.iterdir() if self.eligible(p)]
            except OSError as exc:
                self.emit("error", f"Cannot read Downloads folder: {exc}")
                return

            ranked: list[tuple[tuple[int, int], Path]] = []
            for path in candidates:
                score = self.score(path)
                if self.expected_words and score[0] == 0:
                    continue
                ranked.append((score, path))

            ranked.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)

            for score, path in ranked:
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                state = self.states.setdefault(path, CandidateState())
                if size > 0 and size == state.size:
                    state.stable_scans += 1
                else:
                    state.size = size
                    state.stable_scans = 0

                self.emit(
                    "candidate",
                    f"Candidate found: {path.name} — waiting for download to finish",
                    path=str(path),
                    size=size,
                    overlap=score[0],
                    stable_scans=state.stable_scans,
                )

                if state.stable_scans < STABLE_SCANS_REQUIRED:
                    continue

                try:
                    with path.open("rb") as handle:
                        handle.read(16)
                except OSError:
                    continue

                self.destination.mkdir(parents=True, exist_ok=True)
                target = self.unique_destination(path)
                try:
                    shutil.move(str(path), str(target))
                except OSError as exc:
                    self.emit("error", f"The completed file could not be moved: {exc}")
                    return

                record = {
                    "laboratory": APP_TITLE,
                    "expected_title": self.expected_title,
                    "source_downloads_folder": str(self.downloads),
                    "destination_file": str(target),
                    "moved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "size_bytes": target.stat().st_size,
                }
                report = target.with_suffix(target.suffix + ".banjofy-import.json")
                report.write_text(json.dumps(record, indent=2), encoding="utf-8")
                self.emit(
                    "success",
                    f"Import successful: {target.name}",
                    target=str(target),
                    report=str(report),
                )
                return

            time.sleep(POLL_SECONDS)

        self.emit("stopped", "Waiting stopped")


class LaboratoryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x560")
        self.minsize(720, 520)

        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.watcher: AcquisitionWatcher | None = None

        self.library_var = tk.StringVar()
        self.expected_var = tk.StringVar()
        self.youtube_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready for the controlled handover test")
        self.firefox_var = tk.StringVar()
        self.downloads_var = tk.StringVar(value=str(default_downloads_folder()))

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

    def _save_settings(self) -> None:
        data = {"library_root": self.library_var.get().strip()}
        settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "This laboratory does not download from YouTube itself. It waits for the proven "
                "Firefox extension, then moves only the matching completed media file into the "
                "Library location you select."
            ),
            wraplength=710,
        ).pack(anchor="w", pady=(5, 14))

        status_box = ttk.LabelFrame(outer, text="1. Firefox and downloader")
        status_box.pack(fill="x", pady=5)
        ttk.Label(status_box, textvariable=self.firefox_var).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Button(status_box, text="Open approved downloader page", command=self._open_addon).grid(
            row=0, column=1, sticky="e", padx=10, pady=8
        )
        status_box.columnconfigure(0, weight=1)

        library_box = ttk.LabelFrame(outer, text="2. Select the Banjofy Library location")
        library_box.pack(fill="x", pady=5)
        ttk.Entry(library_box, textvariable=self.library_var).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Button(library_box, text="Choose folder", command=self._choose_library).grid(
            row=0, column=1, padx=10, pady=8
        )
        library_box.columnconfigure(0, weight=1)

        request_box = ttk.LabelFrame(outer, text="3. Name the song Banjofy is waiting for")
        request_box.pack(fill="x", pady=5)
        ttk.Label(request_box, text="Expected song title:").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 3))
        ttk.Entry(request_box, textvariable=self.expected_var).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8)
        )
        ttk.Label(request_box, text="YouTube address (optional):").grid(row=2, column=0, sticky="w", padx=10, pady=(3, 3))
        ttk.Entry(request_box, textvariable=self.youtube_var).grid(
            row=3, column=0, sticky="ew", padx=10, pady=(0, 8)
        )
        ttk.Button(request_box, text="Open song in Firefox", command=self._open_youtube).grid(
            row=3, column=1, padx=10, pady=(0, 8)
        )
        request_box.columnconfigure(0, weight=1)

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=12)
        self.start_button = ttk.Button(action_row, text="Start waiting for this song", command=self._start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(action_row, text="Stop waiting", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(action_row, text="Open Library folder", command=self._open_library).pack(side="right")

        result_box = ttk.LabelFrame(outer, text="Test status")
        result_box.pack(fill="both", expand=True, pady=5)
        ttk.Label(result_box, textvariable=self.status_var, wraplength=690).pack(anchor="w", padx=10, pady=8)
        self.log = tk.Text(result_box, height=9, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ttk.Label(
            outer,
            text=f"Firefox remains unchanged. Watched folder: {self.downloads_var.get()}",
        ).pack(anchor="w", pady=(8, 0))

    def _append_log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{stamp}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_firefox_status(self) -> None:
        firefox = detect_firefox()
        if firefox:
            self.firefox_var.set(f"Firefox found: {firefox}")
        else:
            self.firefox_var.set("Firefox was not found. Install Firefox before running the download test.")

    def _open_addon(self) -> None:
        webbrowser.open(OFFICIAL_ADDON_URL)

    def _choose_library(self) -> None:
        selected = filedialog.askdirectory(title="Choose the Banjofy Library location")
        if selected:
            self.library_var.set(selected)
            self._save_settings()

    def _open_youtube(self) -> None:
        address = self.youtube_var.get().strip()
        if not address:
            messagebox.showinfo(APP_TITLE, "Paste the exact YouTube address first, or open it manually in Firefox.")
            return
        firefox = detect_firefox()
        try:
            if firefox:
                subprocess.Popen([str(firefox), address])
            else:
                webbrowser.open(address)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not open Firefox: {exc}")

    def _validate(self) -> tuple[Path, Path, str] | None:
        firefox = detect_firefox()
        if not firefox:
            messagebox.showerror(APP_TITLE, "Firefox was not found.")
            return None
        downloads = default_downloads_folder()
        if not downloads.is_dir():
            messagebox.showerror(APP_TITLE, f"Downloads folder was not found:\n{downloads}")
            return None
        root_text = self.library_var.get().strip()
        if not root_text:
            messagebox.showerror(APP_TITLE, "Choose the Banjofy Library location first.")
            return None
        root = Path(root_text).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
            test = root / ".banjofy_write_test"
            test.write_text("write test", encoding="utf-8")
            test.unlink()
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Banjofy cannot write to that Library location:\n{exc}")
            return None
        expected = self.expected_var.get().strip()
        if len(normalise_words(expected)) < 1:
            messagebox.showerror(APP_TITLE, "Enter the song title Banjofy should expect.")
            return None
        return downloads, root / "Downloaded", expected

    def _start(self) -> None:
        validated = self._validate()
        if validated is None:
            return
        downloads, destination, expected = validated
        self._save_settings()
        self.stop_event = threading.Event()
        self.watcher = AcquisitionWatcher(
            downloads=downloads,
            destination=destination,
            expected_title=expected,
            armed_at=time.time(),
            events=self.events,
            stop_event=self.stop_event,
        )
        self.watcher.start()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Waiting. Now use the Firefox downloader on the selected song.")
        self._append_log(f"Armed for: {expected}")
        self._append_log(f"Only new supported media in {downloads} will be considered")
        self._append_log(f"Confirmed file will be moved to {destination}")

    def _stop(self) -> None:
        self.stop_event.set()
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def _open_library(self) -> None:
        root_text = self.library_var.get().strip()
        if not root_text:
            messagebox.showinfo(APP_TITLE, "Choose the Library location first.")
            return
        path = Path(root_text)
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(path.as_uri())

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = str(event.get("kind", "status"))
            message = str(event.get("message", ""))
            self.status_var.set(message)
            if kind != "candidate" or not self.log.get("end-2l", "end-1l").strip().endswith(message):
                self._append_log(message)
            if kind in {"success", "error", "stopped"}:
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
            if kind == "success":
                target = str(event.get("target", ""))
                messagebox.showinfo(
                    APP_TITLE,
                    "The Firefox-to-Banjofy handover succeeded.\n\n"
                    f"Moved file:\n{target}",
                )
            elif kind == "error":
                messagebox.showerror(APP_TITLE, message)
        self.after(200, self._poll_events)

    def _close(self) -> None:
        self.stop_event.set()
        self.destroy()


def main() -> int:
    app = LaboratoryApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
