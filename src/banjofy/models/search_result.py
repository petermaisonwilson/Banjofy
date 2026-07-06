from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    channel: str
    duration: str
    url: str
    thumbnail_url: str = ""
    thumbnail_data: bytes | None = None
