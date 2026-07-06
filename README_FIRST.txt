BANJOFY 006.3.0 MODULE 3A - LIBRARY STARTUP FIX + ANALYSIS
=========================================================

Status
------
BUILD COMPLETE

Clean rebuild module
--------------------
This is Module 3 with the first-run Library startup crash fixed.

Diagnosis
---------
Module 3 crashed on first run because the UI called audio_folder() while no Library
folder had been chosen yet.

Fix
---
- App now starts even if no Library folder is set.
- UI shows:
  Audio folder: choose Library folder first
- User chooses permanent Library folder.
- Only then does the app resolve/create:
  Audio
  Analysis
  Artwork
  Songs

Included
--------
- Application shell.
- YouTube search.
- Result selection.
- Download Selected Audio.
- Persistent user-chosen Library folder.
- Analysis record creation.

Not included yet
----------------
- Library save/load list.
- Practice screen.
- Chord diagrams.
- Playback/timing.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 3A library startup fix
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens before any Library folder has been chosen.
- It says Library not set.
- It says Audio folder: choose Library folder first.
- Choose Library Folder works.
- Close/reopen remembers the folder.
- Download saves into chosen Library/Audio.
- Analysis creates JSON in chosen Library/Analysis.
