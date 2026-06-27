from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class YouTubeSearchResult:
    """Small, UI-friendly representation of a YouTube search result."""

    title: str
    channel: str
    duration_text: str
    webpage_url: str
    thumbnail_url: str = ""


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def search_youtube(query: str, limit: int = 8) -> list[YouTubeSearchResult]:
    """Search YouTube using yt-dlp.

    This is Build 004.1A: search only. It deliberately does not download audio yet.
    """

    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Check requirements.txt and rebuild the EXE.") from exc

    clean_query = query.strip()
    if not clean_query:
        return []

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }

    search_term = f"ytsearch{limit}:{clean_query}"
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(search_term, download=False)

    entries = info.get("entries", []) if isinstance(info, dict) else []
    results: list[YouTubeSearchResult] = []

    for entry in entries:
        if not entry:
            continue

        title = entry.get("title") or "Untitled YouTube result"
        channel = entry.get("uploader") or entry.get("channel") or entry.get("creator") or "YouTube"
        duration_text = _format_duration(entry.get("duration"))
        webpage_url = entry.get("webpage_url") or entry.get("url") or ""
        thumbnail_url = entry.get("thumbnail") or ""

        results.append(
            YouTubeSearchResult(
                title=title,
                channel=channel,
                duration_text=duration_text,
                webpage_url=webpage_url,
                thumbnail_url=thumbnail_url,
            )
        )

    return results


class YouTubeSearchWorker(QObject):
    """Runs a YouTube search off the UI thread so the app does not freeze."""

    completed = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, limit: int = 8) -> None:
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self) -> None:
        try:
            self.completed.emit(search_youtube(self.query, self.limit))
        except Exception as exc:
            self.failed.emit(str(exc))
