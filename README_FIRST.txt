BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 007
COMPLETE CLEAN REBUILD

Build 007 is rebuilt from the complete confirmed Build 002 package.

ROOT-CAUSE CORRECTION
Build 006 failed before the downloader was tested because GitHub Actions did
not add the repository src folder to Python's import path before running the
internal audits.

Build 007 corrects that build-system defect by:
- setting PYTHONPATH for the entire GitHub Actions job;
- adding an early application import gate before Deno/provider preparation;
- keeping the complete Build 006 downloader, timing and diagnostic architecture
  otherwise unchanged.

INSTALLATION
1. Extract this ZIP.
2. Copy everything inside M17_B007 into the root Banjofy GitHub folder.
3. Allow Windows to merge folders and replace files.
4. Commit and push.
5. Download the complete Build 007 artifact after GitHub Actions passes.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-007-Windows
