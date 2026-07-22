BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 013
COMPLETE CLEAN REBUILD

Build 013 is rebuilt from the complete confirmed Build 002 baseline.

DIRECTLY VERIFIED CORRECTION
Build 012 successfully built an EXE, but Windows startup failed with:

ModuleNotFoundError: No module named 'backports'

The traceback proved the exact frozen runtime chain:
pkg_resources -> jaraco.text -> jaraco.context -> backports.tarfile

Build 013 therefore:
- installs backports.tarfile==1.2.0;
- verifies pkg_resources, jaraco.text, jaraco.context and backports.tarfile;
- explicitly collects that exact chain in PyInstaller;
- launches the newly built Banjofy.exe for ten seconds before uploading it;
- fails GitHub Actions if the EXE exits during startup.

No downloader, timing or chord-analysis algorithm has changed.

INSTALLATION
Copy everything inside M17_B013 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-013-Windows
