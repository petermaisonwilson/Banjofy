from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = [ROOT / "main.py", ROOT / "firefox_acquisition_lab.spec"]
for path in required:
    assert path.is_file(), f"Missing required file: {path}"

source = (ROOT / "main.py").read_text(encoding="utf-8")
ast.parse(source)

required_text = [
    'APP_TITLE = "Banjofy Firefox Acquisition Laboratory 001"',
    'SUPPORTED_MEDIA =',
    'default_downloads_folder()',
    'root / "Downloaded"',
    'shutil.move',
    'STABLE_SCANS_REQUIRED = 3',
]
for text in required_text:
    assert text in source, f"Release-gate evidence missing: {text}"

for forbidden in ["yt-dlp", "youtube_dl", "cookies-from-browser"]:
    assert forbidden not in source.lower(), f"Laboratory must not contain its own downloader: {forbidden}"

print("Firefox Acquisition Laboratory 001 release gate: passed")
