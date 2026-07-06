BANJOFY 006.3.0 MODULE 3B - SEARCH FIX + RESTART BANNER
======================================================

Status
------
BUILD COMPLETE

Fixes
-----
- Search now has yt-dlp/network timeout settings.
- UI search polling now has a timeout and re-enables the Search button if no result arrives.
- If YouTube search times out, the user sees a clear message rather than a permanent hang.
- After the user first chooses a Library folder, a bold restart banner appears.
- Banner disappears on subsequent launches once the stored Library path is loaded.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary:
   Banjofy 006.3.0 module 3B search fix restart banner
6. Commit, Push origin, wait for Actions, download artifact.

Acceptance test
---------------
PASS if:
- App opens.
- Existing Library folder is remembered.
- If Library folder is newly chosen, bold restart banner appears.
- After restart, banner disappears.
- Search either returns results or times out cleanly without hanging forever.
- Search button becomes usable again after timeout/error.
- Download and Analyse workflow still works after a successful search.
