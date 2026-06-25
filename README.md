# Banjofy 0.1.0

Banjofy is a banjo-first practice companion. This first GitHub build is the desktop app shell: dark UI, search area, Current/Next chord diagrams, capo/mode controls, and a beat-square grid.

## Build locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.banjofy.main
```

## Build EXE locally

```bash
pip install -r requirements.txt
pyinstaller Banjofy.spec --noconfirm
```

The EXE will be in `dist/Banjofy/Banjofy.exe`.

## GitHub build

Go to **Actions → Build Windows EXE → Run workflow**. Download the `Banjofy-Windows` artifact when complete.
