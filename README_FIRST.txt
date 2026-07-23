BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 016
COMPLETE CLEAN REBUILD

Build 016 is rebuilt from the confirmed Build 002 baseline.

CONFIRMED DOWNLOAD ROOT CAUSE
Build 015 started successfully. Its full diagnostic proved Deno, EJS, FFmpeg
and the bgutil server were present, but reported:
- Plugin directories: none
- PO Token Providers: none

Build 016 stages the exact yt_dlp_plugins files from the installed pinned
bgutil-ytdlp-pot-provider distribution and packages them in the portable
yt-dlp-plugins directory beside Banjofy.exe. The downloader also points yt-dlp
explicitly at that directory and refuses to start if the plugin files are absent.

CONFIRMED REPEAT ROOT CAUSE AREA
Build 015 stored the chosen grid markers but playback did not reliably begin at
the corresponding media position. Build 016:
- maps the End marker as an exact boundary;
- locks start/end timestamps at Play;
- waits until QMediaPlayer confirms the selected start position;
- rechecks the position after count-in;
- uses the locked end timestamp for completion.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-016-Windows
