BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 014
COMPLETE CLEAN REBUILD

Build 014 is rebuilt from the complete confirmed Build 002 baseline.

DIRECTLY VERIFIED CORRECTION
Build 013 proved that pkg_resources, jaraco.text, jaraco.context and
backports.tarfile all import successfully. The build failed only because the
workflow incorrectly required standalone distribution metadata for jaraco.text
and jaraco.context.

Build 014 removes only that unsupported requirement.

It now verifies:
- all four runtime modules import;
- the resolved module file locations;
- importlib can locate jaraco.text, jaraco.context and backports.tarfile;
- backports.tarfile has the expected installed distribution metadata;
- PyInstaller completes;
- Banjofy.exe stays running during the ten-second startup smoke test.

No dependency, downloader, timing, chord-analysis or PyInstaller collection
logic has changed.

INSTALLATION
Copy everything inside M17_B014 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-014-Windows
