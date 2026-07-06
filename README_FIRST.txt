BANJOFY 006.3.0 MODULE 3C - SEARCH RESTORED + RESTART BANNER
===========================================================

Status
------
BUILD COMPLETE

Precise diagnosis
-----------------
Module 1 search worked.

Module 3B added yt-dlp/socket timeout options inside the YouTube search manager.
On your setup, that stopped search results returning.

Fix
---
- Restored the proven Module 1 YouTube search manager.
- Kept the UI timeout wrapper so the screen does not hang forever.
- Kept the restart banner after choosing Library folder.
- Kept Library location and Analysis functionality from Module 3A.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 3C search restored
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens.
- Library folder is remembered.
- Search returns results again.
- Select result works.
- Download works.
- Analyse works.
