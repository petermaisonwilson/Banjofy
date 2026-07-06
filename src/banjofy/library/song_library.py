from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path

from banjofy.analysis.audio_analysis import AnalysisResult
from banjofy.storage.paths import songs_folder


@dataclass(frozen=True)
class LibrarySong:
    title: str
    channel: str
    duration: str
    bpm: int
    estimated_bars: int
    audio_file: str
    analysis_file: str
    source_url: str


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:140] or "song"


class LibraryManager:
    def save_from_analysis(self, result: AnalysisResult) -> Path:
        if not result:
            raise ValueError("No analysis result to save")
        song = LibrarySong(
            title=result.title,
            channel=result.channel,
            duration=result.duration,
            bpm=result.bpm,
            estimated_bars=result.estimated_bars,
            audio_file=result.audio_file,
            analysis_file=result.analysis_file,
            source_url=result.source_url,
        )
        path = songs_folder() / f"{_safe_filename(song.title + ' - ' + song.channel)}.song.json"
        path.write_text(json.dumps(asdict(song), indent=2), encoding="utf-8")
        return path

    def load_all(self) -> list[LibrarySong]:
        folder = songs_folder()
        songs: list[LibrarySong] = []
        for path in sorted(folder.glob("*.song.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                songs.append(LibrarySong(**json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return songs
