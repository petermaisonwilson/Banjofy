from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess
import tempfile
import wave
from typing import Callable

import imageio_ffmpeg
import numpy as np
from scipy.signal import find_peaks

from banjofy.storage.paths import get_library_path


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class TimingAnalysis:
    beat_times_ms: tuple[int, ...]
    downbeat_indices: tuple[int, ...]
    estimated_bpm: float
    first_downbeat_ms: int
    confidence: float
    source_audio: str
    meter_numerator: int
    meter_denominator: int
    source_kind: str
    diagnostic: str

    @property
    def usable(self) -> bool:
        return len(self.beat_times_ms) >= 8 and self.estimated_bpm > 0


class TimingAnalyzer:
    CACHE_VERSION = 2
    SAMPLE_RATE = 22050
    HOP_SIZE = 512
    FRAME_SIZE = 2048
    MIN_BPM = 55.0
    MAX_BPM = 210.0

    def _cache_folder(self) -> Path:
        library = get_library_path()
        if library is None:
            raise RuntimeError("Library folder is not configured")
        folder = Path(library) / "timing"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def cache_path_for(self, audio_path: Path) -> Path:
        safe = "".join(
            char if char.isalnum() or char in "._-" else "_"
            for char in audio_path.stem
        )[:120]
        return self._cache_folder() / f"{safe}.timing.json"

    def delete_cache(self, audio_path: Path) -> None:
        path = self.cache_path_for(audio_path)
        if path.exists():
            path.unlink()

    def load_cached(self, audio_path: Path) -> TimingAnalysis | None:
        cache = self.cache_path_for(audio_path)
        if not cache.exists():
            return None
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            stat = audio_path.stat()
            if payload.get("cache_version") != self.CACHE_VERSION:
                return None
            if payload.get("audio_size") != stat.st_size:
                return None
            if int(payload.get("audio_mtime", 0)) != int(stat.st_mtime):
                return None
            result = TimingAnalysis(
                beat_times_ms=tuple(int(v) for v in payload["beat_times_ms"]),
                downbeat_indices=tuple(int(v) for v in payload["downbeat_indices"]),
                estimated_bpm=float(payload["estimated_bpm"]),
                first_downbeat_ms=int(payload["first_downbeat_ms"]),
                confidence=float(payload.get("confidence", 0.0)),
                source_audio=str(audio_path),
                meter_numerator=int(payload.get("meter_override", payload.get("meter_numerator", 4))),
                meter_denominator=int(payload.get("meter_denominator", 4)),
                source_kind="Cached analysis",
                diagnostic=str(payload.get("diagnostic", "Cached timing loaded")),
            )
            return result if result.usable else None
        except Exception:
            return None

    def save_cached(self, audio_path: Path, result: TimingAnalysis) -> Path:
        stat = audio_path.stat()
        payload = {
            "cache_version": self.CACHE_VERSION,
            "audio_size": stat.st_size,
            "audio_mtime": int(stat.st_mtime),
            "beat_times_ms": list(result.beat_times_ms),
            "downbeat_indices": list(result.downbeat_indices),
            "estimated_bpm": result.estimated_bpm,
            "first_downbeat_ms": result.first_downbeat_ms,
            "confidence": result.confidence,
            "meter_numerator": result.meter_numerator,
            "meter_denominator": result.meter_denominator,
            "diagnostic": result.diagnostic,
        }
        path = self.cache_path_for(audio_path)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _decode_audio(self, audio_path: Path) -> np.ndarray:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory(prefix="banjofy_timing_") as temp_dir:
            wav_path = Path(temp_dir) / "timing.wav"
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
                width = wav_file.getsampwidth()
                rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
            if width != 2:
                raise RuntimeError("Decoded audio was not 16-bit PCM")
            if rate != self.SAMPLE_RATE:
                raise RuntimeError(f"Unexpected decoded sample rate: {rate}")
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)
            samples /= 32768.0
        if samples.size < self.SAMPLE_RATE * 8:
            raise RuntimeError("Audio is shorter than eight seconds")
        peak = float(np.max(np.abs(samples)))
        if peak < 0.003:
            raise RuntimeError("Audio is silent or too quiet")
        return samples / peak

    def _onset_envelope(self, samples: np.ndarray) -> np.ndarray:
        usable = 1 + (len(samples) - self.FRAME_SIZE) // self.HOP_SIZE
        if usable < 100:
            raise RuntimeError("Not enough audio frames for timing analysis")
        window = np.hanning(self.FRAME_SIZE).astype(np.float32)
        onset = np.zeros(usable, dtype=np.float32)
        previous = None
        for index in range(usable):
            start = index * self.HOP_SIZE
            spectrum = np.abs(np.fft.rfft(
                samples[start:start + self.FRAME_SIZE] * window
            ))
            spectrum = np.log1p(spectrum)
            if previous is not None:
                flux = spectrum - previous
                flux[flux < 0] = 0
                onset[index] = float(np.sum(flux))
            previous = spectrum
        radius = 16
        padded = np.pad(onset, (radius, radius), mode="edge")
        kernel = np.ones(radius * 2 + 1, dtype=np.float32) / (radius * 2 + 1)
        local_mean = np.convolve(padded, kernel, mode="valid")
        centred = onset - local_mean
        centred[centred < 0] = 0
        std = float(np.std(centred))
        if std < 1e-6:
            raise RuntimeError("No reliable onset pattern was found")
        return centred / std

    def _estimate_tempo(self, onset: np.ndarray) -> tuple[float, float]:
        envelope_rate = self.SAMPLE_RATE / self.HOP_SIZE
        min_lag = max(1, int(envelope_rate * 60.0 / self.MAX_BPM))
        max_lag = min(len(onset) - 2, int(envelope_rate * 60.0 / self.MIN_BPM))
        if max_lag <= min_lag:
            raise RuntimeError("Audio window was too short for tempo estimation")
        autocorr = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
        search = autocorr[min_lag:max_lag + 1].astype(np.float64)
        lags = np.arange(min_lag, max_lag + 1, dtype=np.float64)
        bpms = 60.0 * envelope_rate / lags
        preference = np.exp(-0.5 * (np.log2(bpms / 110.0) / 0.95) ** 2)
        scores = search * (0.78 + 0.22 * preference)
        best = int(np.argmax(scores))
        positive = scores[scores > 0]
        if positive.size == 0:
            raise RuntimeError("Tempo autocorrelation had no positive peak")
        bpm = float(bpms[best])
        median = float(np.median(positive))
        confidence = max(
            0.0,
            min(1.0, (float(scores[best]) / (median + 1e-9) - 1.0) / 8.0),
        )
        return bpm, confidence

    def _track_beats(self, onset: np.ndarray, bpm: float) -> tuple[np.ndarray, np.ndarray]:
        envelope_rate = self.SAMPLE_RATE / self.HOP_SIZE
        expected = envelope_rate * 60.0 / bpm
        peaks, _ = find_peaks(
            onset,
            distance=max(1, int(round(expected * 0.55))),
            prominence=max(0.15, float(np.std(onset)) * 0.20),
        )
        if peaks.size < 8:
            raise RuntimeError(f"Only {peaks.size} onset peaks were found")
        strengths = onset[peaks]
        anchor = int(peaks[int(np.argmax(strengths[: min(len(strengths), 80)]))])
        beats = [anchor]
        current = float(anchor)
        while True:
            target = current + expected
            if target >= len(onset):
                break
            window = max(2, int(round(expected * 0.30)))
            candidates = peaks[
                (peaks >= max(0, int(round(target - window))))
                & (peaks < min(len(onset), int(round(target + window + 1))))
            ]
            if candidates.size:
                score = onset[candidates] - 0.35 * (
                    np.abs(candidates - target) / max(1.0, window)
                )
                chosen = int(candidates[int(np.argmax(score))])
            else:
                chosen = int(round(target))
            if chosen <= beats[-1]:
                chosen = beats[-1] + max(1, int(round(expected)))
            beats.append(chosen)
            current = float(chosen)
        backwards = []
        current = float(anchor)
        while True:
            target = current - expected
            if target < 0:
                break
            window = max(2, int(round(expected * 0.30)))
            candidates = peaks[
                (peaks >= max(0, int(round(target - window))))
                & (peaks < min(len(onset), int(round(target + window + 1))))
            ]
            if candidates.size:
                score = onset[candidates] - 0.35 * (
                    np.abs(candidates - target) / max(1.0, window)
                )
                chosen = int(candidates[int(np.argmax(score))])
            else:
                chosen = int(round(target))
            backwards.append(chosen)
            current = float(chosen)
        all_beats = np.unique(np.asarray(list(reversed(backwards)) + beats, dtype=int))
        if all_beats.size < 8:
            raise RuntimeError("Beat tracking produced too few beats")
        return all_beats, onset[np.clip(all_beats, 0, len(onset) - 1)]

    def _estimate_meter_and_phase(self, strengths: np.ndarray) -> tuple[int, int, float]:
        values = np.asarray(strengths, dtype=np.float64)
        values = (values - values.mean()) / (values.std() + 1e-9)
        best = (-math.inf, 4, 0)
        second = -math.inf
        for meter in (3, 4):
            complete = (len(values) // meter) * meter
            if complete < meter * 4:
                continue
            matrix = values[:complete].reshape(-1, meter)
            for phase in range(meter):
                down = matrix[:, phase]
                others = np.delete(matrix, phase, axis=1)
                score = float(np.mean(down) - 0.35 * np.mean(others))
                if meter == 4:
                    score += 0.05
                if score > best[0]:
                    second = best[0]
                    best = (score, meter, phase)
                elif score > second:
                    second = score
        confidence = max(0.0, min(1.0, (best[0] - second) / 1.5))

        # Conservative beginner-friendly rule:
        # choose 3/4 only when it clearly wins; uncertain material defaults to 4/4.
        meter, phase = best[1], best[2]
        if meter == 3 and confidence < 0.12:
            meter = 4
            phase = 0

        return meter, phase, confidence

    def save_meter_override(self, audio_path: Path, meter_numerator: int) -> None:
        if meter_numerator not in (3, 4):
            raise ValueError("Meter override must be 3 or 4")

        cache = self.cache_path_for(audio_path)
        payload = {}
        if cache.exists():
            try:
                payload = json.loads(cache.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        payload["meter_override"] = int(meter_numerator)
        payload.setdefault("cache_version", self.CACHE_VERSION)
        payload.setdefault("audio_size", audio_path.stat().st_size)
        payload.setdefault("audio_mtime", int(audio_path.stat().st_mtime))
        cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def clear_meter_override(self, audio_path: Path) -> None:
        cache = self.cache_path_for(audio_path)
        if not cache.exists():
            return
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            return
        payload.pop("meter_override", None)
        cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def analyse(self, audio_path: Path, progress: ProgressCallback | None = None) -> TimingAnalysis:
        cached = self.load_cached(audio_path)
        if cached is not None:
            if progress:
                progress("Loaded cached timing")
            return cached
        if progress:
            progress("Decoding audio with FFmpeg")
        samples = self._decode_audio(audio_path)
        if progress:
            progress("Calculating onset strength")
        onset = self._onset_envelope(samples)
        if progress:
            progress("Estimating tempo")
        bpm, tempo_confidence = self._estimate_tempo(onset)
        if progress:
            progress("Tracking individual beats")
        beat_frames, strengths = self._track_beats(onset, bpm)
        if progress:
            progress("Detecting metre and downbeat phase")
        meter, phase, meter_confidence = self._estimate_meter_and_phase(strengths)
        aligned = beat_frames[phase:]
        if aligned.size < 8:
            raise RuntimeError("Metre alignment left too few usable beats")
        beat_times_ms = tuple(
            int(round(frame * self.HOP_SIZE * 1000.0 / self.SAMPLE_RATE))
            for frame in aligned
        )
        result = TimingAnalysis(
            beat_times_ms=beat_times_ms,
            downbeat_indices=tuple(range(0, len(beat_times_ms), meter)),
            estimated_bpm=bpm,
            first_downbeat_ms=beat_times_ms[0],
            confidence=max(
                0.0,
                min(1.0, 0.55 * tempo_confidence + 0.45 * meter_confidence),
            ),
            source_audio=str(audio_path),
            meter_numerator=meter,
            meter_denominator=4,
            source_kind="Fresh analysis",
            diagnostic=(
                f"FFmpeg decode OK; {len(beat_times_ms)} beats tracked; "
                f"meter {meter}/4; tempo {bpm:.1f} BPM"
            ),
        )
        self.save_cached(audio_path, result)
        if progress:
            progress("Automatic timing complete")
        return result
