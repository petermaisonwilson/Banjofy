from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

import imageio_ffmpeg
from yt_dlp import YoutubeDL

from banjofy.models.search_result import SearchResult
from banjofy.storage.paths import audio_folder


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


def _usable_media_files(folder: Path, stem: str) -> list[Path]:
    rejected = {".part", ".ytdl", ".tmp", ".json", ".webp", ".jpg", ".jpeg", ".png"}
    files = []
    for path in folder.glob(stem + ".*"):
        if not path.is_file() or path.suffix.lower() in rejected:
            continue
        if path.stat().st_size < 4096:
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


class DownloadManager:
    """Download and normalise one usable audio file for the selected result."""

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

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        errors: list[str] = []

        def hook(data: dict) -> None:
            if not progress:
                return
            status = str(data.get("status", ""))
            if status == "downloading":
                downloaded = int(data.get("downloaded_bytes") or 0)
                total = int(
                    data.get("total_bytes")
                    or data.get("total_bytes_estimate")
                    or 0
                )
                percent = int(downloaded * 100 / total) if total else 0
                progress("downloading", max(0, min(percent, 99)), "")
            elif status == "finished":
                progress("converting audio", 99, str(data.get("filename", "")))

        common = {
            "outtmpl": str(folder / (safe + ".%(ext)s")),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 3,
            "socket_timeout": 30,
            "concurrent_fragment_downloads": 1,
            "progress_hooks": [hook],
            "ffmpeg_location": ffmpeg,
            "windowsfilenames": True,
            "overwrites": True,
            "nopart": False,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }],
        }

        # Use one selector that explicitly accepts either audio-only or any
        # combined stream containing audio. Alternate player clients are tried
        # only when the normal extraction route cannot expose a usable stream.
        attempts: list[tuple[str, dict]] = [
            ("Firefox signed-in session", {
                "format": "ba/b[acodec!=none]/best*[acodec!=none]/best",
                "cookiesfrombrowser": ("firefox",),
                "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"},
            }),
            ("Firefox signed-in web session", {
                "format": "best*[acodec!=none]/b[acodec!=none]/ba/best",
                "cookiesfrombrowser": ("firefox",),
                "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"},
                "extractor_args": {"youtube": {"player_client": ["web", "web_safari", "web_embedded"]}},
            }),
            ("single anonymous fallback", {
                "format": "best*[acodec!=none]/b[acodec!=none]/ba/best",
            }),
        ]

        for label, special in attempts:
            if progress:
                progress(f"trying {label}", 5, "")
            try:
                options = dict(common)
                options.update(special)
                with YoutubeDL(options) as ydl:
                    ydl.download([result.url])

                downloaded = _usable_media_files(folder, safe)
                if not downloaded:
                    raise FileNotFoundError(
                        "Download completed but no usable audio file was produced"
                    )
                chosen = downloaded[0]
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
                errors.append(f"{label}: {exc}")
                for partial in folder.glob(safe + ".*"):
                    if partial.suffix.lower() in {".part", ".ytdl", ".tmp"}:
                        try:
                            partial.unlink()
                        except OSError:
                            pass

        combined = " | ".join(errors[-3:]) or "No downloader diagnostic was returned"
        lowered = combined.lower()
        if "sign in to confirm" in lowered or "not a bot" in lowered:
            raise RuntimeError(
                "YouTube requires a signed-in browser session. Banjofy tried "
                "Firefox, Edge and Chrome cookies but could not use one. Sign in "
                "to YouTube in Firefox, close Firefox completely, then retry. "
                f"Technical detail: {combined}"
            )
        raise RuntimeError(
            "Banjofy could not obtain a usable audio stream after standard, TV/mobile "
            "and web extraction attempts. Technical detail: " + combined
        )
