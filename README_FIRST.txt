BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 009
COMPLETE CLEAN REBUILD

Build 009 is rebuilt from the complete confirmed Build 002 package.

ROOT-CAUSE CORRECTION
Build 008's dependency installation failed on chord-extractor==0.1.2, which has
no compatible distribution for Python 3.12. The confirmed Laboratory 016 chord
engine does not import or use chord-extractor.

Because pip resolves the requirements as one transaction, numpy,
imageio-ffmpeg and the other dependencies were never installed. The following
PyInstaller command then succeeded, causing the whole PowerShell step to appear
successful.

Build 009:
- removes only the unused incompatible chord-extractor dependency;
- checks every pip command's exit code;
- adds a dedicated dependency import/version gate before the application import
  gate;
- leaves downloader, timing and chord logic unchanged.

INSTALLATION
Copy everything inside M17_B009 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-009-Windows
