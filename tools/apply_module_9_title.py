from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

replacements = {
    'APP_VERSION = "Banjofy 006.3.0 Module 8B Build 001 - Data Display and Safe Seeking"':
        'APP_VERSION = "Banjofy 006.3.0 Module 9 Build 001 - Real BPM Detection"',
    'self.statusBar().showMessage("Ready - Module 8B data display and safe seeking loaded")':
        'self.statusBar().showMessage("Ready - Module 9 real BPM detection loaded")',
    'note = QLabel("Module 5 test build: Search + Download + Analysis + Library save/list. No Practice yet.")':
        'note = QLabel("Module 9: Real audio BPM detection with Library and Practice integration.")',
}

missing = []
for old, new in replacements.items():
    if old not in text:
        missing.append(old)
    else:
        text = text.replace(old, new)

if missing:
    raise RuntimeError(
        "Could not apply the Module 9 title update. Missing expected text: "
        + " | ".join(missing)
    )

path.write_text(text, encoding="utf-8")
print("Module 9 title, header note and status text applied.")
