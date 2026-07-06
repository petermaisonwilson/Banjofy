BANJOFY 006.3.0 MODULE 4 BUILD 001 - ANALYSIS
============================================

Status
------
BUILD COMPLETE

Starting point
--------------
This build starts from confirmed-good Module 3 Build 001.

What changed
------------
Only one capability was added:
- Analyse Downloaded Audio.

What was NOT changed
--------------------
- Proven YouTube search manager was not changed.
- Library folder selection was not changed.
- Download manager was not changed.
- No Library save/load list was added.
- No Practice screen was added.
- No chord diagrams were added.

Included
--------
- Search.
- Select result.
- Permanent Library folder.
- Download Selected Audio.
- Audio file saved into chosen Library/Audio folder.
- Analyse Downloaded Audio.
- Analysis JSON saved into chosen Library/Analysis folder.

Important limitation
--------------------
Module 4 analysis is a workflow/storage placeholder:
- BPM is placeholder/initial estimate.
- Chord recognition is not included yet.
- Key detection is not included yet.
- Timing engine is not included yet.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 4 build 001 analysis
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens.
- Library folder is remembered.
- Search still works.
- Select result works.
- Download still works.
- Analyse button enables only after download.
- Analyse creates a .analysis.json file in chosen Library/Analysis.
- No Library save/list or Practice opens.

FAIL if:
- Search breaks.
- Download breaks.
- Analyse runs before download.
- Analysis opens Practice or saves to Library list.
