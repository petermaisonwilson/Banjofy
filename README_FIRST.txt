BANJOFY 006.3.0 MODULE 2A - SEARCH + LIBRARY FOLDER
==================================================

Status
------
BUILD COMPLETE

Purpose
-------
This build starts again from the proven-working Module 1 search code.

It adds only:
- permanent Library folder selection,
- persistent settings in AppData/Roaming/Banjofy/settings.json,
- creation of Library subfolders:
  Audio
  Analysis
  Artwork
  Songs,
- restart banner after first choosing Library folder.

It deliberately does NOT add:
- download,
- analysis,
- Library save/load,
- Practice,
- chord diagrams,
- playback/timing.

Diagnosis from previous attempt
-------------------------------
Module 1 search works.
Module 3 search failed.
Therefore the fault was in added Module 3 surrounding code, not the search engine itself.

This module proves that Library folder setup does not break search.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 2A search library folder
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens.
- Search works exactly like Module 1.
- Selecting result works exactly like Module 1.
- Choose Library Folder works.
- Restart banner appears after choosing Library folder.
- After restart, Library folder is remembered and banner disappears.
- Choosing Library folder does not break search.

FAIL if:
- Search stops returning results.
- Selecting a result triggers hidden actions.
- App crashes.
