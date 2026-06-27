from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class YouTubeResult:
    title: str
    channel: str
    duration: str
    url: str
    thumbnail: str = ""


def _format_duration(seconds: Any) -> str:
    if seconds is None:
        return "—"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "—"
    mins, secs = divmod(total, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _best_thumbnail(entry: dict[str, Any]) -> str:
    """Return the best thumbnail URL yt-dlp gives us.

    yt-dlp sometimes returns `thumbnail`, sometimes a list called
    `thumbnails`, and when using flat search results it may return neither.
    This helper checks all the common places and picks the highest-quality
    available URL.
    """
    direct = entry.get("thumbnail")
    if isinstance(direct, str) and direct.startswith("http"):
        return direct

    thumbnails = entry.get("thumbnails") or []
    if isinstance(thumbnails, list):
        urls: list[str] = []
        for item in thumbnails:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.startswith("http"):
                    urls.append(url)
        if urls:
            return urls[-1]

    video_id = entry.get("id") or entry.get("url")
    if isinstance(video_id, str) and video_id and not video_id.startswith("http"):
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return ""


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    """Search YouTube using yt-dlp and return display-ready results."""
    query = query.strip()
    if not query:
        return []

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover - depends on installed package
        raise RuntimeError("yt-dlp is not installed in this build") from exc

    # Do NOT use extract_flat here. Flat search is faster but often loses
    # thumbnails, which is exactly what broke Build 004.1C.
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 25,
        "noplaylist": True,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except Exception as exc:
        raise RuntimeError(f"YouTube search failed: {exc}") from exc

    entries = (info or {}).get("entries") or []
    results: list[YouTubeResult] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title") or "Untitled result"
        channel = entry.get("uploader") or entry.get("channel") or entry.get("channel_id") or "Unknown channel"
        duration = _format_duration(entry.get("duration"))
        webpage_url = entry.get("webpage_url") or entry.get("original_url") or entry.get("url") or ""
        if webpage_url and not str(webpage_url).startswith("http"):
            webpage_url = f"https://www.youtube.com/watch?v={webpage_url}"
        thumb = _best_thumbnail(entry)
        results.append(
            YouTubeResult(
                title=str(title),
                channel=str(channel),
                duration=duration,
                url=str(webpage_url),
                thumbnail=thumb,
            )
        )

    return results
