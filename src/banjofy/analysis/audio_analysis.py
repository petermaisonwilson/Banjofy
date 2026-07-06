from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from banjofy.download.audio_downloader import DownloadedAudio
from banjofy.storage.paths import analysis_folder


@dataclass(frozen=True)
class AnalysisResult:
    title: str
    channel: str
    duration: str
    bpm: int
    key: str
    chords_by_bar: list[str]
    estimated_bars: int
    source_audio: str
    confidence_note: str = "BPM/key/chords are placeholder analysis in Module 3."


class AnalysisManager:
    """Responsible only for creating/storing a first analysis record.

    Module 3 analysis is deliberately simple. It proves the workflow and
    storage format. Accurate chord/key recognition comes later.
    """

    def analyse(self, audio: DownloadedAudio) -> AnalysisResult:
        if not audio or not audio.file_path:
            raise ValueError("No downloaded audio to analyse")

        bpm = 92
        key = "Unknown"
        estimated_bars = self._estimate_bars(audio.duration, bpm)
        if estimated_bars < 16:
            estimated_bars = 16

        # Placeholder progression only. 006.3.x will replace this with the real engine.
        progression = ["G", "C", "G", "D"]
        chords = [progression[i % len(progression)] for i in range(estimated_bars)]

        result = AnalysisResult(
            title=audio.title,
            channel=audio.channel,
            duration=audio.duration or "—",
            bpm=bpm,
            key=key,
            chords_by_bar=chords,
            estimated_bars=estimated_bars,
            source_audio=str(audio.file_path),
        )
        self.save_result(result)
        return result

    def save_result(self, result: AnalysisResult) -> Path:
        folder = analysis_folder()
        safe = self._safe_name(f"{result.title} - {result.channel}")
        path = folder / f"{safe}.json"
        path.write_text(json.dumps(result.__dict__, indent=2), encoding="utf-8")
        return path

    def _estimate_bars(self, duration: str, bpm: int) -> int:
        try:
            if not duration or duration == "—":
                return 16
            parts = duration.split(":")
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

    def _safe_name(self, text: str) -> str:
        keep = []
        for ch in text:
            keep.append(ch if ch.isalnum() or ch in " ._-" else "_")
        return "".join(keep).strip()[:140] or "analysis"
