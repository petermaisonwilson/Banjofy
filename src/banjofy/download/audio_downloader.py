from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable
from yt_dlp import YoutubeDL
from banjofy.models.search_result import SearchResult
from banjofy.storage.paths import audio_folder

ProgressCallback = Callable[[str, int, str], None]

@dataclass(frozen=True)
class DownloadedAudio:
    title: str
    channel: str
    duration: str
    source_url: str
    file_path: Path
    was_cached: bool = False

def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:140] or "audio"

class DownloadManager:
    """Downloads selected YouTube result audio only."""
    def download(self, result: SearchResult, progress: ProgressCallback | None = None) -> DownloadedAudio:
        if not result or not result.url:
            raise ValueError("No selected YouTube result to download")
        folder = audio_folder()
        safe = _safe_filename(f"{result.title} - {result.channel}")
        existing = sorted(folder.glob(safe + ".*"))
        if existing:
            if progress: progress("cached", 100, str(existing[0]))
            return DownloadedAudio(result.title, result.channel, result.duration, result.url, existing[0], True)

        def hook(data: dict) -> None:
            if not progress: return
            status = data.get("status", "")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                pct = int(downloaded * 100 / total) if total else 0
                progress("downloading", max(0, min(pct, 99)), "")
            elif status == "finished":
                progress("downloaded", 100, data.get("filename", ""))

        base = {
            "format": "bestaudio/best",
            "outtmpl": str(folder / (safe + ".%(ext)s")),
            "quiet": True,
            "noplaylist": True,
            "progress_hooks": [hook],
        }
        attempts = [
            ("standard", {}),
            ("edge cookies", {"cookiesfrombrowser": ("edge",)}),
            ("chrome cookies", {"cookiesfrombrowser": ("chrome",)}),
            ("firefox cookies", {"cookiesfrombrowser": ("firefox",)}),
        ]
        last_error: Exception | None = None
        for label, extra in attempts:
            if progress: progress(f"trying {label}", 5, "")
            try:
                opts = dict(base); opts.update(extra)
                with YoutubeDL(opts) as ydl: ydl.download([result.url])
                downloaded = sorted(folder.glob(safe + ".*"))
                if not downloaded: raise FileNotFoundError("Download finished but no audio file was found")
                if progress: progress("complete", 100, str(downloaded[0]))
                return DownloadedAudio(result.title, result.channel, result.duration, result.url, downloaded[0], False)
            except Exception as exc:
                last_error = exc
        msg = str(last_error) if last_error else "unknown download error"
        if "Sign in to confirm" in msg or "not a bot" in msg or "cookies" in msg.lower():
            raise RuntimeError("YouTube needs browser sign-in/cookies. Open YouTube in Edge or Chrome, sign in once, then try again.") from last_error
        raise RuntimeError(msg) from last_error
