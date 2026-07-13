from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import re
from pathlib import Path

from banjofy.analysis.audio_analysis import AnalysisResult
from banjofy.storage.paths import songs_folder


@dataclass(frozen=True)
class LibrarySong:
    title: str
    channel: str
    duration: str
    bpm: int
    estimated_bars: int
    audio_file: str
    analysis_file: str
    source_url: str
    key: str = "Not analysed yet"
    chords_by_bar: list[str] | None = None
    detected_bpm: int = 0


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:140] or "song"


class LibraryManager:
    def save_from_analysis(self, result: AnalysisResult) -> Path:
        if not result:
            raise ValueError("No analysis result to save")
        song = LibrarySong(
            title=result.title,
            channel=result.channel,
            duration=result.duration,
            bpm=result.bpm,
            estimated_bars=result.estimated_bars,
            audio_file=result.audio_file,
            analysis_file=result.analysis_file,
            source_url=result.source_url,
            key=getattr(result, "key", "Not analysed yet"),
            chords_by_bar=getattr(result, "chords_by_bar", None),
            detected_bpm=result.bpm,
        )
        path = self._path_for_song(song)
        path.write_text(json.dumps(asdict(song), indent=2), encoding="utf-8")
        return path

    def update_bpm(self, song: LibrarySong, bpm: int, estimated_bars: int) -> tuple[LibrarySong, Path]:
        if not song:
            raise ValueError("No Library song supplied")
        bpm = max(30, min(300, int(round(bpm))))
        estimated_bars = max(1, int(estimated_bars))
        detected = int(getattr(song, "detected_bpm", 0) or song.bpm)
        updated = replace(song, bpm=bpm, estimated_bars=estimated_bars, detected_bpm=detected)
        path = self._path_for_song(updated)
        path.write_text(json.dumps(asdict(updated), indent=2), encoding="utf-8")
        return updated, path

    def load_all(self) -> list[LibrarySong]:
        folder = songs_folder()
        songs: list[LibrarySong] = []
        for path in sorted(folder.glob("*.song.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("key", "Not analysed yet")
                data.setdefault("chords_by_bar", None)
                data.setdefault("detected_bpm", int(data.get("bpm", 0) or 0))
                songs.append(LibrarySong(**data))
            except Exception:
                continue
        return songs

    def _path_for_song(self, song: LibrarySong) -> Path:
        return songs_folder() / f"{_safe_filename(song.title + ' - ' + song.channel)}.song.json"
