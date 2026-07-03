from __future__ import annotations
from dataclasses import dataclass, field
from banjofy.models.beat_map import BeatMap
from banjofy.models.chord_event import ChordEvent

@dataclass
class SongMetadata:
    title: str = ""
    artist: str = ""
    duration: str = ""
    source: str = "YouTube"
    source_url: str = ""
    thumbnail_path: str = ""

@dataclass
class Song:
    metadata: SongMetadata = field(default_factory=SongMetadata)
    bpm: float | None = None
    key: str | None = None
    beat_map: BeatMap = field(default_factory=BeatMap)
    chord_events: list[ChordEvent] = field(default_factory=list)
