BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 015
COMPLETE CLEAN REBUILD

Build 015 is rebuilt from the complete confirmed Build 002 baseline.

DIRECTLY VERIFIED CORRECTION
Build 014 proved that pkg_resources, jaraco.text, jaraco.context and
backports.tarfile all import successfully and exposed their real file paths.

The build failed only because a second, fresh Python process attempted
find_spec('jaraco.text') before setuptools' vendored jaraco loader had been
activated. That test did not represent the real runtime mechanism.

Build 015 removes only that disproven find_spec gate.

It retains:
- the successful single-process import and file-path assertions;
- the backports.tarfile installed-version check;
- explicit PyInstaller collection of backports and jaraco;
- the ten-second Banjofy.exe startup smoke test;
- all Build 014 dependencies and application logic unchanged.

INSTALLATION
Copy everything inside M17_B015 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-015-Windows
