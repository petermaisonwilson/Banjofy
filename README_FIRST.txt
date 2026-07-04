BANJOFY 006.1D - COMPLETE RELEASE - FFMPEG DOWNLOAD FIX
=======================================================

Status
------
BUILD COMPLETE

Objective
---------
This is a complete release package based on the working Recovery 006.1C baseline.

Only intended functional change:
- Fix audio download failure caused by ffmpeg/ffprobe not being found inside the packaged EXE.

What changed
------------
1. src/banjofy/youtube/downloader.py
   - Uses imageio-ffmpeg to locate the packaged ffmpeg executable.
   - Passes that explicit ffmpeg path to yt-dlp.
   - Adds a fallback direct-audio download if MP3 conversion still fails.

2. Banjofy.spec
   - Keeps imageio_ffmpeg data collection.
   - Explicitly includes imageio_ffmpeg as a hidden import.

3. src/banjofy/ui/main_window.py
   - Version text changed to Banjofy 006.1D - FFmpeg Download Fix.

No other feature work is included.

How to apply using GitHub Desktop
---------------------------------
1. Unzip this package.
2. Open the unzipped folder.
3. Select all contents inside it:
   - .github
   - src
   - Banjofy.spec
   - requirements.txt
   - README files / manifest
4. Copy them into your local Banjofy repository folder:

   C:\Users\peter\Reulo Dropbox\Peter Wilson\Peter Wilson\Documents\Banjo Stuff\Banjo Software\github\Banjofy

5. Windows will ask whether to replace files. Choose Replace.
6. Open GitHub Desktop.
7. Confirm the changed files look sensible.
8. Commit with this exact summary:

   Banjofy 006.1D FFmpeg download fix

9. Click Push origin.
10. GitHub Actions should start automatically.
11. When Actions has a green tick, download the Banjofy-Windows artifact.
12. Unzip it and run Banjofy.exe.

What to test
------------
1. App opens.
2. Search YouTube.
3. Select a result.
4. Click Download Audio.
5. Expected result: download should continue past the previous ffmpeg error.
6. Analysis should complete using the current recovery analyser.
7. Practice Studio should open and show the grid.

Known limitations
-----------------
- This is still a recovery baseline, not the fully restored feature-rich target.
- Analysis is deliberately conservative/reliable rather than musically advanced.
- Timing drift and beat-level chord detection are not addressed in this build.

Rollback plan
-------------
If this build makes things worse:
1. In GitHub Desktop, go to History.
2. Select the previous working commit: Recovery 006.1C compatibility baseline.
3. We will revert to that point before trying anything else.
