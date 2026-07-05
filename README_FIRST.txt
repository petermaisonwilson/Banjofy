BANJOFY 006.1G - LIBRARY LOAD + GRID LENGTH + RESET REPAIR
==========================================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Audit summary
-------------
Before building 006.1G I audited the current source flow.

Findings:
1. Saved Library songs were listed but not connected to a loader.
   The list existed, but clicking a saved song did not reconstruct the Practice song.

2. Library entries stored only basic text metadata:
   title, artist, duration, BPM, key.
   They did not store audio path, chord grid, beat timings, source URL, or thumbnail URL.

3. The Practice screen could re-analyse cached audio quickly because the MP3 was cached on disk,
   but the Library had no route to reopen that cached song properly.

4. Grid length was vulnerable to falling back to 16 bars because the Practice song could be rebuilt
   without enough persisted chord/bar information.

5. Cursor reset existed in some paths, but not consistently across Library load, analyse, and audio reload.

Changes in 006.1G
-----------------
Library:
- LibrarySong now stores:
  title, artist, duration, BPM, key, source,
  audio_path, source_url, thumbnail_url, chords_by_bar, beat_times_ms.
- Library loading remains backwards-compatible with old saved entries.
- Clicking a saved Library item now loads it into Practice Studio.
- If saved audio still exists on disk, the audio is loaded and ready.
- If saved chord data exists, the grid is rebuilt from it.
- If old saved entries have no chord data, a sensible full-length grid is generated.

Grid length:
- Grid length is restored from saved chords where possible.
- When no chords are saved, grid length is estimated from duration + BPM.
- This avoids defaulting back to 16 bars where possible.

Cursor reset:
- Library-loaded songs reset to first beat/bar.
- Analysed songs reset to first beat/bar.
- Audio position is reset to start when relevant.
- Grid scroll resets to the top.

Not changed
-----------
- Timing engine is not changed.
- Chord detection is not upgraded.
- UI layout is not redesigned.
- FFmpeg fix from 006.1D is retained.
- Grid visibility from 006.1F is retained.

Known remaining issue
---------------------
Timing may still be out. That is separate and should be handled in 006.2A.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents of the unzipped folder.
3. Paste into your local Banjofy repository folder:
   C:\Users\peter\Reulo Dropbox\Peter Wilson\Peter Wilson\Documents\Banjo Stuff\Banjo Software\github\Banjofy
4. Allow Windows to replace files.
5. Open GitHub Desktop.
6. Review changed files.
7. Commit summary:
   Banjofy 006.1G library load grid length reset
8. Commit.
9. Push origin.
10. Wait for GitHub Actions.
11. Download and test the Banjofy-Windows artifact.

Test checklist
--------------
1. App opens.
2. Search a song.
3. Download/analyse.
4. Confirm grid is longer than 16 bars.
5. Confirm cursor starts at beat 1/bar 1.
6. Confirm song appears in Saved Song Library.
7. Click the saved song in Library.
8. Confirm it loads into Practice Studio.
9. Confirm the cursor starts at beat 1/bar 1 again.
10. Confirm audio is loaded from cache if the MP3 still exists.
