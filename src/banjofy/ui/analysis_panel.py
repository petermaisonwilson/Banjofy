from __future__ import annotations


class AnalysisPanelController:
    def __init__(self, bpm_label, key_label, progress_bar, status_label) -> None:
        self.bpm_label = bpm_label
        self.key_label = key_label
        self.progress_bar = progress_bar
        self.status_label = status_label

    def reset(self) -> None:
        self.bpm_label.setText("BPM: —")
        self.key_label.setText("Key: —")
        self.progress_bar.setValue(0)
        self.status_label.setText("Analysis: waiting")

    def waiting_for_download(self) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("Analysis: waiting for audio download")

    def progress(self, message: str, percent: float) -> None:
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.status_label.setText(f"Analysis: {message}")

    def apply_result(self, result):
        bpm = int(round(getattr(result, "bpm", 0) or 0))
        key = getattr(result, "key", "") or "Unknown"
        confidence = float(getattr(result, "key_confidence", 0.0) or 0.0)

        self.bpm_label.setText(f"BPM: {bpm if bpm else '—'}")
        self.key_label.setText(f"Key: {key}")
        self.progress_bar.setValue(100)

        bars = getattr(result, "estimated_bars", None)
        chord_count = len(getattr(result, "chords_by_bar", []) or [])
        summary = f"{bpm} BPM, key {key}"
        if bars:
            summary += f", {bars} bars"
        elif chord_count:
            summary += f", {chord_count} chord bars"

        self.status_label.setText(f"Analysis: complete - {summary}")
        return bpm, key, confidence, summary

    def error(self, message: str) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Analysis error: {message}")

    # Backwards-compatible method names
    def set_progress(self, value: int, text: str = "") -> None:
        self.progress(text or "working", value)

    def set_result(self, bpm, key, confidence: float = 0.0) -> None:
        self.bpm_label.setText(f"BPM: {bpm if bpm else '—'}")
        self.key_label.setText(f"Key: {key if key else '—'}")
        self.progress_bar.setValue(100)
        self.status_label.setText("Analysis: complete")
