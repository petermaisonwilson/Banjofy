from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QLabel, QListWidgetItem

from banjofy.youtube.search import YouTubeResult


def make_youtube_result_item(result: YouTubeResult, icon_size: QSize = QSize(96, 54)) -> QListWidgetItem:
    """Create a visible YouTube search result row.

    Build 005.0 begins separating YouTube/search UI code out of main_window.py.
    """
    item = QListWidgetItem(f"YOUTUBE · {result.title}\n{result.channel} · {result.duration}")

    if result.thumbnail_data:
        pix = QPixmap()
        if pix.loadFromData(result.thumbnail_data):
            item.setIcon(
                QIcon(
                    pix.scaled(
                        icon_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            )

    return item


def set_thumbnail(label: QLabel, result: YouTubeResult | None, width: int = 112, height: int = 63) -> None:
    """Update the selected-video thumbnail label."""
    if result and result.thumbnail_data:
        pix = QPixmap()
        if pix.loadFromData(result.thumbnail_data):
            label.setPixmap(
                pix.scaled(
                    width,
                    height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            label.setText("")
            return

    label.setPixmap(QPixmap())
    label.setText("No image")
