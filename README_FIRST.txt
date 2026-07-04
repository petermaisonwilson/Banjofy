BANJOFY RECOVERY 006.1C - FULL COMPATIBILITY BASELINE
====================================================

Status
------
BUILD COMPLETE

What this is
------------
This is a COMPLETE project package, not a patch.

It starts from your current desktop repository and repairs the mismatched helper
modules that caused the recovery scaffold to open in a broken state.

What was repaired
-----------------
- src/banjofy/ui/chord_grid.py
  Matches MainWindow's ChordGridController(self.grid, self.scroll, self._cell_clicked)
- src/banjofy/ui/analysis_panel.py
  Restores the methods MainWindow calls: waiting_for_download, progress,
  apply_result, error, reset
- src/banjofy/audio/analyser.py
  Returns a complete AnalysisResult with estimated_bars and chords_by_bar
- src/banjofy/player/playback_engine.py
  Restores the PlaybackClock API used by MainWindow
- src/banjofy/ui/youtube_panel.py
  Fixes thumbnail handling when MainWindow passes a YouTubeResult object

Important
---------
This is still a recovery baseline. It is intended to give us a build that opens
and behaves coherently again. It is not yet the full feature-restoration build.

How to apply using GitHub Desktop
---------------------------------
1. Unzip this package.
2. Copy the CONTENTS of this unzipped folder into your local Banjofy folder:

   C:\Users\peter\Reulo Dropbox\Peter Wilson\Peter Wilson\Documents\Banjo Stuff\Banjo Software\github\Banjofy

3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Confirm it shows changed files.
6. Commit with this message:

   Recovery 006.1C compatibility baseline

7. Push origin.
8. GitHub Actions should run.
9. Download the EXE and test.

Test checklist
--------------
- App opens
- Library tab appears
- Practice Studio appears
- Demo grid displays in four-beat bars
- Play button advances the cursor
- YouTube search starts
- Selecting a result updates title/thumbnail
- Download no longer fails because of mismatched helper modules

Known compromises
-----------------
- Advanced chord detection/timing is not restored yet.
- Video player is still placeholder/open-button based.
- This build prioritises getting a reliable baseline back.

Next builds
-----------
006.1D - UI layout restoration only
006.1E - YouTube download/analyse restoration only
006.1F - Save/library cleanup only

No more mixed architecture + UI changes.
