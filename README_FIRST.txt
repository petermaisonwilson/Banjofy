BANJOFY 006.1E - UI AND METADATA RESTORE
========================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Purpose
-------
006.1D proved FFmpeg/download analysis was working again, but the Practice Studio layout had regressed.
006.1E restores the visible behaviour without changing the timing/chord engine.

Changes in this release
-----------------------
Library / metadata:
- Keeps BPM and Key display working.
- Improves YouTube duration handling when search results provide duration in seconds.
- Preserves Duration from the selected song into the analysed Practice song.

Practice Studio:
- Reduces the YouTube video panel to a small fixed thumbnail area.
- Hides/removes the visible Open YouTube Video button.
- Removes the unused Practice-side No Image block.
- Adds a compact Practice Song / Analysis panel showing:
  title, artist, BPM, Key, Duration.
- Keeps the Library screen as the place for search/download/analysis.

Grid:
- Restores the multi-bar visual layout:
  three bars per row, four beats per bar.
- Keeps automatic scrolling to the current row.
- Keeps loop and active-beat highlighting.

Not changed
-----------
- No Beat Engine V2 changes.
- No timing algorithm changes.
- No chord detection upgrades.
- No embedded YouTube playback.

GitHub Desktop upload instructions
----------------------------------
1. Download and unzip this ZIP.
2. Open the unzipped folder.
3. Copy ALL contents of the unzipped folder.
4. Paste into your local Banjofy repository folder:
   C:\Users\peter\Reulo Dropbox\Peter Wilson\Peter Wilson\Documents\Banjo Stuff\Banjo Software\github\Banjofy
5. Allow Windows to replace files.
6. Open GitHub Desktop.
7. Confirm the changed files look sensible.
8. Commit summary:
   Banjofy 006.1E UI and metadata restore
9. Click Commit.
10. Click Push origin.
11. Wait for GitHub Actions.
12. Download and test the Banjofy-Windows artifact.

Test checklist
--------------
1. App opens.
2. Search YouTube.
3. Select a song.
4. Duration appears if YouTube provides it.
5. Download Audio works.
6. BPM and Key display after analysis.
7. Practice Studio has small video panel.
8. No visible Open YouTube Video button.
9. No Practice-side No Image square.
10. Grid shows three bars per row.

Expected status
---------------
This should be a better visual baseline than 006.1D while preserving the FFmpeg fix.
