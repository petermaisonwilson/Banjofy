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


def _video_id_from_entry(entry: dict[str, Any], webpage_url: str) -> str:
    """Return a YouTube video id if yt-dlp gave us one."""
    raw_id = entry.get("id") or entry.get("url") or ""
    raw_id = str(raw_id).strip()

    # yt-dlp search results often use the video id directly as either id or url.
    if raw_id and not raw_id.startswith("http") and len(raw_id) >= 8:
        return raw_id

    if "watch?v=" in webpage_url:
        return webpage_url.split("watch?v=", 1)[1].split("&", 1)[0]

    if "youtu.be/" in webpage_url:
        return webpage_url.split("youtu.be/", 1)[1].split("?", 1)[0]

    return ""


def _thumbnail_from_entry(entry: dict[str, Any], video_id: str) -> str:
    """Return the best available thumbnail URL without ever raising an error."""
    direct = entry.get("thumbnail")
    if isinstance(direct, str) and direct.startswith("http"):
        return direct

    thumbs = entry.get("thumbnails")
    if isinstance(thumbs, list):
        # Choose the largest thumbnail that has a valid URL.
        valid_urls: list[str] = []
        for item in thumbs:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.startswith("http"):
                    valid_urls.append(url)
        if valid_urls:
            return valid_urls[-1]

    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return ""


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    """Search YouTube using yt-dlp and return display-ready results.

    This version deliberately keeps the known-good search behaviour and only
    adds safer thumbnail handling. Any problem is raised as a readable RuntimeError
    so Banjofy can show it in the results box instead of appearing to do nothing.
    """
    query = query.strip()
    if not query:
        return []

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("yt-dlp is not installed in this build") from exc

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
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
        if not isinstance(entry, dict):
            continue

        title = entry.get("title") or "Untitled result"
        channel = entry.get("uploader") or entry.get("channel") or entry.get("creator") or "Unknown channel"
        duration = _format_duration(entry.get("duration"))

        webpage_url = entry.get("webpage_url") or entry.get("url") or ""
        webpage_url = str(webpage_url).strip()

        if webpage_url and not webpage_url.startswith("http"):
            webpage_url = f"https://www.youtube.com/watch?v={webpage_url}"

        video_id = _video_id_from_entry(entry, webpage_url)
        thumbnail = _thumbnail_from_entry(entry, video_id)

        results.append(
            YouTubeResult(
                title=str(title),
                channel=str(channel),
                duration=duration,
                url=webpage_url,
                thumbnail=thumbnail,
            )
        )

    return results
