from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    audio_path: str = ""
    source_url: str = ""
    thumbnail_url: str = ""
    chords_by_bar: list[str] = field(default_factory=list)
    beat_times_ms: list[int] = field(default_factory=list)


class SongLibrary:
    def __init__(self) -> None:
        self.folder = Path.home() / "Banjofy"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.index_file = self.folder / "library.json"

    def load(self) -> list[LibrarySong]:
        if not self.index_file.exists():
            return []
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            songs: list[LibrarySong] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                # Backwards-compatible load: older library entries only had
                # title/artist/duration/bpm/key/source.
                allowed = {field.name for field in LibrarySong.__dataclass_fields__.values()}
                cleaned = {k: v for k, v in item.items() if k in allowed}
                songs.append(LibrarySong(**cleaned))
            return songs
        except Exception:
            return []

    def save_song(self, song: LibrarySong) -> None:
        songs = self.load()
        key = (song.title.lower(), song.artist.lower(), song.duration.lower())
        songs = [
            s for s in songs
            if (s.title.lower(), s.artist.lower(), s.duration.lower()) != key
        ]
        songs.insert(0, song)
        self.index_file.write_text(
            json.dumps([asdict(s) for s in songs[:200]], indent=2),
            encoding="utf-8",
        )
