from __future__ import annotations

import queue
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QProgressBar,
    QScrollArea, QSlider, QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from banjofy.audio.analyser import AnalysisResult, analyse_audio
from banjofy.banjo.chords import transpose_chord
from banjofy.player.demo_data import DEMO_SONGS, DemoSong
from banjofy.ui.widgets import BeatCell, ChordPanel
from banjofy.youtube.downloader import DownloadResult, download_audio
from banjofy.youtube.search import YouTubeResult, search_youtube

APP_VERSION = "Banjofy 0.4.7F - Timing + Capo Fix"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_VERSION)
        self.resize(1360, 840)
        self.setMinimumSize(1050, 700)

        self.song: DemoSong = DEMO_SONGS[0]
        self.position = 0
        self.is_playing = False
        self.count_in_remaining = 0
        self.loop_start: int | None = None
        self.loop_end: int | None = None
        self.selection_mode: str | None = None
        self.cells: list[BeatCell] = []

        self.youtube_results: list[YouTubeResult] = []
        self.selected_youtube_result: YouTubeResult | None = None
        self.downloaded_audio_path: Path | None = None
        self.audio_ready = False
        self.detected_bpm: int | None = None
        self.detected_key: str | None = None
        self.detected_key_confidence = 0.0
        self.beat_times_ms: list[int] = []
        self.sync_offset_beats = 0

        self.search_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.download_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.analysis_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.search_poll_timer = QTimer(self)
        self.search_poll_timer.timeout.connect(self._poll_search_results)
        self.download_poll_timer = QTimer(self)
        self.download_poll_timer.timeout.connect(self._poll_download_results)
        self.analysis_poll_timer = QTimer(self)
        self.analysis_poll_timer.timeout.connect(self._poll_analysis_results)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.errorOccurred.connect(self._media_error)
        self.media_player.mediaStatusChanged.connect(self._media_status_changed)

        self._apply_style()
        self.setCentralWidget(self._build_ui())
        self.setStatusBar(QStatusBar())
        self._load_song(self.song)
        self._update_all()
        self.statusBar().showMessage("Build 004.7F ready - stable timing sync, capo fix, and filled extended bars.")

    def _build_ui(self) -> QWidget:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(4)
        outer.addLayout(top, 0)

        search_panel = self._panel()
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(6, 4, 6, 4)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search YouTube, e.g. Country Roads banjo")
        self.search.returnPressed.connect(self._start_youtube_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._start_youtube_search)
        search_row.addWidget(self.search)
        search_row.addWidget(self.search_button)
        search_layout.addLayout(search_row)

        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(128)
        self.result_list.setIconSize(QSize(96, 54))
        self.result_list.currentRowChanged.connect(self._select_result)
        for song in DEMO_SONGS:
            self.result_list.addItem(QListWidgetItem(f"DEMO · {song.title}\n{song.artist} · {song.duration} · {song.bpm} BPM"))
        search_layout.addWidget(self.result_list)

        workflow_layout = QVBoxLayout()
        workflow_layout.setSpacing(2)

        self.search_hint = QLabel("Search\nSelect\nDownload\nPlay")
        self.search_hint.setObjectName("HintLabel")
        workflow_layout.addWidget(self.search_hint)

        download_row = QHBoxLayout()
        download_row.setSpacing(6)
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._start_audio_download)
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumWidth(92)
        self.download_btn.setMaximumWidth(120)
        download_row.addWidget(self.download_btn)

        download_col = QVBoxLayout()
        download_col.setSpacing(1)
        download_label = QLabel("Download")
        download_label.setObjectName("HintLabel")
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setTextVisible(True)
        self.download_progress.setMaximumHeight(18)
        download_col.addWidget(download_label)
        download_col.addWidget(self.download_progress)
        download_row.addLayout(download_col)

        analysis_col = QVBoxLayout()
        analysis_col.setSpacing(1)
        analysis_label = QLabel("Audio Analysis")
        analysis_label.setObjectName("HintLabel")
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setTextVisible(True)
        self.analysis_progress.setMaximumHeight(18)
        analysis_col.addWidget(analysis_label)
        analysis_col.addWidget(self.analysis_progress)
        download_row.addLayout(analysis_col)

        workflow_layout.addLayout(download_row)

        self.download_status = QLabel("")
        self.download_status.setObjectName("HintLabel")
        self.download_status.setVisible(False)
        self.analysis_status = QLabel("")
        self.analysis_status.setObjectName("HintLabel")
        self.analysis_status.setVisible(False)

        search_layout.addLayout(workflow_layout)
        top.addWidget(search_panel, 3)

        meta_panel = self._panel()
        meta_layout = QVBoxLayout(meta_panel)
        meta_layout.setContentsMargins(6, 4, 6, 4)
        self.thumbnail_label = QLabel("No image")
        self.thumbnail_label.setObjectName("ThumbnailBox")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(112, 63)
        meta_layout.addWidget(self.thumbnail_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("—")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(48)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #f3d99a;")
        self.artist_label = QLabel("—")
        self.artist_label.setWordWrap(True)
        self.artist_label.setMaximumHeight(26)
        self.source_label = QLabel("")
        self.source_label.setVisible(False)
        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.artist_label)

        self.bpm_label = QLabel("BPM: —")
        self.key_label = QLabel("Key: —")
        self.duration_label = QLabel("Duration: —")
        for w in [self.bpm_label, self.key_label, self.duration_label]:
            meta_layout.addWidget(w)

        top.addWidget(meta_panel, 1)

        centre = self._panel()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(6, 4, 6, 4)
        title = QLabel(APP_VERSION)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f3d99a;")
        centre_layout.addWidget(title)

        chord_row = QHBoxLayout()
        self.current_panel = ChordPanel("NOW", "—", "#65b95c")
        self.next_panel = ChordPanel("NEXT", "—", "#c99424", "in 1")
        self.current_panel.setMaximumHeight(145)
        self.next_panel.setMaximumHeight(145)
        chord_row.addWidget(self.current_panel, 1)
        chord_row.addWidget(self.next_panel, 1)
        centre_layout.addLayout(chord_row)

        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setObjectName("CountdownLabel")
        self.countdown_label.setVisible(False)
        centre_layout.addWidget(self.countdown_label)
        top.addWidget(centre, 3)

        settings = self._panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(6, 4, 6, 4)
        settings_layout.addWidget(QLabel("Mode"))
        self.mode = QComboBox()
        self.mode.addItems(["Beginner", "Intermediate", "Professional"])
        self.mode.setCurrentText("Intermediate")
        self.mode.currentTextChanged.connect(self._mode_changed)
        settings_layout.addWidget(self.mode)
        settings_layout.addWidget(QLabel("Capo"))
        self.capo = QSpinBox()
        self.capo.setRange(0, 12)
        self.capo.setMinimumWidth(78)
        self.capo.setMinimumHeight(34)
        self.capo.valueChanged.connect(self._update_all)
        settings_layout.addWidget(self.capo)
        settings_layout.addWidget(QLabel("Show"))
        self.show_mode = QComboBox()
        self.show_mode.addItems(["Concert Chords", "Banjo Shapes"])
        self.show_mode.currentTextChanged.connect(self._update_all)
        settings_layout.addWidget(self.show_mode)
        settings_layout.addWidget(QLabel("Count-in"))
        self.count_in = QComboBox()
        self.count_in.addItems(["0", "1", "2", "3", "4", "8"])
        self.count_in.setCurrentText("4")
        settings_layout.addWidget(self.count_in)
        settings_layout.addStretch()
        top.addWidget(settings, 1)

        controls = self._panel()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 6, 8, 6)
        controls_layout.setSpacing(4)

        self.back_btn = QPushButton("◀")
        self.back_btn.clicked.connect(self._back)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._play_pause)
        self.forward_btn = QPushButton("▶")
        self.forward_btn.clicked.connect(self._forward)
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._to_start)
        for btn in [self.back_btn, self.play_btn, self.forward_btn, self.start_btn]:
            btn.setMinimumWidth(52)
            btn.setMaximumWidth(70)
            controls_layout.addWidget(btn)

        loop_box = self._panel("LoopBox")
        loop_layout = QHBoxLayout(loop_box)
        loop_layout.setContentsMargins(4, 3, 4, 3)
        self.loop_status = QLabel("Loop: off")
        self.select_start_btn = QPushButton("Loop In")
        self.select_start_btn.clicked.connect(lambda: self._set_selection_mode("start"))
        self.select_end_btn = QPushButton("Loop Out")
        self.select_end_btn.clicked.connect(lambda: self._set_selection_mode("end"))
        self.clear_loop_btn = QPushButton("Clear")
        self.clear_loop_btn.clicked.connect(self._clear_loop)
        for w in [self.loop_status, self.select_start_btn, self.select_end_btn, self.clear_loop_btn]:
            if hasattr(w, "setMaximumWidth"):
                w.setMaximumWidth(104)
            loop_layout.addWidget(w)
        controls_layout.addWidget(loop_box, 2)

        sync_box = self._panel("LoopBox")
        sync_layout = QHBoxLayout(sync_box)
        sync_layout.setContentsMargins(4, 3, 4, 3)
        self.sync_minus_btn = QPushButton("Sync -")
        self.sync_minus_btn.clicked.connect(lambda: self._adjust_sync(-1))
        self.sync_plus_btn = QPushButton("Sync +")
        self.sync_plus_btn.clicked.connect(lambda: self._adjust_sync(1))
        self.sync_reset_btn = QPushButton("Reset")
        self.sync_reset_btn.clicked.connect(self._reset_sync)
        self.sync_label = QLabel("Sync: 0")
        for w in [self.sync_minus_btn, self.sync_label, self.sync_plus_btn, self.sync_reset_btn]:
            if hasattr(w, "setMaximumWidth"):
                w.setMaximumWidth(72)
            sync_layout.addWidget(w)
        controls_layout.addWidget(sync_box, 1)

        controls_layout.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(50, 125)
        self.speed.setValue(100)
        self.speed.valueChanged.connect(self._speed_changed)
        self.speed.setMinimumWidth(105)
        self.speed.setMaximumWidth(135)
        controls_layout.addWidget(self.speed)
        self.speed_label = QLabel("100%")
        controls_layout.addWidget(self.speed_label)
        controls_layout.addStretch()
        outer.addWidget(controls, 0)

        grid_panel = self._panel()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(6, 4, 6, 4)
        grid_layout.addWidget(QLabel("Grid - current row plus next row should remain visible. Use Sync + / - to correct one-beat offset."))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.scroll.setWidget(self.grid_host)
        grid_layout.addWidget(self.scroll)
        outer.addWidget(grid_panel, 1)
        return root

    def _start_youtube_search(self) -> None:
        query = self.search.text().strip()
        if not query:
            self.statusBar().showMessage("Enter a song or artist to search YouTube")
            return
        self._stop()
        self._clear_audio_file()
        self.search_button.setEnabled(False)
        self.result_list.clear()
        self.youtube_results = []
        self.selected_youtube_result = None
        self.download_btn.setEnabled(False)
        self.download_progress.setValue(0)
        self.analysis_progress.setValue(0)
        self.download_status.setText("Audio: not downloaded")
        self.analysis_status.setText("Analysis: waiting")
        self.result_list.addItem(QListWidgetItem(f"Searching YouTube for: {query}\nPlease wait..."))
        self.statusBar().showMessage(f"Searching YouTube for: {query}")

        def worker() -> None:
            try:
                self.search_queue.put(("results", search_youtube(query, limit=8)))
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
        results = payload if isinstance(payload, list) else []
        self.youtube_results = results
        if not results:
            self.result_list.addItem(QListWidgetItem("No YouTube results found\nTry a different search phrase."))
            self.statusBar().showMessage("No YouTube results found")
            return
        for result in results:
            item = QListWidgetItem(f"YOUTUBE · {result.title}\n{result.channel} · {result.duration}")
            if result.thumbnail_data:
                pix = QPixmap()
                if pix.loadFromData(result.thumbnail_data):
                    item.setIcon(QIcon(pix.scaled(96, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            self.result_list.addItem(item)
        self.statusBar().showMessage(f"Found {len(results)} YouTube results. Click one, then Download Audio.")

    def _set_thumbnail(self, result: YouTubeResult | None) -> None:
        if result and result.thumbnail_data:
            pix = QPixmap()
            if pix.loadFromData(result.thumbnail_data):
                self.thumbnail_label.setPixmap(pix.scaled(112, 63, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.thumbnail_label.setText("")
                return
        self.thumbnail_label.setPixmap(QPixmap())
        self.thumbnail_label.setText("No image")

    def _start_audio_download(self) -> None:
        result = self.selected_youtube_result
        if not result:
            self.statusBar().showMessage("Select a YouTube result before downloading audio")
            return
        self._stop()
        self._clear_audio_file()
        self.bpm_label.setText(f"BPM: {self.song.bpm} (demo)")
        self.key_label.setText("Key: analysing after download")
        self.analysis_progress.setValue(0)
        self.analysis_status.setText("Analysis: waiting for download")
        self.download_btn.setEnabled(False)
        self.search_button.setEnabled(False)
        self.download_progress.setValue(0)
        self.download_status.setText("Audio: preparing download...")
        self.statusBar().showMessage("Preparing YouTube audio download...")

        def progress(message: str, percent: float, detail: str) -> None:
            self.download_queue.put(("progress", (message, percent, detail)))

        def worker() -> None:
            try:
                self.download_queue.put(("done", download_audio(result.url, result.title, progress=progress)))
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
                self.download_progress.setValue(int(percent))
                detail_text = f" ({detail})" if detail else ""
                self.download_status.setText(f"Audio: {message}{detail_text}")
                self.statusBar().showMessage(f"{message}{detail_text}")
            elif kind == "done":
                self.download_poll_timer.stop()
                self.search_button.setEnabled(True)
                self.download_btn.setEnabled(True)
                result = payload
                if isinstance(result, DownloadResult):
                    self.downloaded_audio_path = result.file_path
                    self.download_progress.setValue(100)
                    cached = "cached" if result.was_cached else "downloaded"
                    self.download_status.setText(f"Audio: {cached} - press Play")
                    self.statusBar().showMessage(f"Audio {cached}. Starting beat-timing analysis...")
                    self._load_audio_file(result.file_path)
                    self._start_audio_analysis(result.file_path)
                return
            elif kind == "error":
                self.download_poll_timer.stop()
                self.search_button.setEnabled(True)
                self.download_btn.setEnabled(True)
                self.download_status.setText(f"Audio error: {payload}")
                self.statusBar().showMessage(f"Audio download error: {payload}")
                return

    def _start_audio_analysis(self, path: Path) -> None:
        self.analysis_progress.setValue(5)
        self.analysis_status.setText("Analysis: finding tempo, key, chords and beat positions...")
        self.statusBar().showMessage("Analysing audio tempo, key, chords and exact beat positions...")

        def progress(message: str, percent: float) -> None:
            self.analysis_queue.put(("progress", (message, percent)))

        def worker() -> None:
            try:
                self.analysis_queue.put(("done", analyse_audio(path, progress=progress)))
            except Exception as exc:
                self.analysis_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.analysis_poll_timer.start(100)

    def _poll_analysis_results(self) -> None:
        while True:
            try:
                kind, payload = self.analysis_queue.get_nowait()
            except queue.Empty:
                return
            if kind == "progress":
                message, percent = payload
                self.analysis_progress.setValue(int(percent))
                self.analysis_status.setText(f"Analysis: {message}")
            elif kind == "done":
                self.analysis_poll_timer.stop()
                result = payload
                if isinstance(result, AnalysisResult):
                    if result.bpm:
                        self.detected_bpm = int(round(result.bpm))
                        self.bpm_label.setText(f"BPM: {self.detected_bpm} detected")
                    if result.key:
                        self.detected_key = result.key
                        self.detected_key_confidence = result.key_confidence
                        self.key_label.setText(f"Key: {result.key} detected ({int(round(result.key_confidence * 100))}%)")
                    self._build_analysis_grid(result)
                    self.analysis_progress.setValue(100)
                    chord_count = len([c for c in (result.chords_by_bar or []) if c])
                    beat_sync = f"stable timing / sync {self.sync_offset_beats:+d}"
                    summary_bits = []
                    if self.detected_bpm:
                        summary_bits.append(f"{self.detected_bpm} BPM")
                    if self.detected_key:
                        summary_bits.append(self.detected_key)
                    if result.estimated_bars:
                        summary_bits.append(f"~{result.estimated_bars} bars")
                    summary_bits.append(f"{chord_count} chord changes")
                    summary_bits.append(beat_sync)
                    summary = " · ".join(summary_bits)
                    self.analysis_status.setText(f"Analysis: {summary}")
                    self.statusBar().showMessage(f"Analysis complete: {summary}")
                    if self.timer.isActive():
                        self.timer.start(self._interval_ms())
                return
            elif kind == "error":
                self.analysis_poll_timer.stop()
                self.analysis_progress.setValue(0)
                self.analysis_status.setText(f"Analysis error: {payload}")
                self.statusBar().showMessage(f"Analysis error: {payload}")
                return

    def _build_analysis_grid(self, result: AnalysisResult) -> None:
        bars = max(4, min(240, result.estimated_bars or 16))
        duration_bars = self._estimated_bars_from_display_duration(result.bpm)
        if duration_bars:
            bars = max(bars, duration_bars)
        tonic = self._tonic_chord(result.key)
        if result.chords_by_bar:
            chords_by_bar = list(result.chords_by_bar[:bars])
            if len(chords_by_bar) < bars:
                chords_by_bar.extend([""] * (bars - len(chords_by_bar)))

            last_chord = tonic
            for i, chord in enumerate(chords_by_bar):
                if chord:
                    last_chord = chord
                else:
                    chords_by_bar[i] = last_chord

            if not any(chords_by_bar):
                chords_by_bar[0] = tonic
        else:
            chords_by_bar = [tonic for _ in range(bars)]

        self.beat_times_ms = list(result.beat_times_ms or [])
        self.sync_offset_beats = 0
        self._update_sync_label()
        target_beats = len(chords_by_bar) * 4
        if self.beat_times_ms:
            self.beat_times_ms = self.beat_times_ms[:target_beats]
            if len(self.beat_times_ms) < target_beats:
                self.beat_times_ms = []

        title = self.title_label.text() or "Analysed YouTube Song"
        artist = self.artist_label.text() or "YouTube"
        key = result.key or "Unknown"
        bpm = int(round(result.bpm or self.song.bpm))
        self.song = DemoSong(title=title, artist=artist, bpm=bpm, key=key, duration=self.duration_label.text().replace("Duration: ", ""), chords_by_bar=chords_by_bar)
        self.position = 0
        self.loop_start = None
        self.loop_end = None
        self._build_grid()
        self._update_loop_status()
        self._update_all()

    def _estimated_bars_from_display_duration(self, bpm: float | None) -> int:
        """Fallback song length estimate when beat detection stops too early."""
        try:
            duration_text = self.duration_label.text().replace("Duration: ", "").strip()
            parts = duration_text.split(":")
            if len(parts) == 2:
                seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return 0
            if seconds <= 0 or not bpm:
                return 0
            beats = int((seconds * float(bpm)) / 60)
            return max(0, int(beats / 4) + 2)
        except Exception:
            return 0

    def _tonic_chord(self, key: str | None) -> str:
        if not key:
            return "G"
        root = key.split()[0]
        root = root.split("/")[0]
        if "Minor" in key and not root.endswith("m"):
            return f"{root}m"
        return root

    def _load_audio_file(self, path: Path) -> None:
        self.audio_ready = False
        if not path or not path.exists():
            self.download_status.setText("Audio error: downloaded file not found")
            return
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.media_player.setPlaybackRate(self.speed.value() / 100)
        self.audio_ready = True

    def _clear_audio_file(self) -> None:
        self.audio_ready = False
        self.downloaded_audio_path = None
        self.detected_bpm = None
        self.detected_key = None
        self.detected_key_confidence = 0.0
        self.beat_times_ms = []
        self.sync_offset_beats = 0
        if hasattr(self, "sync_label"):
            self._update_sync_label()
        self.media_player.stop()
        self.media_player.setSource(QUrl())

    def _load_song(self, song: DemoSong) -> None:
        self._stop()
        self.song = song
        self.position = 0
        self.loop_start = None
        self.loop_end = None
        self.selection_mode = None
        self.selected_youtube_result = None
        self._clear_audio_file()
        self.download_btn.setEnabled(False)
        self.download_progress.setValue(0)
        self.download_status.setText("Audio: not downloaded")
        self.analysis_progress.setValue(0)
        self.analysis_status.setText("Analysis: waiting")
        self._set_thumbnail(None)
        self.title_label.setText(song.title)
        self.artist_label.setText(song.artist)
        self.source_label.setText("Source: Demo")
        self.bpm_label.setText(f"BPM: {song.bpm}")
        self.key_label.setText(f"Key: {song.key}")
        self.duration_label.setText(f"Duration: {song.duration}")
        self._build_grid()
        self._update_loop_status()
        self._update_all()

    def _select_result(self, row: int) -> None:
        if row < 0:
            return
        if self.youtube_results:
            if row >= len(self.youtube_results):
                return
            result = self.youtube_results[row]
            self._stop()
            self.selected_youtube_result = result
            self._clear_audio_file()
            self.download_btn.setEnabled(True)
            self.download_progress.setValue(0)
            self.analysis_progress.setValue(0)
            self.download_status.setText("Audio: ready to download")
            self.analysis_status.setText("Analysis: waiting")
            self._set_thumbnail(result)
            self.title_label.setText(result.title)
            self.artist_label.setText(result.channel)
            self.source_label.setText("Source: YouTube search result")
            self.duration_label.setText(f"Duration: {result.duration}")
            self.bpm_label.setText(f"BPM: {self.song.bpm} (demo until analysed)")
            self.key_label.setText("Key: waiting for analysis")
            self.statusBar().showMessage("YouTube result selected. Click Download Audio.")
            return
        if 0 <= row < len(DEMO_SONGS):
            self._load_song(DEMO_SONGS[row])
            self.statusBar().showMessage(f"Loaded demo: {DEMO_SONGS[row].title}")

    def _build_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cells = []
        beats = self.song.beat_chords
        bars_per_row = 3
        beats_per_row = bars_per_row * 4
        for bar_start in range(0, len(beats), beats_per_row):
            visual_row = (bar_start // beats_per_row) * 2
            for bar_offset in range(bars_per_row):
                bar_num = (bar_start // 4) + bar_offset + 1
                if (bar_num - 1) * 4 >= len(beats):
                    continue
                hdr = QLabel(f"Bar {bar_num}")
                hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hdr.setObjectName("BarHeader")
                self.grid.addWidget(hdr, visual_row, bar_offset * 4, 1, 4)
            for i in range(beats_per_row):
                idx = bar_start + i
                if idx >= len(beats):
                    break
                cell = BeatCell(idx, self._display_chord(beats[idx]) if beats[idx] else "")
                cell.clicked.connect(self._cell_clicked)
                self.cells.append(cell)
                self.grid.addWidget(cell, visual_row + 1, i)
        for col in range(beats_per_row):
            self.grid.setColumnStretch(col, 1)

    def _display_chord(self, chord: str) -> str:
        if not chord:
            return ""
        return transpose_chord(chord, self.capo.value()) if self.capo.value() else chord

    def _current_raw_chord(self) -> str:
        beats = self.song.beat_chords
        for i in range(min(self.position, len(beats) - 1), -1, -1):
            if beats[i]:
                return beats[i]
        return "G"

    def _next_raw_chord(self) -> str:
        beats = self.song.beat_chords
        current = self._current_raw_chord()
        for i in range(self.position + 1, len(beats)):
            if beats[i] and beats[i] != current:
                return beats[i]
        return ""

    def _update_all(self) -> None:
        current = self._current_raw_chord()
        nxt = self._next_raw_chord()
        self.current_panel.set_chord(self._display_chord(current))
        self.next_panel.set_chord(self._display_chord(nxt) if nxt else "—")
        for idx, cell in enumerate(self.cells):
            raw = self.song.beat_chords[idx]
            cell.set_chord(self._display_chord(raw) if raw else "")
            cell.set_active(idx == self.position)
            cell.set_loop(self.loop_start is not None and self.loop_end is not None and self.loop_start <= idx <= self.loop_end)
        self._scroll_to_position()

    def _scroll_to_position(self) -> None:
        """Place the active row near the top of the grid viewport.

        This makes the row being played fully visible and leaves room for the
        next row underneath it.
        """
        if not self.cells or self.position >= len(self.cells):
            return

        beats_per_row = 12
        current_row_start = (self.position // beats_per_row) * beats_per_row
        current_cell = self.cells[current_row_start]

        # Use scrollbar positioning rather than ensureWidgetVisible alone,
        # because ensureWidgetVisible can leave the active row tucked under the
        # fixed top area on some screen sizes.
        target_y = max(0, current_cell.y() - 2)
        self.scroll.verticalScrollBar().setValue(target_y)

    def _current_bpm(self) -> int:
        return self.detected_bpm or self.song.bpm

    def _play_pause(self) -> None:
        if self.is_playing:
            self._stop()
            return
        if self.loop_start is not None and self.loop_end is not None:
            self.position = self.loop_start
        self.count_in_remaining = int(self.count_in.currentText())
        self.is_playing = True
        self.play_btn.setText("⏸ Pause")
        if self.count_in_remaining:
            self._show_countdown(self.count_in_remaining)
            self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
            self.timer.start(self._interval_ms())
        else:
            self._hide_countdown()
            self._begin_playback_after_count_in()
        self._update_all()

    def _begin_playback_after_count_in(self) -> None:
        if self.audio_ready and self.downloaded_audio_path:
            self.media_player.setPlaybackRate(self.speed.value() / 100)
            self.media_player.setPosition(self._audio_position_for_current_beat())
            self.media_player.play()
            self.timer.start(40)
            self.statusBar().showMessage(f"Playing with stable BPM audio-clock timing, sync {self.sync_offset_beats:+d}")
        else:
            self.timer.start(self._interval_ms())
            self.statusBar().showMessage("Playing demo timing grid - no downloaded audio selected")

    def _audio_position_for_current_beat(self) -> int:
        ms_per_beat = int(60000 / self._current_bpm())
        audio_index = self.position - self.sync_offset_beats
        return max(0, audio_index * ms_per_beat)

    def _position_from_audio_ms(self, audio_ms: int) -> int:
        ms_per_beat = int(60000 / self._current_bpm())
        base_pos = int(audio_ms / max(1, ms_per_beat))
        display_pos = base_pos + self.sync_offset_beats
        return max(0, min(display_pos, len(self.song.beat_chords) - 1))

    def _adjust_sync(self, delta: int) -> None:
        self.sync_offset_beats = max(-8, min(8, self.sync_offset_beats + delta))
        self._update_sync_label()
        if self.audio_ready:
            self._sync_position_to_audio()
        self.statusBar().showMessage(
            f"Sync offset {self.sync_offset_beats:+d}. Use + if cursor is behind, - if cursor is ahead."
        )

    def _reset_sync(self) -> None:
        self.sync_offset_beats = 0
        self._update_sync_label()
        if self.audio_ready:
            self._sync_position_to_audio()
        self.statusBar().showMessage("Sync offset reset to 0")

    def _update_sync_label(self) -> None:
        if hasattr(self, "sync_label"):
            self.sync_label.setText(f"Sync: {self.sync_offset_beats:+d}")

    def _stop(self) -> None:
        self.is_playing = False
        self.timer.stop()
        self.media_player.pause()
        self.play_btn.setText("▶ Play")
        self._hide_countdown()
        self.statusBar().showMessage("Paused")

    def _tick(self) -> None:
        if self.count_in_remaining > 0:
            self.count_in_remaining -= 1
            self._show_countdown(self.count_in_remaining)
            self.statusBar().showMessage(f"Count-in: {self.count_in_remaining}")
            return
        if self.count_in_remaining == 0:
            self.count_in_remaining = -1
            self._hide_countdown()
            self._begin_playback_after_count_in()
            return
        if self.audio_ready and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._sync_position_to_audio()
            return
        self._advance_one()

    def _sync_position_to_audio(self) -> None:
        new_pos = self._position_from_audio_ms(self.media_player.position())

        if self.loop_start is not None and self.loop_end is not None:
            if new_pos > self.loop_end:
                self.position = self.loop_start
                self.media_player.setPosition(self._audio_position_for_current_beat())
                self._update_all()
                return

        if new_pos != self.position:
            self.position = new_pos
            self._update_all()

    def _show_countdown(self, value: int) -> None:
        self.countdown_label.setText("PLAY" if value == 0 else f"COUNT-IN  {value}")
        self.countdown_label.setVisible(True)

    def _hide_countdown(self) -> None:
        self.countdown_label.setVisible(False)
        self.countdown_label.setText("")

    def _advance_one(self) -> None:
        end = len(self.song.beat_chords) - 1
        if self.loop_start is not None and self.loop_end is not None:
            if self.position >= self.loop_end:
                self.position = self.loop_start
                if self.audio_ready:
                    self.media_player.setPosition(self._audio_position_for_current_beat())
            else:
                self.position += 1
        else:
            if self.position >= end:
                self._stop()
                return
            self.position += 1
        self._update_all()

    def _back(self) -> None:
        if self.position > 0:
            self.position -= 1
            if self.audio_ready:
                self.media_player.setPosition(self._audio_position_for_current_beat())
            self._update_all()

    def _forward(self) -> None:
        if self.position < len(self.song.beat_chords) - 1:
            self.position += 1
            if self.audio_ready:
                self.media_player.setPosition(self._audio_position_for_current_beat())
            self._update_all()

    def _to_start(self) -> None:
        self.position = self.loop_start if self.loop_start is not None else 0
        if self.audio_ready:
            self.media_player.setPosition(self._audio_position_for_current_beat())
        self._update_all()

    def _speed_changed(self, value: int) -> None:
        self.speed_label.setText(f"{value}%")
        self.media_player.setPlaybackRate(value / 100)
        if self.timer.isActive() and not (self.beat_times_ms and self.audio_ready and self.count_in_remaining < 0):
            self.timer.start(self._interval_ms())

    def _interval_ms(self) -> int:
        return max(120, int((60000 / self._current_bpm()) / (self.speed.value() / 100)))

    def _set_selection_mode(self, mode: str) -> None:
        self.selection_mode = mode
        self.statusBar().showMessage(f"Click a beat square to set loop {mode}")

    def _cell_clicked(self, index: int) -> None:
        if self.selection_mode == "start":
            self.loop_start = index
            if self.loop_end is not None and self.loop_end < self.loop_start:
                self.loop_end = None
            self.selection_mode = None
        elif self.selection_mode == "end":
            if self.loop_start is None:
                self.loop_start = index
                self.loop_end = index
            else:
                if index < self.loop_start:
                    self.loop_end = self.loop_start
                    self.loop_start = index
                else:
                    self.loop_end = index
            self.selection_mode = None
        else:
            self.position = index
            if self.audio_ready:
                self.media_player.setPosition(self._audio_position_for_current_beat())
        self._update_loop_status()
        self._update_all()

    def _clear_loop(self) -> None:
        self.loop_start = None
        self.loop_end = None
        self.selection_mode = None
        self._update_loop_status()
        self._update_all()

    def _update_loop_status(self) -> None:
        self.loop_status.setText("Loop: off" if self.loop_start is None or self.loop_end is None else f"Loop: bar {self.loop_start // 4 + 1} to {self.loop_end // 4 + 1}")

    def _mode_changed(self) -> None:
        self.statusBar().showMessage(f"Mode set to {self.mode.currentText()} - simplification engine comes later")
        self._update_all()

    def _media_error(self, error, error_string: str = "") -> None:
        if error_string:
            self.download_status.setText(f"Audio playback error: {error_string}")
            self.statusBar().showMessage(f"Audio playback error: {error_string}")

    def _media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.is_playing:
            self._stop()

    def _panel(self, name: str = "Panel") -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        return frame

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #111111; color: #f3e6cc; font-family: Segoe UI, Arial, sans-serif; font-size: 13px; }
            QFrame#Panel, QFrame#LoopBox { background: #1a1a1a; border: 1px solid #333333; border-radius: 8px; }
            QLabel#HintLabel { color: #bcae91; font-size: 10px; line-height: 10px; }
            QLabel#ThumbnailBox { background: #101010; color: #8c806d; border: 1px solid #444444; border-radius: 6px; }
            QLabel#BarHeader { background: #2a2418; color: #f3d99a; border: 1px solid #4b3920; border-radius: 4px; padding: 3px; font-weight: bold; }
            QLabel#CountdownLabel { background: #352915; color: #ffd06a; border: 2px solid #f3c15f; border-radius: 8px; padding: 8px; font-size: 28px; font-weight: bold; }
            QLineEdit, QComboBox, QSpinBox, QListWidget, QProgressBar { background: #252525; color: #f3e6cc; border: 1px solid #444444; border-radius: 5px; padding: 5px; }
            QProgressBar::chunk { background: #6abf69; border-radius: 4px; }
            QListWidget::item { padding: 6px; min-height: 58px; }
            QListWidget::item:selected { background: #4b3920; color: #ffffff; }
            QPushButton { background: #2f2f2f; color: #f3e6cc; border: 1px solid #444444; border-radius: 6px; padding: 6px 7px; min-width: 48px; }
            QPushButton:hover { background: #3b3b3b; }
            QPushButton:disabled { color: #777777; }
            QScrollArea { border: none; }
        """)
