from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar

from banjofy.audio.analyser import AnalysisResult


class AnalysisPanelController:
    """Small controller for analysis display text/progress.

    Build 005.1 starts moving BPM/key/chord analysis display out of
    main_window.py. The analysis itself still lives in audio/analyser.py.
    """

    def __init__(
        self,
        bpm_label: QLabel,
        key_label: QLabel,
        progress_bar: QProgressBar,
        status_label: QLabel,
    ) -> None:
        self.bpm_label = bpm_label
        self.key_label = key_label
        self.progress_bar = progress_bar
        self.status_label = status_label

    def reset(self) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("")

    def waiting_for_download(self) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("")

    def progress(self, message: str, percent: float) -> None:
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(f"Analysis: {message}")

    def error(self, message: str) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Analysis error: {message}")

    def apply_result(self, result: AnalysisResult) -> tuple[int | None, str | None, float, str]:
        detected_bpm: int | None = None
        detected_key: str | None = None
        key_confidence = 0.0

        if result.bpm:
            detected_bpm = int(round(result.bpm))
            self.bpm_label.setText(f"BPM: {detected_bpm} detected")

        if result.key:
            detected_key = result.key
            key_confidence = result.key_confidence
            self.key_label.setText(f"Key: {result.key} detected ({int(round(result.key_confidence * 100))}%)")

        self.progress_bar.setValue(100)

        chord_count = len([c for c in (result.chords_by_bar or []) if c])
        summary_bits: list[str] = []

        if detected_bpm:
            summary_bits.append(f"{detected_bpm} BPM")
        if detected_key:
            summary_bits.append(detected_key)
        if result.estimated_bars:
            summary_bits.append(f"~{result.estimated_bars} bars")
        summary_bits.append(f"{chord_count} chord changes")
        summary_bits.append("stable timing")

        summary = " · ".join(summary_bits)
        self.status_label.setText(f"Analysis: {summary}")
        return detected_bpm, detected_key, key_confidence, summary
