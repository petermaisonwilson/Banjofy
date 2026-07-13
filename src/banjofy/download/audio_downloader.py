from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

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
    return text[:140] or "audio"


class DownloadManager:
    """Downloads the best usable audio stream available for a selected result."""

    def download(self, result: SearchResult, progress: ProgressCallback | None = None) -> DownloadedAudio:
        if not result or not result.url:
            raise ValueError("No selected YouTube result to download")

        folder = audio_folder()
        safe = _safe_filename(f"{result.title} - {result.channel}")

        existing = sorted(folder.glob(safe + ".*"))
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

        def hook(data: dict) -> None:
            if not progress:
                return
            status = data.get("status", "")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                percent = int(downloaded * 100 / total) if total else 0
                progress("downloading", max(0, min(percent, 99)), "")
            elif status == "finished":
                progress("downloaded", 100, data.get("filename", ""))

        common = {
            "outtmpl": str(folder / (safe + ".%(ext)s")),
            "quiet": True,
            "noplaylist": True,
            "progress_hooks": [hook],
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
        }

        # Try normal audio-only first, then more permissive selections and
        # alternate YouTube player clients. The final fallback accepts the
        # best combined stream because FFmpeg later extracts/decodes its audio.
        attempts: list[tuple[str, dict]] = [
            ("best audio", {
                "format": "bestaudio/best",
            }),
            ("any audio stream", {
                "format": "bestaudio*",
            }),
            ("Android audio", {
                "format": "bestaudio/best",
                "extractor_args": {"youtube": {"player_client": ["android"]}},
            }),
            ("web audio", {
                "format": "bestaudio/best",
                "extractor_args": {"youtube": {"player_client": ["web"]}},
            }),
            ("combined fallback", {
                "format": "best",
            }),
            ("Edge cookies", {
                "format": "bestaudio/best",
                "cookiesfrombrowser": ("edge",),
            }),
            ("Chrome cookies", {
                "format": "bestaudio/best",
                "cookiesfrombrowser": ("chrome",),
            }),
            ("Firefox cookies", {
                "format": "bestaudio/best",
                "cookiesfrombrowser": ("firefox",),
            }),
        ]

        last_error: Exception | None = None

        for label, special in attempts:
            if progress:
                progress(f"trying {label}", 5, "")
            try:
                options = dict(common)
                options.update(special)

                with YoutubeDL(options) as ydl:
                    ydl.download([result.url])

                downloaded = sorted(folder.glob(safe + ".*"))
                if not downloaded:
                    raise FileNotFoundError("Download finished but no usable media file was found")

                if progress:
                    progress("complete", 100, str(downloaded[0]))

                return DownloadedAudio(
                    title=result.title,
                    channel=result.channel,
                    duration=result.duration,
                    source_url=result.url,
                    file_path=downloaded[0],
                    was_cached=False,
                )
            except Exception as exc:
                last_error = exc

        message = str(last_error) if last_error else "unknown download error"
        lowered = message.lower()

        if "sign in to confirm" in lowered or "not a bot" in lowered or "cookies" in lowered:
            raise RuntimeError(
                "YouTube needs browser sign-in/cookies. Open YouTube in Edge or Chrome, "
                "sign in once, then try the download again."
            ) from last_error

        if "requested format is not available" in lowered:
            raise RuntimeError(
                "YouTube did not expose a downloadable audio or combined stream for this video. "
                "Try another upload of the same song."
            ) from last_error

        raise RuntimeError(message) from last_error
