from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DemoSong:
    title: str
    artist: str
    bpm: int
    key: str
    duration: str
    chords_by_bar: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.beat_chords: list[str] = []
        for chord in self.chords_by_bar:
            self.beat_chords.append(chord)
            self.beat_chords.extend(["", "", ""])


DEMO_SONGS = [
    DemoSong(
        title="Demo Song",
        artist="Banjofy",
        bpm=92,
        key="G",
        duration="1:04",
        chords_by_bar=["G", "C", "G", "D", "G", "C", "G", "D", "Em", "C", "G", "D", "G", "D", "G", "G"],
    )
]
