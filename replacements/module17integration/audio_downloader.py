from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import threading
import traceback
from typing import Callable

from banjofy.models.search_result import SearchResult
from banjofy.storage.paths import audio_folder, get_library_path


ProgressCallback = Callable[[str, int, str], None]


@dataclass(frozen=True)
class DownloadedAudio:
    title: str
    channel: str
    duration: str
    source_url: str
    file_path: Path
    was_cached: bool = False


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:120] or "audio"


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _agent_root() -> Path:
    return _application_root() / "Acquisition"


def _diagnostic_folder() -> Path:
    library = get_library_path()
    if library is None:
        folder = Path.home() / "Banjofy Diagnostics"
    else:
        folder = Path(library) / "diagnostics"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _usable_media_files(folder: Path, stem: str) -> list[Path]:
    rejected = {
        ".part", ".ytdl", ".tmp", ".json", ".webp", ".jpg",
        ".jpeg", ".png", ".description",
    }
    result: list[Path] = []
    for path in folder.glob(stem + ".*"):
        if not path.is_file() or path.suffix.lower() in rejected:
            continue
        if path.stat().st_size < 4096:
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.stat().st_mtime, reverse=True)


class _DiagnosticLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._lines: list[str] = []

    def add(self, line: str) -> None:
        text = str(line).rstrip()
        with self._lock:
            self._lines.append(text)
            self.path.write_text("\n".join(self._lines) + "\n", encoding="utf-8")


class DownloadManager:
    """Banjofy adapter for the replaceable External Acquisition Agent.

    Banjofy does not import or freeze yt-dlp. It launches the official
    standalone yt-dlp executable from the Acquisition folder and waits for a
    completed local media file.
    """

    _latest_log_path: Path | None = None

    @classmethod
    def latest_log_path(cls) -> Path | None:
        path = cls._latest_log_path
        return path if path and path.exists() else None

    @classmethod
    def latest_log_text(cls) -> str:
        path = cls.latest_log_path()
        if path is None:
            return "No download diagnostic has been created yet."
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Could not read diagnostic log: {exc}"

    def _paths(self) -> dict[str, Path]:
        root = _agent_root()
        return {
            "root": root,
            "yt_dlp": root / "yt-dlp.exe",
            "deno": root / "deno.exe",
            "ffmpeg": root / "ffmpeg.exe",
            "plugins": root / "yt-dlp-plugins",
            "provider_server": root / "runtime" / "bgutil-ytdlp-pot-provider" / "server",
        }

    def health_check(self) -> dict[str, object]:
        paths = self._paths()
        plugin_files = (
            sorted(paths["plugins"].rglob("getpot_bgutil*.py"))
            if paths["plugins"].exists()
            else []
        )
        checks: dict[str, object] = {
            "architecture": "External Acquisition Agent",
            "agent_root": str(paths["root"]),
            "agent_root_exists": paths["root"].exists(),
            "yt_dlp": str(paths["yt_dlp"]),
            "yt_dlp_exists": paths["yt_dlp"].exists(),
            "deno": str(paths["deno"]),
            "deno_exists": paths["deno"].exists(),
            "ffmpeg": str(paths["ffmpeg"]),
            "ffmpeg_exists": paths["ffmpeg"].exists(),
            "plugin_root": str(paths["plugins"]),
            "plugin_root_exists": paths["plugins"].exists(),
            "plugin_files": [str(path) for path in plugin_files],
            "provider_server": str(paths["provider_server"]),
            "provider_server_exists": paths["provider_server"].exists(),
            "provider_package_json": (paths["provider_server"] / "package.json").exists(),
            "provider_node_modules": (paths["provider_server"] / "node_modules").exists(),
        }

        missing: list[str] = []
        for name in ("yt_dlp", "deno", "ffmpeg"):
            if not paths[name].exists():
                missing.append(f"Missing acquisition component: {paths[name]}")
        if not plugin_files:
            missing.append(f"No bgutil plugin files found beneath: {paths['plugins']}")
        if not paths["provider_server"].exists():
            missing.append(f"Missing provider server: {paths['provider_server']}")
        if not (paths["provider_server"] / "node_modules").exists():
            missing.append(
                "Missing provider dependencies: "
                f"{paths['provider_server'] / 'node_modules'}"
            )

        if missing:
            checks["ready"] = False
            checks["missing"] = missing
        else:
            checks["ready"] = True
            checks["missing"] = []
        return checks

    def _command(self, result: SearchResult, folder: Path, safe: str) -> list[str]:
        paths = self._paths()
        provider_arg = (
            "youtubepot-bgutilscript:"
            f"server_home={paths['provider_server']}"
        )
        youtube_arg = (
            "youtube:"
            "player_client=mweb;"
            "fetch_pot=always;"
            "pot_trace=true;"
            "jsc_trace=true"
        )
        return [
            str(paths["yt_dlp"]),
            "--ignore-config",
            "--newline",
            "--verbose",
            "--no-playlist",
            "--windows-filenames",
            "--retries", "5",
            "--fragment-retries", "5",
            "--extractor-retries", "3",
            "--socket-timeout", "40",
            "--plugin-dirs", str(paths["plugins"]),
            "--js-runtimes", f"deno:{paths['deno']}",
            "--extractor-args", youtube_arg,
            "--extractor-args", provider_arg,
            "--ffmpeg-location", str(paths["root"]),
            "--format", "bestaudio/best",
            "--extract-audio",
            "--audio-format", "m4a",
            "--audio-quality", "0",
            "--progress-template",
            "download:BANJOFY_PROGRESS:%(progress._percent_str)s",
            "--print", "after_move:BANJOFY_FILE:%(filepath)s",
            "--output", str(folder / (safe + ".%(ext)s")),
            result.url,
        ]

    @staticmethod
    def _progress_percent(line: str) -> int | None:
        match = re.search(r"BANJOFY_PROGRESS:\s*([0-9]+(?:\.[0-9]+)?)%", line)
        if not match:
            return None
        return max(0, min(99, int(float(match.group(1)))))

    def download(
        self,
        result: SearchResult,
        progress: ProgressCallback | None = None,
    ) -> DownloadedAudio:
        if not result or not result.url:
            raise ValueError("No selected result to acquire")

        folder = audio_folder()
        folder.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(f"{result.title} - {result.channel}")

        existing = _usable_media_files(folder, safe)
        if existing:
            if progress:
                progress("cached", 100, str(existing[0]))
            return DownloadedAudio(
                title=result.title,
                channel=result.channel,
                duration=result.duration,
                source_url=result.url,
                file_path=existing[0],
                was_cached=True,
            )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = _diagnostic_folder() / f"acquisition_{stamp}_{safe[:50]}.log.txt"
        DownloadManager._latest_log_path = log_path
        log = _DiagnosticLog(log_path)

        log.add("[banjofy] BANJOFY MODULE 17 BUILD 019 EAA DIAGNOSTIC")
        log.add(f"[banjofy] Timestamp: {datetime.now().isoformat(timespec='seconds')}")
        log.add(f"[banjofy] Title: {result.title}")
        log.add(f"[banjofy] Channel: {result.channel}")
        log.add(f"[banjofy] URL: {result.url}")

        health = self.health_check()
        log.add("[banjofy] EXTERNAL ACQUISITION AGENT HEALTH")
        log.add(json.dumps(health, indent=2))
        if not health["ready"]:
            raise RuntimeError(
                "External Acquisition Agent is incomplete.\n"
                + "\n".join(str(item) for item in health["missing"])
            )

        command = self._command(result, folder, safe)
        safe_command = [
            item if result.url not in item else "<selected URL>"
            for item in command
        ]
        log.add("[banjofy] COMMAND")
        log.add(json.dumps(safe_command, indent=2))

        if progress:
            progress("starting external acquisition agent", 2, str(log_path))

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            process = subprocess.Popen(
                command,
                cwd=str(self._paths()["root"]),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )

            reported_file: Path | None = None
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                log.add(line)

                percent = self._progress_percent(line)
                if percent is not None and progress:
                    progress("downloading audio", max(3, percent), str(log_path))

                if line.startswith("BANJOFY_FILE:"):
                    candidate = Path(line.split(":", 1)[1].strip())
                    if candidate.exists():
                        reported_file = candidate

            return_code = process.wait()
            log.add(f"[banjofy] EAA exit code: {return_code}")
            if return_code != 0:
                raise RuntimeError(
                    f"External Acquisition Agent ended with code {return_code}. "
                    "Open View Full Download Diagnostic for the exact reason."
                )

            candidates = _usable_media_files(folder, safe)
            chosen = (
                reported_file
                if reported_file is not None and reported_file.exists()
                else (candidates[0] if candidates else None)
            )
            if chosen is None:
                raise FileNotFoundError(
                    "The agent reported success but no usable media file was produced."
                )

            log.add(f"[banjofy] SUCCESS: {chosen}")
            log.add(f"[banjofy] File size: {chosen.stat().st_size} bytes")
            if progress:
                progress("complete", 100, str(chosen))

            return DownloadedAudio(
                title=result.title,
                channel=result.channel,
                duration=result.duration,
                source_url=result.url,
                file_path=chosen,
                was_cached=False,
            )
        except Exception as exc:
            log.add("[banjofy] FAILURE")
            log.add(f"[banjofy] {type(exc).__name__}: {exc}")
            log.add(traceback.format_exc())
            raise RuntimeError(
                f"Acquisition failed. Full diagnostic saved to:\n{log_path}\n\n{exc}"
            ) from exc
