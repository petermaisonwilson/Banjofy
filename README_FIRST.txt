BANJOFY 006.2.1 - LIBRARY LOAD SEARCH REUSE GRID CLEANUP
=========================================================

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
- Confirmed Library click handlers are present.
- Confirmed grid remains chord-name-only.

Purpose
-------
006.2.0 fixed startup, grid length and cursor reset, but:
- clicking saved Library songs did not load them into Practice,
- selecting another song from the same search was awkward,
- grid content needed to remain chord names only.

Changes
-------
Library:
- Clicking or double-clicking a saved Library item now calls a dedicated loader.
- Library-loaded songs switch to Practice Studio.
- Stored audio path is reused if the file still exists.
- Saved library records keep audio_path and chords_by_bar.
- Backward compatible with older saved items.

Search reuse:
- After analysing/downloading one search result, the results list is left in place.
- Search and download buttons are re-enabled.
- Selecting another result from the same search should no longer require a full re-search.

Grid cleanup:
- Grid remains chord-name-only squares.
- Chord diagrams are reserved for NOW and NEXT boxes only.
- This build does not add or change chord diagrams themselves.

Not changed
-----------
- Chord/key accuracy is not changed.
- Timing engine is not changed.
- Difficulty modes are not implemented yet.
- Portable library folder redesign is not included yet.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents of the unzipped folder.
3. Paste into your local Banjofy repository folder.
4. Allow Windows to replace files.
5. Open GitHub Desktop.
6. Review changed files.
7. Commit summary:
   Banjofy 006.2.1 library search grid cleanup
8. Commit.
9. Push origin.
10. Wait for GitHub Actions.
11. Download and test the artifact.

Test checklist
--------------
1. App opens.
2. Search for a song.
3. Select, download and analyse one result.
4. Confirm the search results are still available.
5. Select another result from the same search without re-searching.
6. Confirm saved song appears in Library.
7. Click saved Library song.
8. Confirm it loads into Practice Studio.
9. Confirm grid contains chord names only.
