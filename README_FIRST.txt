BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 006
COMPLETE CLEAN REBUILD

Build 006 is rebuilt from the complete confirmed Build 002 package.

ROOT-CAUSE SOLUTION
The guessed selector/cookie downloader is removed. Build 006 uses the modern
YouTube extraction stack now required by yt-dlp:

- pinned yt-dlp with its default EJS scripts;
- pinned Deno JavaScript runtime;
- pinned bgutil PO-token provider;
- mweb player client with automatic PO-token fetching;
- format discovery before download;
- one normal best-audio selection after verified formats are exposed;
- bundled FFmpeg audio conversion.

DIAGNOSTICS
Every download creates a permanent diagnostic log in the Library diagnostics
folder. The Library screen has a View Full Download Diagnostic button opening
a large window with permanent vertical and horizontal scroll bars, Copy Full
Diagnostic and Save Diagnostic As.

INSTALLATION
1. Extract this ZIP.
2. Copy everything inside M17_B006 into the root Banjofy GitHub folder.
3. Allow Windows to merge folders and replace files.
4. Commit and push.
5. Download the complete GitHub Actions artifact folder.
6. Keep the runtime folder beside Banjofy.exe.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-006-Windows
