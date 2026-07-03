from __future__ import annotations

import time


class PlaybackClock:
    def __init__(self) -> None:
        self.started_at: float | None = None
        self.offset_ms = 0

    def start(self) -> None:
        self.started_at = time.monotonic()

    def stop(self) -> None:
        self.started_at = None

    def reset(self) -> None:
        self.started_at = None
        self.offset_ms = 0

    def elapsed_ms(self) -> int:
        if self.started_at is None:
            return self.offset_ms
        return int((time.monotonic() - self.started_at) * 1000) + self.offset_ms
