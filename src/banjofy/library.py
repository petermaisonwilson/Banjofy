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
    chords_by_bar: list[str] = field(default_factory=list)


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
                allowed = {
                    "title", "artist", "duration", "bpm", "key", "source",
                    "audio_path", "chords_by_bar",
                }
                clean = {k: v for k, v in item.items() if k in allowed}
                clean.setdefault("title", "")
                clean.setdefault("artist", "")
                clean.setdefault("duration", "")
                clean.setdefault("bpm", "")
                clean.setdefault("key", "")
                clean.setdefault("source", "YouTube")
                clean.setdefault("audio_path", "")
                if not isinstance(clean.get("chords_by_bar"), list):
                    clean["chords_by_bar"] = []
                songs.append(LibrarySong(**clean))
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
