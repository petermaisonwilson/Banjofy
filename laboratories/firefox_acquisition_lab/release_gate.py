from pathlib import Path
import ast
import sys

root = Path(__file__).resolve().parent
main_path = root / "main.py"
spec_path = root / "firefox_acquisition_lab.spec"
main = main_path.read_text(encoding="utf-8")
spec = spec_path.read_text(encoding="utf-8")
ast.parse(main)

required = [
    'APP_TITLE = "Banjofy Firefox Acquisition Laboratory 005"',
    'def search_youtube(query: str)',
    'def enum_firefox_windows()',
    'def position_firefox_window(hwnd: int, app_rect:',
    'subprocess.Popen([str(firefox), "-new-window", address])',
    'text="Prepare Song"',
    'self.watcher.start()',
    'self._capture_firefox_window',
    'self.emit("download_started"',
    'hide_window(self.firefox_song_hwnd)',
    'close_window(self.firefox_song_hwnd)',
    'Keep audio only — Recommended',
    'temporary = target.with_name(f"{target.stem}.working{target.suffix}")',
]
for text in required:
    assert text in main, f"Missing required implementation: {text}"

assert main.index("self.watcher.start()") < main.index('subprocess.Popen([str(firefox), "-new-window", address])')
assert 'name="BanjofyFirefoxAcquisitionLab005"' in spec
assert 'collect_all("yt_dlp")' in spec

sys.path.insert(0, str(root))
import main as app

mock = {
    "entries": [
        {"id": "abc123", "title": "Green Day - Holiday", "channel": "Green Day", "duration": 236},
        {"id": "", "title": "Invalid"},
    ]
}
results = app.build_search_results(mock)
assert len(results) == 1
assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"
assert app.format_duration(236) == "3:56"
print("Firefox Acquisition Laboratory 005 release gate: passed")
