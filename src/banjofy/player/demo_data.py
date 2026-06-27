from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class DemoSong:
    title: str
    artist: str
    bpm: int
    key: str
    duration: str
    chords_by_bar: list[str]

    @property
    def beat_chords(self) -> list[str]:
        out: list[str] = []
        for chord in self.chords_by_bar:
            out.extend([chord, "", "", ""])
        return out

DEMO_SONGS = [
    DemoSong(
        title="Country Road Style Demo",
        artist="Banjofy Demo",
        bpm=92,
        key="G",
        duration="1:02",
        chords_by_bar=["G", "Em", "C", "D", "G", "G", "C", "D", "G", "Em", "C", "D", "G", "D", "G", ""],
    ),
    DemoSong(
        title="Simple Bluegrass Demo",
        artist="Banjofy Demo",
        bpm=108,
        key="D",
        duration="0:55",
        chords_by_bar=["D", "G", "D", "A", "D", "G", "D", "A", "D", "D", "G", "A", "D", "G", "A", "D"],
    ),
    DemoSong(
        title="Beginner Waltz? No - Still 4/4 Demo",
        artist="Banjofy Demo",
        bpm=78,
        key="C",
        duration="1:10",
        chords_by_bar=["C", "C", "F", "G", "C", "Am", "F", "G", "C", "F", "C", "G", "C", "G", "C", ""],
    ),
]
