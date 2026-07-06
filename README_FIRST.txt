BANJOFY 006.3.0 MODULE 3 - LIBRARY LOCATION + ANALYSIS
=====================================================

Status
------
BUILD COMPLETE

Clean rebuild
-------------
This continues the clean rebuild from Module 2.

Included in this module
-----------------------
- Application shell.
- YouTube search.
- Result selection.
- Download Selected Audio.
- First-run/user-selected permanent Library folder.
- Library path stored in:
  AppData/Roaming/Banjofy/settings.json
- Library subfolders created:
  Audio
  Analysis
  Artwork
  Songs
- Analysis Manager creates a first analysis record in Analysis.

Important limitation
--------------------
Module 3 analysis is a workflow/storage placeholder:
- BPM is placeholder.
- Key is placeholder.
- Chords are placeholder.
The real music intelligence comes later after the workflow is stable.

Explicitly NOT included yet
---------------------------
- Library save/load list.
- Practice screen.
- Chord diagrams.
- Playback/timing.
- Accurate chord/key engine.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 3 library location analysis
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens.
- It shows Library path status.
- Choose Library Folder works.
- Chosen Library path is remembered next launch.
- Search works.
- Select result works.
- Download works into the chosen Library/Audio folder.
- Analyse Downloaded Audio becomes enabled after download.
- Analysis creates a JSON file in chosen Library/Analysis.
- No save-to-library list yet.
- No Practice screen opens.

FAIL if:
- App crashes.
- Library path is still tied to temporary EXE/module folder after choosing a folder.
- Download happens without chosen Library folder.
- Analysis opens Practice or saves to Library list.
