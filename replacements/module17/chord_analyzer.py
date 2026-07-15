from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile
import wave
from typing import Callable

import imageio_ffmpeg
import numpy as np

from banjofy.storage.paths import get_library_path


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ChordAnalysis:
    beat_chords: tuple[str, ...]
    bar_chords: tuple[str, ...]
    confidence: float
    source_kind: str
    diagnostic: str

    @property
    def usable(self) -> bool:
        return len(self.beat_chords) >= 4 and any(chord not in ("N", "") for chord in self.beat_chords)


class ChordAnalyzer:
    """Neutral major/minor chord estimation aligned to detected beat timestamps."""

    CACHE_VERSION = 1
    SAMPLE_RATE = 22050
    FRAME_SIZE = 4096
    HOP_SIZE = 2048

    NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

    def _cache_folder(self) -> Path:
        library = get_library_path()
        if library is None:
            raise RuntimeError("Library folder is not configured")
        folder = Path(library) / "chords"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def cache_path_for(self, audio_path: Path) -> Path:
        safe = "".join(
            char if char.isalnum() or char in "._-" else "_"
            for char in audio_path.stem
        )[:120]
        return self._cache_folder() / f"{safe}.chords.json"

    def delete_cache(self, audio_path: Path) -> None:
        path = self.cache_path_for(audio_path)
        if path.exists():
            path.unlink()

    def load_cached(self, audio_path: Path) -> ChordAnalysis | None:
        path = self.cache_path_for(audio_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stat = audio_path.stat()
            if payload.get("cache_version") != self.CACHE_VERSION:
                return None
            if payload.get("audio_size") != stat.st_size:
                return None
            if int(payload.get("audio_mtime", 0)) != int(stat.st_mtime):
                return None
            result = ChordAnalysis(
                beat_chords=tuple(str(v) for v in payload["beat_chords"]),
                bar_chords=tuple(str(v) for v in payload["bar_chords"]),
                confidence=float(payload.get("confidence", 0.0)),
                source_kind="Cached analysis",
                diagnostic=str(payload.get("diagnostic", "Cached chord analysis loaded")),
            )
            return result if result.usable else None
        except Exception:
            return None

    def save_cached(self, audio_path: Path, result: ChordAnalysis) -> None:
        stat = audio_path.stat()
        payload = {
            "cache_version": self.CACHE_VERSION,
            "audio_size": stat.st_size,
            "audio_mtime": int(stat.st_mtime),
            "beat_chords": list(result.beat_chords),
            "bar_chords": list(result.bar_chords),
            "confidence": result.confidence,
            "diagnostic": result.diagnostic,
        }
        self.cache_path_for(audio_path).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _decode_audio(self, audio_path: Path) -> np.ndarray:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory(prefix="banjofy_chords_") as temp_dir:
            wav_path = Path(temp_dir) / "chords.wav"
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(audio_path), "-vn", "-ac", "1",
                "-ar", str(self.SAMPLE_RATE), "-c:a", "pcm_s16le", str(wav_path),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=420,
            )
            if completed.returncode != 0 or not wav_path.exists():
                detail = completed.stderr.strip() or "FFmpeg did not create decoded audio"
                raise RuntimeError(f"FFmpeg decode failed: {detail}")

            with wave.open(str(wav_path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()

            if rate != self.SAMPLE_RATE or width != 2:
                raise RuntimeError("Unexpected decoded WAV format")

            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            samples /= 32768.0

        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak < 0.003:
            raise RuntimeError("Audio is silent or too quiet")
        return samples / peak

    def _frame_chroma(self, frame: np.ndarray) -> np.ndarray:
        window = np.hanning(len(frame)).astype(np.float32)
        spectrum = np.abs(np.fft.rfft(frame * window))
        frequencies = np.fft.rfftfreq(len(frame), d=1.0 / self.SAMPLE_RATE)

        valid = (frequencies >= 55.0) & (frequencies <= 5000.0)
        frequencies = frequencies[valid]
        spectrum = spectrum[valid]

        if spectrum.size == 0 or float(np.sum(spectrum)) <= 0:
            return np.zeros(12, dtype=np.float64)

        midi = 69.0 + 12.0 * np.log2(frequencies / 440.0)
        pitch_classes = np.mod(np.rint(midi).astype(int), 12)

        weights = np.sqrt(np.maximum(spectrum, 0.0))
        chroma = np.bincount(
            pitch_classes,
            weights=weights,
            minlength=12,
        ).astype(np.float64)
        total = float(np.sum(chroma))
        return chroma / total if total > 0 else chroma

    def _segment_chroma(self, samples: np.ndarray, start_ms: int, end_ms: int) -> np.ndarray:
        start = max(0, int(start_ms * self.SAMPLE_RATE / 1000))
        end = min(len(samples), int(end_ms * self.SAMPLE_RATE / 1000))
        if end - start < self.FRAME_SIZE:
            return np.zeros(12, dtype=np.float64)

        aggregate = np.zeros(12, dtype=np.float64)
        used = 0
        for pos in range(start, end - self.FRAME_SIZE + 1, self.HOP_SIZE):
            frame = samples[pos:pos + self.FRAME_SIZE]
            rms = float(np.sqrt(np.mean(frame * frame)))
            if rms < 0.01:
                continue
            aggregate += self._frame_chroma(frame)
            used += 1

        if used == 0 or float(np.sum(aggregate)) <= 0:
            return np.zeros(12, dtype=np.float64)
        aggregate /= float(np.sum(aggregate))
        return aggregate

    def _templates(self) -> list[tuple[str, np.ndarray]]:
        templates = []
        for root, name in enumerate(self.NOTE_NAMES):
            major = np.full(12, 0.03, dtype=np.float64)
            major[root] = 1.0
            major[(root + 4) % 12] = 0.78
            major[(root + 7) % 12] = 0.88
            major /= np.linalg.norm(major)
            templates.append((name, major))

            minor = np.full(12, 0.03, dtype=np.float64)
            minor[root] = 1.0
            minor[(root + 3) % 12] = 0.78
            minor[(root + 7) % 12] = 0.88
            minor /= np.linalg.norm(minor)
            templates.append((f"{name}m", minor))
        return templates

    def _classify(self, chroma: np.ndarray) -> tuple[str, float]:
        if float(np.sum(chroma)) <= 0:
            return "N", 0.0

        norm = np.linalg.norm(chroma)
        if norm <= 0:
            return "N", 0.0

        vector = chroma / norm
        scores = [(float(np.dot(vector, template)), name) for name, template in self._templates()]
        scores.sort(reverse=True)
        best_score, best_name = scores[0]
        second_score = scores[1][0]
        confidence = max(0.0, min(1.0, (best_score - second_score) / 0.20))

        if best_score < 0.52:
            return "N", confidence
        return best_name, confidence

    def _smooth(self, chords: list[str]) -> list[str]:
        if len(chords) < 3:
            return chords
        smoothed = chords[:]
        for index in range(1, len(chords) - 1):
            if chords[index - 1] == chords[index + 1] and chords[index] != chords[index - 1]:
                smoothed[index] = chords[index - 1]
        return smoothed

    def analyse(
        self,
        audio_path: Path,
        beat_times_ms: tuple[int, ...],
        beats_per_bar: int,
        progress: ProgressCallback | None = None,
    ) -> ChordAnalysis:
        cached = self.load_cached(audio_path)
        if cached is not None and len(cached.beat_chords) == len(beat_times_ms):
            if progress:
                progress("Loaded cached chord analysis")
            return cached

        if len(beat_times_ms) < 4:
            raise RuntimeError("Detected beat timeline is too short for chord analysis")

        if progress:
            progress("Decoding audio for chord analysis")
        samples = self._decode_audio(audio_path)

        if progress:
            progress("Estimating chords on detected beats")

        beat_chords: list[str] = []
        confidences: list[float] = []

        for index, start_ms in enumerate(beat_times_ms):
            if index + 1 < len(beat_times_ms):
                end_ms = beat_times_ms[index + 1]
            elif len(beat_times_ms) >= 2:
                end_ms = start_ms + (beat_times_ms[-1] - beat_times_ms[-2])
            else:
                end_ms = start_ms + 500

            chroma = self._segment_chroma(samples, start_ms, end_ms)
            chord, confidence = self._classify(chroma)
            beat_chords.append(chord)
            confidences.append(confidence)

        beat_chords = self._smooth(beat_chords)

        bar_chords: list[str] = []
        for start in range(0, len(beat_chords), beats_per_bar):
            group = [c for c in beat_chords[start:start + beats_per_bar] if c != "N"]
            if not group:
                bar_chords.append("N")
                continue
            counts = {}
            for chord in group:
                counts[chord] = counts.get(chord, 0) + 1
            bar_chords.append(max(counts, key=counts.get))

        result = ChordAnalysis(
            beat_chords=tuple(beat_chords),
            bar_chords=tuple(bar_chords),
            confidence=float(np.mean(confidences)) if confidences else 0.0,
            source_kind="Fresh analysis",
            diagnostic=(
                f"{len(beat_chords)} beat chords and {len(bar_chords)} bar chords estimated"
            ),
        )
        self.save_cached(audio_path, result)
        if progress:
            progress("Neutral chord analysis complete")
        return result
