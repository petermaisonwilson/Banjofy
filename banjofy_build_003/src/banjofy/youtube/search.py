from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeResult:
    title: str
    uploader: str
    duration: str
    url: str
    thumbnail: str


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def search_youtube(query: str, limit: int = 8) -> list[YouTubeResult]:
    """Search YouTube using yt-dlp and return lightweight results.

    This is search-only. Build 003 does not download or play audio.
    """
    import yt_dlp

    query = query.strip()
    if not query:
        return []

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    results: list[YouTubeResult] = []
    for entry in data.get("entries", []) if data else []:
        if not entry:
            continue
        title = entry.get("title") or "Untitled"
        uploader = entry.get("uploader") or entry.get("channel") or "YouTube"
        url = entry.get("webpage_url") or entry.get("url") or ""
        if url and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        thumbnail = entry.get("thumbnail") or ""
        results.append(
            YouTubeResult(
                title=title,
                uploader=uploader,
                duration=_format_duration(entry.get("duration")),
                url=url,
                thumbnail=thumbnail,
            )
        )
    return results
