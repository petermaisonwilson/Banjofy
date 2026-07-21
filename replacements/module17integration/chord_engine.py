from __future__ import annotations

import csv
import json
import os
import queue
import runpy
import shutil
import sys
import tempfile
import subprocess
import threading
import traceback
import io
from contextlib import redirect_stdout, redirect_stderr
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np
import scipy.signal
from tkinter import (
    BOTH, END, LEFT, RIGHT, X,
    Button, Entry, Frame, Label, StringVar, Text, Tk,
    filedialog, messagebox,
)

APP_TITLE = "Banjofy 006.4.0 Module 17 Integration Build 001"
MODEL_NAME = "Laboratory 016: ChordMini ChordNet + confidence-gated independent chroma detector"
ANALYSIS_VERSION = 17

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

class _SilentStream:
    """Writable stream used by console-oriented libraries in windowed EXEs."""

    encoding = "utf-8"

    def write(self, value) -> int:
        return len(str(value)) if value is not None else 0

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return -1


def ensure_safe_console_streams() -> None:
    if sys.stdout is None:
        sys.stdout = _SilentStream()
    if sys.stderr is None:
        sys.stderr = _SilentStream()



@dataclass(frozen=True)
class ChordSegment:
    start_s: float
    end_s: float
    chord: str
    duration_s: float
    start_beat: int | None = None
    end_beat: int | None = None


@dataclass(frozen=True)
class AnalysisResult:
    source_audio: str
    model: str
    analysis_version: int
    key: str
    key_confidence: float
    bpm: float
    raw_bpm: float
    practice_bpm: float
    meter: str
    meter_confidence: float
    beat_count: int
    main_chords: list[str]
    beginner_chords: list[str]
    intermediate_chords: list[str]
    professional_chords: list[str]
    musical_end_s: float
    raw_segment_count: int
    cleaned_segment_count: int
    duration_s: float
    segments: list[ChordSegment]
    diagnostics: list[str]
    detector_disagreements: list[dict]
    chord_importance: list[dict]


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def chordmini_root() -> Path:
    candidates = [resource_root() / "ChordMini", Path.cwd() / "ChordMini"]
    source = Path(__file__).resolve()
    candidates.extend(parent / "ChordMini" for parent in source.parents)
    for root in candidates:
        if root.exists():
            return root
    raise RuntimeError(
        "The packaged ChordMini model folder is missing. "
        "The GitHub build did not include the dedicated chord model."
    )


def normalise_chord_label(label: str) -> str:
    value = label.strip()
    if not value:
        return "N"
    if value.upper() in {"N", "NO_CHORD", "X"}:
        return "N"

    value = value.replace("♭", "b").replace("♯", "#")
    if ":" not in value:
        return value

    root, quality = value.split(":", 1)
    quality_lower = quality.lower()

    if quality_lower in {"maj", "major"}:
        return root
    if quality_lower in {"min", "minor"}:
        return root + "m"
    if quality_lower in {"5", "power"}:
        return root + "5"
    if quality_lower.startswith("maj7"):
        return root + "maj7"
    if quality_lower.startswith("min7"):
        return root + "m7"
    if quality_lower.startswith("7"):
        return root + "7"
    if quality_lower.startswith("sus2"):
        return root + "sus2"
    if quality_lower.startswith("sus4"):
        return root + "sus4"
    if quality_lower.startswith("dim"):
        return root + "dim"
    if quality_lower.startswith("aug"):
        return root + "aug"
    return f"{root}:{quality}"


def parse_lab(path: Path) -> list[ChordSegment]:
    segments: list[ChordSegment] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            start_s = float(parts[0])
            end_s = float(parts[1])
        except ValueError:
            continue
        chord = normalise_chord_label(" ".join(parts[2:]))
        if end_s <= start_s:
            continue
        segments.append(
            ChordSegment(
                start_s=start_s,
                end_s=end_s,
                chord=chord,
                duration_s=end_s - start_s,
            )
        )

    if not segments:
        raise RuntimeError(
            f"The dedicated model produced no usable chord segments in {path.name}."
        )
    return segments


def root_pitch_class(chord: str) -> int | None:
    if chord == "N":
        return None
    text = chord.split(":", 1)[0]
    for suffix in ("maj7", "sus2", "sus4", "dim", "aug", "m7", "m", "7", "5"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[:-len(suffix)]
            break
    text = text.split("/", 1)[0]
    enharmonic = {
        "Db": "C#", "Eb": "D#", "Gb": "F#",
        "Ab": "G#", "Bb": "A#",
    }
    text = enharmonic.get(text, text)
    try:
        return NOTE_NAMES.index(text)
    except ValueError:
        return None


def chord_quality(chord: str) -> str:
    if chord == "N":
        return "none"
    if "dim" in chord:
        return "dim"
    if "aug" in chord:
        return "aug"
    if chord.endswith("m") or "m7" in chord or ":min" in chord:
        return "minor"
    return "major"



def trim_unreliable_tail(segments: list[ChordSegment]) -> tuple[list[ChordSegment], float]:
    """Remove implausibly long final holds caused by silence or video end cards."""
    kept = list(segments)
    useful = [segment.duration_s for segment in kept if segment.chord != "N"]
    median_duration = float(np.median(useful)) if useful else 1.0
    while len(kept) > 1:
        final = kept[-1]
        beat_span = 0
        if final.start_beat is not None and final.end_beat is not None:
            beat_span = max(0, final.end_beat - final.start_beat)
        if final.duration_s > max(15.0, median_duration * 8.0) and beat_span <= 2:
            kept.pop()
            continue
        break
    musical_end = kept[-1].end_s if kept else 0.0
    return kept, musical_end


def infer_key(segments: list[ChordSegment]) -> tuple[str, float]:
    """Infer key from capped chord duration, chord quality, starts and cadences."""
    segments, _ = trim_unreliable_tail(segments)
    major = {0: "major", 2: "minor", 4: "minor", 5: "major", 7: "major", 9: "minor", 11: "dim"}
    minor = {0: "minor", 2: "dim", 3: "major", 5: "minor", 7: "ambiguous", 8: "major", 10: "major"}
    root_totals: dict[int, float] = defaultdict(float)
    quality_totals: dict[tuple[int, str], float] = defaultdict(float)
    start_weights: dict[int, float] = defaultdict(float)
    transitions: dict[tuple[int, int], int] = defaultdict(int)
    previous_root: int | None = None
    first_root: int | None = None
    total = 0.0
    for index, segment in enumerate(segments):
        root = root_pitch_class(segment.chord)
        if root is None:
            continue
        if first_root is None:
            first_root = root
        quality = chord_quality(segment.chord)
        if "sus" in segment.chord or segment.chord.endswith("5"):
            quality = "ambiguous"
        duration = min(max(0.0, segment.duration_s), 8.0)
        root_totals[root] += duration
        quality_totals[(root, quality)] += duration
        total += duration
        if index < 8:
            start_weights[root] += duration * ((8 - index) / 8.0)
        if previous_root is not None and previous_root != root:
            transitions[(previous_root, root)] += 1
        previous_root = root
    if total <= 0.0:
        return "Unknown", 0.0
    candidates: list[tuple[float, int, str]] = []
    for key_root in range(12):
        for mode, dictionary in (("major", major), ("minor", minor)):
            score = 0.0
            for root, duration in root_totals.items():
                interval = (root - key_root) % 12
                expected = dictionary.get(interval)
                if expected is None:
                    score -= duration * 0.70
                    continue
                score += duration * 0.75
                for (quality_root, quality), quality_duration in quality_totals.items():
                    if quality_root != root:
                        continue
                    if quality == "ambiguous":
                        score += quality_duration * 0.10
                    elif quality == expected:
                        score += quality_duration * 0.65
                    elif quality in {"major", "minor"} and expected in {"major", "minor"}:
                        score -= quality_duration * 0.40
                if interval == 0:
                    score += duration * 0.80
                elif interval == 7:
                    score += duration * 0.20
            score += start_weights[key_root] * 0.70
            score += transitions[((key_root + 7) % 12, key_root)] * 1.20
            score += transitions[((key_root + 10) % 12, key_root)] * 0.50
            if first_root == key_root:
                score += total * 0.60
            candidates.append((score / total, key_root, mode))
    candidates.sort(reverse=True)
    best, second = candidates[0], candidates[1]
    margin = max(0.0, best[0] - second[0])
    confidence = max(0.05, min(0.99, 0.55 + margin * 1.10))
    return f"{NOTE_NAMES[best[1]]} {best[2]}", confidence


def stabilise_chord_qualities(segments: list[ChordSegment], key: str) -> list[ChordSegment]:
    """Correct minority major/minor labels only when duration evidence is decisive."""
    totals: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for segment in segments:
        root = root_pitch_class(segment.chord)
        quality = chord_quality(segment.chord)
        if root is not None and quality in {"major", "minor"}:
            totals[root][quality] += min(segment.duration_s, 8.0)
    preferred: dict[int, str] = {}
    for root, values in totals.items():
        major_value = values.get("major", 0.0)
        minor_value = values.get("minor", 0.0)
        combined = major_value + minor_value
        if combined <= 0.0:
            continue
        winning = "major" if major_value >= minor_value else "minor"
        if max(major_value, minor_value) / combined >= 0.78:
            preferred[root] = winning
    result: list[ChordSegment] = []
    for segment in segments:
        root = root_pitch_class(segment.chord)
        current = chord_quality(segment.chord)
        replacement = segment.chord
        if root in preferred and current in {"major", "minor"} and current != preferred[root]:
            root_name = NOTE_NAMES[root]
            replacement = root_name + ("m" if preferred[root] == "minor" else "")
        result.append(ChordSegment(segment.start_s, segment.end_s, replacement, segment.duration_s, segment.start_beat, segment.end_beat))
    return _merge_adjacent(result)


def simplify_chord(chord: str, level: str) -> str:
    if chord == "N":
        return chord
    root = root_pitch_class(chord)
    if root is None:
        return chord
    root_name = NOTE_NAMES[root]
    minor = chord_quality(chord) == "minor"
    if level == "beginner":
        return root_name + ("m" if minor else "")
    if level == "intermediate":
        if "min6" in chord or ":min6" in chord:
            return root_name + "m6"
        return chord
    return chord


def _segment_occurrences(segments: list[ChordSegment], labels: set[str]) -> int:
    count = 0
    previous = None
    for segment in segments:
        label = simplify_chord(segment.chord, "beginner")
        if label in labels and label != previous:
            count += 1
        previous = label
    return count


def chord_importance_table(
    segments: list[ChordSegment],
    original_segments: list[ChordSegment] | None = None,
    detector_disagreements: list[dict] | None = None,
) -> list[dict]:
    """Explain Beginner importance and distinguish model-confirmed from detector-only chords."""
    totals: dict[str, float] = defaultdict(float)
    occurrences: dict[str, int] = defaultdict(int)
    source_labels: dict[str, set[str]] = defaultdict(set)
    previous = None
    harmonic_duration = sum(s.duration_s for s in segments if s.chord != "N") or 1.0

    for segment in segments:
        label = simplify_chord(segment.chord, "beginner")
        if label == "N":
            previous = None
            continue
        totals[label] += segment.duration_s
        source_labels[label].add(segment.chord)
        if label != previous:
            occurrences[label] += 1
        previous = label

    original_labels = {
        simplify_chord(segment.chord, "beginner")
        for segment in (original_segments or segments)
        if segment.chord != "N"
    }
    disagreement_categories: dict[str, list[str]] = defaultdict(list)
    for item in detector_disagreements or []:
        disagreement_categories[simplify_chord(item["resolved"], "beginner")].append(
            item.get("promotion_category", "possible")
        )

    ranked = sorted(totals, key=lambda item: totals[item], reverse=True)
    result: list[dict] = []
    for rank, label in enumerate(ranked, start=1):
        share = totals[label] / harmonic_duration
        recurring = occurrences[label] >= 3
        substantial = share >= 0.06
        core_rank = rank <= 3
        detector_only = label not in original_labels
        is_minor = label.endswith("m")

        if not detector_only:
            confidence_category = "confirmed"
            included = core_rank or recurring or substantial
        elif is_minor:
            # New minor colours remain visible to Professional users but are not
            # promoted automatically into the Beginner chord set.
            confidence_category = "possible"
            included = False
        else:
            # Repeated new major roots can recover a genuinely missed I/IV/V chord.
            robust_major = recurring and totals[label] >= 3.0
            confidence_category = "probable" if robust_major else "possible"
            included = robust_major

        if detector_only and is_minor:
            reason = "detector-only minor; retained as possible harmony outside Beginner view"
        elif detector_only and included:
            reason = "repeated detector-supported major root"
        elif detector_only:
            reason = "detector-only root lacks enough support for Beginner view"
        else:
            reason = (
                "top-three root" if core_rank else
                "repeats at least three times" if recurring else
                "at least six percent of harmonic duration" if substantial else
                "too isolated or too brief for Beginner view"
            )
        result.append({
            "chord": label,
            "total_duration_s": round(totals[label], 3),
            "duration_share": round(share, 5),
            "occurrences": occurrences[label],
            "source_labels": sorted(source_labels[label]),
            "beginner_included": included,
            "detector_only": detector_only,
            "confidence_category": confidence_category,
            "reason": reason,
        })
    return result


def level_vocabulary(
    segments: list[ChordSegment],
    level: str,
    limit: int = 12,
    original_segments: list[ChordSegment] | None = None,
    detector_disagreements: list[dict] | None = None,
) -> list[str]:
    table = chord_importance_table(segments, original_segments, detector_disagreements)
    if level == "beginner":
        return [row["chord"] for row in table if row["beginner_included"]][:limit]

    totals: dict[str, float] = defaultdict(float)
    for segment in segments:
        label = simplify_chord(segment.chord, level)
        if label != "N":
            totals[label] += segment.duration_s

    ordered = [item[0] for item in sorted(totals.items(), key=lambda item: item[1], reverse=True)]
    if level == "intermediate":
        possible_detector_minors = {
            row["chord"] for row in table
            if row["detector_only"] and row["confidence_category"] == "possible" and row["chord"].endswith("m")
        }
        ordered = [label for label in ordered if simplify_chord(label, "beginner") not in possible_detector_minors]
    return ordered[:limit]


def _chord_templates() -> list[tuple[str, np.ndarray]]:
    """Return deliberately simple major/minor templates for an independent detector."""
    templates: list[tuple[str, np.ndarray]] = []
    for root in range(12):
        for quality, intervals in (("major", (0, 4, 7)), ("minor", (0, 3, 7))):
            vector = np.full(12, 0.03, dtype=float)
            vector[root] = 1.00
            vector[(root + intervals[1]) % 12] = 0.72
            vector[(root + 7) % 12] = 0.58
            vector /= np.linalg.norm(vector) or 1.0
            label = NOTE_NAMES[root] + ("m" if quality == "minor" else "")
            templates.append((label, vector))
    return templates


def independent_chroma_windows(audio_path: Path, beat_times: list[float], duration: float) -> list[dict]:
    """Detect basic chords independently in two-beat windows from harmonic chroma."""
    ensure_scipy_signal_compatibility()
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    if y is None or len(y) == 0:
        raise RuntimeError("Independent detector audio was empty.")
    harmonic, _ = librosa.effects.hpss(y)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr, hop_length=512)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)
    boundaries = sorted(set([0.0] + [float(x) for x in beat_times if 0 <= x <= duration] + [duration]))
    templates = _chord_templates()
    windows: list[dict] = []

    # Two-beat windows reduce note-level bluegrass noise while retaining short dominants.
    step = 2
    for index in range(0, max(0, len(boundaries) - step), step):
        start_s = boundaries[index]
        end_s = boundaries[min(index + step, len(boundaries) - 1)]
        if end_s - start_s < 0.30:
            continue
        mask = (frame_times >= start_s) & (frame_times < end_s)
        if not np.any(mask):
            continue
        vector = np.median(chroma[:, mask], axis=1).astype(float)
        energy = float(np.sum(vector))
        if energy <= 1e-8:
            continue
        vector /= np.linalg.norm(vector) or 1.0
        scores = sorted(((float(np.dot(vector, template)), label) for label, template in templates), reverse=True)
        best_score, best_label = scores[0]
        second_score = scores[1][0]
        confidence = max(0.0, min(1.0, (best_score - second_score) / max(best_score, 1e-6) * 4.0))
        windows.append({
            "start_s": start_s,
            "end_s": end_s,
            "chord": best_label,
            "root": root_pitch_class(best_label),
            "confidence": confidence,
            "score": best_score,
        })
    return windows


def _model_chord_at(segments: list[ChordSegment], midpoint: float) -> ChordSegment | None:
    for segment in segments:
        if segment.start_s <= midpoint < segment.end_s:
            return segment
    return None


def fuse_independent_detector(
    segments: list[ChordSegment],
    windows: list[dict],
) -> tuple[list[ChordSegment], list[dict]]:
    """Promote repeatedly supported roots missed inside long ChordMini holds.

    A differing root is accepted only when it recurs in at least three separated
    windows, has adequate chroma confidence, and sits inside a long model segment.
    This prevents music-theory invention and keeps the original model authoritative
    for ordinary changes.
    """
    candidates: list[dict] = []
    for window in windows:
        midpoint = (window["start_s"] + window["end_s"]) / 2.0
        model = _model_chord_at(segments, midpoint)
        if model is None or model.chord == "N" or model.duration_s < 6.0:
            continue
        model_root = root_pitch_class(model.chord)
        if window["root"] is None or window["root"] == model_root:
            continue
        if window["confidence"] < 0.16 or window["score"] < 0.55:
            continue
        candidates.append({**window, "model_chord": model.chord, "model_start_s": model.start_s, "model_end_s": model.end_s})

    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate["root"], candidate["model_chord"])].append(candidate)

    accepted: list[dict] = []
    for (_, _), group in grouped.items():
        # Require recurrence in separate long model holds, not adjacent windows in one passage.
        separate_holds = {(round(item["model_start_s"], 3), round(item["model_end_s"], 3)) for item in group}
        total = sum(item["end_s"] - item["start_s"] for item in group)
        mean_conf = float(np.mean([item["confidence"] for item in group]))
        if len(separate_holds) >= 3 and total >= 3.0 and mean_conf >= 0.20:
            accepted.extend(group)

    if not accepted:
        return segments, []

    # Rebuild at accepted-window boundaries. Overlapping accepted windows are merged.
    accepted.sort(key=lambda item: item["start_s"])
    merged_windows: list[dict] = []
    for item in accepted:
        if merged_windows and item["chord"] == merged_windows[-1]["chord"] and item["start_s"] <= merged_windows[-1]["end_s"] + 0.05:
            merged_windows[-1]["end_s"] = max(merged_windows[-1]["end_s"], item["end_s"])
            merged_windows[-1]["confidence"] = max(merged_windows[-1]["confidence"], item["confidence"])
        else:
            merged_windows.append(dict(item))

    boundaries = sorted(set(
        [s.start_s for s in segments] + [s.end_s for s in segments] +
        [w["start_s"] for w in merged_windows] + [w["end_s"] for w in merged_windows]
    ))
    rebuilt: list[ChordSegment] = []
    disagreements: list[dict] = []
    for a, b in zip(boundaries, boundaries[1:]):
        if b <= a:
            continue
        midpoint = (a + b) / 2.0
        model = _model_chord_at(segments, midpoint)
        if model is None:
            continue
        replacement = None
        for window in merged_windows:
            if window["start_s"] <= midpoint < window["end_s"]:
                replacement = window
                break
        chord = replacement["chord"] if replacement else model.chord
        rebuilt.append(ChordSegment(a, b, chord, b - a, model.start_beat, model.end_beat))
        if replacement:
            disagreements.append({
                "start_s": round(a, 3),
                "end_s": round(b, 3),
                "chordmini": model.chord,
                "independent": replacement["chord"],
                "resolved": chord,
                "independent_confidence": round(float(replacement["confidence"]), 4),
                "promotion_category": "possible" if replacement["chord"].endswith("m") else "probable",
                "reason": "repeated independent audio evidence inside a long model hold",
            })
    return _merge_adjacent(rebuilt), disagreements

def choose_practice_bpm(raw_bpm: float, segments: list[ChordSegment]) -> float:
    """Conservatively reduce obvious double-time acoustic readings."""
    spans = [max(0, (s.end_beat or 0) - (s.start_beat or 0)) for s in segments if s.chord != "N"]
    median_span = float(np.median(spans)) if spans else 0.0
    if raw_bpm >= 138.0 and median_span >= 4.0:
        return raw_bpm / 2.0
    return raw_bpm

def main_chord_vocabulary(
    segments: list[ChordSegment],
    limit: int = 10,
) -> list[str]:
    totals: dict[str, float] = defaultdict(float)
    for segment in segments:
        if segment.chord != "N":
            totals[segment.chord] += segment.duration_s
    return [
        chord
        for chord, _ in sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]


def locate_output_lab(
    output_dir: Path,
    audio_stem: str,
    captured_output: str = "",
) -> Path:
    candidates = list(output_dir.rglob("*.lab"))
    if not candidates:
        details = captured_output.strip()
        if not details:
            details = (
                "The model produced no visible diagnostic output. "
                "Its internal exception handler may have swallowed the original error."
            )
        raise RuntimeError(
            "The dedicated chord model completed without producing a .lab result.\n\n"
            "Captured model output:\n"
            + details[-8000:]
        )

    exact = [
        path for path in candidates
        if path.stem.lower() == audio_stem.lower()
    ]
    if exact:
        return exact[0]

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def prepare_model_audio(
    source_audio: Path,
    work_dir: Path,
    status_callback,
) -> Path:
    status_callback(
        "Preparing a model-compatible WAV copy of the selected song..."
    )

    output_audio = work_dir / "banjofy_model_input.wav"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source_audio),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "22050",
        "-sample_fmt",
        "s16",
        str(output_audio),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=(
            subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0
        ),
    )

    if completed.returncode != 0 or not output_audio.exists():
        details = completed.stderr[-1500:] if completed.stderr else ""
        raise RuntimeError(
            "FFmpeg could not prepare the selected audio for the chord model. "
            + details
        )

    if output_audio.stat().st_size < 1024:
        raise RuntimeError(
            "The converted WAV file was unexpectedly empty."
        )

    return output_audio


def run_chordmini(
    audio_path: Path,
    work_dir: Path,
    status_callback,
) -> Path:
    ensure_safe_console_streams()
    model_root = chordmini_root()
    test_script = model_root / "src/evaluation/test.py"
    checkpoint = model_root / "checkpoints/2e1d_model_best.pth"
    config = model_root / "config/ChordMini.yaml"
    output_dir = work_dir / "model_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    for required in (test_script, checkpoint, config):
        if not required.exists():
            raise RuntimeError(
                f"Required dedicated-model file is missing: {required.name}"
            )

    status_callback(
        "Running the dedicated full-song chord model. "
        "This may take several minutes on the first test..."
    )

    old_argv = sys.argv[:]
    old_cwd = Path.cwd()
    old_path = sys.path[:]

    original_tqdm = None
    tqdm_module = None
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()

    try:
        ensure_safe_console_streams()

        try:
            import tqdm as tqdm_module
            original_tqdm = tqdm_module.tqdm

            def _quiet_tqdm(iterable=None, *args, **kwargs):
                if iterable is None:
                    return original_tqdm(
                        iterable,
                        *args,
                        disable=True,
                        **kwargs,
                    )
                return original_tqdm(
                    iterable,
                    *args,
                    disable=True,
                    **kwargs,
                )

            tqdm_module.tqdm = _quiet_tqdm
        except Exception:
            tqdm_module = None
            original_tqdm = None

        os.chdir(model_root)
        sys.path.insert(0, str(model_root))
        sys.argv = [
            str(test_script),
            "--model_type", "ChordNet",
            "--checkpoint", str(checkpoint),
            "--config", str(config),
            "--audio_dir", str(audio_path),
            "--save_dir", str(output_dir),
            "--use_overlap",
            "--use_gaussian",
            "--kernel_size", "9",
            "--vote_aggregation", "logit",
            "--min_segment_duration", "0.5",
            "--smooth_predictions",
        ]
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            runpy.run_path(str(test_script), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise RuntimeError(
                f"The dedicated chord model stopped with code {exc.code}."
            ) from exc
    finally:
        if tqdm_module is not None and original_tqdm is not None:
            try:
                tqdm_module.tqdm = original_tqdm
            except Exception:
                pass

        sys.argv = old_argv
        os.chdir(old_cwd)
        sys.path[:] = old_path

    captured_output = "\n".join(
        part for part in (
            captured_stdout.getvalue(),
            captured_stderr.getvalue(),
        )
        if part
    )
    return locate_output_lab(
        output_dir,
        audio_path.stem,
        captured_output=captured_output,
    )



def _merge_adjacent(segments: list[ChordSegment]) -> list[ChordSegment]:
    merged: list[ChordSegment] = []
    for segment in segments:
        if segment.end_s - segment.start_s < 0.02:
            continue
        if (
            merged
            and merged[-1].chord == segment.chord
            and abs(merged[-1].end_s - segment.start_s) <= 0.15
        ):
            previous = merged[-1]
            merged[-1] = ChordSegment(
                start_s=previous.start_s,
                end_s=segment.end_s,
                chord=previous.chord,
                duration_s=segment.end_s - previous.start_s,
                start_beat=previous.start_beat,
                end_beat=segment.end_beat,
            )
        else:
            merged.append(segment)
    return merged

def clean_segments(segments: list[ChordSegment]) -> list[ChordSegment]:
    cleaned=list(segments)
    for i in range(1,len(cleaned)-1):
        p,c,n=cleaned[i-1],cleaned[i],cleaned[i+1]
        if c.chord == "N" and c.duration_s <= 1.20 and p.chord == n.chord and p.chord != "N":
            cleaned[i]=ChordSegment(c.start_s,c.end_s,p.chord,c.duration_s)
    for i in range(1,len(cleaned)-1):
        p,c,n=cleaned[i-1],cleaned[i],cleaned[i+1]
        if c.chord != "N" and c.duration_s <= 0.85 and p.chord == n.chord and p.chord != c.chord:
            cleaned[i]=ChordSegment(c.start_s,c.end_s,p.chord,c.duration_s)
    return _merge_adjacent(cleaned)


def ensure_scipy_signal_compatibility() -> None:
    """Provide legacy SciPy window names expected by some Librosa versions."""
    for name in (
        "hann",
        "hamming",
        "blackman",
        "blackmanharris",
        "bartlett",
        "boxcar",
    ):
        if not hasattr(scipy.signal, name) and hasattr(scipy.signal.windows, name):
            setattr(scipy.signal, name, getattr(scipy.signal.windows, name))


def detect_beats(audio_path: Path) -> tuple[float, list[float]]:
    ensure_scipy_signal_compatibility()

    if not audio_path.exists():
        raise RuntimeError(f"Beat-analysis audio does not exist: {audio_path}")

    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    if y is None or len(y) == 0:
        raise RuntimeError("Beat-analysis audio was empty.")

    try:
        tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
        beats = librosa.frames_to_time(frames, sr=sr).tolist()
        bpm = float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 0.0
    except Exception as exc:
        raise RuntimeError(f"Beat detection failed: {exc}") from exc

    duration = float(librosa.get_duration(y=y, sr=sr))

    if not beats or bpm <= 0.0:
        bpm = 120.0
        beats = list(np.arange(0.0, duration, 0.5))

    beats = [
        float(value)
        for value in beats
        if 0.0 <= float(value) <= duration
    ]
    if not beats:
        beats = [0.0]

    return bpm, beats


def align_segments_to_beats(
    segments: list[ChordSegment],
    beat_times: list[float],
    duration: float,
) -> list[ChordSegment]:
    if not segments or not beat_times:
        return segments

    boundaries = sorted(
        set(
            [0.0]
            + [round(float(value), 6) for value in beat_times if 0.0 <= float(value) <= duration]
            + [round(float(duration), 6)]
        )
    )
    if len(boundaries) < 2:
        return segments

    values = np.asarray(boundaries, dtype=float)
    aligned: list[ChordSegment] = []

    for segment in segments:
        start_index = int(np.argmin(np.abs(values - segment.start_s)))
        end_index = int(np.argmin(np.abs(values - segment.end_s)))

        if end_index <= start_index:
            end_index = min(start_index + 1, len(boundaries) - 1)

        start_s = boundaries[start_index]
        end_s = boundaries[end_index]

        if aligned and start_s < aligned[-1].end_s:
            start_s = aligned[-1].end_s
            if aligned[-1].end_beat is not None:
                start_index = aligned[-1].end_beat + 1

        if end_s <= start_s:
            continue

        aligned.append(
            ChordSegment(
                start_s=start_s,
                end_s=end_s,
                chord=segment.chord,
                duration_s=end_s - start_s,
                start_beat=max(0, start_index - 1),
                end_beat=max(0, end_index - 1),
            )
        )

    return _merge_adjacent(aligned)

def clean_detector_disagreements(items: list[dict], minimum_duration_s: float = 0.02) -> list[dict]:
    """Return only meaningful detector disagreements for reporting and counting."""
    cleaned: list[dict] = []
    for item in items:
        try:
            start_s = float(item.get("start_s", 0.0))
            end_s = float(item.get("end_s", 0.0))
        except (TypeError, ValueError):
            continue
        if end_s - start_s < minimum_duration_s:
            continue
        cleaned.append(item)
    return cleaned


def save_reports(
    result: AnalysisResult,
    output_folder: Path,
    stem: str,
) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)

    json_path = output_folder / f"{stem}_dedicated_chords.json"
    json_path.write_text(
        json.dumps(asdict(result), indent=2),
        encoding="utf-8",
    )

    csv_path = output_folder / f"{stem}_dedicated_chords.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["start_s", "end_s", "duration_s", "start_beat", "end_beat", "chord"])
        for segment in result.segments:
            writer.writerow(
                [
                    f"{segment.start_s:.3f}",
                    f"{segment.end_s:.3f}",
                    f"{segment.duration_s:.3f}",
                    "" if segment.start_beat is None else segment.start_beat,
                    "" if segment.end_beat is None else segment.end_beat,
                    segment.chord,
                ]
            )

    report_path = output_folder / f"{stem}_dedicated_chord_report.txt"
    lines = [
        APP_TITLE,
        "=" * len(APP_TITLE),
        "",
        f"Audio: {result.source_audio}",
        f"Model: {result.model}",
        f"Likely key: {result.key}",
        f"Key confidence: {result.key_confidence:.0%}",
        f"Main chords: {', '.join(result.main_chords)}",
        f"Beginner chords: {', '.join(result.beginner_chords)}",
        f"Intermediate chords: {', '.join(result.intermediate_chords)}",
        f"Professional chords: {', '.join(result.professional_chords)}",
        f"Raw tempo: {result.raw_bpm:.1f} BPM",
        f"Suggested Practice tempo: {result.practice_bpm:.1f} BPM",
        f"Metre: {result.meter}",
        f"Musical end used for key analysis: {result.musical_end_s:.2f}s",
        f"Detected beats: {result.beat_count}",
        f"Raw chord segments: {result.raw_segment_count}",
        f"Cleaned beat-aligned segments: {result.cleaned_segment_count}",
        f"Analysed duration: {result.duration_s:.2f}s",
        f"Accepted dual-detector corrections: {len(result.detector_disagreements)}",
        "",
        "Beginner chord importance",
        "--------------------------",
    ]
    for row in result.chord_importance:
        lines.append(
            f"{row['chord']}: {'INCLUDED' if row['beginner_included'] else 'excluded'}; "
            f"{row['occurrences']} appearances; {row['total_duration_s']:.2f}s; {row['confidence_category'].upper()}; {row['reason']}"
        )
    lines.extend([
        "",
        "Dual-detector corrections",
        "-------------------------",
    ])
    if result.detector_disagreements:
        for item in result.detector_disagreements:
            lines.append(
                f"{item['start_s']:.2f}s–{item['end_s']:.2f}s: "
                f"ChordMini {item['chordmini']} / independent {item['independent']} "
                f"=> {item['resolved']} ({item['independent_confidence']:.0%}; {item.get('promotion_category', 'possible').upper()})"
            )
    else:
        lines.append("None accepted.")
    lines.extend([
        "",
        "Chord timeline",
        "--------------",
    ])
    for segment in result.segments:
        lines.append(
            f"{segment.start_s:8.2f}s–{segment.end_s:8.2f}s  "
            f"{segment.chord}"
        )

    lines.extend(["", "Diagnostics", "-----------"])
    lines.extend(f"- {item}" for item in result.diagnostics)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def analyse_audio(
    audio_path: Path,
    output_folder: Path,
    status_callback,
) -> AnalysisResult:
    diagnostics = [
        "This result comes from a model trained specifically for automatic "
        "chord recognition from music audio.",
        "Key is inferred automatically from the completed chord timeline.",
        "Laboratory 016 analysis is integrated into Module 17 without instrument-specific fingering logic.",
    ]

    with tempfile.TemporaryDirectory(prefix="banjofy_chord_lab_016_") as temp:
        work_dir = Path(temp)
        model_audio = prepare_model_audio(
            audio_path,
            work_dir,
            status_callback,
        )
        lab_path = run_chordmini(
            model_audio,
            work_dir,
            status_callback,
        )

        status_callback("Reading and interpreting the model chord timeline...")
        raw_segments = parse_lab(lab_path)
        duration = max(segment.end_s for segment in raw_segments)
        status_callback("Cleaning isolated fragments and short no-chord gaps...")
        cleaned = clean_segments(raw_segments)
        status_callback("Detecting beats and snapping chord changes to the beat grid...")
        bpm, beat_times = detect_beats(model_audio)
        aligned = align_segments_to_beats(cleaned, beat_times, duration)
        aligned, musical_end = trim_unreliable_tail(aligned)
        status_callback("Running the independent chroma chord detector...")
        independent_windows = independent_chroma_windows(model_audio, beat_times, musical_end)
        status_callback("Resolving repeated detector disagreements...")
        fused, disagreements = fuse_independent_detector(aligned, independent_windows)
        disagreements = clean_detector_disagreements(disagreements)
        key, key_confidence = infer_key(fused)
        resolved = stabilise_chord_qualities(fused, key)
        raw_bpm = bpm
        practice_bpm = choose_practice_bpm(raw_bpm, resolved)
        main_chords = main_chord_vocabulary(resolved)
        importance = chord_importance_table(resolved, aligned, disagreements)
        beginner_chords = level_vocabulary(resolved, "beginner", original_segments=aligned, detector_disagreements=disagreements)
        intermediate_chords = level_vocabulary(resolved, "intermediate", original_segments=aligned, detector_disagreements=disagreements)
        professional_chords = level_vocabulary(resolved, "professional", original_segments=aligned, detector_disagreements=disagreements)
        result = AnalysisResult(
            source_audio=str(audio_path), model=MODEL_NAME, analysis_version=ANALYSIS_VERSION,
            key=key, key_confidence=key_confidence, bpm=practice_bpm, raw_bpm=raw_bpm, practice_bpm=practice_bpm,
            meter="Unknown", meter_confidence=0.0, beat_count=len(beat_times), main_chords=main_chords,
            beginner_chords=beginner_chords, intermediate_chords=intermediate_chords, professional_chords=professional_chords,
            musical_end_s=musical_end, raw_segment_count=len(raw_segments), cleaned_segment_count=len(resolved),
            duration_s=duration, segments=resolved,
            diagnostics=diagnostics + [
                "Short isolated fragments were removed only when the same chord surrounded them.",
                "Short no-chord gaps were filled only when the same chord surrounded them.",
                "Chord boundaries were snapped to automatically detected beats.",
                "An independent chroma detector checked long model holds for repeatedly missed roots.",
                "Beginner chords require model confirmation or robust repeated major-root recovery.",
                "Detector-only minor chords are marked possible and kept out of Beginner and Intermediate views.",
                "Microscopic zero-length fusion fragments and diagnostic disagreements are removed before reporting.",
            ],
            detector_disagreements=disagreements,
            chord_importance=importance,
        )

        status_callback("Saving dedicated chord-model reports...")
        save_reports(result, output_folder, audio_path.stem)
        return result


class ChordLabWindow:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("930x700")
        self.root.minsize(780, 580)

        self.audio_var = StringVar()
        self.output_var = StringVar()
        self.status_var = StringVar(value="Ready")
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()

        Label(
            self.root,
            text=APP_TITLE,
            font=("Segoe UI", 20, "bold"),
        ).pack(pady=(16, 4))

        Label(
            self.root,
            text=(
                "Dedicated full-song chord-recognition test with automatic audio conversion. "
                "No key or chord input is required, and Module 16 Solid is untouched."
            ),
            wraplength=850,
            justify=LEFT,
        ).pack(padx=18, pady=(0, 12))

        self._file_row("Audio file", self.audio_var, self._choose_audio)
        self._file_row("Results folder", self.output_var, self._choose_output)

        controls = Frame(self.root)
        controls.pack(fill=X, padx=18, pady=10)

        self.run_button = Button(
            controls,
            text="Analyse Song",
            command=self._start,
            width=18,
        )
        self.run_button.pack(side=LEFT)

        Button(
            controls,
            text="Open Results Folder",
            command=self._open_results,
            width=20,
        ).pack(side=RIGHT)

        Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=X, padx=18, pady=(4, 8))

        self.output = Text(
            self.root,
            wrap="word",
            font=("Consolas", 10),
        )
        self.output.pack(fill=BOTH, expand=True, padx=18, pady=(0, 18))
        self.root.after(100, self._poll)

    def _file_row(self, label_text, variable, command) -> None:
        row = Frame(self.root)
        row.pack(fill=X, padx=18, pady=5)
        Label(row, text=label_text, width=15, anchor="w").pack(side=LEFT)
        Entry(row, textvariable=variable).pack(
            side=LEFT,
            fill=X,
            expand=True,
            padx=6,
        )
        Button(row, text="Browse", command=command, width=10).pack(side=RIGHT)

    def _choose_audio(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choose a song audio file",
            filetypes=[
                (
                    "Audio files",
                    "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.webm",
                ),
                ("All files", "*.*"),
            ],
        )
        if chosen:
            self.audio_var.set(chosen)
            if not self.output_var.get():
                self.output_var.set(
                    str(Path(chosen).parent / "Chord Lab 016 Results")
                )

    def _choose_output(self) -> None:
        chosen = filedialog.askdirectory(title="Choose results folder")
        if chosen:
            self.output_var.set(chosen)

    def _start(self) -> None:
        audio = Path(self.audio_var.get().strip())
        output = Path(self.output_var.get().strip())

        if not audio.exists():
            messagebox.showerror(APP_TITLE, "Choose an existing audio file first.")
            return
        if not self.output_var.get().strip():
            messagebox.showerror(APP_TITLE, "Choose a results folder.")
            return

        self.run_button.config(state="disabled")
        self.output.delete("1.0", END)
        self.status_var.set("Starting dedicated chord analysis...")

        def worker() -> None:
            try:
                result = analyse_audio(
                    audio,
                    output,
                    lambda message: self.messages.put(("status", message)),
                )
                self.messages.put(("done", result))
            except Exception as exc:
                self.messages.put(
                    (
                        "error",
                        f"{exc}\n\n{traceback.format_exc()}",
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "error":
                    self.run_button.config(state="normal")
                    self.status_var.set("Analysis failed")
                    self.output.insert(END, str(payload))
                    messagebox.showerror(
                        APP_TITLE,
                        "Analysis failed. The exact error is displayed "
                        "in the laboratory window.",
                    )
                elif kind == "done":
                    self.run_button.config(state="normal")
                    self.status_var.set("Analysis complete")
                    self._show_result(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _show_result(self, result: AnalysisResult) -> None:
        lines = [
            "ANALYSIS COMPLETE",
            "",
            f"Model: {result.model}",
            f"Likely key: {result.key}",
            f"Key confidence: {result.key_confidence:.0%}",
            f"Beginner chords: {', '.join(result.beginner_chords)}",
            f"Intermediate chords: {', '.join(result.intermediate_chords)}",
            f"Professional chords: {', '.join(result.professional_chords)}",
            f"Raw tempo: {result.raw_bpm:.1f} BPM",
            f"Suggested Practice tempo: {result.practice_bpm:.1f} BPM",
        f"Detected beats: {result.beat_count}",
        f"Raw chord segments: {result.raw_segment_count}",
        f"Cleaned beat-aligned segments: {result.cleaned_segment_count}",
            "",
            "First chord segments:",
        ]
        for segment in result.segments[:80]:
            lines.append(
                f"{segment.start_s:7.2f}s–{segment.end_s:7.2f}s  "
                f"{segment.chord}"
            )
        if len(result.segments) > 80:
            lines.append(
                f"... plus {len(result.segments) - 80} further segments "
                "in the saved report."
            )
        lines.extend(
            [
                "",
                "Saved outputs:",
                "- readable text report",
                "- chord timeline CSV",
                "- complete JSON analysis",
            ]
        )
        self.output.insert(END, "\n".join(lines))

    def _open_results(self) -> None:
        folder = Path(self.output_var.get().strip())
        if not folder.exists():
            messagebox.showinfo(APP_TITLE, "No results folder exists yet.")
            return
        try:
            os.startfile(folder)
        except Exception:
            messagebox.showinfo(APP_TITLE, str(folder))

    def run(self) -> None:
        self.root.mainloop()



def run_internal_self_audit() -> list[str]:
    """Run non-model checks used during GitHub Actions and release audit."""
    messages: list[str] = []

    ensure_scipy_signal_compatibility()
    if not hasattr(scipy.signal, "hann"):
        raise RuntimeError("SciPy compatibility audit failed.")
    messages.append("SciPy compatibility passed")

    sample = [
        ChordSegment(0.0, 4.0, "B", 4.0),
        ChordSegment(4.0, 4.5, "Bm", 0.5),
        ChordSegment(4.5, 8.0, "B", 3.5),
        ChordSegment(8.0, 10.0, "A", 2.0),
        ChordSegment(10.0, 12.0, "E", 2.0),
    ]

    cleaned = clean_segments(sample)
    if any(segment.chord == "Bm" for segment in cleaned):
        raise RuntimeError("Chord cleanup audit failed.")
    messages.append("Chord cleanup passed")

    key, _ = infer_key(cleaned)
    if key != "B major":
        raise RuntimeError(f"Key inference audit failed: expected B major, got {key}")
    messages.append("Key inference passed")

    beats = [float(value) for value in range(13)]
    aligned = align_segments_to_beats(cleaned, beats, 12.0)
    if not aligned:
        raise RuntimeError("Beat alignment audit produced no segments.")
    if any(segment.end_s <= segment.start_s for segment in aligned):
        raise RuntimeError("Beat alignment audit produced invalid segments.")
    messages.append("Beat alignment passed")

    tail_sample = aligned + [ChordSegment(12.0, 70.0, "C#", 58.0, 12, 13)]
    trimmed, musical_end = trim_unreliable_tail(tail_sample)
    if musical_end != 12.0 or len(trimmed) != len(aligned):
        raise RuntimeError("Trailing artefact audit failed.")
    messages.append("Trailing artefact exclusion passed")

    teen_sample = [
        ChordSegment(0.0, 1.0, "F", 1.0), ChordSegment(1.0, 2.0, "A#", 1.0),
        ChordSegment(2.0, 3.0, "G#", 1.0), ChordSegment(3.0, 4.0, "C#", 1.0),
    ] * 8
    teen_key, _ = infer_key(teen_sample)
    if teen_key != "F minor":
        raise RuntimeError(f"Minor/power-root key audit failed: {teen_key}")
    messages.append("Minor/root-pattern key inference passed")

    quality_sample = [ChordSegment(0, 2, "F#", 2), ChordSegment(2, 12, "F#m", 10)]
    quality_fixed = stabilise_chord_qualities(quality_sample, "A major")
    if any(item.chord == "F#" for item in quality_fixed):
        raise RuntimeError("Contextual chord-quality audit failed.")
    messages.append("Contextual chord-quality stabilisation passed")

    if simplify_chord("E7", "beginner") != "E" or simplify_chord("Esus4", "beginner") != "E":
        raise RuntimeError("Beginner simplification audit failed.")
    messages.append("Three-level presentation audit passed")

    beginner_sample = (
        [ChordSegment(0, 10, "F", 10), ChordSegment(10, 20, "A#", 10),
         ChordSegment(20, 30, "G#", 10), ChordSegment(30, 40, "C#", 10)] * 3
        + [ChordSegment(120, 121, "Csus4", 1)]
    )
    beginner = level_vocabulary(beginner_sample, "beginner")
    if "C" in beginner or set(beginner) != {"F", "A#", "G#", "C#"}:
        raise RuntimeError(f"Beginner importance audit failed: {beginner}")
    messages.append("Beginner importance filtering passed")

    model_holds = [
        ChordSegment(0, 10, "D", 10), ChordSegment(10, 12, "G", 2),
        ChordSegment(12, 22, "D", 10), ChordSegment(22, 24, "G", 2),
        ChordSegment(24, 34, "D", 10), ChordSegment(34, 36, "G", 2),
    ]
    windows = [
        {"start_s": 6.0, "end_s": 8.0, "chord": "A", "root": 9, "confidence": 0.42, "score": 0.81},
        {"start_s": 18.0, "end_s": 20.0, "chord": "A", "root": 9, "confidence": 0.40, "score": 0.80},
        {"start_s": 30.0, "end_s": 32.0, "chord": "A", "root": 9, "confidence": 0.44, "score": 0.82},
    ]
    fused, disagreements = fuse_independent_detector(model_holds, windows)
    if not disagreements or "A" not in {item.chord for item in fused}:
        raise RuntimeError("Dual-detector fusion audit failed.")
    messages.append("Dual-detector repeated-root fusion passed")

    # Detector-only minor chords must not enter Beginner or Intermediate views.
    original_minor_gate = [ChordSegment(0, 10, "F", 10), ChordSegment(10, 12, "A#", 2)] * 3
    resolved_minor_gate = original_minor_gate + [
        ChordSegment(36, 37, "Am", 1), ChordSegment(48, 49, "Am", 1), ChordSegment(60, 61, "Am", 1)
    ]
    minor_disagreements = [
        {"resolved": "Am", "promotion_category": "possible"},
        {"resolved": "Am", "promotion_category": "possible"},
        {"resolved": "Am", "promotion_category": "possible"},
    ]
    gated_beginner = level_vocabulary(resolved_minor_gate, "beginner", original_segments=original_minor_gate, detector_disagreements=minor_disagreements)
    gated_intermediate = level_vocabulary(resolved_minor_gate, "intermediate", original_segments=original_minor_gate, detector_disagreements=minor_disagreements)
    gated_professional = level_vocabulary(resolved_minor_gate, "professional", original_segments=original_minor_gate, detector_disagreements=minor_disagreements)
    if "Am" in gated_beginner or "Am" in gated_intermediate or "Am" not in gated_professional:
        raise RuntimeError("Detector-only minor confidence gating audit failed.")
    messages.append("Detector-only minor confidence gating passed")

    # Repeated detector-supported major roots remain available to Beginner users.
    original_major_gate = [
        ChordSegment(0, 10, "D", 10), ChordSegment(10, 12, "G", 2),
        ChordSegment(12, 22, "D", 10), ChordSegment(22, 24, "G", 2),
        ChordSegment(24, 34, "D", 10), ChordSegment(34, 36, "G", 2),
        ChordSegment(36, 46, "D", 10), ChordSegment(46, 48, "G", 2),
    ]
    resolved_major_gate = [
        ChordSegment(0, 8, "D", 8), ChordSegment(8, 9, "A", 1), ChordSegment(9, 10, "D", 1), ChordSegment(10, 12, "G", 2),
        ChordSegment(12, 20, "D", 8), ChordSegment(20, 21, "A", 1), ChordSegment(21, 22, "D", 1), ChordSegment(22, 24, "G", 2),
        ChordSegment(24, 32, "D", 8), ChordSegment(32, 33, "A", 1), ChordSegment(33, 34, "D", 1), ChordSegment(34, 36, "G", 2),
        ChordSegment(36, 44, "D", 8), ChordSegment(44, 45, "A", 1), ChordSegment(45, 46, "D", 1), ChordSegment(46, 48, "G", 2),
    ]
    major_disagreements = [{"resolved": "A", "promotion_category": "probable"}] * 4
    major_beginner = level_vocabulary(resolved_major_gate, "beginner", original_segments=original_major_gate, detector_disagreements=major_disagreements)
    if "A" not in major_beginner:
        raise RuntimeError("Recovered major-root Beginner promotion audit failed.")
    messages.append("Recovered major-root promotion passed")

    microscopic = _merge_adjacent([
        ChordSegment(0.0, 1.0, "F", 1.0),
        ChordSegment(1.0, 1.0000001, "Am", 0.0000001),
        ChordSegment(1.0000001, 2.0, "F", 0.9999999),
    ])
    if any(item.duration_s < 0.02 for item in microscopic):
        raise RuntimeError("Microscopic boundary cleanup audit failed.")
    messages.append("Microscopic boundary cleanup passed")

    diagnostic_sample = [
        {"start_s": 62.671, "end_s": 62.671, "resolved": "Am"},
        {"start_s": 62.671, "end_s": 64.946, "resolved": "Am"},
    ]
    cleaned_diagnostics = clean_detector_disagreements(diagnostic_sample)
    if len(cleaned_diagnostics) != 1 or cleaned_diagnostics[0]["end_s"] <= cleaned_diagnostics[0]["start_s"]:
        raise RuntimeError("Zero-duration diagnostic cleanup audit failed.")
    messages.append("Zero-duration diagnostic cleanup passed")

    with tempfile.TemporaryDirectory(prefix="banjofy_lab_016_audit_") as temp:
        folder = Path(temp)
        result = AnalysisResult(
            source_audio="audit.wav",
            model=MODEL_NAME,
            analysis_version=ANALYSIS_VERSION,
            key=key,
            key_confidence=0.90,
            bpm=120.0, raw_bpm=120.0, practice_bpm=120.0, meter="Unknown", meter_confidence=0.0,
            beat_count=len(beats), main_chords=["B", "A", "E"],
            beginner_chords=["B", "A", "E"], intermediate_chords=["B", "A", "E"],
            professional_chords=["B", "A", "E"], musical_end_s=12.0,
            raw_segment_count=len(sample),
            cleaned_segment_count=len(aligned),
            duration_s=12.0,
            segments=aligned,
            diagnostics=["Internal release audit"],
            detector_disagreements=[],
            chord_importance=chord_importance_table(aligned),
        )
        save_reports(result, folder, "audit")
        expected = (
            folder / "audit_dedicated_chord_report.txt",
            folder / "audit_dedicated_chords.csv",
            folder / "audit_dedicated_chords.json",
        )
        if not all(path.exists() and path.stat().st_size > 0 for path in expected):
            raise RuntimeError("Report generation audit failed.")
    messages.append("Report generation passed")

    return messages


def main() -> None:
    ChordLabWindow().run()


if __name__ == "__main__":
    main()
