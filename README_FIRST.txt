BANJOFY 006.3.0 MODULE 2 - SEARCH + DOWNLOAD
===========================================

Status
------
BUILD COMPLETE

Clean rebuild
-------------
This continues the clean rebuild from Module 1.

Included
--------
- Application shell.
- YouTube search.
- Result selection.
- Download Selected Audio button.
- Portable local audio storage folder: Banjofy Library/Audio.
- Download attempts: standard, Edge cookies, Chrome cookies, Firefox cookies.

Not included yet
----------------
- Analysis.
- Library save/load.
- Practice screen.
- Chord diagrams.
- Playback/timing.

Important
---------
Module 2 deliberately avoids FFmpeg post-processing.
It downloads the best available audio file as provided by YouTube.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 2 download
6. Commit, Push origin, wait for Actions, download artifact.

Acceptance test
---------------
PASS if:
- App opens.
- Search works.
- Selecting a result fills the right panel.
- Download button enables only after selecting a result.
- Download Selected Audio downloads or loads cached audio.
- A file appears in Banjofy Library/Audio.
- No analysis, save, Library load, or Practice opens.
