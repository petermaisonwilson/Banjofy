from __future__ import annotations

import bisect
import json
import os
import queue
import threading
import time
import traceback
import webbrowser
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import structure_engine

APP_TITLE = "Banjofy Song Analysis Laboratory 024 — Automated Truth Validation"
SETTINGS_FILENAME = "song_analysis_lab_settings.json"


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    folder = base / "Banjofy" / "SongAnalysisLab"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def load_library_setting(path: Path | None = None) -> str:
    target = path or settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("library_root") or "")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} is not a valid JSON object")
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".working")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def resolve_audio(record: dict, record_path: Path) -> Path | None:
    raw = record.get("practice_audio_path")
    if not raw:
        return None
    candidate = Path(str(raw)).expanduser()
    if candidate.is_file():
        return candidate
    library_root = record_path.parents[2]
    recovered = library_root / "Media" / "Audio" / candidate.name
    return recovered if recovered.is_file() else None


def resolve_analysis(record: dict, record_path: Path) -> Path | None:
    raw = record.get("analysis_path")
    if raw:
        candidate = Path(str(raw)).expanduser()
        if candidate.is_file():
            return candidate
    library_root = record_path.parents[2]
    song_id = str(record.get("song_id") or record_path.stem)
    recovered = library_root / "Analysis" / song_id / "song_analysis.json"
    return recovered if recovered.is_file() else None


def discover_analysed_songs(library_root: Path) -> list[dict]:
    folder = library_root / "Library" / "Songs"
    if not folder.is_dir():
        return []
    songs = []
    for record_path in sorted(folder.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            record = read_json(record_path)
            audio = resolve_audio(record, record_path)
            analysis = resolve_analysis(record, record_path)
        except Exception:
            continue
        if audio is None or analysis is None:
            continue
        songs.append({
            "record_path": record_path,
            "record": record,
            "audio_path": audio,
            "analysis_path": analysis,
            "song_id": str(record.get("song_id") or record_path.stem),
            "title": str(record.get("title_requested") or audio.stem),
            "structure_status": str(record.get("structure_status") or "not_started"),
        })
    return songs




PULSE_MODES = {
    "detected": "Detected pulse",
    "half_a": "Half pulse A",
    "half_b": "Half pulse B",
}


def detected_beat_times_from_analysis(analysis: dict) -> list[float]:
    raw = analysis.get("detected_beat_times")
    if not isinstance(raw, list) or not raw:
        raw = analysis.get("beat_times", [])
    return [
        float(value)
        for value in raw
        if isinstance(value, (int, float))
    ]


def pulse_times_for_mode(analysis: dict, pulse_mode: str) -> list[float]:
    detected = detected_beat_times_from_analysis(analysis)
    if not detected:
        raise RuntimeError("The saved analysis contains no detected beat times.")

    mode = str(pulse_mode)
    if mode == "detected":
        return detected
    if mode == "half_a":
        result = detected[0::2]
    elif mode == "half_b":
        result = detected[1::2]
    else:
        raise RuntimeError(f"Unknown pulse interpretation: {mode}")

    if len(result) < 8:
        raise RuntimeError(
            "The selected half-pulse interpretation contains too few beats."
        )
    return result


def build_confirmed_alternative_grid_updates(
    record: dict,
    analysis: dict,
    method: str,
    confirmed_at: str,
) -> tuple[dict, dict, dict]:
    """Make one generated alternative grid the active beat source."""
    candidates = analysis.get("alternative_beat_grids")
    if not isinstance(candidates, dict):
        raise RuntimeError("Create the alternative beat grids before confirming one.")
    candidate = candidates.get(str(method))
    if not isinstance(candidate, dict):
        raise RuntimeError("The selected alternative beat grid is unavailable.")
    beat_times = [
        float(value) for value in candidate.get("beat_times", [])
        if isinstance(value, (int, float))
    ]
    if len(beat_times) < 8:
        raise RuntimeError("The selected alternative beat grid contains too few beats.")
    segments = analysis.get("segments", [])
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("The saved analysis contains no chord segments.")

    meter = str(analysis.get("confirmed_meter") or analysis.get("meter") or "")
    beats_per_bar = 3 if meter == "3/4" else 4 if meter == "4/4" else 0
    if beats_per_bar not in (3, 4):
        raise RuntimeError("Confirm 3/4 or 4/4 before confirming the beat grid.")

    original_detected = detected_beat_times_from_analysis(analysis)
    phase_index = int(analysis.get("detected_first_downbeat_beat_index", 0)) % beats_per_bar
    beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
        beat_times, beats_per_bar, phase_index, segments
    )
    label = str(candidate.get("label") or method)
    fields = {
        "detected_beat_times": original_detected,
        "confirmed_beat_grid_method": str(method),
        "confirmed_beat_grid_label": label,
        "beat_grid_confirmation_status": "confirmed",
        "beat_grid_confirmed_by": "manual_audition",
        "beat_grid_confirmed_at": confirmed_at,
        "beat_grid_source_bpm": float(candidate.get("bpm") or 0.0),
        "beat_times": beat_times,
        "beat_count": len(beat_times),
        "pulse_interpretation": "alternative_grid",
        "pulse_interpretation_label": label,
        "pulse_confirmation_status": "confirmed",
        "pulse_confirmed_by": "manual_audition",
        "pulse_confirmed_at": confirmed_at,
        "first_downbeat_beat_index": phase_index,
        "downbeat_phase_status": "unconfirmed",
    }
    phase_keys=(
        "confirmed_phase_number","confirmed_phase_offset",
        "confirmed_first_downbeat_beat_index","downbeat_phase_confirmed_by",
        "downbeat_phase_confirmed_at",
    )
    updated_analysis=dict(analysis)
    for key in phase_keys: updated_analysis.pop(key,None)
    updated_analysis.update(fields)
    updated_analysis.update({
        "downbeat_times":downbeats,"bar_start_times":downbeats,
        "bar_count":len(bars),"beat_grid":beat_grid,"bars":bars,
        "bar_aligned_chords":aligned,
    })
    updated_record=dict(record)
    for key in phase_keys: updated_record.pop(key,None)
    for key,value in fields.items():
        if key != "beat_times": updated_record[key]=value
    summary=dict(updated_record.get("structure_summary") or {})
    for key in phase_keys: summary.pop(key,None)
    summary.update({
        "confirmed_beat_grid_method":str(method),
        "confirmed_beat_grid_label":label,
        "beat_grid_confirmation_status":"confirmed",
        "beat_grid_confirmed_by":"manual_audition",
        "beat_grid_confirmed_at":confirmed_at,
        "beat_count":len(beat_times),
        "first_downbeat_beat_index":phase_index,
        "downbeat_phase_status":"unconfirmed",
        "downbeat_times":downbeats,"bar_start_times":downbeats,
        "bar_count":len(bars),
    })
    updated_record["structure_summary"]=summary
    structure_updates={
        **fields,"downbeat_times":downbeats,"bar_start_times":downbeats,
        "bar_count":len(bars),"beat_grid":beat_grid,"bars":bars,
        "bar_aligned_chords":aligned,
        "remove_phase_confirmation_keys":list(phase_keys),
    }
    return updated_record,updated_analysis,structure_updates


def build_confirmed_pulse_updates(
    record: dict,
    analysis: dict,
    pulse_mode: str,
    confirmed_at: str,
) -> tuple[dict, dict, dict]:
    """Apply a manual pulse interpretation while retaining detected beats."""
    mode = str(pulse_mode)
    if mode not in PULSE_MODES:
        raise RuntimeError("Choose detected pulse, half pulse A or half pulse B.")

    effective_beats = pulse_times_for_mode(analysis, mode)
    detected_beats = detected_beat_times_from_analysis(analysis)
    segments = analysis.get("segments", [])
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("The saved analysis contains no chord segments.")

    meter = str(analysis.get("confirmed_meter") or analysis.get("meter") or "")
    beats_per_bar = 3 if meter == "3/4" else 4 if meter == "4/4" else 0
    if beats_per_bar not in (3, 4):
        raise RuntimeError("Confirm 3/4 or 4/4 before confirming a pulse.")

    detected_index = int(
        analysis.get(
            "detected_first_downbeat_beat_index",
            analysis.get("first_downbeat_beat_index", 0),
        )
    ) % beats_per_bar

    beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
        effective_beats,
        beats_per_bar,
        detected_index,
        segments,
    )

    pulse_fields = {
        "detected_beat_times": detected_beats,
        "pulse_interpretation": mode,
        "pulse_interpretation_label": PULSE_MODES[mode],
        "pulse_confirmation_status": "confirmed",
        "pulse_confirmed_by": "manual_audition",
        "pulse_confirmed_at": confirmed_at,
        "beat_times": effective_beats,
        "beat_count": len(effective_beats),
        "first_downbeat_beat_index": detected_index,
        "downbeat_phase_status": "unconfirmed",
    }

    phase_keys = (
        "confirmed_phase_number",
        "confirmed_phase_offset",
        "confirmed_first_downbeat_beat_index",
        "downbeat_phase_confirmed_by",
        "downbeat_phase_confirmed_at",
    )

    updated_analysis = dict(analysis)
    for key in phase_keys:
        updated_analysis.pop(key, None)
    updated_analysis.update(pulse_fields)
    updated_analysis["downbeat_times"] = downbeats
    updated_analysis["bar_start_times"] = downbeats
    updated_analysis["bar_count"] = len(bars)
    updated_analysis["beat_grid"] = beat_grid
    updated_analysis["bars"] = bars
    updated_analysis["bar_aligned_chords"] = aligned

    updated_record = dict(record)
    for key in phase_keys:
        updated_record.pop(key, None)
    for key, value in pulse_fields.items():
        if key not in {"beat_times"}:
            updated_record[key] = value
    summary = dict(updated_record.get("structure_summary") or {})
    for key in phase_keys:
        summary.pop(key, None)
    summary.update({
        "pulse_interpretation": mode,
        "pulse_interpretation_label": PULSE_MODES[mode],
        "pulse_confirmation_status": "confirmed",
        "pulse_confirmed_by": "manual_audition",
        "pulse_confirmed_at": confirmed_at,
        "beat_count": len(effective_beats),
        "first_downbeat_beat_index": detected_index,
        "downbeat_phase_status": "unconfirmed",
        "downbeat_times": downbeats,
        "bar_start_times": downbeats,
        "bar_count": len(bars),
    })
    updated_record["structure_summary"] = summary

    structure_updates = {
        **pulse_fields,
        "downbeat_times": downbeats,
        "bar_start_times": downbeats,
        "bar_count": len(bars),
        "beat_grid": beat_grid,
        "bars": bars,
        "bar_aligned_chords": aligned,
        "remove_phase_confirmation_keys": list(phase_keys),
    }

    return updated_record, updated_analysis, structure_updates


def create_phase_auditions(
    audio_path: Path,
    analysis: dict,
    folder: Path,
) -> list[str]:
    """Create the exact phase set required by the effective meter and pulse."""
    beat_times = [
        float(value)
        for value in analysis.get("beat_times", [])
        if isinstance(value, (int, float))
    ]
    if not beat_times:
        raise RuntimeError("The saved analysis contains no effective beat times.")

    meter = str(analysis.get("confirmed_meter") or analysis.get("meter") or "")
    beats_per_bar = 3 if meter == "3/4" else 4 if meter == "4/4" else 0
    if beats_per_bar not in (3, 4):
        raise RuntimeError("The song must have an active 3/4 or 4/4 meter.")

    detected_index = int(
        analysis.get(
            "detected_first_downbeat_beat_index",
            analysis.get("first_downbeat_beat_index", 0),
        )
    ) % beats_per_bar

    phase_paths: list[str] = []
    for phase_offset in range(beats_per_bar):
        effective = (detected_index + phase_offset) % beats_per_bar
        phase_downbeats = [
            float(beat_times[index])
            for index in range(effective, len(beat_times), beats_per_bar)
        ]
        phase_path = folder / f"audible_phase_{phase_offset + 1}.wav"
        structure_engine.create_audible_bar_check(
            audio_path,
            beat_times,
            phase_downbeats,
            phase_path,
        )
        if not phase_path.is_file() or phase_path.stat().st_size == 0:
            raise RuntimeError(
                f"Phase audition file {phase_offset + 1} was not created."
            )
        phase_paths.append(str(phase_path))

    for stale_number in range(beats_per_bar + 1, 5):
        stale = folder / f"audible_phase_{stale_number}.wav"
        stale.unlink(missing_ok=True)

    return phase_paths


def persist_phase_audition_paths(
    record_path: Path,
    analysis_path: Path,
    phase_paths: list[str],
) -> None:
    record = read_json(record_path)
    analysis = read_json(analysis_path)
    record["downbeat_phase_audition_paths"] = phase_paths
    analysis["downbeat_phase_audition_paths"] = phase_paths

    structure_raw = record.get("structure_path")
    structure_path = (
        Path(str(structure_raw))
        if structure_raw
        else analysis_path.parent / "song_structure.json"
    )
    structure = read_json(structure_path) if structure_path.is_file() else {}
    structure["downbeat_phase_audition_paths"] = phase_paths

    write_json_atomic(structure_path, structure)
    write_json_atomic(record_path, record)
    write_json_atomic(analysis_path, analysis)


def build_confirmed_meter_updates(
    record: dict,
    analysis: dict,
    confirmed_meter: str,
    confirmed_at: str,
) -> tuple[dict, dict, dict]:
    """Return JSON updates for an explicitly confirmed 3/4 or 4/4 meter.

    Detector results remain recorded. Beat times, chord segments, BPM and chord
    timing are preserved. The meter change resets phase confirmation because the
    number and meaning of possible phases has changed.
    """
    meter = str(confirmed_meter)
    mapping = {"3/4": 3, "4/4": 4}
    if meter not in mapping:
        raise RuntimeError("Only 3/4 and 4/4 can be confirmed.")

    beat_times = [
        float(value)
        for value in analysis.get("beat_times", [])
        if isinstance(value, (int, float))
    ]
    segments = analysis.get("segments", [])
    if not beat_times:
        raise RuntimeError("The saved analysis contains no beat times.")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("The saved analysis contains no chord segments.")

    beats_per_bar = mapping[meter]
    detected_meter = str(
        analysis.get("detected_meter_candidate")
        or analysis.get("best_meter_candidate")
        or analysis.get("meter")
        or "Uncertain"
    )
    detected_index = int(
        analysis.get(
            "detected_first_downbeat_beat_index",
            analysis.get("first_downbeat_beat_index", 0),
        )
    ) % beats_per_bar

    beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
        beat_times,
        beats_per_bar,
        detected_index,
        segments,
    )

    meter_fields = {
        "detected_meter_candidate": detected_meter,
        "confirmed_meter": meter,
        "meter_confirmation_status": "confirmed",
        "meter_confirmed_by": "manual_audition",
        "meter_confirmed_at": confirmed_at,
        "meter": meter,
        "meter_status": "confirmed",
        "beats_per_bar": beats_per_bar,
        "first_downbeat_beat_index": detected_index,
        "detected_first_downbeat_beat_index": detected_index,
        "downbeat_phase_status": "unconfirmed",
    }

    # Old phase confirmation is no longer valid after a meter change.
    phase_keys = (
        "confirmed_phase_number",
        "confirmed_phase_offset",
        "confirmed_first_downbeat_beat_index",
        "downbeat_phase_confirmed_by",
        "downbeat_phase_confirmed_at",
    )

    updated_analysis = dict(analysis)
    for key in phase_keys:
        updated_analysis.pop(key, None)
    updated_analysis.update(meter_fields)
    updated_analysis["downbeat_times"] = downbeats
    updated_analysis["bar_start_times"] = downbeats
    updated_analysis["bar_count"] = len(bars)
    updated_analysis["beat_grid"] = beat_grid
    updated_analysis["bars"] = bars
    updated_analysis["bar_aligned_chords"] = aligned

    updated_record = dict(record)
    for key in phase_keys:
        updated_record.pop(key, None)
    updated_record.update(meter_fields)
    summary = dict(updated_record.get("structure_summary") or {})
    for key in phase_keys:
        summary.pop(key, None)
    summary.update(meter_fields)
    summary["downbeat_times"] = downbeats
    summary["bar_start_times"] = downbeats
    summary["bar_count"] = len(bars)
    updated_record["structure_summary"] = summary

    structure_updates = dict(meter_fields)
    structure_updates["downbeat_times"] = downbeats
    structure_updates["bar_start_times"] = downbeats
    structure_updates["bar_count"] = len(bars)
    structure_updates["beat_grid"] = beat_grid
    structure_updates["bars"] = bars
    structure_updates["bar_aligned_chords"] = aligned
    structure_updates["remove_phase_confirmation_keys"] = list(phase_keys)

    return updated_record, updated_analysis, structure_updates


def build_confirmed_phase_updates(
    record: dict,
    analysis: dict,
    selected_phase_number: int,
    confirmed_at: str,
) -> tuple[dict, dict, dict]:
    """Return updated record, analysis and structure fields for a confirmed phase.

    The detector's original phase is retained separately. Only bar grouping and
    bar-aligned chord data are rebuilt; chord segments, beat times, BPM and meter
    candidate remain unchanged.
    """
    beat_times = [
        float(value)
        for value in analysis.get("beat_times", [])
        if isinstance(value, (int, float))
    ]
    segments = analysis.get("segments", [])
    if not beat_times:
        raise RuntimeError("The saved analysis contains no beat times.")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("The saved analysis contains no chord segments.")

    beats_per_bar = int(analysis.get("beats_per_bar") or 0)
    if beats_per_bar not in (3, 4):
        raise RuntimeError("Only confirmed 3/4 and 4/4 phases are supported.")

    phase_number = int(selected_phase_number)
    if not 1 <= phase_number <= beats_per_bar:
        raise RuntimeError(
            f"Phase {phase_number} is invalid for {beats_per_bar} beats per bar."
        )

    detected_index = int(
        analysis.get(
            "detected_first_downbeat_beat_index",
            analysis.get("first_downbeat_beat_index", 0),
        )
    ) % beats_per_bar
    phase_offset = phase_number - 1
    confirmed_index = (detected_index + phase_offset) % beats_per_bar

    beat_grid, bars, aligned, downbeats = structure_engine.build_bar_grid(
        beat_times,
        beats_per_bar,
        confirmed_index,
        segments,
    )

    confirmation = {
        "downbeat_phase_status": "confirmed",
        "confirmed_phase_number": phase_number,
        "confirmed_phase_offset": phase_offset,
        "detected_first_downbeat_beat_index": detected_index,
        "confirmed_first_downbeat_beat_index": confirmed_index,
        "downbeat_phase_confirmed_by": "manual_audition",
        "downbeat_phase_confirmed_at": confirmed_at,
    }

    updated_analysis = dict(analysis)
    updated_analysis.update(confirmation)
    updated_analysis["first_downbeat_beat_index"] = confirmed_index
    updated_analysis["downbeat_times"] = downbeats
    updated_analysis["bar_start_times"] = downbeats
    updated_analysis["bar_count"] = len(bars)
    updated_analysis["beat_grid"] = beat_grid
    updated_analysis["bars"] = bars
    updated_analysis["bar_aligned_chords"] = aligned

    updated_record = dict(record)
    updated_record.update(confirmation)
    summary = dict(updated_record.get("structure_summary") or {})
    summary.update(confirmation)
    summary["first_downbeat_beat_index"] = confirmed_index
    summary["downbeat_times"] = downbeats
    summary["bar_start_times"] = downbeats
    summary["bar_count"] = len(bars)
    updated_record["structure_summary"] = summary

    structure_updates = dict(confirmation)
    structure_updates["first_downbeat_beat_index"] = confirmed_index
    structure_updates["downbeat_times"] = downbeats
    structure_updates["bar_start_times"] = downbeats
    structure_updates["bar_count"] = len(bars)
    structure_updates["beat_grid"] = beat_grid
    structure_updates["bars"] = bars
    structure_updates["bar_aligned_chords"] = aligned

    return updated_record, updated_analysis, structure_updates


def commit_structure(
    library_root: Path,
    record_path: Path,
    analysis_path: Path,
    result: structure_engine.StructureResult,
) -> tuple[Path, Path, Path, Path]:
    record = read_json(record_path)
    analysis = read_json(analysis_path)
    song_id = str(record.get("song_id") or record_path.stem)
    folder = library_root / "Analysis" / song_id
    folder.mkdir(parents=True, exist_ok=True)

    audible_check_path = folder / "audible_bar_check.wav"
    structure_engine.create_audible_bar_check(
        Path(result.source_audio),
        result.beat_times,
        result.downbeat_times,
        audible_check_path,
    )
    if not audible_check_path.is_file() or audible_check_path.stat().st_size == 0:
        raise RuntimeError("The audible bar-check file was not created successfully.")

    # Create one full 180-second audition file for each possible phase.
    # Chord times and beat spacing are unchanged; only the strong downbeat click moves.
    phase_check_paths: list[str] = []
    beats_per_bar = int(result.beats_per_bar)
    for phase_offset in range(beats_per_bar):
        effective_phase = (
            int(result.first_downbeat_beat_index) + phase_offset
        ) % beats_per_bar
        phase_downbeats = [
            float(result.beat_times[index])
            for index in range(effective_phase, len(result.beat_times), beats_per_bar)
        ]
        phase_path = folder / f"audible_phase_{phase_offset + 1}.wav"
        structure_engine.create_audible_bar_check(
            Path(result.source_audio),
            result.beat_times,
            phase_downbeats,
            phase_path,
        )
        if not phase_path.is_file() or phase_path.stat().st_size == 0:
            raise RuntimeError(
                f"Downbeat phase audition file {phase_offset + 1} was not created."
            )
        phase_check_paths.append(str(phase_path))

    structure_path = folder / "song_structure.json"
    payload = asdict(result)
    payload["integration_laboratory"] = APP_TITLE
    payload["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    payload["audible_bar_check_path"] = str(audible_check_path)
    payload["downbeat_phase_audition_paths"] = phase_check_paths
    payload["detected_first_downbeat_beat_index"] = result.first_downbeat_beat_index
    payload["downbeat_phase_status"] = "unconfirmed"
    payload["detected_meter_candidate"] = result.best_meter_candidate
    payload["meter_confirmation_status"] = "unconfirmed"

    summary = {
        "meter": result.meter,
        "meter_status": result.meter_status,
        "best_meter_candidate": result.best_meter_candidate,
        "detected_meter_candidate": result.best_meter_candidate,
        "meter_confirmation_status": "unconfirmed",
        "meter_confidence": round(float(result.meter_confidence), 4),
        "full_track_meter_confidence": round(float(result.full_track_meter_confidence), 4),
        "rhythmic_window_candidate": result.rhythmic_window_candidate,
        "rhythmic_window_meter_confidence": round(float(result.rhythmic_window_meter_confidence), 4),
        "meter_candidate_agreement": bool(result.meter_candidate_agreement),
        "rhythmic_window_start_beat": int(result.rhythmic_window_start_beat),
        "rhythmic_window_end_beat": int(result.rhythmic_window_end_beat),
        "rhythmic_window_start_s": float(result.rhythmic_window_start_s),
        "rhythmic_window_end_s": float(result.rhythmic_window_end_s),
        "beats_per_bar": int(result.beats_per_bar),
        "first_downbeat_beat_index": int(result.first_downbeat_beat_index),
        "detected_first_downbeat_beat_index": int(result.first_downbeat_beat_index),
        "downbeat_phase_status": "unconfirmed",
        "beat_count": int(result.beat_count),
        "bar_count": int(result.bar_count),
        "bar_start_times": list(result.bar_start_times),
        "downbeat_times": list(result.downbeat_times),
    }

    updated_record = dict(record)
    updated_record["structure_status"] = "completed"
    updated_record["structure_version"] = result.structure_version
    updated_record["structure_path"] = str(structure_path)
    updated_record["structure_completed_at"] = payload["completed_at"]
    updated_record["structure_summary"] = summary
    updated_record["detected_first_downbeat_beat_index"] = result.first_downbeat_beat_index
    updated_record["downbeat_phase_status"] = "unconfirmed"
    updated_record["detected_meter_candidate"] = result.best_meter_candidate
    updated_record["meter_confirmation_status"] = "unconfirmed"
    updated_record["audible_bar_check_path"] = str(audible_check_path)
    updated_record["downbeat_phase_audition_paths"] = phase_check_paths

    updated_analysis = dict(analysis)
    updated_analysis["meter"] = result.meter
    updated_analysis["meter_status"] = result.meter_status
    updated_analysis["best_meter_candidate"] = result.best_meter_candidate
    updated_analysis["detected_meter_candidate"] = result.best_meter_candidate
    updated_analysis["meter_confirmation_status"] = "unconfirmed"
    updated_analysis["meter_confidence"] = result.meter_confidence
    updated_analysis["full_track_meter_confidence"] = result.full_track_meter_confidence
    updated_analysis["rhythmic_window_candidate"] = result.rhythmic_window_candidate
    updated_analysis["rhythmic_window_meter_confidence"] = result.rhythmic_window_meter_confidence
    updated_analysis["meter_candidate_agreement"] = result.meter_candidate_agreement
    updated_analysis["rhythmic_window_start_beat"] = result.rhythmic_window_start_beat
    updated_analysis["rhythmic_window_end_beat"] = result.rhythmic_window_end_beat
    updated_analysis["rhythmic_window_start_s"] = result.rhythmic_window_start_s
    updated_analysis["rhythmic_window_end_s"] = result.rhythmic_window_end_s
    updated_analysis["beats_per_bar"] = result.beats_per_bar
    updated_analysis["detected_first_downbeat_beat_index"] = result.first_downbeat_beat_index
    updated_analysis["first_downbeat_beat_index"] = result.first_downbeat_beat_index
    updated_analysis["downbeat_phase_status"] = "unconfirmed"
    updated_analysis["detected_beat_times"] = result.beat_times
    updated_analysis["pulse_interpretation"] = "detected"
    updated_analysis["pulse_confirmation_status"] = "unconfirmed"
    updated_analysis["beat_times"] = result.beat_times
    updated_analysis["downbeat_times"] = result.downbeat_times
    updated_analysis["bar_start_times"] = result.bar_start_times
    updated_analysis["bar_count"] = result.bar_count
    updated_analysis["beat_grid"] = result.beat_grid
    updated_analysis["bars"] = result.bars
    updated_analysis["bar_aligned_chords"] = result.bar_aligned_chords
    updated_analysis["structure_version"] = result.structure_version
    updated_analysis["audible_bar_check_path"] = str(audible_check_path)
    updated_analysis["downbeat_phase_audition_paths"] = phase_check_paths

    write_json_atomic(structure_path, payload)
    write_json_atomic(record_path, updated_record)
    write_json_atomic(analysis_path, updated_analysis)

    return structure_path, record_path, analysis_path, audible_check_path


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1550x820")
        self.minsize(880, 650)
        # Tk variables must exist before any persisted settings are read.
        self.library_var = tk.StringVar(master=self, value="")
        self.status_var = tk.StringVar(
            master=self,
            value="Choose the Library that passed Song Analysis Laboratory 001",
        )
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.songs: list[dict] = []
        self.selected_song: dict | None = None
        self.visual_window: tk.Toplevel | None = None
        self.visual_started_at: float | None = None
        self.visual_beat_times: list[float] = []
        self.visual_downbeat_times: list[float] = []
        self.visual_chord_segments: list[dict] = []
        self.visual_beats_per_bar: int = 4
        self.visual_duration: float = 0.0
        self.visual_phase_offset: int = 0
        self.visual_base_first_downbeat_index: int = 0
        self.visual_phase_paths: list[Path] = []
        self.visual_phase_buttons: list[ttk.Button] = []
        self.visual_meter_var: tk.StringVar | None = None
        self.visual_pulse_var: tk.StringVar | None = None
        self.alt_window: tk.Toplevel | None = None
        self.alt_started_at: float | None = None
        self.alt_candidates: dict[str, dict] = {}
        self.alt_selected_method: str = "standard"
        self.alt_chord_segments: list[dict] = []
        self._load_settings()
        self._build_ui()
        self.after(150, self._poll)

        saved_library = self.library_var.get().strip()
        startup_probe = bool(os.environ.get("BANJOFY_STARTUP_PROBE_FILE", "").strip())
        if saved_library and Path(saved_library).is_dir() and not startup_probe:
            self.after(300, self._refresh)
        elif saved_library and not Path(saved_library).is_dir():
            self.status_var.set(
                "The remembered Library folder is currently unavailable. "
                "Choose the correct top-level Library folder."
            )

    def _load_settings(self) -> None:
        # This method is deliberately safe when a settings file already exists.
        # GitHub now proves this exact persisted-settings startup path.
        library_value = load_library_setting()
        if hasattr(self, "library_var"):
            self.library_var.set(library_value)

    def _save_settings(self) -> None:
        write_json_atomic(settings_path(), {"library_root": self.library_var.get().strip()})

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "This build leaves the scorer untouched and compares the current automatic timing winner against each verified manual truth record."
            ),
            wraplength=950,
        ).pack(anchor="w", pady=(5, 12))

        library = ttk.LabelFrame(outer, text="1. Open the analysed Banjofy Library")
        library.pack(fill="x", pady=5)
        ttk.Entry(library, textvariable=self.library_var).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Button(library, text="Choose Library folder", command=self._choose).grid(row=0, column=1, padx=10, pady=8)
        ttk.Button(library, text="Refresh songs", command=self._refresh).grid(row=0, column=2, padx=(0, 10), pady=8)
        library.columnconfigure(0, weight=1)

        songs = ttk.LabelFrame(outer, text="2. Select a song that passed Laboratory 001")
        songs.pack(fill="both", expand=True, pady=5)
        columns = ("title", "analysis", "structure", "audio")
        self.tree = ttk.Treeview(songs, columns=columns, show="headings", height=10, selectmode="browse")
        for key, title, width in (
            ("title", "Song", 330),
            ("analysis", "Chord analysis", 120),
            ("structure", "Structure", 110),
            ("audio", "Practice audio", 380),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w" if key in {"title", "audio"} else "center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._selected)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        self.run_button = ttk.Button(
            controls, text="Detect 3/4 or 4/4 and Create Audible Check",
            command=self._start, state="disabled",
        )
        self.run_button.pack(side="left")
        self.play_button = ttk.Button(
            controls,
            text="Play 180-Second Chord + Downbeat Phase Check",
            command=self._play_audible_check,
            state="disabled",
        )
        self.play_button.pack(side="left", padx=8)
        self.alt_create_button = ttk.Button(
            controls,
            text="Create Alternative Beat Grids",
            command=self._create_alternative_beat_grids,
            state="disabled",
        )
        self.alt_create_button.pack(side="left", padx=8)
        self.alt_play_button = ttk.Button(
            controls,
            text="Play Alternative Beat Grids",
            command=self._play_alternative_beat_grids,
            state="disabled",
        )
        self.alt_play_button.pack(side="left", padx=4)
        self.recommend_button = ttk.Button(
            controls,
            text="Recommend Meter, Beat Grid and Phase",
            command=self._recommend_timing,
            state="disabled",
        )
        self.recommend_button.pack(side="left", padx=8)
        self.evidence_button = ttk.Button(
            controls,
            text="Create Timing Evidence Report",
            command=self._create_timing_evidence_report,
            state="disabled",
        )
        self.evidence_button.pack(side="left", padx=8)
        self.truth_button = ttk.Button(
            controls,
            text="Review / Save Verified Truth",
            command=self._recover_manual_truth,
            state="disabled",
        )
        self.truth_button.pack(side="left", padx=8)
        self.validate_button = ttk.Button(
            controls,
            text="Validate Automatic Timing",
            command=self._validate_automatic_timing,
            state="disabled",
        )
        self.validate_button.pack(side="left", padx=8)
        ttk.Button(controls, text="Open Analysis Folder", command=self._open_folder).pack(side="right")

        status = ttk.LabelFrame(outer, text="Structure-analysis status")
        status.pack(fill="both", expand=True, pady=5)
        ttk.Label(status, textvariable=self.status_var, wraplength=950).pack(anchor="w", padx=10, pady=8)
        self.output = tk.Text(status, height=13, state="disabled", wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _choose(self) -> None:
        chosen = filedialog.askdirectory(title="Choose the analysed Banjofy Library root")
        if chosen:
            self.library_var.set(chosen)
            self._save_settings()
            self._refresh()

    def _library_root(self) -> Path | None:
        text = self.library_var.get().strip()
        if not text:
            messagebox.showerror(APP_TITLE, "Choose the Banjofy Library root first.")
            return None
        root = Path(text)
        if not root.is_dir():
            messagebox.showerror(APP_TITLE, f"The selected folder does not exist:\n{root}")
            return None
        return root

    def _refresh(self) -> None:
        root = self._library_root()
        if root is None:
            return
        self.songs = discover_analysed_songs(root)
        self.selected_song = None
        self.run_button.configure(state="disabled")
        self.alt_create_button.configure(state="disabled")
        self.alt_play_button.configure(state="disabled")
        self.evidence_button.configure(state="disabled")
        self.truth_button.configure(state="disabled")
        self.validate_button.configure(state="disabled")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, song in enumerate(self.songs):
            self.tree.insert("", "end", iid=str(index), values=(
                song["title"],
                song["record"].get("analysis_status", "unknown"),
                song["structure_status"],
                song["audio_path"].name,
            ))
        self.status_var.set(
            f"Found {len(self.songs)} song(s) with both Practice audio and Laboratory 001 analysis"
            if self.songs else
            "No song with both Practice audio and Laboratory 001 analysis was found"
        )

    def _selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            self.selected_song = None
            self.run_button.configure(state="disabled")
            self.alt_create_button.configure(state="disabled")
            self.alt_play_button.configure(state="disabled")
            self.recommend_button.configure(state="disabled")
            self.evidence_button.configure(state="disabled")
            self.truth_button.configure(state="disabled")
            self.validate_button.configure(state="disabled")
            return
        self.selected_song = self.songs[int(selected[0])]
        self.run_button.configure(state="normal")
        self.alt_create_button.configure(state="normal")

        existing_check = self.selected_song["record"].get("audible_bar_check_path")
        if existing_check and Path(str(existing_check)).is_file():
            self.play_button.configure(state="normal")
        else:
            self.play_button.configure(state="disabled")

        analysis_now = read_json(self.selected_song["analysis_path"])
        alt = analysis_now.get("alternative_beat_grids")
        valid_alt = isinstance(alt, dict) and any(
            isinstance(item, dict)
            and item.get("audible_path")
            and Path(str(item.get("audible_path"))).is_file()
            for item in alt.values()
        )
        self.alt_play_button.configure(state="normal" if valid_alt else "disabled")
        self.recommend_button.configure(state="normal" if valid_alt else "disabled")
        self.evidence_button.configure(state="normal" if valid_alt else "disabled")
        self.truth_button.configure(state="normal")
        self.validate_button.configure(state="normal")
        self.status_var.set(f"Selected: {self.selected_song['title']}")

    def _start(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        root = self._library_root()
        if root is None:
            return

        song = self.selected_song

        current_record = read_json(song["record_path"])
        current_analysis = read_json(song["analysis_path"])
        protected = any(
            str(current_analysis.get(key) or current_record.get(key) or "").lower()
            == "confirmed"
            for key in (
                "meter_confirmation_status",
                "pulse_confirmation_status",
                "downbeat_phase_status",
            )
        )
        if protected:
            reset = messagebox.askyesno(
                APP_TITLE,
                (
                    "This song contains manually confirmed timing.\n\n"
                    "Re-running automatic structure analysis will reset the confirmed "
                    "meter, pulse and phase for this song.\n\n"
                    "Reset confirmed timing and continue?"
                ),
            )
            if not reset:
                self.status_var.set(
                    "Automatic re-analysis cancelled; confirmed timing was preserved."
                )
                return

        self.run_button.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._append(f"Existing Library JSON filename: {song['record_path'].name}")
        self._append("That filename will remain unchanged; its contents will be updated.")

        def worker() -> None:
            try:
                analysis = read_json(song["analysis_path"])
                segments = analysis.get("segments")
                if not isinstance(segments, list) or not segments:
                    raise RuntimeError("The Laboratory 001 song_analysis.json contains no chord segments.")
                result = structure_engine.analyse_structure(
                    song["audio_path"], segments,
                    lambda text: self.messages.put(("status", text)),
                )
                paths = commit_structure(
                    root, song["record_path"], song["analysis_path"], result
                )
                self.messages.put(("done", {"result": result, "paths": paths}))
            except Exception as exc:
                self.messages.put(("error", f"{exc}\n\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status_var.set(str(payload))
                self._append(str(payload))
            elif kind == "error":
                self.run_button.configure(state="normal")
                self.status_var.set("Structure analysis failed")
                self._append(str(payload))
                messagebox.showerror(APP_TITLE, "Structure analysis failed. The exact error is shown in the window.")
            elif kind == "alternative_error":
                self.alt_create_button.configure(state="normal")
                self.status_var.set("Alternative beat-grid analysis failed")
                self._append(str(payload))
                messagebox.showerror(APP_TITLE, "Alternative beat-grid analysis failed. The exact error is shown in the window.")
            elif kind == "recommendation_done":
                self.recommend_button.configure(state="normal")
                method_label = str(payload.get("recommended_beat_grid_label") or payload.get("recommended_beat_grid_method"))
                meter = str(payload.get("recommended_meter"))
                phase = int(payload.get("recommended_phase_number") or 1)
                confidence = float(payload.get("confidence_percent") or 0.0)
                self.status_var.set(
                    f"Recommendation: {meter}, {method_label}, Phase {phase} ({confidence:.0f}% confidence)"
                )
                self._append(
                    f"Recommended {meter} · {method_label} · Phase {phase} · {confidence:.1f}% confidence."
                )
                messagebox.showinfo(
                    APP_TITLE,
                    (
                        f"Build 024 recommendation\n\n"
                        f"Meter: {meter}\n"
                        f"Beat grid: {method_label}\n"
                        f"Downbeat: Phase {phase}\n"
                        f"Confidence: {confidence:.1f}%\n\n"
                        "This is a laboratory recommendation only. It has not changed the saved timing."
                    ),
                )
            elif kind == "recommendation_error":
                self.recommend_button.configure(state="normal")
                self.status_var.set("Automatic timing recommendation failed")
                self._append(str(payload))
                messagebox.showerror(APP_TITLE, "Automatic recommendation failed. The exact error is shown in the window.")
            elif kind == "validation_done":
                self.validate_button.configure(state="normal")
                self.status_var.set("Automatic timing validation complete")
                self._append("")
                self._append(f"Validation report: {payload['text_path']}")
                self._append(f"Validation JSON: {payload['json_path']}")
                messagebox.showinfo(
                    APP_TITLE,
                    (
                        "Automatic timing validation complete.\n\n"
                        f"Meter: {payload['meter_result']}\n"
                        f"Beat grid: {payload['grid_result']}\n"
                        f"Phase: {payload['phase_result']}\n"
                        f"Overall: {'PASS' if payload['overall_pass'] else 'FAIL'}\n\n"
                        "Open timing_validation_024.txt in the Analysis folder."
                    ),
                )
            elif kind == "validation_error":
                self.validate_button.configure(state="normal")
                self.status_var.set("Automatic timing validation failed")
                self._append(str(payload))
                messagebox.showerror(APP_TITLE, "Validation failed. The exact error is shown in the window.")
            elif kind == "truth_review":
                self.truth_button.configure(state="normal")
                self.status_var.set("Review the located timing truth")
                self._show_truth_review(payload)
            elif kind == "truth_done":
                self.truth_button.configure(state="normal")
                self.status_var.set("Manual truth recovery complete")
                self._append("")
                self._append(f"Truth report: {payload['text_path']}")
                self._append(f"Canonical truth: {payload['json_path']}")
                conflicts = payload.get("conflicts") or []
                missing = payload.get("missing") or []
                self._append(f"Conflicts: {len(conflicts)}")
                self._append(f"Missing fields: {len(missing)}")
                messagebox.showinfo(
                    APP_TITLE,
                    (
                        "Build 024 recovered and consolidated the saved manual timing data.\n\n"
                        f"Conflicts found: {len(conflicts)}\n"
                        f"Missing fields: {len(missing)}\n\n"
                        "Use Open Analysis Folder and open "
                        "manual_truth_recovery_022.txt in Notepad."
                    ),
                )
            elif kind == "truth_error":
                self.truth_button.configure(state="normal")
                self.status_var.set("Manual truth recovery failed")
                self._append(str(payload))
                messagebox.showerror(
                    APP_TITLE,
                    "Manual truth recovery failed. The exact error is shown in the window.",
                )
            elif kind == "evidence_done":
                self.evidence_button.configure(state="normal")
                self.status_var.set("Timing evidence report created")
                self._append("")
                self._append(f"Evidence report: {payload['text_path']}")
                self._append(f"Evidence data: {payload['json_path']}")
                verified = payload.get("verified_candidate") or {}
                if verified.get("complete"):
                    self._append(
                        f"Saved manual result ranked {verified.get('rank')} of "
                        f"{payload.get('candidate_count')} candidates."
                    )
                else:
                    self._append(
                        "The saved manual result is incomplete; the report marks "
                        "the missing meter, beat-grid or phase field."
                    )
                messagebox.showinfo(
                    APP_TITLE,
                    (
                        "Build 024 created the complete timing evidence report.\n\n"
                        "No timing scores, confirmations or song data were changed.\n\n"
                        "Use Open Analysis Folder and open timing_evidence_021.txt in Notepad."
                    ),
                )
            elif kind == "evidence_error":
                self.evidence_button.configure(state="normal")
                self.status_var.set("Timing evidence report failed")
                self._append(str(payload))
                messagebox.showerror(
                    APP_TITLE,
                    "The timing evidence report failed. The exact error is shown in the window.",
                )
            elif kind == "alternative_done":
                self.alt_create_button.configure(state="normal")
                self.alt_play_button.configure(state="normal")
                self.status_var.set("Four alternative beat grids created")
                self._append("")
                for method, candidate in payload["candidates"].items():
                    self._append(
                        f"{candidate['label']}: {len(candidate['beat_times'])} beats, "
                        f"{float(candidate['bpm']):.1f} BPM"
                    )
                self._append(f"Alternative grid data: {payload['proof_path']}")
                messagebox.showinfo(
                    APP_TITLE,
                    "Four genuinely different beat grids are ready.\n\n"
                    "Use Play Alternative Beat Grids and identify which ordinary click track follows the real musical beat.",
                )
            elif kind == "done":
                result = payload["result"]
                structure_path, record_path, analysis_path, audible_check_path = payload["paths"]
                self.status_var.set("Meter, bars and downbeats saved successfully")
                self._append("")
                self._append(f"Meter result: {result.meter}")
                self._append(f"Best candidate: {result.best_meter_candidate}")
                self._append(f"Meter status: {result.meter_status}")
                self._append(f"Whole-track confidence: {result.full_track_meter_confidence:.0%}")
                self._append(f"Rhythmic-window candidate: {result.rhythmic_window_candidate}")
                self._append(f"Rhythmic-window confidence: {result.rhythmic_window_meter_confidence:.0%}")
                self._append(f"Candidate agreement: {'Yes' if result.meter_candidate_agreement else 'No'}")
                self._append(f"Supporting window: {result.rhythmic_window_start_s:.1f}s to {result.rhythmic_window_end_s:.1f}s")
                self._append(f"Beats per bar: {result.beats_per_bar}")
                self._append(f"Detected beats: {result.beat_count}")
                self._append(f"Estimated bars: {result.bar_count}")
                self._append(f"First downbeat beat index: {result.first_downbeat_beat_index}")
                self._append(f"New structure file: {structure_path}")
                self._append(f"Updated existing Library JSON: {record_path}")
                self._append(f"Updated existing song analysis JSON: {analysis_path}")
                self._append(f"Audible bar check: {audible_check_path}")
                self.play_button.configure(state="normal")
                self.run_button.configure(state="normal")
                self._refresh()
                messagebox.showinfo(
                    APP_TITLE,
                    "The 3/4 or 4/4 structure pass completed.\n\n"
                    "The existing JSON filenames have not changed. Open them in Notepad "
                    "to inspect the new meter, bar and downbeat fields.",
                )
        self.after(150, self._poll)

    def _recommend_timing(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        analysis_path = Path(self.selected_song["analysis_path"])
        analysis = read_json(analysis_path)
        candidates = analysis.get("alternative_beat_grids")
        if not isinstance(candidates, dict) or not candidates:
            messagebox.showerror(
                APP_TITLE,
                "Create the alternative beat grids before requesting a recommendation.",
            )
            return

        self.recommend_button.configure(state="disabled")
        self.status_var.set("Build 024 is scoring meter, beat grid and downbeat phase…")
        self._append("Started automatic timing recommendation.")
        song = dict(self.selected_song)

        def worker() -> None:
            try:
                result = structure_engine.recommend_timing_structure(
                    Path(song["audio_path"]),
                    candidates,
                    analysis.get("segments", []),
                )
                record_path = Path(song["record_path"])
                current_record = read_json(record_path)
                current_analysis = read_json(analysis_path)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                payload = {
                    **result,
                    "timing_recommendation_status": "recommended",
                    "timing_recommended_at": timestamp,
                    "timing_recommended_by": "automatic_scoring_v2_repeating_pattern",
                }
                current_record["timing_recommendation"] = payload
                current_analysis["timing_recommendation"] = payload
                report_path = analysis_path.parent / "timing_recommendation_020.json"
                write_json_atomic(report_path, payload)
                current_record["timing_recommendation_path"] = str(report_path)
                current_analysis["timing_recommendation_path"] = str(report_path)
                write_json_atomic(record_path, current_record)
                write_json_atomic(analysis_path, current_analysis)
                self.messages.put(("recommendation_done", payload))
            except Exception as exc:
                self.messages.put(("recommendation_error", f"{exc}\n\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _validate_automatic_timing(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        song = dict(self.selected_song)
        self.validate_button.configure(state="disabled")
        self.status_var.set("Build 024 is comparing automatic timing with verified truth…")
        self._append("Started automatic timing validation.")

        def worker() -> None:
            try:
                analysis_path = Path(song["analysis_path"])
                folder = analysis_path.parent
                truth_path = folder / "manual_truth_023.json"
                if not truth_path.is_file():
                    raise FileNotFoundError(
                        "manual_truth_023.json was not found. "
                        "Use Review / Save Verified Truth first."
                    )
                result = structure_engine.validate_automatic_timing(
                    song_title=str(song.get("title") or folder.name),
                    analysis=read_json(analysis_path),
                    truth=read_json(truth_path),
                    analysis_path=analysis_path,
                    truth_path=truth_path,
                )
                json_path = folder / "timing_validation_024.json"
                text_path = folder / "timing_validation_024.txt"
                write_json_atomic(json_path, result)
                text_path.write_text(
                    structure_engine.format_timing_validation(result),
                    encoding="utf-8",
                )
                self.messages.put(("validation_done", {
                    "json_path": str(json_path),
                    "text_path": str(text_path),
                    "overall_pass": result["overall_pass"],
                    "meter_result": result["checks"]["meter"]["result"],
                    "grid_result": result["checks"]["beat_grid_method"]["result"],
                    "phase_result": result["checks"]["phase_number"]["result"],
                }))
            except Exception as exc:
                self.messages.put(("validation_error", f"{exc}\\n\\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _recover_manual_truth(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return

        song = dict(self.selected_song)
        self.truth_button.configure(state="disabled")
        self.status_var.set("Build 024 is locating explicit confirmations…")
        self._append("Started verified timing truth review.")

        def worker() -> None:
            try:
                analysis_path = Path(song["analysis_path"])
                record_path = Path(song["record_path"])
                folder = analysis_path.parent
                structure_path = folder / "song_structure.json"

                record = read_json(record_path) if record_path.is_file() else {}
                analysis = read_json(analysis_path) if analysis_path.is_file() else {}
                structure = read_json(structure_path) if structure_path.is_file() else {}

                result = structure_engine.recover_verified_truth(
                    record=record,
                    analysis=analysis,
                    structure=structure,
                    song_title=str(song.get("title") or folder.name),
                    record_path=record_path,
                    analysis_path=analysis_path,
                    structure_path=structure_path,
                )
                self.messages.put((
                    "truth_review",
                    {
                        "song": song,
                        "folder": str(folder),
                        "result": result,
                    },
                ))
            except Exception as exc:
                self.messages.put((
                    "truth_error",
                    f"{exc}\n\n{traceback.format_exc()}",
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _show_truth_review(self, payload: dict) -> None:
        result = payload["result"]
        canonical = dict(result["canonical_record"])
        folder = Path(payload["folder"])

        dialog = tk.Toplevel(self)
        dialog.title("Build 024 — Review Verified Timing Truth")
        dialog.geometry("720x520")
        dialog.minsize(660, 480)
        dialog.transient(self)
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(
            body,
            text=str(canonical.get("song_title") or ""),
            font=("Segoe UI", 12, "bold"),
            wraplength=650,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        ttk.Label(body, text="Meter").grid(row=1, column=0, sticky="w", pady=6)
        meter_var = tk.StringVar(value=str(canonical.get("meter") or ""))
        meter_combo = ttk.Combobox(
            body,
            textvariable=meter_var,
            values=("3/4", "4/4"),
            state="readonly",
            width=18,
        )
        meter_combo.grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(body, text="Beat-grid method").grid(row=2, column=0, sticky="w", pady=6)
        grid_var = tk.StringVar(value=str(canonical.get("beat_grid_method") or ""))
        grid_combo = ttk.Combobox(
            body,
            textvariable=grid_var,
            values=("standard", "percussive", "low_frequency", "steady_pulse"),
            state="readonly",
            width=24,
        )
        grid_combo.grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(body, text="Phase number").grid(row=3, column=0, sticky="w", pady=6)
        phase_var = tk.StringVar(
            value="" if canonical.get("phase_number") is None
            else str(canonical.get("phase_number"))
        )
        phase_values = ("1", "2", "3") if meter_var.get() == "3/4" else ("1", "2", "3", "4")
        phase_combo = ttk.Combobox(
            body,
            textvariable=phase_var,
            values=phase_values,
            state="readonly",
            width=18,
        )
        phase_combo.grid(row=3, column=1, sticky="w", pady=6)

        def refresh_phases(*_args) -> None:
            values = ("1", "2", "3") if meter_var.get() == "3/4" else ("1", "2", "3", "4")
            phase_combo.configure(values=values)
            if phase_var.get() not in values:
                phase_var.set("")

        meter_var.trace_add("write", refresh_phases)

        source_text = tk.Text(body, height=13, wrap="word")
        source_text.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(14, 10))
        body.rowconfigure(4, weight=1)

        lines = [
            "Located explicit evidence:",
            f"Meter source: {canonical.get('meter_source_label') or 'None'}",
            f"Grid source: {canonical.get('beat_grid_source_label') or 'None'}",
            f"Phase source: {canonical.get('phase_source_label') or 'None'}",
            "",
        ]
        for note in canonical.get("notes") or []:
            lines.append(f"• {note}")
        source_text.insert("1.0", "\n".join(lines))
        source_text.configure(state="disabled")

        ttk.Label(
            body,
            text=(
                "Saving creates manual_truth_023.json and does not change "
                "the timing scorer or original analysis."
            ),
            wraplength=650,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 10))

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e")

        def save_truth() -> None:
            meter = meter_var.get().strip()
            grid = grid_var.get().strip()
            phase_text = phase_var.get().strip()
            if meter not in {"3/4", "4/4"}:
                messagebox.showerror(APP_TITLE, "Choose 3/4 or 4/4.", parent=dialog)
                return
            if grid not in {"standard", "percussive", "low_frequency", "steady_pulse"}:
                messagebox.showerror(APP_TITLE, "Choose a beat-grid method.", parent=dialog)
                return
            if not phase_text:
                messagebox.showerror(APP_TITLE, "Choose a phase number.", parent=dialog)
                return
            phase = int(phase_text)
            max_phase = 3 if meter == "3/4" else 4
            if not 1 <= phase <= max_phase:
                messagebox.showerror(APP_TITLE, "The phase does not match the meter.", parent=dialog)
                return

            verified = structure_engine.build_verified_truth_record(
                canonical,
                meter=meter,
                beat_grid_method=grid,
                phase_number=phase,
            )
            json_path = folder / "manual_truth_023.json"
            text_path = folder / "manual_truth_023.txt"
            write_json_atomic(json_path, verified)
            text_path.write_text(
                structure_engine.format_verified_truth_record(verified),
                encoding="utf-8",
            )
            dialog.destroy()
            self.truth_button.configure(state="normal")
            self.status_var.set("Verified timing truth saved")
            self._append(f"Verified truth: {text_path}")
            messagebox.showinfo(
                APP_TITLE,
                (
                    "Verified timing truth saved.\n\n"
                    f"Meter: {meter}\n"
                    f"Beat grid: {grid}\n"
                    f"Phase: {phase}\n\n"
                    "Use Open Analysis Folder and open manual_truth_023.txt."
                ),
            )

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save Verified Truth", command=save_truth).pack(side="right")

    def _create_timing_evidence_report(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return

        song = dict(self.selected_song)
        analysis_path = Path(song["analysis_path"])
        analysis = read_json(analysis_path)
        candidates = analysis.get("alternative_beat_grids")
        if not isinstance(candidates, dict) or not candidates:
            messagebox.showerror(
                APP_TITLE,
                "Create the alternative beat grids before creating an evidence report.",
            )
            return

        self.evidence_button.configure(state="disabled")
        self.status_var.set("Build 024 is calculating the complete candidate evidence…")
        self._append("Started full timing evidence comparison.")

        def worker() -> None:
            try:
                record = read_json(Path(song["record_path"]))
                current_analysis = read_json(analysis_path)
                result = structure_engine.build_timing_evidence_report(
                    Path(song["audio_path"]),
                    candidates,
                    current_analysis.get("segments", []),
                    record,
                    current_analysis,
                    str(song.get("title") or analysis_path.parent.name),
                )

                folder = analysis_path.parent
                json_path = folder / "timing_evidence_021.json"
                text_path = folder / "timing_evidence_021.txt"
                write_json_atomic(json_path, result)
                text_path.write_text(
                    structure_engine.format_timing_evidence_text(result),
                    encoding="utf-8",
                )
                self.messages.put((
                    "evidence_done",
                    {
                        "json_path": str(json_path),
                        "text_path": str(text_path),
                        "candidate_count": result.get("candidate_count"),
                        "verified_candidate": result.get("verified_candidate"),
                    },
                ))
            except Exception as exc:
                self.messages.put((
                    "evidence_error",
                    f"{exc}\\n\\n{traceback.format_exc()}",
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _create_alternative_beat_grids(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        song = self.selected_song
        self.alt_create_button.configure(state="disabled")
        self.alt_play_button.configure(state="disabled")
        self.status_var.set("Creating genuinely different beat grids…")

        def worker() -> None:
            try:
                candidates = structure_engine.generate_alternative_beat_grids(
                    Path(song["audio_path"]),
                    lambda text: self.messages.put(("status", text)),
                )
                folder = Path(song["analysis_path"]).parent
                for method, candidate in candidates.items():
                    target = folder / f"alternative_beat_{method}.wav"
                    structure_engine.create_audible_beat_grid_check(
                        Path(song["audio_path"]),
                        candidate["beat_times"],
                        target,
                    )
                    candidate["audible_path"] = str(target)

                proof_path = folder / "alternative_beat_grids.json"
                proof_path.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
                record = read_json(Path(song["record_path"]))
                analysis = read_json(Path(song["analysis_path"]))
                record["alternative_beat_grids_path"] = str(proof_path)
                analysis["alternative_beat_grids_path"] = str(proof_path)
                analysis["alternative_beat_grids"] = candidates
                write_json_atomic(Path(song["record_path"]), record)
                write_json_atomic(Path(song["analysis_path"]), analysis)
                self.messages.put(("alternative_done", {"candidates": candidates, "proof_path": proof_path}))
            except Exception as exc:
                self.messages.put(("alternative_error", f"{exc}\n\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _play_alternative_beat_grids(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select an analysed song first.")
            return
        analysis = read_json(Path(self.selected_song["analysis_path"]))
        candidates = analysis.get("alternative_beat_grids")
        if not isinstance(candidates, dict) or not candidates:
            messagebox.showerror(APP_TITLE, "Create the Build 024 alternative beat grids first.")
            return
        valid = {
            key: value for key, value in candidates.items()
            if isinstance(value, dict)
            and Path(str(value.get("audible_path") or "")).is_file()
            and isinstance(value.get("beat_times"), list)
        }
        if not valid:
            messagebox.showerror(APP_TITLE, "The Build 024 alternative beat files are missing.")
            return
        self.alt_candidates = valid
        self.alt_chord_segments = sorted(
            [item for item in analysis.get("segments", []) if isinstance(item, dict)],
            key=lambda item: float(item.get("start_s", 0.0)),
        )
        self.alt_selected_method = next(iter(valid))
        self._open_alternative_window()
        self._start_alternative_method(self.alt_selected_method)

    def _open_alternative_window(self) -> None:
        if self.alt_window is not None and self.alt_window.winfo_exists():
            self.alt_window.destroy()
        self.alt_window = tk.Toplevel(self)
        self.alt_window.title("Banjofy Alternative Beat-Grid Audition")
        self.alt_window.geometry("900x470")
        frame = ttk.Frame(self.alt_window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Alternative Beat-Grid Audition", font=("Segoe UI", 18, "bold")).pack()
        ttk.Label(
            frame,
            text=("Every method uses the original recording and identical ordinary clicks. "
                  "There are no strong downbeat clicks. Choose the method whose clicks follow "
                  "the genuine musical beat without speeding up, slowing down or drifting."),
            wraplength=840,
        ).pack(pady=(4,14))
        methods = ttk.LabelFrame(frame, text="Genuinely different beat trackers")
        methods.pack(fill="x")
        for key, candidate in self.alt_candidates.items():
            ttk.Button(
                methods,
                text=str(candidate.get("label") or key),
                command=lambda value=key: self._start_alternative_method(value),
            ).pack(side="left", padx=6, pady=10)
        self.alt_method_var = tk.StringVar(value="")
        self.alt_time_var = tk.StringVar(value="0:00")
        self.alt_beat_var = tk.StringVar(value="Beat —")
        self.alt_chord_var = tk.StringVar(value="Chord —")
        ttk.Label(frame, textvariable=self.alt_method_var, font=("Segoe UI", 15, "bold")).pack(pady=(18,4))
        ttk.Label(frame, textvariable=self.alt_beat_var, font=("Segoe UI", 30, "bold")).pack()
        ttk.Label(frame, textvariable=self.alt_chord_var, font=("Segoe UI", 26)).pack(pady=6)
        ttk.Label(frame, textvariable=self.alt_time_var, font=("Segoe UI", 14)).pack()
        self.alt_canvas = tk.Canvas(frame, height=70, highlightthickness=1)
        self.alt_canvas.pack(fill="x", pady=14)
        self.alt_canvas.create_line(30,35,830,35,width=3)
        self.alt_marker = self.alt_canvas.create_oval(22,19,38,51)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Confirm Selected Beat Grid and Rebuild Phases",
            command=self._confirm_selected_alternative_grid,
        ).pack(side="left")
        ttk.Button(actions, text="Stop Test", command=self._stop_alternative_test).pack(side="right")
        self.alt_window.protocol("WM_DELETE_WINDOW", self._stop_alternative_test)

    def _start_alternative_method(self, method: str) -> None:
        candidate = self.alt_candidates.get(method)
        if not candidate:
            return
        path = Path(str(candidate.get("audible_path") or ""))
        if not path.is_file():
            messagebox.showerror(APP_TITLE, f"Alternative beat file missing:\n{path}")
            return
        try:
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not play alternative beat grid:\n{exc}")
            return
        self.alt_selected_method = method
        self.alt_started_at = time.monotonic()
        label = str(candidate.get("label") or method)
        bpm = float(candidate.get("bpm") or 0.0)
        self.alt_method_var.set(f"{label} · estimated {bpm:.1f} BPM")
        self._update_alternative_marker()

    def _alternative_chord_at(self, elapsed: float) -> str:
        for segment in self.alt_chord_segments:
            if float(segment.get("start_s",0.0)) <= elapsed < float(segment.get("end_s",0.0)):
                return str(segment.get("chord") or "N")
        return "—"

    def _update_alternative_marker(self) -> None:
        if self.alt_started_at is None or self.alt_window is None or not self.alt_window.winfo_exists():
            return
        candidate = self.alt_candidates.get(self.alt_selected_method, {})
        beats = [float(v) for v in candidate.get("beat_times", [])]
        if not beats:
            return
        elapsed = time.monotonic() - self.alt_started_at
        duration = min(structure_engine.AUDIBLE_PREVIEW_SECONDS, beats[-1])
        if elapsed >= duration:
            self._stop_alternative_test(); return
        index = max(0, bisect.bisect_right(beats, elapsed)-1)
        near = abs(elapsed-beats[index]) < 0.14
        self.alt_beat_var.set(f"Beat {index+1}")
        self.alt_chord_var.set(f"Chord {self._alternative_chord_at(elapsed)}")
        self.alt_time_var.set(f"{int(elapsed)//60}:{int(elapsed)%60:02d} / {int(duration)//60}:{int(duration)%60:02d}")
        width=max(100,self.alt_canvas.winfo_width()); x=30+(elapsed/max(1.0,duration))*(width-60)
        size=24 if near else 14
        self.alt_canvas.coords(self.alt_marker,x-size/2,35-size,x+size/2,35+size)
        self.after(25,self._update_alternative_marker)

    def _confirm_selected_alternative_grid(self) -> None:
        if self.selected_song is None or not self.alt_selected_method:
            messagebox.showerror(APP_TITLE, "Play and select an alternative beat grid first.")
            return
        candidate = self.alt_candidates.get(self.alt_selected_method)
        if not isinstance(candidate, dict):
            messagebox.showerror(APP_TITLE, "The selected beat-grid candidate is unavailable.")
            return
        label = str(candidate.get("label") or self.alt_selected_method)
        analysis = read_json(Path(self.selected_song["analysis_path"]))
        meter = str(analysis.get("confirmed_meter") or analysis.get("meter") or "")
        if meter not in {"3/4", "4/4"}:
            messagebox.showerror(APP_TITLE, "Confirm 3/4 or 4/4 before confirming this beat grid.")
            return
        if not messagebox.askyesno(
            APP_TITLE,
            (
                f"Confirm {label} as this song's active beat grid?\n\n"
                f"Build 024 will retain the original detector grid, rebuild {meter} bars "
                "and create a completely fresh phase-audition set.\n\n"
                "Chord names and chord-change times will not be altered."
            ),
        ):
            return
        try:
            record_path=Path(self.selected_song["record_path"])
            analysis_path=Path(self.selected_song["analysis_path"])
            audio_path=Path(self.selected_song["audio_path"])
            record=read_json(record_path)
            analysis=read_json(analysis_path)
            confirmed_at=time.strftime("%Y-%m-%d %H:%M:%S")
            updated_record,updated_analysis,structure_updates=(
                build_confirmed_alternative_grid_updates(
                    record,analysis,self.alt_selected_method,confirmed_at
                )
            )
            folder=analysis_path.parent
            phase_paths=create_phase_auditions(audio_path,updated_analysis,folder)
            updated_record["downbeat_phase_audition_paths"]=phase_paths
            updated_analysis["downbeat_phase_audition_paths"]=phase_paths
            structure_updates["downbeat_phase_audition_paths"]=phase_paths
            structure_raw=updated_record.get("structure_path")
            structure_path=(Path(str(structure_raw)) if structure_raw else folder/"song_structure.json")
            updated_structure=read_json(structure_path) if structure_path.is_file() else {}
            for key in structure_updates.pop("remove_phase_confirmation_keys",[]):
                updated_structure.pop(key,None)
            updated_structure.update(structure_updates)
            write_json_atomic(structure_path,updated_structure)
            write_json_atomic(record_path,updated_record)
            write_json_atomic(analysis_path,updated_analysis)
            self._stop_alternative_test()
            self.play_button.configure(state="normal")
            self.status_var.set(f"Confirmed beat grid: {label}")
            self._append(f"Confirmed alternative beat grid: {label}.")
            self._append(f"Created {len(phase_paths)} fresh {meter} phase auditions.")
            messagebox.showinfo(
                APP_TITLE,
                (
                    f"{label} is now the active beat grid.\n\n"
                    f"Build 024 created {len(phase_paths)} fresh {meter} phase auditions. "
                    "Open the chord and downbeat phase check and audition them."
                ),
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE,f"Could not confirm the selected beat grid:\n{exc}")

    def _stop_alternative_test(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self.alt_started_at=None
        if self.alt_window is not None and self.alt_window.winfo_exists(): self.alt_window.destroy()
        self.alt_window=None

    def _play_audible_check(self) -> None:
        if self.selected_song is None:
            messagebox.showinfo(APP_TITLE, "Select a Library song first.")
            return

        record = read_json(self.selected_song["record_path"])
        analysis = read_json(self.selected_song["analysis_path"])

        raw_phase_paths = (
            record.get("downbeat_phase_audition_paths")
            or analysis.get("downbeat_phase_audition_paths")
            or []
        )
        expected_meter = str(
            analysis.get("confirmed_meter") or analysis.get("meter") or ""
        )
        expected_count = 3 if expected_meter == "3/4" else 4
        valid_paths = [
            Path(str(value))
            for value in raw_phase_paths
            if isinstance(value, str) and Path(str(value)).is_file()
        ]

        if len(valid_paths) != expected_count:
            self.status_var.set(
                "Rebuilding missing or mismatched phase audition files in Build 024…"
            )
            folder = Path(self.selected_song["analysis_path"]).parent
            rebuilt_paths = create_phase_auditions(
                Path(self.selected_song["audio_path"]),
                analysis,
                folder,
            )
            persist_phase_audition_paths(
                Path(self.selected_song["record_path"]),
                Path(self.selected_song["analysis_path"]),
                rebuilt_paths,
            )
            record = read_json(self.selected_song["record_path"])
            analysis = read_json(self.selected_song["analysis_path"])
            valid_paths = [Path(path) for path in rebuilt_paths]
            self._append(
                f"Build 024 rebuilt {len(valid_paths)} phase audition files."
            )

        self.visual_phase_paths = valid_paths

        self.visual_beat_times = [float(v) for v in analysis.get("beat_times", [])]
        self.visual_downbeat_times = [float(v) for v in analysis.get("downbeat_times", [])]
        raw_segments = analysis.get("segments", [])
        self.visual_chord_segments = [
            segment for segment in raw_segments
            if isinstance(segment, dict)
            and isinstance(segment.get("start_s"), (int, float))
            and isinstance(segment.get("end_s"), (int, float))
        ] if isinstance(raw_segments, list) else []
        self.visual_chord_segments.sort(key=lambda item: float(item.get("start_s", 0.0)))

        effective_meter = str(analysis.get("confirmed_meter") or analysis.get("meter") or "")
        self.visual_beats_per_bar = 3 if effective_meter == "3/4" else 4
        self.visual_base_first_downbeat_index = int(
            analysis.get(
                "detected_first_downbeat_beat_index",
                analysis.get("first_downbeat_beat_index", 0),
            )
        )
        confirmed_phase_number = int(
            analysis.get("confirmed_phase_number")
            or record.get("confirmed_phase_number")
            or 1
        )
        self.visual_phase_offset = max(
            0,
            min(self.visual_beats_per_bar - 1, confirmed_phase_number - 1),
        )

        if not self.visual_beat_times or not self.visual_downbeat_times:
            messagebox.showerror(APP_TITLE, "Beat or downbeat data is missing.")
            return
        if not self.visual_chord_segments:
            messagebox.showerror(
                APP_TITLE,
                "The saved song analysis contains no chord segments to display.",
            )
            return
        if len(self.visual_phase_paths) != self.visual_beats_per_bar:
            messagebox.showerror(
                APP_TITLE,
                "Build 024 could not create the required phase audition files. "
                "The exact file state is shown in the status window.",
            )
            return

        self.visual_duration = min(
            structure_engine.AUDIBLE_PREVIEW_SECONDS,
            self.visual_beat_times[-1],
        )
        self._open_visual_window()
        self._start_selected_phase()

    def _start_selected_phase(self) -> None:
        if not self.visual_phase_paths:
            return
        path = self.visual_phase_paths[self.visual_phase_offset]
        if not path.is_file():
            messagebox.showerror(APP_TITLE, f"The selected phase file is missing:\n{path}")
            return
        try:
            import winsound
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not start the phase audition:\n{exc}")
            return
        self.visual_started_at = time.monotonic()
        self._refresh_phase_display()
        self._update_visual_marker()

    def _set_visual_phase(self, phase_offset: int) -> None:
        if self.visual_beats_per_bar <= 0:
            return
        self.visual_phase_offset = int(phase_offset) % self.visual_beats_per_bar
        self._start_selected_phase()

    def _effective_first_downbeat_index(self) -> int:
        return (
            self.visual_base_first_downbeat_index + self.visual_phase_offset
        ) % max(1, self.visual_beats_per_bar)

    def _phase_downbeat_times(self) -> list[float]:
        effective = self._effective_first_downbeat_index()
        return [
            float(self.visual_beat_times[index])
            for index in range(
                effective,
                len(self.visual_beat_times),
                self.visual_beats_per_bar,
            )
        ]

    def _refresh_phase_display(self) -> None:
        if hasattr(self, "visual_phase_var"):
            self.visual_phase_var.set(
                f"Selected Phase {self.visual_phase_offset + 1} · "
                f"first downbeat beat index {self._effective_first_downbeat_index()}"
            )
        for index, button in enumerate(self.visual_phase_buttons):
            button.state(
                ["disabled"]
                if index == self.visual_phase_offset
                else ["!disabled"]
            )

    def _open_visual_window(self) -> None:
        if self.visual_window is not None and self.visual_window.winfo_exists():
            self.visual_window.destroy()

        self.visual_window = tk.Toplevel(self)
        self.visual_window.title("Banjofy Downbeat Phase Audition")
        self.visual_window.geometry("960x620")
        self.visual_window.minsize(840, 560)

        frame = ttk.Frame(self.visual_window, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Chord, Beat and Confirmed Downbeat Phase",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="center")
        ttk.Label(
            frame,
            text=(
                "The chord names and beat spacing remain unchanged. "
                "Choose each phase in turn; playback restarts from the beginning "
                "and only the strong downbeat click moves."
            ),
            wraplength=900,
        ).pack(anchor="center", pady=(4, 14))

        self.visual_bar_var = tk.StringVar(value="Bar —")
        self.visual_beat_var = tk.StringVar(value="Beat —")
        self.visual_time_var = tk.StringVar(value="0:00 / 3:00")
        self.visual_status_var = tk.StringVar(value="Starting…")
        self.visual_current_chord_var = tk.StringVar(value="—")
        self.visual_next_chord_var = tk.StringVar(value="Next chord: —")
        self.visual_change_var = tk.StringVar(value="Change in: —")
        self.visual_phase_var = tk.StringVar(value="")

        timing = ttk.Frame(frame)
        timing.pack(fill="x", pady=(4, 12))
        ttk.Label(
            timing,
            textvariable=self.visual_bar_var,
            font=("Segoe UI", 26, "bold"),
        ).pack(side="left")
        ttk.Label(
            timing,
            textvariable=self.visual_beat_var,
            font=("Segoe UI", 26),
        ).pack(side="left", padx=24)
        ttk.Label(
            timing,
            textvariable=self.visual_time_var,
            font=("Segoe UI", 16),
        ).pack(side="right")

        pulse_frame = ttk.LabelFrame(
            frame,
            text="Underlying pulse interpretation — use when no phase works",
        )
        pulse_frame.pack(fill="x", pady=(0, 12))
        current_pulse = str(
            read_json(self.selected_song["analysis_path"]).get(
                "pulse_interpretation",
                "detected",
            )
        )
        if current_pulse not in PULSE_MODES:
            current_pulse = "detected"
        self.visual_pulse_var = tk.StringVar(value=current_pulse)
        ttk.Radiobutton(
            pulse_frame,
            text="Detected pulse",
            value="detected",
            variable=self.visual_pulse_var,
        ).pack(side="left", padx=(10, 4), pady=8)
        ttk.Radiobutton(
            pulse_frame,
            text="Half pulse A",
            value="half_a",
            variable=self.visual_pulse_var,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            pulse_frame,
            text="Half pulse B",
            value="half_b",
            variable=self.visual_pulse_var,
        ).pack(side="left", padx=4)
        ttk.Button(
            pulse_frame,
            text="Apply Pulse and Rebuild Phase Auditions",
            command=self._confirm_selected_pulse,
        ).pack(side="right", padx=10, pady=8)

        meter_frame = ttk.LabelFrame(frame, text="Confirm meter before phase audition")
        meter_frame.pack(fill="x", pady=(0, 12))
        current_meter = "3/4" if self.visual_beats_per_bar == 3 else "4/4"
        self.visual_meter_var = tk.StringVar(value=current_meter)
        ttk.Label(
            meter_frame,
            text="Detected/active meter:",
        ).pack(side="left", padx=(10, 6), pady=10)
        ttk.Radiobutton(
            meter_frame,
            text="3/4",
            value="3/4",
            variable=self.visual_meter_var,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            meter_frame,
            text="4/4",
            value="4/4",
            variable=self.visual_meter_var,
        ).pack(side="left", padx=4)
        ttk.Button(
            meter_frame,
            text="Apply Meter and Rebuild Phase Auditions",
            command=self._confirm_selected_meter,
        ).pack(side="right", padx=10, pady=8)

        phase_frame = ttk.LabelFrame(frame, text="Audition every possible Beat 1 phase")
        phase_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            phase_frame,
            text="Choose a phase; playback restarts from the beginning:",
        ).pack(side="left", padx=10, pady=10)
        self.visual_phase_buttons = []
        for phase in range(self.visual_beats_per_bar):
            button = ttk.Button(
                phase_frame,
                text=f"Phase {phase + 1}",
                command=lambda value=phase: self._set_visual_phase(value),
            )
            button.pack(side="left", padx=4, pady=8)
            self.visual_phase_buttons.append(button)
        ttk.Label(
            phase_frame,
            textvariable=self.visual_phase_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=10)

        chord_box = ttk.LabelFrame(frame, text="Current chord from saved timeline")
        chord_box.pack(fill="x", pady=(4, 14))
        ttk.Label(
            chord_box,
            textvariable=self.visual_current_chord_var,
            font=("Segoe UI", 42, "bold"),
            anchor="center",
        ).pack(fill="x", padx=12, pady=(8, 2))
        chord_details = ttk.Frame(chord_box)
        chord_details.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(
            chord_details,
            textvariable=self.visual_next_chord_var,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")
        ttk.Label(
            chord_details,
            textvariable=self.visual_change_var,
            font=("Segoe UI", 15),
        ).pack(side="right")

        self.visual_canvas = tk.Canvas(frame, height=90, highlightthickness=1)
        self.visual_canvas.pack(fill="x")
        self.visual_canvas.create_line(30, 45, 890, 45, width=3)
        self.visual_marker = self.visual_canvas.create_oval(22, 29, 38, 61)

        ttk.Label(
            frame,
            textvariable=self.visual_status_var,
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=10)
        action_row = ttk.Frame(frame)
        action_row.pack(fill="x", pady=(6, 0))
        ttk.Button(
            action_row,
            text="Confirm Selected Phase",
            command=self._confirm_selected_phase,
        ).pack(side="left")
        ttk.Button(
            action_row,
            text="Stop Test",
            command=self._stop_visual_test,
        ).pack(side="right")
        self.visual_window.protocol("WM_DELETE_WINDOW", self._stop_visual_test)
        self._refresh_phase_display()

    def _chord_display_at(self, elapsed: float) -> tuple[str, str, float | None]:
        current_index = None
        for index, segment in enumerate(self.visual_chord_segments):
            start = float(segment.get("start_s", 0.0))
            end = float(segment.get("end_s", start))
            if start <= elapsed < end:
                current_index = index
                break

        if current_index is None:
            next_segment = next(
                (
                    segment
                    for segment in self.visual_chord_segments
                    if float(segment.get("start_s", 0.0)) > elapsed
                ),
                None,
            )
            if next_segment is None:
                return "—", "—", None
            next_chord = str(next_segment.get("chord") or "N")
            return (
                "—",
                next_chord,
                max(0.0, float(next_segment.get("start_s", 0.0)) - elapsed),
            )

        current = self.visual_chord_segments[current_index]
        current_chord = str(current.get("chord") or "N")
        next_segment = (
            self.visual_chord_segments[current_index + 1]
            if current_index + 1 < len(self.visual_chord_segments)
            else None
        )
        if next_segment is None:
            return current_chord, "—", None
        next_chord = str(next_segment.get("chord") or "N")
        change_in = max(
            0.0,
            float(next_segment.get("start_s", 0.0)) - elapsed,
        )
        return current_chord, next_chord, change_in

    def _update_visual_marker(self) -> None:
        if (
            self.visual_started_at is None
            or self.visual_window is None
            or not self.visual_window.winfo_exists()
        ):
            return

        elapsed = time.monotonic() - self.visual_started_at
        if elapsed >= self.visual_duration:
            self._stop_visual_test()
            return

        phase_downbeats = self._phase_downbeat_times()
        if not phase_downbeats:
            return

        beat_index = max(
            0,
            bisect.bisect_right(self.visual_beat_times, elapsed) - 1,
        )
        down_index = max(
            0,
            bisect.bisect_right(phase_downbeats, elapsed) - 1,
        )
        down_time = phase_downbeats[down_index]
        first_beat = bisect.bisect_left(self.visual_beat_times, down_time)
        beat_in_bar = max(
            1,
            min(
                self.visual_beats_per_bar,
                beat_index - first_beat + 1,
            ),
        )
        is_down = abs(elapsed - down_time) < 0.16

        width = max(100, self.visual_canvas.winfo_width())
        x = 30 + (elapsed / max(1, self.visual_duration)) * (width - 60)
        size = 26 if is_down else 16
        self.visual_canvas.coords(
            self.visual_marker,
            x - size / 2,
            45 - size,
            x + size / 2,
            45 + size,
        )

        self.visual_bar_var.set(f"Bar {down_index + 1}")
        self.visual_beat_var.set(
            f"Beat {beat_in_bar} of {self.visual_beats_per_bar}"
        )
        self.visual_time_var.set(
            f"{int(elapsed)//60}:{int(elapsed)%60:02d} / 3:00"
        )
        self.visual_status_var.set(
            "DOWNBEAT — selected phase"
            if is_down
            else "Beat"
        )

        current_chord, next_chord, change_in = self._chord_display_at(elapsed)
        self.visual_current_chord_var.set(current_chord)
        self.visual_next_chord_var.set(f"Next chord: {next_chord}")
        self.visual_change_var.set(
            "Change in: —"
            if change_in is None
            else f"Change in: {change_in:.1f}s"
        )

        self.after(25, self._update_visual_marker)

    def _confirm_selected_pulse(self) -> None:
        if self.selected_song is None or self.visual_pulse_var is None:
            messagebox.showerror(APP_TITLE, "Select an analysed song first.")
            return

        selected_mode = self.visual_pulse_var.get()
        label = PULSE_MODES.get(selected_mode, selected_mode)
        confirmed = messagebox.askyesno(
            APP_TITLE,
            (
                f"Apply {label} to this song?\n\n"
                "This retains the original detected beat times, changes the "
                "effective beat grid, rebuilds bars and creates a fresh phase set.\n\n"
                "Chord names, chord-change times, BPM and meter will not change."
            ),
        )
        if not confirmed:
            return

        try:
            record_path = Path(self.selected_song["record_path"])
            analysis_path = Path(self.selected_song["analysis_path"])
            audio_path = Path(self.selected_song["audio_path"])
            record = read_json(record_path)
            analysis = read_json(analysis_path)
            confirmed_at = time.strftime("%Y-%m-%d %H:%M:%S")

            updated_record, updated_analysis, structure_updates = (
                build_confirmed_pulse_updates(
                    record,
                    analysis,
                    selected_mode,
                    confirmed_at,
                )
            )

            folder = analysis_path.parent
            phase_paths = create_phase_auditions(
                audio_path,
                updated_analysis,
                folder,
            )
            updated_record["downbeat_phase_audition_paths"] = phase_paths
            updated_analysis["downbeat_phase_audition_paths"] = phase_paths
            structure_updates["downbeat_phase_audition_paths"] = phase_paths

            structure_raw = updated_record.get("structure_path")
            structure_path = (
                Path(str(structure_raw))
                if structure_raw
                else folder / "song_structure.json"
            )
            updated_structure = (
                read_json(structure_path)
                if structure_path.is_file()
                else {}
            )
            for key in structure_updates.pop(
                "remove_phase_confirmation_keys",
                [],
            ):
                updated_structure.pop(key, None)
            updated_structure.update(structure_updates)

            write_json_atomic(structure_path, updated_structure)
            write_json_atomic(record_path, updated_record)
            write_json_atomic(analysis_path, updated_analysis)

            self._stop_visual_test()
            self.status_var.set(
                f"{label} applied to {self.selected_song['title']}"
            )
            self._append(
                f"Applied {label}; effective beats: "
                f"{len(updated_analysis['beat_times'])}."
            )
            self._append(
                f"Created {len(phase_paths)} fresh phase audition files."
            )
            messagebox.showinfo(
                APP_TITLE,
                (
                    f"{label} is now active for this song.\n\n"
                    "Reopen the phase check and audition every phase."
                ),
            )
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Could not apply the selected pulse:\n{exc}",
            )

    def _confirm_selected_meter(self) -> None:
        if self.selected_song is None or self.visual_meter_var is None:
            messagebox.showerror(APP_TITLE, "Select an analysed song first.")
            return

        selected_meter = self.visual_meter_var.get()
        new_beats_per_bar = 3 if selected_meter == "3/4" else 4
        confirmed = messagebox.askyesno(
            APP_TITLE,
            (
                f"Confirm {selected_meter} for this song?\n\n"
                "This will retain the detector result, rebuild the bar grid, "
                f"and create {new_beats_per_bar} new phase audition files.\n\n"
                "Chord names, chord-change times, beat times and BPM will not change."
            ),
        )
        if not confirmed:
            return

        try:
            record_path = Path(self.selected_song["record_path"])
            analysis_path = Path(self.selected_song["analysis_path"])
            audio_path = Path(self.selected_song["audio_path"])
            record = read_json(record_path)
            analysis = read_json(analysis_path)
            confirmed_at = time.strftime("%Y-%m-%d %H:%M:%S")

            updated_record, updated_analysis, structure_updates = (
                build_confirmed_meter_updates(
                    record,
                    analysis,
                    selected_meter,
                    confirmed_at,
                )
            )

            folder = analysis_path.parent
            phase_paths = create_phase_auditions(
                audio_path,
                updated_analysis,
                folder,
            )
            detected_index = int(
                updated_analysis["detected_first_downbeat_beat_index"]
            )

            updated_record["downbeat_phase_audition_paths"] = phase_paths
            updated_analysis["downbeat_phase_audition_paths"] = phase_paths
            structure_updates["downbeat_phase_audition_paths"] = phase_paths

            structure_path_raw = updated_record.get("structure_path")
            structure_path = (
                Path(str(structure_path_raw))
                if structure_path_raw
                else folder / "song_structure.json"
            )
            updated_structure = read_json(structure_path) if structure_path.is_file() else {}
            for key in structure_updates.pop("remove_phase_confirmation_keys", []):
                updated_structure.pop(key, None)
            updated_structure.update(structure_updates)

            # New media outputs exist before any JSON record is replaced.
            write_json_atomic(structure_path, updated_structure)
            write_json_atomic(record_path, updated_record)
            write_json_atomic(analysis_path, updated_analysis)

            self.visual_beats_per_bar = new_beats_per_bar
            self.visual_base_first_downbeat_index = detected_index
            self.visual_phase_offset = 0
            self.visual_phase_paths = [Path(path) for path in phase_paths]
            self.visual_downbeat_times = list(updated_analysis["downbeat_times"])

            self._stop_visual_test()
            self.status_var.set(
                f"{selected_meter} confirmed for {self.selected_song['title']}"
            )
            self._append(
                f"Confirmed meter {selected_meter}; created "
                f"{new_beats_per_bar} phase auditions."
            )
            messagebox.showinfo(
                APP_TITLE,
                (
                    f"{selected_meter} is now confirmed for this song.\n\n"
                    f"Reopen the phase check and audition Phases 1 to "
                    f"{new_beats_per_bar}."
                ),
            )
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Could not confirm the selected meter:\n{exc}",
            )

    def _confirm_selected_phase(self) -> None:
        if self.selected_song is None:
            messagebox.showerror(APP_TITLE, "Select a Library song first.")
            return

        phase_number = self.visual_phase_offset + 1
        effective_index = self._effective_first_downbeat_index()
        confirmed = messagebox.askyesno(
            APP_TITLE,
            (
                f"Confirm Phase {phase_number} for this song?\n\n"
                f"This will save first downbeat beat index {effective_index} and "
                "rebuild the bar grid and bar-aligned chords.\n\n"
                "Chord names, chord-change times, beat times, BPM and meter "
                "and confirmed meter will not be changed."
            ),
        )
        if not confirmed:
            return

        try:
            record_path = Path(self.selected_song["record_path"])
            analysis_path = Path(self.selected_song["analysis_path"])
            record = read_json(record_path)
            analysis = read_json(analysis_path)
            confirmed_at = time.strftime("%Y-%m-%d %H:%M:%S")

            updated_record, updated_analysis, structure_updates = (
                build_confirmed_phase_updates(
                    record,
                    analysis,
                    phase_number,
                    confirmed_at,
                )
            )

            structure_path_raw = (
                updated_record.get("structure_path")
                or record.get("structure_path")
            )
            structure_path = (
                Path(str(structure_path_raw))
                if structure_path_raw
                else analysis_path.parent / "song_structure.json"
            )
            updated_structure = (
                read_json(structure_path)
                if structure_path.is_file()
                else {}
            )
            updated_structure.update(structure_updates)

            # All calculations finish before any existing file is replaced.
            write_json_atomic(structure_path, updated_structure)
            write_json_atomic(record_path, updated_record)
            write_json_atomic(analysis_path, updated_analysis)

            self.visual_downbeat_times = list(
                updated_analysis["downbeat_times"]
            )
            self.status_var.set(
                f"Phase {phase_number} confirmed for "
                f"{self.selected_song['title']}"
            )
            self._append(
                f"Confirmed Phase {phase_number}; "
                f"first downbeat beat index {effective_index}"
            )
            self._append(
                "Bars, downbeats and bar-aligned chords rebuilt and saved."
            )
            self._refresh_phase_display()
            messagebox.showinfo(
                APP_TITLE,
                (
                    f"Phase {phase_number} has been confirmed for this song.\n\n"
                    f"Saved first downbeat beat index: {effective_index}\n"
                    "Future playback will open on this confirmed phase."
                ),
            )
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Could not save the confirmed phase:\n{exc}",
            )

    def _stop_visual_test(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self.visual_started_at = None
        if self.visual_window is not None and self.visual_window.winfo_exists():
            self.visual_window.destroy()
        self.visual_window = None

    def _open_folder(self) -> None:
        root = self._library_root()
        if root is None:
            return
        folder = root / "Analysis"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(folder.as_uri())


def main() -> int:
    app = App()

    probe_file = os.environ.get("BANJOFY_STARTUP_PROBE_FILE", "").strip()
    if probe_file:
        probe_path = Path(probe_file)
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_text(
            json.dumps({
                "status": "ready",
                "application": APP_TITLE,
                "library_setting": app.library_var.get(),
            }, indent=2),
            encoding="utf-8",
        )
        app.after(300, app.destroy)

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
