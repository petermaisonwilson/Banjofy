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

    def set_progress(self, value: int, text: str = "") -> None:
        self.progress_bar.setValue(value)
        if text:
            self.status_label.setText(text)

    def set_result(self, bpm, key, confidence: float = 0.0) -> None:
        self.bpm_label.setText(f"BPM: {bpm if bpm else '—'}")
        self.key_label.setText(f"Key: {key if key else '—'}")
        self.progress_bar.setValue(100)
        self.status_label.setText("Analysis: complete")
