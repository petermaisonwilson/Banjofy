# Banjofy

Banjo-first song practice app.

## What this first GitHub build is
This is the proper project starter, not a chat-only prototype. It builds a Windows executable using GitHub Actions.

It currently includes:
- PySide6 desktop shell
- dark Banjofy interface
- YouTube search stub/import panel
- Current and Next chord panels
- readable 5-string banjo chord diagrams
- beat-square grid, 4 bars per row
- mode selector
- capo selector
- concert/shape display selector

The audio/downloader/analysis engine is separated so we can improve it module by module.

## How to build on GitHub
1. Create a GitHub repo called `Banjofy`.
2. Upload all files from this folder.
3. Go to the repo's **Actions** tab.
4. Run **Build Windows EXE**.
5. Download the artifact named `Banjofy-Windows`.

## Local run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m banjofy
```

## Local build
```bash
build.bat
```
