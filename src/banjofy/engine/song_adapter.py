from __future__ import annotations

from typing import Any

from banjofy.models import Beat, BeatMap, ChordEvent, Song, SongMetadata


def _parse_duration_seconds(duration: str) -> int:
    if not duration:
        return 0
    token = str(duration).replace("Duration:", "").strip().split()[0]
    try:
        parts = [int(p) for p in token.split(":") if p != ""]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(float(token))
    except Exception:
        return 0


def _beats_from_chords(beat_chords: list[str], bpm: float | None) -> BeatMap:
    bpm = bpm or 100
    ms_per_beat = int(60000 / max(1, bpm))
    beats: list[Beat] = []
    current = ""
    for idx, chord in enumerate(beat_chords):
        if chord:
            current = chord
        beats.append(
            Beat(
                index=idx,
                timestamp_ms=idx * ms_per_beat,
                bar_number=(idx // 4) + 1,
                beat_in_bar=(idx % 4) + 1,
                chord=current,
                confidence=None,
            )
        )
    return BeatMap(beats=beats)


def song_model_from_demo_song(demo_song: Any, source_url: str = "") -> Song:
    beat_chords = list(getattr(demo_song, "beat_chords", []) or [])
    bpm = float(getattr(demo_song, "bpm", 0) or 0) or None
    key = getattr(demo_song, "key", None)

    beat_map = _beats_from_chords(beat_chords, bpm)
    chord_events: list[ChordEvent] = []
    last = ""
    for beat in beat_map.beats:
        if beat.chord and beat.chord != last:
            chord_events.append(
                ChordEvent(
                    chord=beat.chord,
                    beat_index=beat.index,
                    timestamp_ms=beat.timestamp_ms,
                    confidence=beat.confidence,
                )
            )
            last = beat.chord

    return Song(
        metadata=SongMetadata(
            title=getattr(demo_song, "title", ""),
            artist=getattr(demo_song, "artist", ""),
            duration=getattr(demo_song, "duration", ""),
            source="YouTube" if source_url else "Demo",
            source_url=source_url,
        ),
        bpm=bpm,
        key=key,
        beat_map=beat_map,
        chord_events=chord_events,
    )


def song_model_from_analysis(
    title: str,
    artist: str,
    duration: str,
    bpm: float | None,
    key: str | None,
    beat_chords: list[str],
    beat_times_ms: list[int] | None = None,
    source_url: str = "",
) -> Song:
    beat_times_ms = beat_times_ms or []
    fallback_bpm = bpm or 100
    ms_per_beat = int(60000 / max(1, fallback_bpm))

    beats: list[Beat] = []
    current = ""
    for idx, chord in enumerate(beat_chords):
        if chord:
            current = chord
        timestamp = beat_times_ms[idx] if idx < len(beat_times_ms) else idx * ms_per_beat
        beats.append(
            Beat(
                index=idx,
                timestamp_ms=timestamp,
                bar_number=(idx // 4) + 1,
                beat_in_bar=(idx % 4) + 1,
                chord=current,
                confidence=None,
            )
        )

    chord_events: list[ChordEvent] = []
    last = ""
    for beat in beats:
        if beat.chord and beat.chord != last:
            chord_events.append(
                ChordEvent(
                    chord=beat.chord,
                    beat_index=beat.index,
                    timestamp_ms=beat.timestamp_ms,
                    confidence=beat.confidence,
                )
            )
            last = beat.chord

    return Song(
        metadata=SongMetadata(
            title=title,
            artist=artist,
            duration=duration,
            source="YouTube" if source_url else "Demo",
            source_url=source_url,
        ),
        bpm=bpm,
        key=key,
        beat_map=BeatMap(beats=beats),
        chord_events=chord_events,
    )
