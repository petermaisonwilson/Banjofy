from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class LibrarySong:
    title: str
    artist: str
    duration: str
    bpm: str = ""
    key: str = ""
    source: str = "YouTube"


class SongLibrary:
    """Tiny local library index.

    Build 006.0D creates the first real saved-song library foundation.
    It stores lightweight metadata only. Audio caching already happens elsewhere.
    """

    def __init__(self) -> None:
        self.folder = Path.home() / "Banjofy"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.index_file = self.folder / "library.json"

    def load(self) -> list[LibrarySong]:
        if not self.index_file.exists():
            return []
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            return [LibrarySong(**item) for item in data if isinstance(item, dict)]
        except Exception:
            return []

    def save_song(self, song: LibrarySong) -> None:
        songs = self.load()
        key = (song.title.strip().lower(), song.artist.strip().lower(), song.duration.strip().lower())
        songs = [
            existing for existing in songs
            if (existing.title.strip().lower(), existing.artist.strip().lower(), existing.duration.strip().lower()) != key
        ]
        songs.insert(0, song)
        songs = songs[:100]
        self.index_file.write_text(
            json.dumps([asdict(s) for s in songs], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
