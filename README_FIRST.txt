BANJOFY 006.2.0 - LIBRARY GRID RESET STABILISATION
===================================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Validation performed before release
-----------------------------------
- Parsed all Python files for syntax errors.
- Checked MainWindow for missing private self._method calls.
- Confirmed _scroll_grid_to_start exists as a MainWindow method.

Purpose
-------
006.1G failed at startup because _scroll_grid_to_start was called but not present
as a MainWindow method. 006.2.0 fixes that and stabilises the unfinished
library/grid/reset work.

Changes
-------
Startup:
- Fixes the missing _scroll_grid_to_start method crash.

Cursor reset:
- New selected songs reset to beat 1.
- Analysed songs reset to beat 1.
- Library-loaded songs reset to beat 1.
- Practice grid scrolls back to the start on load.

Grid length:
- Uses detected beat count, displayed duration, and estimated bars.
- Removes the repeated 16-bar fallback where better evidence exists.
- Allows up to 300 bars.

Library:
- Extends saved library records to include audio_path and chords_by_bar.
- Backward-compatible with old saved library entries.
- Clicking or double-clicking a saved Library item loads it into Practice Studio.
- If the saved audio file still exists, it is reloaded.

Not changed
-----------
- Timing engine is not repaired in this build.
- Chord accuracy is not changed.
- Portable library folder beside/near EXE is not included yet.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents of the unzipped folder.
3. Paste into your local Banjofy repository folder.
4. Allow Windows to replace files.
5. Open GitHub Desktop.
6. Review changed files.
7. Commit summary:
   Banjofy 006.2.0 library grid reset stabilisation
8. Commit.
9. Push origin.
10. Wait for GitHub Actions.
11. Download and test the artifact.

Test checklist
--------------
1. App opens.
2. Search/download/analyse a song.
3. Cursor starts at beat 1.
4. Grid extends beyond 16 bars when duration or beat count supports it.
5. Saved song appears in Library.
6. Click saved song in Library.
7. It loads into Practice Studio.
8. If audio file still exists locally, playback can use it.
