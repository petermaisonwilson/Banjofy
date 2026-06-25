from dataclasses import dataclass

@dataclass(frozen=True)
class BanjoChord:
    name: str
    frets: tuple[int, int, int, int, int]  # 5th to 1st string: g D G B D
    fingers: tuple[int, int, int, int, int]

# Starter library. We will expand this heavily.
CHORDS = {
    "G": BanjoChord("G", (0,0,0,0,0), (0,0,0,0,0)),
    "C": BanjoChord("C", (0,2,0,1,2), (0,2,0,1,3)),
    "D": BanjoChord("D", (0,0,0,2,3), (0,0,0,1,2)),
    "A": BanjoChord("A", (2,2,2,2,2), (1,1,1,1,1)),
    "E": BanjoChord("E", (2,2,1,0,2), (3,2,1,0,4)),
    "F": BanjoChord("F", (3,3,2,1,3), (4,3,2,1,4)),
    "Em": BanjoChord("Em", (0,2,0,0,2), (0,2,0,0,3)),
    "Am": BanjoChord("Am", (2,2,1,2,2), (2,3,1,4,4)),
    "Bm": BanjoChord("Bm", (4,4,4,3,4), (2,3,4,1,4)),
    "G7": BanjoChord("G7", (0,0,0,0,3), (0,0,0,0,3)),
    "C7": BanjoChord("C7", (0,2,0,1,1), (0,2,0,1,1)),
    "D7": BanjoChord("D7", (0,0,0,2,1), (0,0,0,2,1)),
    "Dsus4": BanjoChord("Dsus4", (0,0,0,3,3), (0,0,0,3,4)),
}

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ENHARMONIC = {"Db":"C#","Eb":"D#","Gb":"F#","Ab":"G#","Bb":"A#"}

def transpose_chord_name(name: str, semitones: int) -> str:
    if not name or name == "—":
        return name
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    suffix = name[len(root):]
    root = ENHARMONIC.get(root, root)
    if root not in NOTES:
        return name
    return NOTES[(NOTES.index(root) + semitones) % 12] + suffix

def get_chord(name: str) -> BanjoChord:
    return CHORDS.get(name, CHORDS.get(name.replace("#", ""), BanjoChord(name, (0,0,0,0,0), (0,0,0,0,0))))
