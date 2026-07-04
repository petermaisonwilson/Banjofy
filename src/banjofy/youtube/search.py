from __future__ import annotations

from dataclasses import dataclass
from urllib.request import urlopen


@dataclass
class YouTubeResult:
    title: str
    channel: str
    duration: str
    url: str
    thumbnail_url: str = ""
    thumbnail_data: bytes | None = None


def _format_duration(value) -> str:
    if value in (None, ""):
        return ""
    try:
        seconds = int(float(value))
        if seconds <= 0:
            return ""
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    except Exception:
        return str(value)


def _load_thumbnail(url: str) -> bytes | None:
    if not url:
        return None
    try:
        with urlopen(url, timeout=8) as response:
            return response.read()
    except Exception:
        return None


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    from yt_dlp import YoutubeDL

    options = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
    }

    results: list[YouTubeResult] = []
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    for entry in info.get("entries", []) or []:
        video_id_or_url = entry.get("url") or entry.get("id") or ""
        url = video_id_or_url if video_id_or_url.startswith("http") else f"https://www.youtube.com/watch?v={video_id_or_url}"
        thumbs = entry.get("thumbnails") or []
        thumb_url = thumbs[-1].get("url") if thumbs else ""
        results.append(
            YouTubeResult(
                title=entry.get("title") or "Untitled",
                channel=entry.get("uploader") or entry.get("channel") or "",
                duration=entry.get("duration_string") or _format_duration(entry.get("duration")),
                url=url,
                thumbnail_url=thumb_url,
                thumbnail_data=_load_thumbnail(thumb_url),
            )
        )
    return results
