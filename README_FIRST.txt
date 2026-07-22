BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 008
COMPLETE CLEAN REBUILD

Build 008 is rebuilt from the complete confirmed Build 002 package.

ROOT-CAUSE CORRECTION
Build 007 proved that job-wide PYTHONPATH works because the banjofy package
import passed. The remaining imports failed because the import gate ran before
third-party dependencies such as numpy and imageio-ffmpeg were installed.

Build 008 corrects only the workflow order:
1. install complete Build 008 source;
2. install pinned Python dependencies;
3. run the early five-part application import gate;
4. continue to Deno, provider, audits and PyInstaller.

No downloader, timing or chord-analysis logic has changed.

INSTALLATION
Copy everything inside M17_B008 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-008-Windows
