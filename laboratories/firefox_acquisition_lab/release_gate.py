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
    'APP_TITLE = "Banjofy Firefox Acquisition Laboratory 004"',
    'def search_youtube(query: str)',
    'yt_dlp.YoutubeDL(options)',
    'f"ytsearch{SEARCH_LIMIT}:{query}"',
    'def build_search_results(info: dict[str, object])',
    'Open selected recording in Firefox',
    'Start waiting for selected song',
    'Keep audio only — Recommended',
    'temporary = target.with_name(f"{target.stem}.working{target.suffix}")',
]
for text in required:
    assert text in main, f"Missing required implementation: {text}"
assert 'name="BanjofyFirefoxAcquisitionLab004"' in spec
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
assert results[0]["title"] == "Green Day - Holiday"
assert app.format_duration(236) == "3:56"
print("Firefox Acquisition Laboratory 004 release gate: passed")
