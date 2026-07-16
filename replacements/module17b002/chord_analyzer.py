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
    tonal_center: str
    mode: str

    @property
    def usable(self) -> bool:
        return (
            len(self.beat_chords) >= 4
            and any(chord not in ("N", "") for chord in self.beat_chords)
        )


class ChordAnalyzer:
    """Neutral, conservative chord analysis aligned to detected beat timestamps."""

    CACHE_VERSION = 2
    SAMPLE_RATE = 22050
    FRAME_SIZE = 8192
    HOP_SIZE = 2048

    NOTE_NAMES = (
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B",
    )

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
                tonal_center=str(payload.get("tonal_center", "Not detected")),
                mode=str(payload.get("mode", "Uncertain")),
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
            "tonal_center": result.tonal_center,
            "mode": result.mode,
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

        valid = (frequencies >= 55.0) & (frequencies <= 3500.0)
        frequencies = frequencies[valid]
        spectrum = spectrum[valid]

        if spectrum.size == 0 or float(np.sum(spectrum)) <= 0:
            return np.zeros(12, dtype=np.float64)

        midi = 69.0 + 12.0 * np.log2(frequencies / 440.0)
        pitch_classes = np.mod(np.rint(midi).astype(int), 12)

        # Compress loud harmonics so distorted guitar does not dominate.
        weights = np.power(np.maximum(spectrum, 0.0), 0.35)
        chroma = np.bincount(
            pitch_classes,
            weights=weights,
            minlength=12,
        ).astype(np.float64)
        total = float(np.sum(chroma))
        return chroma / total if total > 0 else chroma

    def _segment_chroma(
        self,
        samples: np.ndarray,
        start_ms: int,
        end_ms: int,
    ) -> np.ndarray:
        start = max(0, int(start_ms * self.SAMPLE_RATE / 1000))
        end = min(len(samples), int(end_ms * self.SAMPLE_RATE / 1000))
        if end - start < self.FRAME_SIZE:
            return np.zeros(12, dtype=np.float64)

        aggregate = np.zeros(12, dtype=np.float64)
        used = 0
        for pos in range(start, end - self.FRAME_SIZE + 1, self.HOP_SIZE):
            frame = samples[pos:pos + self.FRAME_SIZE]
            rms = float(np.sqrt(np.mean(frame * frame)))
            if rms < 0.008:
                continue
            aggregate += self._frame_chroma(frame)
            used += 1

        if used == 0 or float(np.sum(aggregate)) <= 0:
            return np.zeros(12, dtype=np.float64)
        aggregate /= float(np.sum(aggregate))
        return aggregate

    def _global_chroma(self, samples: np.ndarray) -> np.ndarray:
        # Sample the complete recording in broad windows.
        duration_ms = int(len(samples) * 1000 / self.SAMPLE_RATE)
        aggregate = np.zeros(12, dtype=np.float64)
        used = 0
        window_ms = 4000
        step_ms = 2000
        for start_ms in range(0, max(1, duration_ms - window_ms), step_ms):
            chroma = self._segment_chroma(samples, start_ms, start_ms + window_ms)
            if float(chroma.sum()) > 0:
                aggregate += chroma
                used += 1
        if used == 0:
            return aggregate
        aggregate /= aggregate.sum()
        return aggregate

    def _detect_tonal_center(self, chroma: np.ndarray) -> tuple[int, str, float]:
        if float(chroma.sum()) <= 0:
            return 0, "Uncertain", 0.0

        scores = []
        for root in range(12):
            tonic = chroma[root]
            fifth = chroma[(root + 7) % 12]
            major_third = chroma[(root + 4) % 12]
            minor_third = chroma[(root + 3) % 12]
            flat_seventh = chroma[(root + 10) % 12]
            major_seventh = chroma[(root + 11) % 12]

            centre = (
                1.35 * tonic
                + 0.90 * fifth
                + 0.35 * max(major_third, minor_third)
                + 0.20 * flat_seventh
            )
            scores.append((centre, root))

        scores.sort(reverse=True)
        best_score, root = scores[0]
        second_score = scores[1][0]
        confidence = max(
            0.0,
            min(1.0, (best_score - second_score) / max(0.01, best_score)),
        )

        major_third = chroma[(root + 4) % 12]
        minor_third = chroma[(root + 3) % 12]
        flat_seventh = chroma[(root + 10) % 12]
        major_seventh = chroma[(root + 11) % 12]

        if max(major_third, minor_third) < 0.75 * chroma[root]:
            mode = "Power/ambiguous"
        elif major_third > minor_third * 1.08:
            mode = "Mixolydian" if flat_seventh > major_seventh * 1.08 else "Major"
        elif minor_third > major_third * 1.08:
            mode = "Dorian" if chroma[(root + 9) % 12] > chroma[(root + 8) % 12] else "Minor"
        else:
            mode = "Power/ambiguous"

        return root, mode, confidence

    def _templates(self) -> list[tuple[str, int, str, np.ndarray]]:
        templates = []
        for root, name in enumerate(self.NOTE_NAMES):
            major = np.full(12, 0.015, dtype=np.float64)
            major[root] = 1.00
            major[(root + 4) % 12] = 0.68
            major[(root + 7) % 12] = 0.88
            major /= np.linalg.norm(major)
            templates.append((name, root, "major", major))

            minor = np.full(12, 0.015, dtype=np.float64)
            minor[root] = 1.00
            minor[(root + 3) % 12] = 0.68
            minor[(root + 7) % 12] = 0.88
            minor /= np.linalg.norm(minor)
            templates.append((f"{name}m", root, "minor", minor))

            power = np.full(12, 0.01, dtype=np.float64)
            power[root] = 1.00
            power[(root + 7) % 12] = 0.92
            power /= np.linalg.norm(power)
            templates.append((name, root, "power", power))
        return templates

    def _compatible_roots(self, tonic: int, mode: str) -> set[int]:
        if mode in ("Major", "Mixolydian", "Power/ambiguous"):
            # I, bVII, IV, V, vi, ii are common in rock/major contexts.
            return {
                tonic,
                (tonic + 10) % 12,
                (tonic + 5) % 12,
                (tonic + 7) % 12,
                (tonic + 9) % 12,
                (tonic + 2) % 12,
            }
        return {
            tonic,
            (tonic + 3) % 12,
            (tonic + 5) % 12,
            (tonic + 7) % 12,
            (tonic + 8) % 12,
            (tonic + 10) % 12,
        }

    def _rank_chords(
        self,
        chroma: np.ndarray,
        tonic: int,
        mode: str,
    ) -> list[tuple[float, str]]:
        if float(np.sum(chroma)) <= 0:
            return []

        norm = np.linalg.norm(chroma)
        if norm <= 0:
            return []

        vector = chroma / norm
        compatible = self._compatible_roots(tonic, mode)
        ranked = []
        for name, root, quality, template in self._templates():
            score = float(np.dot(vector, template))

            if root in compatible:
                score += 0.035
            else:
                score -= 0.045

            if root == tonic:
                score += 0.025

            # Rock and ambiguous material should not be forced into minor.
            if mode in ("Power/ambiguous", "Mixolydian") and quality == "minor":
                score -= 0.035
            if mode == "Minor" and quality == "major" and root == tonic:
                score -= 0.035

            ranked.append((score, name))

        ranked.sort(reverse=True)
        return ranked

    def _classify(
        self,
        chroma: np.ndarray,
        tonic: int,
        mode: str,
    ) -> tuple[str, float, float]:
        ranked = self._rank_chords(chroma, tonic, mode)
        if len(ranked) < 2:
            return "N", 0.0, 0.0

        best_score, best_name = ranked[0]
        second_score = ranked[1][0]
        margin = best_score - second_score
        confidence = max(0.0, min(1.0, margin / 0.12))

        if best_score < 0.60 or margin < 0.018:
            return "N", confidence, best_score
        return best_name, confidence, best_score

    def _stabilise(
        self,
        raw_chords: list[str],
        confidences: list[float],
        beats_per_bar: int,
    ) -> list[str]:
        if not raw_chords:
            return []

        # Fill uncertain beats from nearby stable evidence rather than inventing.
        filled = raw_chords[:]
        for i, chord in enumerate(filled):
            if chord != "N":
                continue
            left = filled[i - 1] if i > 0 else "N"
            right = filled[i + 1] if i + 1 < len(filled) else "N"
            if left != "N" and left == right:
                filled[i] = left
            elif left != "N" and confidences[i] < 0.35:
                filled[i] = left

        # Remove one-beat and weak two-beat excursions.
        stable = filled[:]
        index = 0
        while index < len(stable):
            chord = stable[index]
            end = index + 1
            while end < len(stable) and stable[end] == chord:
                end += 1
            run_length = end - index
            previous = stable[index - 1] if index > 0 else None
            following = stable[end] if end < len(stable) else None
            run_conf = float(np.mean(confidences[index:end])) if end > index else 0.0

            if chord == "N" and previous:
                for pos in range(index, end):
                    stable[pos] = previous
            elif run_length == 1 and previous and following == previous:
                stable[index] = previous
            elif run_length < 2 and previous and run_conf < 0.62:
                stable[index] = previous
            elif run_length == 2 and previous and following == previous and run_conf < 0.48:
                for pos in range(index, end):
                    stable[pos] = previous
            index = end

        # Hysteresis: a change must persist for two beats, unless it starts a bar
        # and has strong evidence.
        output = stable[:]
        current = next((c for c in stable if c != "N"), "N")
        for i in range(len(stable)):
            candidate = stable[i]
            if candidate == "N":
                output[i] = current
                continue
            if candidate == current:
                output[i] = current
                continue

            persists = (
                i + 1 < len(stable)
                and stable[i + 1] == candidate
            )
            strong_bar_change = (
                i % max(1, beats_per_bar) == 0
                and confidences[i] >= 0.68
            )
            if persists or strong_bar_change:
                current = candidate
            output[i] = current

        return output

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
            progress("Decoding audio for tonal and chord analysis")
        samples = self._decode_audio(audio_path)

        if progress:
            progress("Detecting tonal centre and mode")
        global_chroma = self._global_chroma(samples)
        tonic, mode, key_confidence = self._detect_tonal_center(global_chroma)
        tonal_center = self.NOTE_NAMES[tonic]

        if progress:
            progress("Estimating stable chords across detected beats")

        raw_chords: list[str] = []
        confidences: list[float] = []

        for index, beat_ms in enumerate(beat_times_ms):
            previous_ms = (
                beat_times_ms[index - 1]
                if index > 0
                else max(0, beat_ms - 500)
            )
            next_ms = (
                beat_times_ms[index + 1]
                if index + 1 < len(beat_times_ms)
                else beat_ms + max(300, beat_ms - previous_ms)
            )

            # Use a wider centre-weighted window spanning roughly two beats.
            start_ms = max(0, int((previous_ms + beat_ms) / 2))
            end_ms = int(next_ms + max(100, (next_ms - beat_ms) * 0.45))

            chroma = self._segment_chroma(samples, start_ms, end_ms)
            chord, confidence, _ = self._classify(chroma, tonic, mode)
            raw_chords.append(chord)
            confidences.append(confidence)

        beat_chords = self._stabilise(raw_chords, confidences, beats_per_bar)

        bar_chords: list[str] = []
        for start in range(0, len(beat_chords), beats_per_bar):
            group = [c for c in beat_chords[start:start + beats_per_bar] if c != "N"]
            if not group:
                bar_chords.append("N")
                continue
            counts: dict[str, int] = {}
            for chord in group:
                counts[chord] = counts.get(chord, 0) + 1
            bar_chords.append(max(counts, key=counts.get))

        changes = 0
        previous = None
        for chord in beat_chords:
            if chord != previous:
                changes += 1
                previous = chord

        combined_confidence = (
            0.70 * (float(np.mean(confidences)) if confidences else 0.0)
            + 0.30 * key_confidence
        )

        result = ChordAnalysis(
            beat_chords=tuple(beat_chords),
            bar_chords=tuple(bar_chords),
            confidence=combined_confidence,
            source_kind="Fresh analysis",
            diagnostic=(
                f"{len(beat_chords)} beats analysed; {changes} stable chord events"
            ),
            tonal_center=tonal_center,
            mode=mode,
        )
        self.save_cached(audio_path, result)
        if progress:
            progress("Stable neutral chord analysis complete")
        return result
