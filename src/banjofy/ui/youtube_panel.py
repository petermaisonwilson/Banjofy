from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidgetItem


def make_youtube_result_item(result) -> QListWidgetItem:
    item = QListWidgetItem(f"{getattr(result, 'title', 'Untitled')}\n{getattr(result, 'channel', '')} · {getattr(result, 'duration', '')}")
    if getattr(result, "thumbnail_data", None):
        pix = QPixmap()
        if pix.loadFromData(result.thumbnail_data):
            item.setIcon(QIcon(pix))
    return item


def set_thumbnail(label, data: bytes | None) -> None:
    if not data:
        label.setText("No image")
        label.setPixmap(QPixmap())
        return
    pix = QPixmap()
    if pix.loadFromData(data):
        label.setPixmap(pix.scaled(label.width(), label.height()))
        label.setText("")
    else:
        label.setText("No image")
