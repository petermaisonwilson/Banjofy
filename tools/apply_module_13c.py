from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 13B Build 001 - Count-In Startup Fix"':
        'APP_VERSION = "Banjofy 006.3.0 Module 13C Build 001 - Count-In Play Fix"',
    'self.statusBar().showMessage("Ready - Module 13B count-in startup fix loaded")':
        'self.statusBar().showMessage("Ready - Module 13C count-in Play fix loaded")',
    'note = QLabel("Module 13B: Adjustable count-in with corrected startup initialisation.")':
        'note = QLabel("Module 13C: Adjustable count-in with corrected Play handoff.")',
    'title = QLabel("Practice Studio - Module 13B")':
        'title = QLabel("Practice Studio - Module 13C")',
    'hint = QLabel("Module 13B: Choose 2-5 count-in beats. Repeat sections play once per Play press.")':
        'hint = QLabel("Module 13C: Choose 2-5 count-in beats. Repeat sections play once per Play press.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 13B text not found: {old}")
    text = text.replace(old, new, 1)

# QApplication.beep() is used by Module 13A, so QApplication must be imported.
widgets_anchor = "from PySide6.QtWidgets import (\n"
if widgets_anchor not in text:
    raise RuntimeError("Could not find QtWidgets import block.")

if "    QApplication,\n" not in text:
    text = text.replace(
        widgets_anchor,
        widgets_anchor + "    QApplication,\n",
        1,
    )

required = [
    "Module 13C Build 001",
    "Practice Studio - Module 13C",
    "    QApplication,",
    "QApplication.beep()",
]

for item in required:
    if item not in text:
        raise RuntimeError("Module 13C verification failed: " + item)

path.write_text(text, encoding="utf-8")
print("Module 13C QApplication import and Play fix applied.")
