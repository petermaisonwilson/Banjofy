BANJOFY MODULE 13 BUILD 003 - CLEAN WORKFLOW FIX

COPY THESE ITEMS INTO THE LOCAL BANJOFY REPOSITORY
---------------------------------------------------
1. replacements/module13/main_window.py
2. .github/workflows/windows-build.yml
3. MANIFEST_006_3_0_MODULE_13_BUILD_003_CLEAN.txt

No Module 13 patch script is included or used.

GITHUB DESKTOP SUMMARY
----------------------
Banjofy 006.3.0 Module 13 Build 003 clean workflow correction

GITHUB DESKTOP DESCRIPTION
--------------------------
Corrects the clean Build 002 GitHub workflow false failure by removing the
self-matching patch-script check. Verifies the replacement file exists, installs
the complete clean Module 13 window, compile-checks it and builds the EXE.
