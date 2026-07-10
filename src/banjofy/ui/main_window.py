from __future__ import annotations

import queue
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QLabel,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QTabWidget,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from banjofy.models.search_result import SearchResult
from banjofy.search.youtube_search import YouTubeSearchManager
from banjofy.storage.paths import get_library_path, set_library_path, audio_folder
from banjofy.download.audio_downloader import DownloadManager, DownloadedAudio
from banjofy.analysis.audio_analysis import AnalysisManager, AnalysisResult
from banjofy.library.song_library import LibraryManager, LibrarySong


APP_VERSION = "Banjofy 006.3.0 Module 8A Build 001 - Playback and Key Display Fix"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.search_manager = YouTubeSearchManager()
        self.download_manager = DownloadManager()
        self.analysis_manager = AnalysisManager()
        self.library_manager = LibraryManager()
        self.search_results: list[SearchResult] = []
        self.selected_result: SearchResult | None = None
        self.downloaded_audio: DownloadedAudio | None = None
        self.analysis_result: AnalysisResult | None = None
        self.library_songs: list[LibrarySong] = []
        self.selected_library_song: LibrarySong | None = None
        self.practice_song: LibrarySong | None = None
        self.grid_cells: list[QLabel] = []
        self.grid_bar_count = 0
        self.current_beat_index = 0
        self.search_queue: queue.Queue = queue.Queue()
        self.download_queue: queue.Queue = queue.Queue()
        self.analysis_queue: queue.Queue = queue.Queue()

        self.setWindowTitle(APP_VERSION)
        self.resize(1200, 760)
        self._build_ui()
        self._apply_style()

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)
        self.media_player.positionChanged.connect(self._player_position_changed)
        self.media_player.durationChanged.connect(self._player_duration_changed)
        self.media_player.playbackStateChanged.connect(self._player_state_changed)

        self.search_poll_timer = QTimer(self)
        self.search_poll_timer.timeout.connect(self._poll_search_results)

        self.download_poll_timer = QTimer(self)
        self.download_poll_timer.timeout.connect(self._poll_download_results)

        self.analysis_poll_timer = QTimer(self)
        self.analysis_poll_timer.timeout.connect(self._poll_analysis_results)

        self.setStatusBar(QStatusBar())
        self._refresh_library_status()
        self._refresh_library_list()
        self.statusBar().showMessage("Ready - Module 8A playback and key display fix loaded")

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title = QLabel(APP_VERSION)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("Title")
        outer.addWidget(title)

        note = QLabel("Module 5 test build: Search + Download + Analysis + Library save/list. No Practice yet.")
        note.setObjectName("Hint")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(note)

        self.library_setup_panel = QWidget()
        self.library_setup_panel.setObjectName("LibrarySetupPanel")
        library_panel_layout = QVBoxLayout(self.library_setup_panel)
        library_panel_layout.setContentsMargins(8, 8, 8, 8)
        library_panel_layout.setSpacing(6)

        self.library_path_label = QLabel("LIBRARY: not set")
        self.library_path_label.setObjectName("LibraryPathLabel")
        self.library_path_label.setWordWrap(True)
        library_panel_layout.addWidget(self.library_path_label)

        self.restart_banner = QLabel("")
        self.restart_banner.setObjectName("RestartBanner")
        self.restart_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.restart_banner.setVisible(False)
        library_panel_layout.addWidget(self.restart_banner)

        self.choose_library_button = QPushButton("CHOOSE / CHANGE LIBRARY FOLDER")
        self.choose_library_button.setMinimumHeight(44)
        self.choose_library_button.clicked.connect(self._choose_library_folder)
        library_panel_layout.addWidget(self.choose_library_button)

        outer.addWidget(self.library_setup_panel)

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
        self.result_list.setMaximumHeight(300)
        self.result_list.itemClicked.connect(self._select_result)
        left.addWidget(self.result_list, 1)

        left.addWidget(QLabel("Library"))
        self.library_message_label = QLabel("Library: ready")
        self.library_message_label.setObjectName("LibraryMessage")
        self.library_message_label.setWordWrap(True)
        left.addWidget(self.library_message_label)
        self.library_list = QListWidget()
        self.library_list.setMinimumHeight(260)
        self.library_list.itemClicked.connect(self._select_library_song)
        left.addWidget(self.library_list, 2)

        library_buttons = QHBoxLayout()
        self.save_library_button = QPushButton("Save Analysis to Library")
        self.save_library_button.setEnabled(False)
        self.save_library_button.clicked.connect(self._save_analysis_to_library)
        self.refresh_library_button = QPushButton("Refresh Library")
        self.refresh_library_button.clicked.connect(self._refresh_library_list)
        self.send_practice_button = QPushButton("Send to Practice")
        self.send_practice_button.setEnabled(False)
        self.send_practice_button.clicked.connect(self._send_library_to_practice_placeholder)
        library_buttons.addWidget(self.save_library_button)
        library_buttons.addWidget(self.refresh_library_button)
        library_buttons.addWidget(self.send_practice_button)
        left.addLayout(library_buttons)

        body.addLayout(left, 2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Selected Result"))
        self.thumbnail = QLabel("No result selected")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(320, 180)
        self.thumbnail.setMinimumSize(320, 180)
        self.thumbnail.setMaximumSize(320, 180)
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

        self.download_button = QPushButton("Download Selected Audio")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._start_download)

        self.download_status = QLabel("Download: select a result first")
        self.download_status.setWordWrap(True)
        self.download_status.setMaximumHeight(44)
        self.audio_folder_label = QLabel("Audio folder: choose Library folder first")
        self.audio_folder_label.setWordWrap(True)
        self.audio_folder_label.setMaximumHeight(44)

        self.analyse_button = QPushButton("Analyse Downloaded Audio")
        self.analyse_button.setEnabled(False)
        self.analyse_button.clicked.connect(self._start_analysis)

        self.analysis_status = QLabel("Analysis: download audio first")
        self.analysis_status.setWordWrap(True)
        self.analysis_status.setMaximumHeight(60)

        right.addWidget(self.download_button)
        right.addWidget(self.download_status)
        right.addWidget(self.audio_folder_label)
        right.addWidget(self.analyse_button)
        right.addWidget(self.analysis_status)
        right.addStretch()
        body.addLayout(right, 1)

        outer.addLayout(body, 1)
        self.library_page = root
        self.practice_page = self._build_practice_page()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.library_page, "Library / Search")
        self.tabs.addTab(self.practice_page, "Practice Studio")

        self.setCentralWidget(self.tabs)

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
            QWidget#LibrarySetupPanel {
                background: #1b2638;
                border: 2px solid #f3d99a;
                border-radius: 6px;
            }
            QLabel#LibraryPathLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#RestartBanner {
                background: #6b1f1f;
                color: #ffffff;
                border: 2px solid #ffcc88;
                padding: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#LibraryMessage {
                background: #202020;
                color: #f3d99a;
                border: 1px solid #555;
                padding: 6px;
                font-weight: bold;
            }
            QLabel#GridHeader {
                background: #303030;
                color: #f3d99a;
                border: 1px solid #555;
                padding: 4px;
                font-weight: bold;
            }
            QLabel#BarLabel {
                background: #242424;
                color: #dddddd;
                border: 1px solid #444;
                padding: 4px;
            }
            QLabel#BeatCell {
                background: #181818;
                color: #dddddd;
                border: 1px solid #555;
                padding: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#BeatCell[active="true"] {
                background: #f3d99a;
                color: #111111;
                border: 2px solid #ffffff;
            }
        """)

    def _refresh_library_status(self) -> None:
        path = get_library_path()
        if path is None:
            self.library_path_label.setText("Library: not set - choose a permanent folder")
            self.restart_banner.setVisible(False)
        else:
            self.library_path_label.setText(f"Library: {path}")
            if hasattr(self, "audio_folder_label"):
                self.audio_folder_label.setText("Audio folder: ready")
            self.restart_banner.setVisible(False)

    def _choose_library_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Banjofy Library Folder")
        if not folder:
            return
        path = set_library_path(folder)
        self.library_path_label.setText(f"Library: {path}")
        if hasattr(self, "audio_folder_label"):
            self.audio_folder_label.setText("Audio folder: ready")
        self.restart_banner.setText("IMPORTANT: Library folder set. Please close and restart Banjofy before continuing.")
        self.restart_banner.setVisible(True)
        self._refresh_library_list()
        self.statusBar().showMessage(f"Library folder set: {path}. Please restart Banjofy.")

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
        self.downloaded_audio = None
        self.analysis_result = None
        self._clear_selected_panel()
        self.download_button.setEnabled(False)
        self.analyse_button.setEnabled(False)
        self.download_status.setText("Download: select a result first")
        self.analysis_status.setText("Analysis: download audio first")
        if hasattr(self, "save_library_button"):
            self.save_library_button.setEnabled(False)
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
        self.downloaded_audio = None
        self.analysis_result = None
        self._show_selected_result(self.selected_result)
        self.download_button.setEnabled(True)
        self.analyse_button.setEnabled(False)
        self.download_status.setText("Download: ready")
        self.analysis_status.setText("Analysis: download audio first")
        if hasattr(self, "save_library_button"):
            self.save_library_button.setEnabled(False)
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

    def _build_practice_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title = QLabel("Practice Studio - Player Foundation")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        hint = QLabel("Module 6: Library song playback only. Chord grid, timing and diagrams come later.")
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(hint)

        body = QHBoxLayout()

        left = QVBoxLayout()
        self.practice_artwork = QLabel("No song loaded")
        self.practice_artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.practice_artwork.setFixedSize(360, 220)
        self.practice_artwork.setMinimumSize(360, 220)
        self.practice_artwork.setMaximumSize(360, 220)
        self.practice_artwork.setObjectName("Thumbnail")
        left.addWidget(self.practice_artwork, alignment=Qt.AlignmentFlag.AlignCenter)

        self.practice_title_label = QLabel("Title: —")
        self.practice_title_label.setWordWrap(True)
        self.practice_channel_label = QLabel("Artist/Channel: —")
        self.practice_duration_label = QLabel("Duration: —")
        self.practice_bpm_label = QLabel("BPM: —")
        self.practice_key_label = QLabel("Key: not available yet")
        for label in [
            self.practice_title_label,
            self.practice_channel_label,
            self.practice_duration_label,
            self.practice_bpm_label,
            self.practice_key_label,
        ]:
            label.setObjectName("PracticeInfo")
            left.addWidget(label)

        body.addLayout(left, 1)

        right = QVBoxLayout()
        self.practice_message = QLabel("Select a Library song, then click Send to Practice.")
        self.practice_message.setObjectName("LibraryMessage")
        self.practice_message.setWordWrap(True)
        right.addWidget(self.practice_message)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.play_button.clicked.connect(self._practice_play)
        self.pause_button.clicked.connect(self._practice_pause)
        self.stop_button.clicked.connect(self._practice_stop)
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        right.addLayout(controls)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._practice_seek)
        right.addWidget(self.position_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.time_label)

        self.grid_status_label = QLabel("Grid: no song loaded")
        self.grid_status_label.setObjectName("LibraryMessage")
        self.grid_status_label.setWordWrap(True)
        right.addWidget(self.grid_status_label)

        self.beat_grid_container = QWidget()
        self.beat_grid_layout = QGridLayout(self.beat_grid_container)
        self.beat_grid_layout.setContentsMargins(4, 4, 4, 4)
        self.beat_grid_layout.setSpacing(3)

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setMinimumHeight(260)
        self.grid_scroll.setWidget(self.beat_grid_container)
        right.addWidget(self.grid_scroll, 1)

        self.loaded_audio_label = QLabel("Audio: none")
        self.loaded_audio_label.setWordWrap(True)
        right.addWidget(self.loaded_audio_label)

        right.addStretch()
        body.addLayout(right, 1)

        outer.addLayout(body, 1)
        return page

    def _load_selected_song_into_practice(self) -> None:
        if not self.selected_library_song:
            self._set_library_message("Select a Library song first")
            return

        song = self.selected_library_song
        self.practice_song = song
        self.practice_title_label.setText(f"Title: {song.title}")
        self.practice_channel_label.setText(f"Artist/Channel: {song.channel}")
        self.practice_duration_label.setText(f"Duration: {song.duration}")
        self.practice_bpm_label.setText(f"BPM: {song.bpm}")
        self.practice_key_label.setText(f"Key: {getattr(song, 'key', 'Unknown')}")

        audio_path = Path(song.audio_file)
        if not audio_path.exists():
            self.practice_message.setText("Audio file missing. Re-download this song before practice.")
            self.loaded_audio_label.setText(f"Audio missing: {audio_path}")
            self._set_library_message(f"Practice load failed: audio missing for {song.title}")
            self.tabs.setCurrentWidget(self.practice_page)
            return

        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(audio_path)))
        self.position_slider.setValue(0)
        self.current_beat_index = 0
        self.practice_artwork.setText("Artwork\ncoming later")
        self._build_beat_grid(song)
        self._highlight_beat(0)
        self.practice_message.setText(f"Loaded for Practice: {song.title}")
        self.loaded_audio_label.setText(f"Audio loaded: {audio_path.name}")
        self._set_library_message(f"Loaded into Practice: {song.title}")
        self.tabs.setCurrentWidget(self.practice_page)

    def _build_beat_grid(self, song: LibrarySong) -> None:
        while self.beat_grid_layout.count():
            item = self.beat_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.grid_cells = []
        try:
            bars = int(song.estimated_bars)
        except Exception:
            bars = 16
        bars = max(16, min(300, bars))
        self.grid_bar_count = bars

        chords_by_bar = getattr(song, "chords_by_bar", None) or []
        # Module 8 feeds analysis chord data into the grid.
        # Accuracy remains provisional until the real chord-recognition module.
        header = QLabel("Bar")
        header.setObjectName("GridHeader")
        self.beat_grid_layout.addWidget(header, 0, 0)

        for beat in range(4):
            beat_header = QLabel(f"Beat {beat + 1}")
            beat_header.setObjectName("GridHeader")
            beat_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beat_grid_layout.addWidget(beat_header, 0, beat + 1)

        for bar in range(bars):
            bar_label = QLabel(str(bar + 1))
            bar_label.setObjectName("BarLabel")
            bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beat_grid_layout.addWidget(bar_label, bar + 1, 0)

            for beat in range(4):
                chord_name = chords_by_bar[bar] if bar < len(chords_by_bar) else ""
                cell_text = chord_name if beat == 0 and chord_name else "•"
                cell = QLabel(cell_text)
                cell.setObjectName("BeatCell")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setMinimumSize(54, 30)
                cell.setProperty("beat_index", bar * 4 + beat)
                self.beat_grid_layout.addWidget(cell, bar + 1, beat + 1)
                self.grid_cells.append(cell)

        self.grid_status_label.setText(f"Grid: {bars} bars / {bars * 4} beats | chords provisional")
        self._highlight_beat(0)

    def _highlight_beat(self, beat_index: int) -> None:
        if not self.grid_cells:
            return

        beat_index = max(0, min(beat_index, len(self.grid_cells) - 1))
        self.current_beat_index = beat_index

        for i, cell in enumerate(self.grid_cells):
            bar = i // 4
            beat = i % 4
            chords_by_bar = getattr(self.practice_song, "chords_by_bar", None) or []
            chord_name = chords_by_bar[bar] if bar < len(chords_by_bar) else ""
            base_text = chord_name if beat == 0 and chord_name else "•"

            if i == beat_index:
                cell.setProperty("active", True)
                cell.setText(f"▶ {base_text}" if base_text != "•" else "▶")
            else:
                cell.setProperty("active", False)
                cell.setText(base_text)
            cell.style().unpolish(cell)
            cell.style().polish(cell)

        self._scroll_grid_to_beat(beat_index)

    def _scroll_grid_to_beat(self, beat_index: int) -> None:
        if not hasattr(self, "grid_scroll") or not self.grid_cells:
            return
        cell = self.grid_cells[max(0, min(beat_index, len(self.grid_cells) - 1))]
        self.grid_scroll.ensureWidgetVisible(cell, 20, 80)

    def _update_grid_cursor_from_position(self, position_ms: int) -> None:
        if not self.practice_song or not self.grid_cells:
            return
        duration = self.media_player.duration()
        if duration <= 0:
            return
        total_beats = len(self.grid_cells)
        beat_index = int((position_ms / duration) * total_beats)
        beat_index = max(0, min(beat_index, total_beats - 1))
        if beat_index != self.current_beat_index:
            self._highlight_beat(beat_index)

    def _practice_play(self) -> None:
        if not self.practice_song:
            self.practice_message.setText("Load a Library song into Practice first.")
            return
        duration = self.media_player.duration()
        if duration > 0 and self.media_player.position() >= max(0, duration - 250):
            self.media_player.setPosition(0)
            self.position_slider.setValue(0)
            self.current_beat_index = 0
            self._highlight_beat(0)
        self.media_player.play()

    def _practice_pause(self) -> None:
        self.media_player.pause()

    def _practice_stop(self) -> None:
        self.media_player.stop()
        self.media_player.setPosition(0)
        if hasattr(self, "position_slider"):
            self.position_slider.setValue(0)
        self.current_beat_index = 0
        self._highlight_beat(0)
        if hasattr(self, "time_label"):
            self._update_time_label(0, self.media_player.duration())
        if hasattr(self, "practice_message") and self.practice_song:
            self.practice_message.setText(f"Stopped: {self.practice_song.title}")

    def _practice_seek(self, position: int) -> None:
        self.media_player.setPosition(position)

    def _player_position_changed(self, position: int) -> None:
        if hasattr(self, "position_slider") and not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        if hasattr(self, "time_label"):
            self._update_time_label(position, self.media_player.duration())
        self._update_grid_cursor_from_position(position)

    def _player_duration_changed(self, duration: int) -> None:
        if hasattr(self, "position_slider"):
            self.position_slider.setRange(0, max(0, duration))
        if hasattr(self, "time_label"):
            self._update_time_label(self.media_player.position(), duration)

    def _player_state_changed(self, state) -> None:
        if not hasattr(self, "practice_message"):
            return
        if self.practice_song:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.practice_message.setText(f"Playing: {self.practice_song.title}")
            elif state == QMediaPlayer.PlaybackState.PausedState:
                self.practice_message.setText(f"Paused: {self.practice_song.title}")
            elif state == QMediaPlayer.PlaybackState.StoppedState:
                self.practice_message.setText(f"Stopped: {self.practice_song.title}")

    def _update_time_label(self, position_ms: int, duration_ms: int) -> None:
        self.time_label.setText(f"{self._format_ms(position_ms)} / {self._format_ms(duration_ms)}")

    def _format_ms(self, value: int) -> str:
        seconds = max(0, int(value / 1000))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _set_library_message(self, message: str) -> None:
        if hasattr(self, "library_message_label"):
            self.library_message_label.setText(message)
        self.statusBar().showMessage(message)

    def _refresh_library_list(self) -> None:
        self.library_list.clear()
        self.library_songs = []
        self.selected_library_song = None
        if hasattr(self, "send_practice_button"):
            self.send_practice_button.setEnabled(False)

        if get_library_path() is None:
            self.library_list.addItem(QListWidgetItem("Choose Library folder first"))
            self._set_library_message("Library refresh: choose Library folder first")
            return

        self.library_songs = self.library_manager.load_all()
        if not self.library_songs:
            self.library_list.addItem(QListWidgetItem("No saved songs yet"))
            self._set_library_message("Library refreshed: 0 songs found")
            return

        for song in self.library_songs:
            item_text = f"{song.title}\n{song.channel} · {song.duration} · BPM {song.bpm}"
            self.library_list.addItem(QListWidgetItem(item_text))

        self._set_library_message(f"Library refreshed: {len(self.library_songs)} songs found")

    def _save_analysis_to_library(self) -> None:
        if not self.analysis_result:
            self._set_library_message("Analyse a downloaded song before saving to Library")
            return
        try:
            path = self.library_manager.save_from_analysis(self.analysis_result)
            self._refresh_library_list()
            self._set_library_message(f"Saved to Library: {path.name}")
        except Exception as exc:
            self._set_library_message(f"Save to Library failed: {exc}")

    def _select_library_song(self, item: QListWidgetItem) -> None:
        row = self.library_list.row(item)
        if row < 0 or row >= len(self.library_songs):
            self.selected_library_song = None
            self.send_practice_button.setEnabled(False)
            self._set_library_message("No saved Library song selected")
            return

        self.selected_library_song = self.library_songs[row]
        self.send_practice_button.setEnabled(True)
        self._set_library_message(
            f"Library song selected: {self.selected_library_song.title} | Send to Practice now available"
        )

    def _send_library_to_practice_placeholder(self) -> None:
        if not self.selected_library_song:
            self._set_library_message("Select a Library song first")
            return
        self._load_selected_song_into_practice()

    def _start_download(self) -> None:
        if not self.selected_result:
            self.statusBar().showMessage("Select a result before downloading")
            return

        if get_library_path() is None:
            self.statusBar().showMessage("Choose a Library folder before downloading")
            self.download_status.setText("Download: choose Library folder first")
            return

        self.download_button.setEnabled(False)
        self.download_status.setText("Download: starting...")
        self.statusBar().showMessage(f"Downloading audio: {self.selected_result.title}")

        def progress(message: str, percent: int, detail: str) -> None:
            self.download_queue.put(("progress", (message, percent, detail)))

        def worker() -> None:
            try:
                result = self.download_manager.download(self.selected_result, progress=progress)
                self.download_queue.put(("done", result))
            except Exception as exc:
                self.download_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.download_poll_timer.start(100)

    def _poll_download_results(self) -> None:
        while True:
            try:
                kind, payload = self.download_queue.get_nowait()
            except queue.Empty:
                return

            if kind == "progress":
                message, percent, detail = payload
                suffix = f" ({percent}%)" if percent is not None else ""
                self.download_status.setText(f"Download: {message}{suffix}")
                self.statusBar().showMessage(f"Download: {message}{suffix}")
            elif kind == "done":
                self.download_poll_timer.stop()
                self.download_button.setEnabled(True)
                self.downloaded_audio = payload
                cached = "cached" if payload.was_cached else "downloaded"
                self.download_status.setText(f"Download: {cached}")
                self.analyse_button.setEnabled(True)
                self.analysis_status.setText("Analysis: ready")
                self.statusBar().showMessage(f"Audio {cached}: {payload.file_path}")
                return
            elif kind == "error":
                self.download_poll_timer.stop()
                self.download_button.setEnabled(True)
                self.download_status.setText(f"Download error: {payload}")
                self.statusBar().showMessage(f"Download error: {payload}")
                return

    def _start_analysis(self) -> None:
        if not self.downloaded_audio:
            self.statusBar().showMessage("Download audio before analysis")
            self.analysis_status.setText("Analysis: download audio first")
            return

        self.analyse_button.setEnabled(False)
        self.analysis_status.setText("Analysis: running...")
        self.statusBar().showMessage(f"Analysing: {self.downloaded_audio.title}")

        def worker() -> None:
            try:
                result = self.analysis_manager.analyse(self.downloaded_audio)
                self.analysis_queue.put(("done", result))
            except Exception as exc:
                self.analysis_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.analysis_poll_timer.start(100)

    def _poll_analysis_results(self) -> None:
        try:
            kind, payload = self.analysis_queue.get_nowait()
        except queue.Empty:
            return

        self.analysis_poll_timer.stop()
        self.analyse_button.setEnabled(True)

        if kind == "error":
            self.analysis_status.setText(f"Analysis error: {payload}")
            self.statusBar().showMessage(f"Analysis error: {payload}")
            return

        self.analysis_result = payload
        self.save_library_button.setEnabled(True)
        self.analysis_status.setText(
            f"Analysis: complete | BPM {payload.bpm} | Key {payload.key} | Bars {payload.estimated_bars}"
        )
        self.statusBar().showMessage(
            f"Analysis complete: BPM {payload.bpm}, Key {payload.key}, Bars {payload.estimated_bars}. Use Save Analysis to Library if wanted."
        )

    def _clear_selected_panel(self) -> None:
        self.thumbnail.setPixmap(QPixmap())
        self.thumbnail.setText("No result selected")
        self.selected_title.setText("Title: —")
        self.selected_channel.setText("Channel: —")
        self.selected_duration.setText("Duration: —")
        self.selected_url.setPlainText("")
        if hasattr(self, "download_button"):
            self.download_button.setEnabled(False)
        if hasattr(self, "download_status"):
            self.download_status.setText("Download: select a result first")
        if hasattr(self, "analyse_button"):
            self.analyse_button.setEnabled(False)
        if hasattr(self, "analysis_status"):
            self.analysis_status.setText("Analysis: download audio first")
