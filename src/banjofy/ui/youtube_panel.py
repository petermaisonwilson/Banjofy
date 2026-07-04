from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidgetItem


def make_youtube_result_item(result) -> QListWidgetItem:
    item = QListWidgetItem(
        f"{getattr(result, 'title', 'Untitled')}\n"
        f"{getattr(result, 'channel', '')} · {getattr(result, 'duration', '')}"
    )
    if getattr(result, "thumbnail_data", None):
        pix = QPixmap()
        if pix.loadFromData(result.thumbnail_data):
            item.setIcon(QIcon(pix))
    return item


def set_thumbnail(label, result_or_data) -> None:
    data = None
    if isinstance(result_or_data, (bytes, bytearray)):
        data = bytes(result_or_data)
    elif result_or_data is not None:
        data = getattr(result_or_data, "thumbnail_data", None)

    if not data:
        label.setPixmap(QPixmap())
        label.setText("No image")
        return

    pix = QPixmap()
    if pix.loadFromData(data):
        label.setPixmap(
            pix.scaled(
                label.width(),
                label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        label.setText("")
    else:
        label.setPixmap(QPixmap())
        label.setText("No image")
