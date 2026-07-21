BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 002
COMPLETE CLEAN REBUILD

PURPOSE
This is a complete clean rebuild from the confirmed Module 17 Integration
Build 001 baseline. It verifies and improves the existing grid cursor timing
without adding chord letters or altering the confirmed Laboratory 016 chord
analysis engine.

TIMING CHANGE
- The cursor still uses the detected musical beat timestamps.
- A precise 30 ms timer now checks the media player's actual position while
  audio is playing.
- Pause, stop and seeking immediately refresh the cursor from the player clock.
- Bar-label seeking now respects the selected 3/4 or 4/4 meter instead of
  assuming four beats per bar.

INSTALLATION
1. Extract this ZIP.
2. Copy everything inside M17_B002 into the root of the Banjofy GitHub
   repository, alongside the existing Module 17 Build 001 files.
3. Allow folders and the workflow file to merge/replace.
4. Commit and push with GitHub Desktop.
5. GitHub Actions will build the Windows executable.

EXPECTED GITHUB ACTIONS OUTPUT
Banjofy.exe
Artifact name:
Banjofy-006.4.0-Module-17-Integration-Build-002-Windows

GITHUB DESKTOP SUMMARY
Banjofy 006.4.0 Module 17 Integration Build 002

GITHUB DESKTOP DESCRIPTION
Complete clean rebuild from confirmed Module 17 Integration Build 001. Verifies
and improves the existing Practice grid cursor by polling the actual media
position every 30 ms while retaining detected beat timestamps as the musical
source of truth. Corrects bar-label seeking for both 3/4 and 4/4 meter. Preserves
all successful chord analysis, Practice, repeat, count-in, Library and report
behaviour. Does not yet add chord letters to the grid.
