BANJOFY MODULE 9 BUILD 001 - CORRECTED UPLOAD INSTRUCTIONS

This corrected package displays:
Banjofy 006.3.0 Module 9 Build 001 - Real BPM Detection

Upload/replace these files in GitHub, preserving their folders:

1. requirements.txt
2. src/banjofy/analysis/audio_analysis.py
3. tools/apply_module_9_title.py
4. .github/workflows/windows-build.yml
5. MANIFEST_006_3_0_MODULE_9_BUILD_001.txt

You do not need to replace the 900-line main_window.py manually.
The Windows build workflow safely changes only these three exact pieces of text:
- Window/application version
- Header explanation
- Ready message in the status bar

Commit all five files to main. The Build Windows EXE workflow should run
automatically. Download Banjofy-Windows from the completed green workflow run.

The resulting EXE will identify itself as Module 9 Build 001.
