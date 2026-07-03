from __future__ import annotations

NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def transpose_chord(chord: str, semitones: int) -> str:
    if not chord or not semitones:
        return chord
    root = chord[:2] if len(chord) >= 2 and chord[1] in ["#", "b"] else chord[:1]
    suffix = chord[len(root):]
    root = FLAT_TO_SHARP.get(root, root)
    if root not in NOTES_SHARP:
        return chord
    return NOTES_SHARP[(NOTES_SHARP.index(root) + semitones) % 12] + suffix
