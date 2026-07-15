from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

import numpy as np

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

    @property
    def usable(self) -> bool:
        return len(self.beat_times_ms) >= 8 and self.estimated_bpm > 0


class TimingAnalyzer:
    """Automatic beat and downbeat timing using librosa.

    Beat timestamps remain neutral song data. No chord diagrams or
    instrument-specific information is stored here.
    """

    CACHE_VERSION = 1

    def _cache_folder(self) -> Path:
        library = get_library_path()
        if library is None:
            raise RuntimeError("Library folder is not configured")
        folder = Path(library) / "timing"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _cache_path(self, audio_path: Path) -> Path:
        safe = "".join(
            char if char.isalnum() or char in "._-" else "_"
            for char in audio_path.stem
        )[:120]
        return self._cache_folder() / f"{safe}.timing.json"

    def load_cached(self, audio_path: Path) -> TimingAnalysis | None:
        cache = self._cache_path(audio_path)
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
            "source_audio": str(audio_path),
            "beat_times_ms": list(result.beat_times_ms),
            "downbeat_indices": list(result.downbeat_indices),
            "estimated_bpm": result.estimated_bpm,
            "first_downbeat_ms": result.first_downbeat_ms,
            "confidence": result.confidence,
        }
        path = self._cache_path(audio_path)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def analyse(
        self,
        audio_path: Path,
        progress: ProgressCallback | None = None,
    ) -> TimingAnalysis:
        cached = self.load_cached(audio_path)
        if cached is not None:
            if progress:
                progress("Loaded cached timing")
            return cached

        if progress:
            progress("Loading audio for beat analysis")

        import librosa

        y, sample_rate = librosa.load(
            str(audio_path),
            sr=22050,
            mono=True,
            duration=None,
        )
        if y.size < sample_rate * 4:
            raise RuntimeError("Audio is too short for reliable beat analysis")

        if progress:
            progress("Detecting beat pulses")

        hop_length = 512
        onset_env = librosa.onset.onset_strength(
            y=y,
            sr=sample_rate,
            hop_length=hop_length,
            aggregate=np.median,
        )

        tempo, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            units="frames",
            trim=False,
        )
        tempo_value = float(np.asarray(tempo).reshape(-1)[0])
        beat_frames = np.asarray(beat_frames, dtype=int)

        if beat_frames.size < 8:
            raise RuntimeError("Not enough musical beats could be detected")

        beat_times = librosa.frames_to_time(
            beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if progress:
            progress("Estimating Bar 1 Beat 1")

        # Downbeat phase estimation for common 4/4 music:
        # compare onset strength, RMS energy and harmonic change for each of
        # the four possible beat phases. Chord/bass changes and accents often
        # favour the first beat of a bar.
        rms = librosa.feature.rms(
            y=y,
            frame_length=2048,
            hop_length=hop_length,
        )[0]
        chroma = librosa.feature.chroma_cqt(
            y=y,
            sr=sample_rate,
            hop_length=hop_length,
        )

        max_frame = min(len(onset_env), len(rms), chroma.shape[1]) - 1
        valid_frames = np.clip(beat_frames, 1, max_frame)

        onset_values = onset_env[valid_frames]
        rms_values = rms[valid_frames]
        chroma_change = np.linalg.norm(
            chroma[:, valid_frames] - chroma[:, valid_frames - 1],
            axis=0,
        )

        def normalise(values: np.ndarray) -> np.ndarray:
            values = np.asarray(values, dtype=float)
            spread = np.std(values)
            if spread < 1e-9:
                return np.zeros_like(values)
            return (values - np.mean(values)) / spread

        accent = (
            0.45 * normalise(onset_values)
            + 0.25 * normalise(rms_values)
            + 0.30 * normalise(chroma_change)
        )

        # Ignore the first couple of detected beats because intros and pickup
        # notes are frequently less stable than the established pulse.
        phase_scores: list[float] = []
        for phase in range(4):
            indices = np.arange(phase, len(accent), 4)
            indices = indices[indices >= 2]
            if indices.size == 0:
                phase_scores.append(float("-inf"))
            else:
                phase_scores.append(float(np.mean(accent[indices])))

        best_phase = int(np.argmax(phase_scores))
        finite_scores = np.asarray(
            [score for score in phase_scores if np.isfinite(score)],
            dtype=float,
        )
        if finite_scores.size > 1:
            confidence = float(
                max(0.0, min(1.0, (max(phase_scores) - np.median(finite_scores)) / 2.5))
            )
        else:
            confidence = 0.0

        # The selected phase defines Beat 1 of each bar. Beats before that are
        # treated as pickup/intro beats and are not shown in the main grid.
        aligned_times = beat_times[best_phase:]
        beat_times_ms = tuple(int(round(value * 1000.0)) for value in aligned_times)

        if len(beat_times_ms) < 8:
            raise RuntimeError("Downbeat alignment left too few usable beats")

        downbeat_indices = tuple(range(0, len(beat_times_ms), 4))
        first_downbeat_ms = beat_times_ms[0]

        result = TimingAnalysis(
            beat_times_ms=beat_times_ms,
            downbeat_indices=downbeat_indices,
            estimated_bpm=tempo_value,
            first_downbeat_ms=first_downbeat_ms,
            confidence=confidence,
            source_audio=str(audio_path),
        )
        self.save_cached(audio_path, result)

        if progress:
            progress("Automatic beat timing complete")
        return result
