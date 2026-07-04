BANJOFY 006.1F - GRID VISIBILITY AND SONG RESET
================================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Purpose
-------
006.1E restored FFmpeg plus some UI/metadata behaviour, but the Practice grid was hard to read,
only showed 16 bars in some cases, and the cursor did not always reset properly when loading a new song.

Changes in this release
-----------------------
Grid:
- Restores clear visible beat squares.
- Makes the moving cursor much more obvious.
- Restores a 3-bars-per-row layout.
- Keeps automatic current-row scrolling.
- Keeps loop highlighting.

Song length:
- Improves grid length calculation so analysed songs can extend beyond 16 bars.
- Uses detected beat count and/or displayed duration where available.

Song loading:
- When a new YouTube result is selected, position resets to beat 1.
- When a new analysed song is built, position resets to beat 1.
- When a demo song is loaded, the grid scrolls back to the start.

Not changed
-----------
- No timing-engine changes.
- No chord-detection changes.
- No new features.
- FFmpeg fix from 006.1D retained.
- UI/metadata restore from 006.1E retained.

Known remaining issue
---------------------
Timing may still be out. That is planned for 006.2A as a separate timing-engine repair build.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents of the unzipped folder.
3. Paste into your local Banjofy folder:
   C:\Users\peter\Reulo Dropbox\Peter Wilson\Peter Wilson\Documents\Banjo Stuff\Banjo Software\github\Banjofy
4. Allow Windows to replace files.
5. Open GitHub Desktop.
6. Check changed files.
7. Commit summary:
   Banjofy 006.1F grid visibility and song reset
8. Commit.
9. Push origin.
10. Wait for Actions.
11. Download and test the artifact.

Test checklist
--------------
1. App opens.
2. Search and select a song.
3. Download/analyse.
4. Practice page cursor starts at beat 1/bar 1.
5. Grid shows visible beat squares.
6. Active cursor is easy to see.
7. Grid length goes beyond 16 bars when song duration/beat count is available.
