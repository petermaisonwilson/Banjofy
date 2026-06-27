from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import urllib.request


@dataclass(frozen=True)
class YouTubeResult:
    title: str
    channel: str
    duration: str
    url: str
    thumbnail: str = ""
    thumbnail_data: bytes = b""


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


def _video_id_from_url_or_entry(entry: dict[str, Any], webpage_url: str) -> str:
    video_id = str(entry.get("id") or "").strip()
    if video_id and len(video_id) <= 20:
        return video_id

    raw_url = str(entry.get("url") or webpage_url or "").strip()
    if "watch?v=" in raw_url:
        return raw_url.split("watch?v=", 1)[1].split("&", 1)[0]
    if "youtu.be/" in raw_url:
        return raw_url.split("youtu.be/", 1)[1].split("?", 1)[0]
    if raw_url and not raw_url.startswith("http") and len(raw_url) <= 20:
        return raw_url
    return ""


def _best_thumbnail_url(entry: dict[str, Any], webpage_url: str) -> str:
    thumb = entry.get("thumbnail") or ""
    if isinstance(thumb, str) and thumb.startswith("http"):
        return thumb

    thumbs = entry.get("thumbnails") or []
    if isinstance(thumbs, list):
        for candidate in reversed(thumbs):
            if isinstance(candidate, dict):
                url = candidate.get("url") or ""
                if isinstance(url, str) and url.startswith("http"):
                    return url

    video_id = _video_id_from_url_or_entry(entry, webpage_url)
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
    return ""


def _download_thumbnail(url: str) -> bytes:
    if not url:
        return b""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = response.read(250_000)
            return data if data else b""
    except Exception:
        return b""


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    """Search YouTube using yt-dlp and return display-ready results."""
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
        channel = entry.get("uploader") or entry.get("channel") or entry.get("creator") or "Unknown channel"
        duration = _format_duration(entry.get("duration"))

        webpage_url = entry.get("webpage_url") or entry.get("url") or ""
        if webpage_url and not str(webpage_url).startswith("http"):
            webpage_url = f"https://www.youtube.com/watch?v={webpage_url}"

        thumbnail = _best_thumbnail_url(entry, str(webpage_url))
        thumbnail_data = _download_thumbnail(thumbnail)

        results.append(
            YouTubeResult(
                title=str(title),
                channel=str(channel),
                duration=duration,
                url=str(webpage_url),
                thumbnail=thumbnail,
                thumbnail_data=thumbnail_data,
            )
        )

    return results
