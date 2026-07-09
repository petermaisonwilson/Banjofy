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
    key: str = "Unknown"
    chords_by_bar: list[str] | None = None
    analysis_file: str = ""
    note: str = "Module 8 provides first chord/key data plumbing. Musical accuracy is still provisional."


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
        key = self._estimate_key_from_title(audio.title)
        chords_by_bar = self._provisional_chords_for_key(key, estimated_bars)

        result = AnalysisResult(
            title=audio.title,
            channel=audio.channel,
            duration=audio.duration or "—",
            bpm=bpm,
            estimated_bars=estimated_bars,
            audio_file=str(audio.file_path),
            source_url=audio.source_url,
            key=key,
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

    def _estimate_key_from_title(self, title: str) -> str:
        """Temporary key seed.

        This is deliberately conservative. True audio key detection is a later build.
        Known false claims are worse than Unknown, so default to Unknown unless a future
        real detector supplies confidence.
        """
        return "Unknown"

    def _provisional_chords_for_key(self, key: str, bars: int) -> list[str]:
        """First chord data plumbing for the Practice grid.

        These are not claimed to be detected chords yet. They allow Module 8 to prove
        that analysis chord data flows into the Library and Practice grid correctly.
        """
        progression = ["G", "C", "G", "D"]
        return [progression[i % len(progression)] for i in range(max(1, bars))]

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
