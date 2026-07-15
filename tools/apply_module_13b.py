from pathlib import Path

path = Path("src/banjofy/ui/main_window.py")
text = path.read_text(encoding="utf-8")

pairs = {
    'APP_VERSION = "Banjofy 006.3.0 Module 13A Build 001 - Count-In Practice"':
        'APP_VERSION = "Banjofy 006.3.0 Module 13B Build 001 - Count-In Startup Fix"',
    'self.statusBar().showMessage("Ready - Module 13A count-in practice loaded")':
        'self.statusBar().showMessage("Ready - Module 13B count-in startup fix loaded")',
    'note = QLabel("Module 13A: Adjustable count-in before every Play; repeat sections play once.")':
        'note = QLabel("Module 13B: Adjustable count-in with corrected startup initialisation.")',
    'title = QLabel("Practice Studio - Module 13A")':
        'title = QLabel("Practice Studio - Module 13B")',
    'hint = QLabel("Module 13A: Choose 2-5 count-in beats. Repeat sections play once per Play press.")':
        'hint = QLabel("Module 13B: Choose 2-5 count-in beats. Repeat sections play once per Play press.")',
}

for old, new in pairs.items():
    if old not in text:
        raise RuntimeError(f"Expected Module 13A text not found: {old}")
    text = text.replace(old, new, 1)

old_cancel = '''    def _cancel_count_in(self, label: str = "Ready") -> None:
        self.count_in_token += 1
        self.count_in_active = False
        self.count_in_remaining = 0
        if hasattr(self, "count_in_label"):
            self.count_in_label.setText(label)
'''
new_cancel = '''    def _cancel_count_in(self, label: str = "Ready") -> None:
        self.count_in_token = int(getattr(self, "count_in_token", 0)) + 1
        self.count_in_active = False
        self.count_in_remaining = 0
        if hasattr(self, "count_in_label"):
            self.count_in_label.setText(label)
'''
if old_cancel not in text:
    raise RuntimeError("Could not find Module 13A _cancel_count_in method.")
text = text.replace(old_cancel, new_cancel, 1)

init_anchor = "        self.user_is_seeking = False\n"
init_block = (
    "        self.user_is_seeking = False\n"
    "        self.count_in_beats = 4\n"
    "        self.count_in_remaining = 0\n"
    "        self.count_in_token = 0\n"
    "        self.count_in_active = False\n"
)

if init_block not in text:
    if init_anchor not in text:
        raise RuntimeError("Could not find main initialization anchor.")
    text = text.replace(init_anchor, init_block, 1)

duplicate = (
    "        self.count_in_beats = 4\n"
    "        self.count_in_remaining = 0\n"
    "        self.count_in_token = 0\n"
    "        self.count_in_active = False\n"
)
first = text.find(duplicate)
second = text.find(duplicate, first + len(duplicate)) if first >= 0 else -1
if second >= 0:
    text = text[:second] + text[second + len(duplicate):]

for item in [
    "Module 13B Build 001",
    "Practice Studio - Module 13B",
    'getattr(self, "count_in_token", 0)',
    "self.count_in_token = 0",
]:
    if item not in text:
        raise RuntimeError("Module 13B verification failed: " + item)

path.write_text(text, encoding="utf-8")
print("Module 13B startup initialisation fix applied.")
