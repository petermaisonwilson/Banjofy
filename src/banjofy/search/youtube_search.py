from __future__ import annotations

from urllib.request import urlopen
from yt_dlp import YoutubeDL
from banjofy.models.search_result import SearchResult


def _format_duration(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str) and ":" in value:
        return value
    try:
        seconds = int(float(value))
    except Exception:
        return str(value)
    if seconds <= 0:
        return ""
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _load_thumbnail(url: str) -> bytes | None:
    if not url:
        return None
    try:
        with urlopen(url, timeout=8) as response:
            return response.read()
    except Exception:
        return None


class YouTubeSearchManager:
    """Responsible only for YouTube searching."""

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        if not query.strip():
            return []

        options = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": True,
        }

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

        results: list[SearchResult] = []
        for entry in info.get("entries", []) or []:
            video_id_or_url = entry.get("url") or entry.get("id") or ""
            url = video_id_or_url if str(video_id_or_url).startswith("http") else f"https://www.youtube.com/watch?v={video_id_or_url}"

            thumbs = entry.get("thumbnails") or []
            thumb_url = thumbs[-1].get("url") if thumbs else ""

            results.append(
                SearchResult(
                    title=entry.get("title") or "Untitled",
                    channel=entry.get("uploader") or entry.get("channel") or "",
                    duration=entry.get("duration_string") or _format_duration(entry.get("duration")),
                    url=url,
                    thumbnail_url=thumb_url,
                    thumbnail_data=_load_thumbnail(thumb_url),
                )
            )

        return results
