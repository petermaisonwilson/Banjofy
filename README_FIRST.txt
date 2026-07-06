BANJOFY 006.3.0 MODULE 3 - SEARCH + LIBRARY + DOWNLOAD
=====================================================

Status
------
BUILD COMPLETE

Starting point
--------------
This build starts from confirmed-good Module 2B.

What changed
------------
Only one capability was added:
- Download Selected Audio.

What was NOT changed
--------------------
- Proven YouTube search manager was not changed.
- Library folder selection was not changed.
- No analysis was added.
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
- Cached download reuse.

Important
---------
Module 3 deliberately does not use FFmpeg post-processing.
It downloads the best audio file YouTube provides. Analysis comes later.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 3 download
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
- Download button enables only after result selection.
- Download saves an audio file into chosen Library/Audio.
- Re-downloading same result reports cached/downloaded rather than duplicating unnecessarily.
- No analysis, Library save/list, or Practice opens.

FAIL if:
- Search breaks.
- Download starts before Library folder is set.
- Download opens Practice or saves to Library list.
