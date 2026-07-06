BANJOFY 006.3.0 MODULE 2B - VISIBLE LIBRARY SETUP + SEARCH
=========================================================

Status
------
BUILD COMPLETE

Diagnosis
---------
Module 2A search worked, but the Choose Library Folder controls were not visible.

Fix
---
- Search code remains unchanged from working Module 1/2A.
- Library setup is now a large, clearly visible panel at the top.
- Button text is now:
  CHOOSE / CHANGE LIBRARY FOLDER
- Restart banner appears inside the same visible panel.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 2B visible library setup
6. Commit.
7. Push origin.
8. Wait for GitHub Actions.
9. Download artifact and test.

Acceptance test
---------------
PASS if:
- App opens.
- Library panel is visible at the top.
- Choose/Change Library Folder button is visible.
- Choosing a folder shows the restart banner.
- Restart remembers the folder.
- Search still works.
