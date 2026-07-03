from __future__ import annotations


class ChordGridController:
    @staticmethod
    def display_chord(chord: str, capo: int = 0, beginner: bool = False) -> str:
        if not chord:
            return ""
        if beginner:
            for suffix in ["maj7", "sus4", "sus2", "add9"]:
                chord = chord.replace(suffix, "")
        return chord
