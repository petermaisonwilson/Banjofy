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


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    """Search YouTube using yt-dlp and return simple display-ready results.

    This function is deliberately small and defensive. It raises a readable
    RuntimeError if yt-dlp cannot search, so the UI can show a proper message
    instead of appearing to do nothing.
    """
    query = query.strip()
    if not query:
        return []

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover - depends on installed package
        raise RuntimeError("yt-dlp is not installed in this build") from exc

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "socket_timeout": 20,
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
        if not entry:
            continue
        title = entry.get("title") or "Untitled result"
        channel = entry.get("uploader") or entry.get("channel") or "Unknown channel"
        duration = _format_duration(entry.get("duration"))
        webpage_url = entry.get("webpage_url") or entry.get("url") or ""
        if webpage_url and not webpage_url.startswith("http"):
            webpage_url = f"https://www.youtube.com/watch?v={webpage_url}"
        thumb = entry.get("thumbnail") or ""
        results.append(YouTubeResult(title=title, channel=channel, duration=duration, url=webpage_url, thumbnail=thumb))

    return results
