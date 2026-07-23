from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import os
import re
import sys
import threading
import traceback
from typing import Callable

import imageio_ffmpeg
from yt_dlp import YoutubeDL
import yt_dlp

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


def _executable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _runtime_root() -> Path:
    return _executable_root() / "runtime"


def _portable_plugin_root() -> Path:
    return _executable_root() / "yt-dlp-plugins"


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
    result = []
    for path in folder.glob(stem + ".*"):
        if not path.is_file() or path.suffix.lower() in rejected:
            continue
        if path.stat().st_size < 4096:
            continue
        result.append(path)
    return sorted(result, key=lambda p: p.stat().st_mtime, reverse=True)


class _DiagnosticLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._lock = threading.Lock()
        self._lines: list[str] = []

    def _write(self, level: str, message: str) -> None:
        text = str(message).rstrip()
        line = f"[{level}] {text}"
        with self._lock:
            self._lines.append(line)
            self.log_path.write_text("\n".join(self._lines) + "\n", encoding="utf-8")

    def debug(self, message: str) -> None:
        self._write("debug", message)

    def warning(self, message: str) -> None:
        self._write("warning", message)

    def error(self, message: str) -> None:
        self._write("error", message)

    def add(self, message: str) -> None:
        self._write("banjofy", message)


class DownloadManager:
    """Modern YouTube downloader with explicit component verification.

    This is deliberately a single designed extraction path:
    yt-dlp + EJS + Deno + bgutil PO-token provider + mweb.
    It does not cycle through guessed browser clients or format strings.
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

    def _component_paths(self) -> tuple[Path, Path, Path, Path]:
        runtime = _runtime_root()
        deno = runtime / "deno.exe"
        provider_server = runtime / "bgutil-ytdlp-pot-provider" / "server"
        plugin_root = _portable_plugin_root()
        ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
        return deno, provider_server, plugin_root, ffmpeg

    def _verify_components(
        self,
        logger: _DiagnosticLogger,
    ) -> tuple[Path, Path, Path, Path]:
        deno, provider_server, plugin_root, ffmpeg = self._component_paths()
        plugin_files = sorted(plugin_root.rglob("getpot_bgutil*.py")) if plugin_root.exists() else []
        checks = {
            "runtime_root": str(_runtime_root()),
            "yt_dlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
            "deno": str(deno),
            "deno_exists": deno.exists(),
            "provider_server": str(provider_server),
            "provider_server_exists": provider_server.exists(),
            "provider_package_json": (provider_server / "package.json").exists(),
            "provider_node_modules": (provider_server / "node_modules").exists(),
            "portable_plugin_root": str(plugin_root),
            "portable_plugin_root_exists": plugin_root.exists(),
            "portable_plugin_files": [str(path) for path in plugin_files],
            "ffmpeg": str(ffmpeg),
            "ffmpeg_exists": ffmpeg.exists(),
        }
        logger.add("COMPONENT CHECK")
        logger.add(json.dumps(checks, indent=2))

        missing = []
        if not deno.exists():
            missing.append(f"Deno runtime missing: {deno}")
        if not provider_server.exists():
            missing.append(f"PO-token provider server missing: {provider_server}")
        if not (provider_server / "node_modules").exists():
            missing.append(
                "PO-token provider dependencies are missing: "
                f"{provider_server / 'node_modules'}"
            )
        if not plugin_root.exists():
            missing.append(f"Portable yt-dlp plugin folder missing: {plugin_root}")
        if not plugin_files:
            missing.append(
                "Portable bgutil yt-dlp plugin files are missing beneath: "
                f"{plugin_root}"
            )
        if not ffmpeg.exists():
            missing.append(f"FFmpeg missing: {ffmpeg}")
        if missing:
            raise RuntimeError("Downloader component verification failed:\n" + "\n".join(missing))
        return deno, provider_server, plugin_root, ffmpeg

    def download(
        self,
        result: SearchResult,
        progress: ProgressCallback | None = None,
    ) -> DownloadedAudio:
        if not result or not result.url:
            raise ValueError("No selected YouTube result to download")

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
        log_path = _diagnostic_folder() / f"download_{stamp}_{safe[:50]}.log.txt"
        DownloadManager._latest_log_path = log_path
        logger = _DiagnosticLogger(log_path)
        logger.add("BANJOFY MODULE 17 BUILD 016 DOWNLOAD DIAGNOSTIC")
        logger.add(f"UTC/local timestamp: {datetime.now().isoformat(timespec='seconds')}")
        logger.add(f"Title: {result.title}")
        logger.add(f"Channel: {result.channel}")
        logger.add(f"URL: {result.url}")

        try:
            deno, provider_server, plugin_root, ffmpeg = self._verify_components(logger)

            if progress:
                progress("verifying modern YouTube components", 3, str(log_path))

            def hook(data: dict) -> None:
                status = str(data.get("status", ""))
                if status == "downloading":
                    downloaded = int(data.get("downloaded_bytes") or 0)
                    total = int(
                        data.get("total_bytes")
                        or data.get("total_bytes_estimate")
                        or 0
                    )
                    percent = int(downloaded * 100 / total) if total else 0
                    if progress:
                        progress("downloading", max(5, min(percent, 97)), str(log_path))
                elif status == "finished":
                    if progress:
                        progress("converting audio", 98, str(log_path))

            extractor_args = {
                "youtube": {
                    "player_client": ["mweb"],
                    "fetch_pot": ["always"],
                    "pot_trace": ["true"],
                    "jsc_trace": ["true"],
                },
                "youtubepot-bgutilscript": {
                    "server_home": [str(provider_server)],
                },
            }

            common = {
                "logger": logger,
                "verbose": True,
                "quiet": False,
                "no_warnings": False,
                "noplaylist": True,
                "retries": 5,
                "fragment_retries": 5,
                "extractor_retries": 3,
                "socket_timeout": 40,
                "windowsfilenames": True,
                "ffmpeg_location": str(ffmpeg),
                "js_runtimes": {"deno": {"path": str(deno)}},
                "plugin_dirs": [str(plugin_root)],
                "extractor_args": extractor_args,
                "progress_hooks": [hook],
                "outtmpl": str(folder / (safe + ".%(ext)s")),
            }

            # Stage 1: format discovery. Do not guess a format until yt-dlp,
            # EJS and the PO-token provider have exposed the real formats.
            if progress:
                progress("discovering verified audio formats", 5, str(log_path))
            discovery_options = dict(common)
            discovery_options.update({
                "skip_download": True,
                "listformats": False,
            })

            with YoutubeDL(discovery_options) as ydl:
                info = ydl.extract_info(result.url, download=False)

            formats = list(info.get("formats") or [])
            audio_formats = [
                fmt for fmt in formats
                if fmt.get("acodec") not in (None, "none")
            ]
            logger.add(f"Format discovery returned {len(formats)} total formats")
            logger.add(f"Audio-capable formats: {len(audio_formats)}")
            logger.add(
                "Audio format IDs: "
                + ", ".join(str(fmt.get("format_id")) for fmt in audio_formats[:50])
            )
            if not audio_formats:
                raise RuntimeError(
                    "Modern format discovery completed but exposed no audio-capable formats. "
                    "See the diagnostic log for EJS and PO-token provider messages."
                )

            # Stage 2: one normal yt-dlp selection from the verified format list.
            if progress:
                progress("downloading best verified audio", 8, str(log_path))
            download_options = dict(common)
            download_options.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }],
            })
            with YoutubeDL(download_options) as ydl:
                ydl.download([result.url])

            downloaded = _usable_media_files(folder, safe)
            if not downloaded:
                raise FileNotFoundError(
                    "yt-dlp reported completion but no usable media file was produced"
                )

            chosen = downloaded[0]
            logger.add(f"SUCCESS: {chosen}")
            logger.add(f"File size: {chosen.stat().st_size} bytes")
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
            logger.add("FAILURE")
            logger.add(f"{type(exc).__name__}: {exc}")
            logger.add(traceback.format_exc())
            raise RuntimeError(
                f"Download failed. Full diagnostic saved to:\n{log_path}\n\n{exc}"
            ) from exc
