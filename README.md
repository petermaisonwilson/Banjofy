# Banjofy Build 001

This is the first clean GitHub-ready build of Banjofy.

## What this build does

Build 001 is deliberately limited. It proves that the project structure, Qt desktop window, chord diagram drawing, and GitHub Windows EXE build all work.

Included:

- Native PySide6 / Qt desktop app
- Dark Banjofy-style interface
- Search/results placeholder panel
- Current chord panel with readable banjo diagram
- Next chord panel with readable banjo diagram
- Mode selector: Beginner, Intermediate, Professional
- Capo selector
- Concert Chords / Banjo Shapes selector
- 4-bars-across beat grid placeholder
- GitHub Actions workflow to build a Windows EXE

Not included yet:

- YouTube search/download
- Audio playback
- Chord detection
- Beat detection

Those are later builds once this shell builds correctly.

## Run locally

```bash
pip install -r requirements.txt
python src/main.py
```

## Build locally

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller Banjofy.spec
```

The EXE will appear in `dist/`.

## Build on GitHub

After uploading these files to GitHub:

1. Open the repository.
2. Click **Actions**.
3. Click **Build Windows EXE**.
4. Click **Run workflow**.
5. Wait for the build to finish.
6. Download the artifact named **Banjofy-Windows**.
