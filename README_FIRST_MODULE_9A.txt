BANJOFY MODULE 9A BUILD 001 - GITHUB DESKTOP INSTRUCTIONS

This is a corrective build. Module 9 Build 001 failed because:
- Practice Studio still displayed Module 6 wording.
- Pressing Stop crashed the application.

COPY THESE FILES INTO YOUR LOCAL BANJOFY REPOSITORY
---------------------------------------------------
Preserve the folder structure and replace existing files when prompted:

1. requirements.txt
2. src/banjofy/analysis/audio_analysis.py
3. tools/apply_module_9a_fix.py
4. .github/workflows/windows-build.yml
5. MANIFEST_006_3_0_MODULE_9A_BUILD_001.txt

Also delete this obsolete file if it exists:
tools/apply_module_9_title.py

GITHUB DESKTOP SUMMARY
----------------------
Banjofy 006.3.0 Module 9A Build 001 Practice Stop fix

GITHUB DESKTOP DESCRIPTION
--------------------------
Corrects Practice Studio Module 6 wording and fixes the Stop crash using a guarded
Qt multimedia reset while retaining real BPM detection, Library storage and beat-grid timing.

After committing and pushing, open GitHub Actions and download the Banjofy-Windows
artifact from the newest successful Build Windows EXE run.
