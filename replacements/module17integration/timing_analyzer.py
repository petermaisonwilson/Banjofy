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
import librosa
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
    beat_strengths: tuple[float, ...] = ()

    @property
    def usable(self) -> bool:
        return (
            len(self.beat_times_ms) >= 8
            and self.estimated_bpm > 0
            and self.meter_numerator in (3, 4)
        )


class TimingAnalyzer:
    CACHE_VERSION = 6
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
            meter = int(payload.get("meter_override", payload["meter_numerator"]))
            result = TimingAnalysis(
                beat_times_ms=tuple(int(v) for v in payload["beat_times_ms"]),
                downbeat_indices=tuple(int(v) for v in payload["downbeat_indices"]),
                estimated_bpm=float(payload["estimated_bpm"]),
                first_downbeat_ms=int(payload["first_downbeat_ms"]),
                confidence=float(payload.get("confidence", 0.0)),
                source_audio=str(audio_path),
                meter_numerator=meter if meter in (3, 4) else 4,
                meter_denominator=4,
                source_kind="Cached analysis",
                diagnostic=str(payload.get("diagnostic", "Cached timing loaded")),
                beat_strengths=tuple(float(v) for v in payload.get("beat_strengths", [])),
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
            "meter_denominator": 4,
            "diagnostic": result.diagnostic,
            "beat_strengths": list(result.beat_strengths),
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
            if width != 2 or rate != self.SAMPLE_RATE:
                raise RuntimeError("Decoded audio format was not the expected PCM format")
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
        onset = librosa.onset.onset_strength(
            y=samples,
            sr=self.SAMPLE_RATE,
            hop_length=self.HOP_SIZE,
            aggregate=np.median,
        ).astype(np.float32)
        if onset.size < 100 or float(np.std(onset)) < 1e-6:
            raise RuntimeError("No reliable onset pattern was found")
        onset -= float(np.median(onset))
        onset[onset < 0] = 0
        scale = float(np.std(onset))
        return onset / max(scale, 1e-6)

    def _estimate_tempo(self, onset: np.ndarray) -> tuple[float, float]:
        tempo = librosa.feature.tempo(
            onset_envelope=onset,
            sr=self.SAMPLE_RATE,
            hop_length=self.HOP_SIZE,
            aggregate=np.median,
        )
        bpm = float(np.atleast_1d(tempo)[0])
        while bpm < self.MIN_BPM:
            bpm *= 2.0
        while bpm > self.MAX_BPM:
            bpm /= 2.0
        if not math.isfinite(bpm) or bpm <= 0:
            raise RuntimeError("Tempo estimation did not return a usable value")

        frame_rate = self.SAMPLE_RATE / self.HOP_SIZE
        lag = max(1, int(round(frame_rate * 60.0 / bpm)))
        corr = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
        peak = float(corr[lag]) if lag < len(corr) else 0.0
        baseline = float(np.median(corr[1:])) if len(corr) > 2 else 0.0
        confidence = max(0.0, min(1.0, (peak / (baseline + 1e-9) - 1.0) / 8.0))
        return bpm, confidence

    def _track_beats(self, onset: np.ndarray, bpm: float) -> np.ndarray:
        _, beats = librosa.beat.beat_track(
            onset_envelope=onset,
            sr=self.SAMPLE_RATE,
            hop_length=self.HOP_SIZE,
            bpm=bpm,
            tightness=90,
            trim=False,
        )
        beats = np.asarray(beats, dtype=int)
        beats = beats[(beats >= 0) & (beats < len(onset))]
        beats = np.unique(beats)
        if beats.size < 8:
            raise RuntimeError(f"Beat tracking produced only {beats.size} beats")
        return beats

    @staticmethod
    def _normalise(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=np.float64)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median))) + 1e-9
        return np.clip((values - median) / (1.4826 * mad), -3.0, 3.0)

    def _beat_accents(
        self,
        samples: np.ndarray,
        onset: np.ndarray,
        beat_frames: np.ndarray,
    ) -> np.ndarray:
        onset_values = onset[np.clip(beat_frames, 0, len(onset) - 1)]
        half = int(round(self.SAMPLE_RATE * 0.09))
        rms_values = []
        bass_values = []
        window = np.hanning(max(32, half * 2)).astype(np.float32)

        for frame in beat_frames:
            centre = int(frame * self.HOP_SIZE)
            start = max(0, centre - half)
            stop = min(len(samples), centre + half)
            clip = samples[start:stop]
            if clip.size < 32:
                rms_values.append(0.0)
                bass_values.append(0.0)
                continue
            rms_values.append(float(np.sqrt(np.mean(clip * clip))))
            padded = np.zeros(len(window), dtype=np.float32)
            padded[: min(len(clip), len(padded))] = clip[: len(padded)]
            spectrum = np.abs(np.fft.rfft(padded * window))
            freqs = np.fft.rfftfreq(len(padded), 1.0 / self.SAMPLE_RATE)
            bass_values.append(float(np.sum(spectrum[(freqs >= 45) & (freqs <= 260)])))

        accent = (
            0.45 * self._normalise(onset_values)
            + 0.35 * self._normalise(np.asarray(bass_values))
            + 0.20 * self._normalise(np.asarray(rms_values))
        )
        return accent.astype(np.float64)

    def _score_meter_phase(
        self,
        accents: np.ndarray,
        meter: int,
        phase: int,
    ) -> float:
        shifted = accents[phase:]
        complete = (len(shifted) // meter) * meter
        if complete < meter * 6:
            return -math.inf
        bars = shifted[:complete].reshape(-1, meter)
        position_medians = np.median(bars, axis=0)
        position_means = np.mean(bars, axis=0)

        if meter == 3:
            template = np.asarray([1.0, -0.45, -0.25])
        else:
            template = np.asarray([1.0, -0.45, 0.25, -0.45])

        template -= template.mean()
        profile = 0.65 * position_medians + 0.35 * position_means
        profile -= profile.mean()
        correlation = float(
            np.dot(profile, template)
            / ((np.linalg.norm(profile) * np.linalg.norm(template)) + 1e-9)
        )
        downbeat_margin = float(profile[0] - np.mean(profile[1:]))
        bar_consistency = float(
            np.mean(bars[:, 0] > np.median(bars[:, 1:], axis=1))
        )
        return 0.55 * correlation + 0.30 * downbeat_margin + 0.15 * bar_consistency

    def _estimate_meter_and_phase(
        self,
        accents: np.ndarray,
        forced_meter: int | None = None,
    ) -> tuple[int, int, float]:
        candidates = []
        meters = (forced_meter,) if forced_meter in (3, 4) else (3, 4)
        for meter in meters:
            for phase in range(meter):
                score = self._score_meter_phase(accents, meter, phase)
                if math.isfinite(score):
                    candidates.append((score, meter, phase))
        if not candidates:
            return (forced_meter or 4), 0, 0.0

        candidates.sort(reverse=True)
        best = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else best[0] - 0.5
        margin = best[0] - second_score
        confidence = max(0.0, min(1.0, 0.25 + margin / 1.2))

        # Automatic 3/4 is accepted only when it wins positively. This removes
        # the former built-in 4/4 preference while still avoiding weak guesses.
        meter, phase = best[1], best[2]
        if forced_meter is None and best[0] < 0.18:
            meter, phase, confidence = 4, 0, min(confidence, 0.20)
        return meter, phase, confidence

    def save_meter_override(
        self,
        audio_path: Path,
        meter_numerator: int,
        current_result: TimingAnalysis,
    ) -> TimingAnalysis:
        if meter_numerator not in (3, 4):
            raise ValueError("Meter override must be 3 or 4")

        strengths = np.asarray(current_result.beat_strengths, dtype=np.float64)
        phase = 0
        if strengths.size == len(current_result.beat_times_ms):
            _, phase, _ = self._estimate_meter_and_phase(
                strengths,
                forced_meter=meter_numerator,
            )

        times = current_result.beat_times_ms[phase:]
        aligned_strengths = current_result.beat_strengths[phase:]
        if len(times) < 8:
            times = current_result.beat_times_ms
            aligned_strengths = current_result.beat_strengths
            phase = 0

        updated = TimingAnalysis(
            beat_times_ms=tuple(times),
            downbeat_indices=tuple(range(0, len(times), meter_numerator)),
            estimated_bpm=current_result.estimated_bpm,
            first_downbeat_ms=int(times[0]),
            confidence=current_result.confidence,
            source_audio=current_result.source_audio,
            meter_numerator=meter_numerator,
            meter_denominator=4,
            source_kind="Manual meter correction",
            diagnostic=(
                f"User selected {meter_numerator}/4; strongest downbeat phase {phase}"
            ),
            beat_strengths=tuple(aligned_strengths),
        )
        self.save_cached(audio_path, updated)
        cache = self.cache_path_for(audio_path)
        payload = json.loads(cache.read_text(encoding="utf-8"))
        payload["meter_override"] = meter_numerator
        cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return updated

    def clear_meter_override(self, audio_path: Path) -> None:
        cache = self.cache_path_for(audio_path)
        if cache.exists():
            cache.unlink()

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
            progress("Calculating onset and bass accents")
        onset = self._onset_envelope(samples)
        if progress:
            progress("Estimating tempo")
        bpm, tempo_confidence = self._estimate_tempo(onset)
        if progress:
            progress("Tracking individual beats")
        beat_frames = self._track_beats(onset, bpm)
        accents = self._beat_accents(samples, onset, beat_frames)
        if progress:
            progress("Detecting 3/4 or 4/4 and locating Beat 1")
        meter, phase, meter_confidence = self._estimate_meter_and_phase(accents)

        aligned_frames = beat_frames[phase:]
        aligned_accents = accents[phase:]
        if aligned_frames.size < 8:
            raise RuntimeError("Meter alignment left too few usable beats")

        beat_times_ms = tuple(
            int(round(frame * self.HOP_SIZE * 1000.0 / self.SAMPLE_RATE))
            for frame in aligned_frames
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
                f"FFmpeg decode OK; librosa tracked {len(beat_times_ms)} beats; "
                f"meter {meter}/4; Beat 1 phase {phase}; tempo {bpm:.1f} BPM"
            ),
            beat_strengths=tuple(float(v) for v in aligned_accents),
        )
        self.save_cached(audio_path, result)
        if progress:
            progress("Automatic timing complete")
        return result


def run_internal_timing_audit() -> list[str]:
    analyzer = TimingAnalyzer()

    three = np.tile(np.asarray([2.8, -0.8, -0.3]), 24)
    meter, phase, confidence = analyzer._estimate_meter_and_phase(three)
    assert meter == 3 and phase == 0 and confidence > 0

    four = np.tile(np.asarray([2.8, -0.8, 0.7, -0.7]), 24)
    meter, phase, confidence = analyzer._estimate_meter_and_phase(four)
    assert meter == 4 and phase == 0 and confidence > 0

    shifted_three = np.concatenate([np.asarray([-0.4]), three])
    meter, phase, _ = analyzer._estimate_meter_and_phase(shifted_three)
    assert meter == 3 and phase == 1

    return [
        "Synthetic 3/4 detection passed",
        "Synthetic 4/4 detection passed",
        "Synthetic downbeat phase alignment passed",
    ]
