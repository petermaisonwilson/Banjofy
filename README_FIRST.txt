BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 019
EXTERNAL ACQUISITION AGENT

SIMPLE EXPLANATION
Banjofy now asks a separate helper to obtain the audio.

Banjofy:
- searches for the song;
- sends the selected address to the helper;
- waits for the completed audio file;
- analyses chords and timing;
- stores the song in the Library;
- plays it locally in Practice.

The helper lives in the Acquisition folder beside Banjofy.exe. It contains its
own yt-dlp, Deno, FFmpeg and PO-token provider. It is not frozen inside
Banjofy.exe.

WHY THIS IS STRONGER
When YouTube changes, only the Acquisition folder should need updating.
Library, analysis, Practice, chord display and diagrams remain separate.

DO NOT MOVE OR RENAME THE ACQUISITION FOLDER.
Keep it beside Banjofy.exe.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-019-Windows
