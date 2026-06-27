# Banjofy Build 004.1A - YouTube Search Stage 1

This is the first small Music Engine step.

## What this build adds

- Real YouTube search using `yt-dlp`.
- Search button is now active.
- Pressing Enter in the search box also searches.
- Results show title, channel and duration.
- Clicking a YouTube result loads its title/channel/duration into the song info panel.
- Existing demo player, loop controls, count-in, To Start, 3-bar grid, capo selector and chord diagrams are retained.

## What this build does not do yet

- No thumbnails yet.
- No audio download yet.
- No sound playback yet.
- No chord/BPM/key analysis yet.

Those come in the next Music Engine steps.

## Files to upload to GitHub

Upload/replace these files:

- `src/banjofy/ui/main_window.py`
- `src/banjofy/youtube/__init__.py`
- `src/banjofy/youtube/search.py`
- `requirements.txt`

Do not change the `.github/workflows/windows-build.yml` workflow.
