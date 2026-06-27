from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
import os
import re


ProgressCallback = Callable[[str, float, str], None]


@dataclass(frozen=True)
class DownloadResult:
    file_path: Path
    title: str
    url: str
    was_cached: bool = False


def _safe_name(text: str, fallback: str = "youtube_audio") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip(" ._")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:90] or fallback)


def default_cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Local"
    cache = root / "Banjofy" / "audio_cache"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _existing_download(cache_dir: Path, video_id: str) -> Path | None:
    for candidate in cache_dir.glob(f"{video_id}_*"):
        if candidate.is_file() and candidate.suffix.lower() in {".m4a", ".webm", ".mp3", ".opus"}:
            return candidate
    return None


def download_audio(url: str, title: str = "YouTube audio", progress: ProgressCallback | None = None) -> DownloadResult:
    """Download best available audio using yt-dlp into a local cache.

    Stage 004.2 only downloads and caches audio. It does not play it yet.
    """
    if not url:
        raise RuntimeError("No YouTube URL was supplied")

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("yt-dlp is not installed in this build") from exc

    cache_dir = default_cache_dir()

    if progress:
        progress("Preparing download...", 0, "")

    # First lightly inspect so we can create a stable cache name.
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(f"Could not read YouTube information: {exc}") from exc

    video_id = str((info or {}).get("id") or _safe_name(title, "youtube_audio"))
    real_title = str((info or {}).get("title") or title or "YouTube audio")
    existing = _existing_download(cache_dir, video_id)
    if existing:
        if progress:
            progress("Already downloaded", 100, str(existing))
        return DownloadResult(existing, real_title, url, was_cached=True)

    outtmpl = str(cache_dir / f"{video_id}_{_safe_name(real_title)}.%(ext)s")

    def hook(data: dict[str, Any]) -> None:
        if not progress:
            return
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            pct = (downloaded / total * 100) if total else 0
            speed = data.get("speed") or 0
            eta = data.get("eta")
            detail = ""
            if eta is not None:
                detail = f"ETA {eta}s"
            elif speed:
                detail = f"{int(speed / 1024)} KB/s"
            progress("Downloading audio...", max(0, min(99, pct)), detail)
        elif status == "finished":
            progress("Finalising audio file...", 99, "")

    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        # No postprocessor yet. This avoids requiring FFmpeg for Stage 004.2.
    }

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise RuntimeError(f"Audio download failed: {exc}") from exc

    downloaded = _existing_download(cache_dir, video_id)
    if not downloaded:
        # fallback: anything matching the start of the template
        matches = list(cache_dir.glob(f"{video_id}_*"))
        downloaded = matches[0] if matches else None
    if not downloaded:
        raise RuntimeError("Download finished but the audio file could not be found")

    if progress:
        progress("Audio downloaded", 100, str(downloaded))
    return DownloadResult(downloaded, real_title, url, was_cached=False)
