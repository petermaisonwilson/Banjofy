from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 12 Build 001 - Grid Click Seeking"':
        'APP_VERSION = "Banjofy 006.3.0 Module 12A Build 001 - Download Compatibility"',
    'self.statusBar().showMessage("Ready - Module 12 clickable grid seeking loaded")':
        'self.statusBar().showMessage("Ready - Module 12A grid seeking and resilient download loaded")',
    'note = QLabel("Module 12: Click any bar or beat to jump playback. Repeat selection comes next.")':
        'note = QLabel("Module 12A: Clickable grid seeking with improved YouTube download compatibility.")',
    'title = QLabel("Practice Studio - Module 12")':
        'title = QLabel("Practice Studio - Module 12A")',
    'hint = QLabel("Module 12: Click a bar number or individual beat to jump there. Chords remain provisional.")':
        'hint = QLabel("Module 12A: Click a bar or beat to jump there. Chords remain provisional.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 12 text not found: {old}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Module 12A identity applied.")
