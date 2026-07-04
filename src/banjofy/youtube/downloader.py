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


def _find_newest_audio_file(folder: Path, safe_name: str) -> Path | None:
    candidates: list[Path] = []
    for pattern in [f"{safe_name}.*", f"{safe_name}*.part", f"{safe_name}*.*"]:
        candidates.extend(folder.glob(pattern))

    valid = [
        p for p in candidates
        if p.is_file()
        and not p.name.endswith(".part")
        and p.suffix.lower() in {".mp3", ".m4a", ".webm", ".opus", ".ogg", ".wav"}
    ]
    if not valid:
        return None
    return max(valid, key=lambda p: p.stat().st_mtime)


def _ffmpeg_location() -> str | None:
    try:
        import imageio_ffmpeg

        exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if exe.exists():
            return str(exe)
    except Exception:
        return None
    return None


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

    existing = _find_newest_audio_file(folder, safe)
    if existing and existing.exists():
        if progress:
            progress("cached", 100, str(existing))
        return DownloadResult(existing, was_cached=True)

    def hook(d: dict) -> None:
        if not progress:
            return
        status = d.get("status", "")
        if status == "downloading":
            pct = 10
            try:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if total:
                    pct = max(10, min(85, int((downloaded / total) * 80)))
            except Exception:
                pct = 10
            progress("downloading", pct, "")
        elif status == "finished":
            progress("downloaded", 88, "converting audio")

    ffmpeg = _ffmpeg_location()

    if progress:
        detail = "using packaged ffmpeg" if ffmpeg else "ffmpeg not found; trying direct audio"
        progress("preparing", 5, detail)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(folder / f"{safe}.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "progress_hooks": [hook],
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    }
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

        downloaded = _find_newest_audio_file(folder, safe)
        if downloaded and downloaded.exists():
            if progress:
                progress("complete", 100, str(downloaded))
            return DownloadResult(downloaded, was_cached=False)
    except Exception as first_error:
        if progress:
            progress("retrying", 90, "direct audio without conversion")

        fallback_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(folder / f"{safe}.%(ext)s"),
            "quiet": True,
            "noplaylist": True,
            "progress_hooks": [hook],
        }
        with YoutubeDL(fallback_opts) as ydl:
            ydl.download([url])

        downloaded = _find_newest_audio_file(folder, safe)
        if downloaded and downloaded.exists():
            if progress:
                progress("complete", 100, str(downloaded))
            return DownloadResult(downloaded, was_cached=False)

        raise first_error

    raise RuntimeError("Audio download completed but no output file was found")
