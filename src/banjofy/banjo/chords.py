from __future__ import annotations

from dataclasses import dataclass

NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db":"C#", "Eb":"D#", "Gb":"F#", "Ab":"G#", "Bb":"A#"}

@dataclass(frozen=True)
class ChordShape:
    name: str
    frets: tuple[int, int, int, int, int]
    fingers: tuple[int, int, int, int, int]

# Strings displayed left-to-right as: g D G B D.
# These are practical starter shapes for Open G. More voicings will be added as the library grows.
CHORDS: dict[str, ChordShape] = {
    "G": ChordShape("G", (0, 0, 0, 0, 0), (0, 0, 0, 0, 0)),
    "C": ChordShape("C", (0, 2, 0, 1, 2), (0, 2, 0, 1, 3)),
    "D": ChordShape("D", (0, 0, 0, 3, 4), (0, 0, 0, 1, 2)),
    "A": ChordShape("A", (2, 2, 2, 2, 2), (1, 1, 1, 1, 1)),
    "E": ChordShape("E", (2, 2, 1, 0, 2), (3, 4, 1, 0, 2)),
    "F": ChordShape("F", (0, 3, 2, 1, 3), (0, 3, 2, 1, 4)),
    "B": ChordShape("B", (4, 4, 4, 4, 4), (1, 1, 1, 1, 1)),
    "Am": ChordShape("Am", (2, 2, 2, 1, 2), (2, 3, 4, 1, 4)),
    "Bm": ChordShape("Bm", (4, 4, 4, 3, 4), (2, 3, 4, 1, 4)),
    "Cm": ChordShape("Cm", (0, 1, 0, 1, 1), (0, 1, 0, 2, 3)),
    "Dm": ChordShape("Dm", (0, 0, 0, 3, 3), (0, 0, 0, 2, 3)),
    "Em": ChordShape("Em", (0, 2, 0, 0, 2), (0, 2, 0, 0, 3)),
    "G7": ChordShape("G7", (0, 0, 0, 0, 3), (0, 0, 0, 0, 3)),
    "C7": ChordShape("C7", (0, 2, 0, 1, 1), (0, 3, 0, 1, 2)),
    "D7": ChordShape("D7", (0, 0, 0, 1, 2), (0, 0, 0, 1, 2)),
    "A7": ChordShape("A7", (2, 0, 2, 2, 2), (2, 0, 3, 4, 4)),
    "E7": ChordShape("E7", (2, 2, 1, 0, 0), (3, 4, 1, 0, 0)),
}


def split_chord(name: str) -> tuple[str, str]:
    if not name:
        return "", ""
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    suffix = name[len(root):]
    return FLAT_TO_SHARP.get(root, root), suffix


def transpose_chord(name: str, semitones: int) -> str:
    root, suffix = split_chord(name)
    if root not in NOTES_SHARP:
        return name
    return NOTES_SHARP[(NOTES_SHARP.index(root) + semitones) % 12] + suffix


def get_chord(name: str) -> ChordShape:
    # Prefer exact name. If missing, try root-only. If still missing, G fallback.
    root, suffix = split_chord(name)
    normalised = root + suffix
    if normalised in CHORDS:
        return CHORDS[normalised]
    if root in CHORDS:
        return CHORDS[root]
    return CHORDS["G"]
