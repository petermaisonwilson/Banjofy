# 5-string banjo Open G tuning: gDGBD
# Frets are stored as 5th, 4th, 3rd, 2nd, 1st string.
# This is deliberately small for 0.1.0. We will expand it into the full library next.

CHORDS = {
    "G": [0, 0, 0, 0, 0],
    "C": [0, 2, 0, 1, 2],
    "D": [0, 0, 2, 3, 4],
    "A": [0, 2, 2, 2, 2],
    "E": [0, 2, 1, 0, 2],
    "F": [0, 3, 2, 1, 3],
    "B": [0, 4, 4, 4, 4],
    "Am": [0, 2, 2, 1, 2],
    "Em": [0, 2, 0, 0, 2],
    "Dm": [0, 0, 2, 3, 3],
    "G7": [0, 0, 0, 0, 3],
    "C7": [0, 2, 0, 1, 1],
    "D7": [0, 0, 2, 1, 2],
    "A7": [0, 2, 2, 2, 0],
    "E7": [0, 2, 1, 0, 0],
}

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ENHARMONIC = {"Db":"C#", "Eb":"D#", "Gb":"F#", "Ab":"G#", "Bb":"A#"}


def split_chord(name: str):
    if not name:
        return "G", ""
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    suffix = name[len(root):]
    return ENHARMONIC.get(root, root), suffix


def transpose_chord(name: str, semitones: int) -> str:
    root, suffix = split_chord(name)
    if root not in NOTES:
        return name
    return NOTES[(NOTES.index(root) + semitones) % 12] + suffix


def frets_for(chord: str):
    return CHORDS.get(chord) or CHORDS.get(split_chord(chord)[0]) or CHORDS["G"]
