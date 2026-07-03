from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class DownloadResult:
    file_path: Path
    was_cached: bool = False


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip()[:120] or "audio"


def download_audio(url: str, title: str, progress=None) -> DownloadResult:
    from yt_dlp import YoutubeDL

    folder = Path.home() / "Banjofy" / "audio"
    folder.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(title)
    mp3 = folder / f"{safe}.mp3"
    if mp3.exists():
        if progress:
            progress("cached", 100, str(mp3))
        return DownloadResult(mp3, was_cached=True)

    if progress:
        progress("downloading", 10, "")

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(folder / f"{safe}.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    }

    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    if progress:
        progress("complete", 100, str(mp3))

    return DownloadResult(mp3, was_cached=False)
