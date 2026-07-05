BANJOFY 006.2.4 - VALIDATED WORKFLOW REPAIR
===========================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Why this build exists
---------------------
006.2.3 failed on startup with:

    MainWindow object has no attribute _load_library_song_by_row

006.2.4 fixes that stale button/signal connection and adds validation to catch
this class of error before release.

Validation performed before release
-----------------------------------
PASSED - Python syntax check for all source files.
PASSED - MainWindow missing private self._method check.
PASSED - Qt signal connection target check.
PASSED - _load_library_song_by_row compatibility method confirmed present.

Included behaviour
------------------
- No auto-save after analysis.
- No auto-send to Practice after analysis.
- Save to Library refuses unanalysed songs.
- Send to Practice refuses unanalysed songs.
- Send to Practice can send the current analysed song or selected saved Library song.
- NOW/NEXT diagrams show strings, fret position and finger number.
- Grid remains chord names only.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.2.4 validated workflow repair
6. Commit.
7. Push origin.
8. Wait for Actions, download artifact, test.
