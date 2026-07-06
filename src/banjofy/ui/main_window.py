from __future__ import annotations

import queue
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from banjofy.models.search_result import SearchResult
from banjofy.search.youtube_search import YouTubeSearchManager


APP_VERSION = "Banjofy 006.3.0 Module 1 - Shell + Search"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.search_manager = YouTubeSearchManager()
        self.search_results: list[SearchResult] = []
        self.selected_result: SearchResult | None = None
        self.search_queue: queue.Queue = queue.Queue()

        self.setWindowTitle(APP_VERSION)
        self.resize(1200, 760)
        self._build_ui()
        self._apply_style()

        self.search_poll_timer = QTimer(self)
        self.search_poll_timer.timeout.connect(self._poll_search_results)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready - Module 1 search shell loaded")

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title = QLabel(APP_VERSION)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("Title")
        outer.addWidget(title)

        note = QLabel("Module 1 test build: Search only. Selecting a result must not download, analyse, save, or open Practice.")
        note.setObjectName("Hint")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(note)

        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search YouTube for a song or artist")
        self.search_box.returnPressed.connect(self._start_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._start_search)
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.search_button)
        outer.addLayout(search_row)

        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Search Results"))
        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._select_result)
        left.addWidget(self.result_list, 1)
        body.addLayout(left, 2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Selected Result"))
        self.thumbnail = QLabel("No result selected")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(320, 180)
        self.thumbnail.setObjectName("Thumbnail")
        right.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignCenter)

        self.selected_title = QLabel("Title: —")
        self.selected_title.setWordWrap(True)
        self.selected_channel = QLabel("Channel: —")
        self.selected_duration = QLabel("Duration: —")
        self.selected_url = QTextEdit()
        self.selected_url.setReadOnly(True)
        self.selected_url.setMaximumHeight(80)

        right.addWidget(self.selected_title)
        right.addWidget(self.selected_channel)
        right.addWidget(self.selected_duration)
        right.addWidget(QLabel("URL"))
        right.addWidget(self.selected_url)
        right.addStretch()
        body.addLayout(right, 1)

        outer.addLayout(body, 1)
        self.setCentralWidget(root)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background: #101010;
                color: #f4ead0;
                font-size: 14px;
            }
            QLabel#Title {
                font-size: 18px;
                font-weight: bold;
                color: #f3d99a;
            }
            QLabel#Hint {
                color: #d8c9a2;
            }
            QLineEdit, QListWidget, QTextEdit {
                background: #202020;
                border: 1px solid #444;
                padding: 6px;
                color: #ffffff;
            }
            QPushButton {
                background: #303030;
                border: 1px solid #555;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #3b3b3b;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background: #5a4219;
            }
            QLabel#Thumbnail {
                background: #181818;
                border: 1px solid #555;
            }
        """)

    def _start_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            self.statusBar().showMessage("Enter a song or artist first")
            return

        self.search_button.setEnabled(False)
        self.result_list.clear()
        self.result_list.addItem(QListWidgetItem(f"Searching YouTube for: {query}\nPlease wait..."))
        self.search_results = []
        self.selected_result = None
        self._clear_selected_panel()
        self.statusBar().showMessage(f"Searching YouTube for: {query}")

        def worker() -> None:
            try:
                results = self.search_manager.search(query, limit=8)
                self.search_queue.put(("results", results))
            except Exception as exc:
                self.search_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.search_poll_timer.start(100)

    def _poll_search_results(self) -> None:
        try:
            kind, payload = self.search_queue.get_nowait()
        except queue.Empty:
            return

        self.search_poll_timer.stop()
        self.search_button.setEnabled(True)
        self.result_list.clear()

        if kind == "error":
            self.result_list.addItem(QListWidgetItem(f"YouTube search error\n{payload}"))
            self.statusBar().showMessage(f"YouTube search error: {payload}")
            return

        self.search_results = payload if isinstance(payload, list) else []
        if not self.search_results:
            self.result_list.addItem(QListWidgetItem("No YouTube results found"))
            self.statusBar().showMessage("No YouTube results found")
            return

        for result in self.search_results:
            item = QListWidgetItem(f"{result.title}\n{result.channel} · {result.duration}")
            if result.thumbnail_data:
                pix = QPixmap()
                if pix.loadFromData(result.thumbnail_data):
                    item.setIcon(QIcon(pix))
            self.result_list.addItem(item)

        self.statusBar().showMessage(f"Found {len(self.search_results)} results. Click one to select it.")

    def _select_result(self, item: QListWidgetItem) -> None:
        row = self.result_list.row(item)
        if row < 0 or row >= len(self.search_results):
            return
        self.selected_result = self.search_results[row]
        self._show_selected_result(self.selected_result)
        self.statusBar().showMessage(f"Selected only: {self.selected_result.title}")

    def _show_selected_result(self, result: SearchResult) -> None:
        self.selected_title.setText(f"Title: {result.title}")
        self.selected_channel.setText(f"Channel: {result.channel or '—'}")
        self.selected_duration.setText(f"Duration: {result.duration or '—'}")
        self.selected_url.setPlainText(result.url)

        if result.thumbnail_data:
            pix = QPixmap()
            if pix.loadFromData(result.thumbnail_data):
                self.thumbnail.setPixmap(
                    pix.scaled(
                        self.thumbnail.width(),
                        self.thumbnail.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.thumbnail.setText("")
                return

        self.thumbnail.setPixmap(QPixmap())
        self.thumbnail.setText("No thumbnail")

    def _clear_selected_panel(self) -> None:
        self.thumbnail.setPixmap(QPixmap())
        self.thumbnail.setText("No result selected")
        self.selected_title.setText("Title: —")
        self.selected_channel.setText("Channel: —")
        self.selected_duration.setText("Duration: —")
        self.selected_url.setPlainText("")
