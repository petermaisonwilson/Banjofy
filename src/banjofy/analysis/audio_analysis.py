from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re

from banjofy.download.audio_downloader import DownloadedAudio
from banjofy.storage.paths import analysis_folder


@dataclass(frozen=True)
class AnalysisResult:
    title: str
    channel: str
    duration: str
    bpm: int
    estimated_bars: int
    audio_file: str
    source_url: str
    key: str = "Not analysed yet"
    chords_by_bar: list[str] | None = None
    analysis_file: str = ""
    note: str = "Key and chords are not audio-detected yet. Chord data is provisional for grid plumbing."


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:140] or "analysis"


class AnalysisManager:
    """Creates a basic analysis record for downloaded audio only.

    Module 4 deliberately does not attempt accurate chord/key recognition.
    """

    def analyse(self, audio: DownloadedAudio) -> AnalysisResult:
        if not audio or not audio.file_path:
            raise ValueError("No downloaded audio to analyse")

        bpm = 92
        estimated_bars = self._estimate_bars(audio.duration, bpm)

        provisional = ["G", "C", "G", "D"]
        chords_by_bar = [provisional[i % len(provisional)] for i in range(max(1, estimated_bars))]

        result = AnalysisResult(
            title=audio.title,
            channel=audio.channel,
            duration=audio.duration or "—",
            bpm=bpm,
            estimated_bars=estimated_bars,
            audio_file=str(audio.file_path),
            source_url=audio.source_url,
            key="Not analysed yet",
            chords_by_bar=chords_by_bar,
        )

        path = self.save_result(result)
        return AnalysisResult(
            title=result.title,
            channel=result.channel,
            duration=result.duration,
            bpm=result.bpm,
            estimated_bars=result.estimated_bars,
            audio_file=result.audio_file,
            source_url=result.source_url,
            key=result.key,
            chords_by_bar=result.chords_by_bar,
            analysis_file=str(path),
            note=result.note,
        )

    def save_result(self, result: AnalysisResult) -> Path:
        folder = analysis_folder()
        safe = _safe_filename(f"{result.title} - {result.channel}")
        path = folder / f"{safe}.analysis.json"
        data = asdict(result)
        data["analysis_file"] = str(path)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def _estimate_bars(self, duration: str, bpm: int) -> int:
        try:
            if not duration or duration == "—":
                return 16
            parts = duration.strip().split(":")
            if len(parts) == 2:
                seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return 16
            beats = int(seconds * bpm / 60)
            return max(16, (beats + 3) // 4)
        except Exception:
            return 16
