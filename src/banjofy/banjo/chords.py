from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChordShape:
    name: str
    frets: tuple[int, int, int, int, int]
    fingers: tuple[int, int, int, int, int]


# Strings are displayed left-to-right as: g D G B D
# 0 = open string. These are starter shapes for Build 001.
CHORDS: dict[str, ChordShape] = {
    "G": ChordShape("G", (0, 0, 0, 0, 0), (0, 0, 0, 0, 0)),
    "C": ChordShape("C", (0, 2, 0, 1, 2), (0, 2, 0, 1, 3)),
    "D": ChordShape("D", (0, 0, 0, 3, 4), (0, 0, 0, 1, 2)),
    "A": ChordShape("A", (2, 2, 2, 2, 2), (1, 1, 1, 1, 1)),
    "Em": ChordShape("Em", (0, 2, 0, 0, 2), (0, 2, 0, 0, 3)),
    "Bm": ChordShape("Bm", (4, 4, 4, 3, 4), (2, 3, 4, 1, 4)),
    "F": ChordShape("F", (0, 3, 2, 1, 3), (0, 3, 2, 1, 4)),
    "Am": ChordShape("Am", (2, 2, 2, 1, 2), (2, 3, 4, 1, 4)),
}


def get_chord(name: str) -> ChordShape:
    return CHORDS.get(name, CHORDS["G"])
