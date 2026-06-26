from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoSong:
    title: str
    artist: str
    bpm: int
    key: str
    duration: str
    chords: list[str]


DEMO_SONGS: list[DemoSong] = [
    DemoSong(
        title="Country Roads",
        artist="John Denver demo",
        bpm=82,
        key="G",
        duration="03:10",
        chords=["G", "", "", "", "Em", "", "", "", "D", "", "", "", "C", "", "", ""] * 4,
    ),
    DemoSong(
        title="Wagon Wheel",
        artist="Old Crow style demo",
        bpm=74,
        key="G",
        duration="03:52",
        chords=["G", "", "", "", "D", "", "", "", "Em", "", "", "", "C", "", "", ""] * 4,
    ),
    DemoSong(
        title="Simple Bluegrass Roll",
        artist="Banjofy demo",
        bpm=96,
        key="D",
        duration="02:20",
        chords=["D", "", "", "", "G", "", "", "", "A", "", "", "", "D", "", "", ""] * 4,
    ),
]
