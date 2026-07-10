from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
import re
import subprocess
import tempfile
import wave

import imageio_ffmpeg
import numpy as np

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
    note: str = "BPM detected from audio. Key and chords are not audio-detected yet."


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:140] or "analysis"


class AnalysisManager:
    """Analyses downloaded audio and creates the saved Banjofy analysis record."""

    DEFAULT_BPM = 92
    MIN_BPM = 60
    MAX_BPM = 190
    SAMPLE_RATE = 22050
    ANALYSIS_SECONDS = 180

    def analyse(self, audio: DownloadedAudio) -> AnalysisResult:
        if not audio or not audio.file_path:
            raise ValueError("No downloaded audio to analyse")

        bpm, bpm_note = self._detect_bpm(Path(audio.file_path))
        estimated_bars = self._estimate_bars(audio.duration, bpm)

        # Chords remain provisional until a later real chord-recognition module.
        provisional = ["G", "C", "G", "D"]
        chords_by_bar = [
            provisional[i % len(provisional)]
            for i in range(max(1, estimated_bars))
        ]

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
            note=bpm_note + " Key and chords are not audio-detected yet.",
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

    def _detect_bpm(self, audio_path: Path) -> tuple[int, str]:
        """Decode audio with bundled FFmpeg and estimate tempo from onset periodicity.

        This is genuine audio-derived BPM detection. It deliberately falls back to
        the previous safe value when the file is silent, too short, or undecodable.
        """
        if not audio_path.exists():
            return self.DEFAULT_BPM, "BPM fallback used because the audio file was missing."

        try:
            samples = self._decode_audio(audio_path)
            detected, confidence = self._tempo_from_samples(samples, self.SAMPLE_RATE)
            if detected is None:
                return self.DEFAULT_BPM, "BPM fallback used because no reliable beat pulse was found."

            return detected, f"BPM detected from audio ({confidence:.0%} confidence)."
        except Exception as exc:
            message = str(exc).strip().replace("\n", " ")
            if len(message) > 120:
                message = message[:117] + "..."
            return self.DEFAULT_BPM, f"BPM fallback used because audio decoding failed: {message}"

    def _decode_audio(self, audio_path: Path) -> np.ndarray:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory(prefix="banjofy_bpm_") as temp_dir:
            wav_path = Path(temp_dir) / "analysis.wav"
            command = [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", str(audio_path),
                "-t", str(self.ANALYSIS_SECONDS),
                "-vn",
                "-ac", "1",
                "-ar", str(self.SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                str(wav_path),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=240,
            )
            if completed.returncode != 0 or not wav_path.exists():
                raise RuntimeError(completed.stderr.strip() or "FFmpeg could not decode the audio")

            with wave.open(str(wav_path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                channels = wav_file.getnchannels()
                width = wav_file.getsampwidth()
                rate = wav_file.getframerate()

            if width != 2:
                raise RuntimeError("Decoded audio was not 16-bit PCM")
            if rate != self.SAMPLE_RATE:
                raise RuntimeError("Decoded audio sample rate was unexpected")

            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)
            samples /= 32768.0

        if samples.size < self.SAMPLE_RATE * 8:
            raise RuntimeError("Audio is too short for reliable BPM analysis")

        peak = float(np.max(np.abs(samples)))
        if peak < 0.003:
            raise RuntimeError("Audio is silent or too quiet")
        return samples / peak

    def _tempo_from_samples(self, samples: np.ndarray, sample_rate: int) -> tuple[int | None, float]:
        frame_size = 2048
        hop_size = 512

        usable = 1 + (len(samples) - frame_size) // hop_size
        if usable < 100:
            return None, 0.0

        window = np.hanning(frame_size).astype(np.float32)
        onset = np.zeros(usable, dtype=np.float32)
        previous = None

        for index in range(usable):
            start = index * hop_size
            frame = samples[start:start + frame_size] * window
            spectrum = np.abs(np.fft.rfft(frame))
            spectrum = np.log1p(spectrum)

            if previous is not None:
                positive_flux = spectrum - previous
                positive_flux[positive_flux < 0] = 0
                onset[index] = float(np.sum(positive_flux))
            previous = spectrum

        # Robust local normalisation reduces the effect of quiet intros and loud choruses.
        onset = self._moving_normalise(onset, radius=32)
        onset = np.maximum(onset, 0)
        onset -= float(np.mean(onset))

        if float(np.std(onset)) < 1e-5:
            return None, 0.0

        envelope_rate = sample_rate / hop_size
        min_lag = max(1, int(envelope_rate * 60 / self.MAX_BPM))
        max_lag = min(len(onset) - 2, int(envelope_rate * 60 / self.MIN_BPM))
        if max_lag <= min_lag:
            return None, 0.0

        autocorrelation = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
        search = autocorrelation[min_lag:max_lag + 1].astype(np.float64)

        # Mild preference for typical musical tempos while retaining the full range.
        lags = np.arange(min_lag, max_lag + 1, dtype=np.float64)
        bpms = 60.0 * envelope_rate / lags
        preference = np.exp(-0.5 * ((np.log2(bpms / 110.0)) / 0.85) ** 2)
        scores = search * (0.75 + 0.25 * preference)

        best_offset = int(np.argmax(scores))
        best_lag = min_lag + best_offset
        raw_bpm = 60.0 * envelope_rate / best_lag

        # Resolve common half/double-tempo ambiguity by comparing harmonic candidates.
        candidates = [raw_bpm]
        if raw_bpm * 2 <= self.MAX_BPM:
            candidates.append(raw_bpm * 2)
        if raw_bpm / 2 >= self.MIN_BPM:
            candidates.append(raw_bpm / 2)

        def candidate_score(bpm: float) -> float:
            lag = int(round(60.0 * envelope_rate / bpm))
            if lag < min_lag or lag > max_lag:
                return -math.inf
            base = float(autocorrelation[lag])
            harmonic = 0.0
            if lag * 2 < len(autocorrelation):
                harmonic += 0.35 * float(autocorrelation[lag * 2])
            if lag // 2 >= 1:
                harmonic += 0.20 * float(autocorrelation[lag // 2])
            typical = math.exp(-0.5 * (math.log2(bpm / 110.0) / 0.9) ** 2)
            return (base + harmonic) * (0.8 + 0.2 * typical)

        selected = max(candidates, key=candidate_score)
        bpm = int(round(selected))
        bpm = max(self.MIN_BPM, min(self.MAX_BPM, bpm))

        positive_scores = scores[scores > 0]
        if positive_scores.size == 0:
            return None, 0.0
        median = float(np.median(positive_scores))
        peak_score = float(np.max(scores))
        confidence = max(0.0, min(1.0, (peak_score / (median + 1e-9) - 1.0) / 5.0))

        # Very weak periodicity is more honest as a safe fallback.
        if confidence < 0.08:
            return None, confidence
        return bpm, confidence

    def _moving_normalise(self, values: np.ndarray, radius: int) -> np.ndarray:
        width = radius * 2 + 1
        kernel = np.ones(width, dtype=np.float32) / width
        local_mean = np.convolve(values, kernel, mode="same")
        squared_mean = np.convolve(values * values, kernel, mode="same")
        local_variance = np.maximum(squared_mean - local_mean * local_mean, 1e-8)
        return (values - local_mean) / np.sqrt(local_variance)

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
