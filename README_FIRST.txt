BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 020
EXTERNAL ACQUISITION AGENT

This is a complete clean rebuild from confirmed Build 002.

ROOT-CAUSE CORRECTION
Build 019 stopped because its workflow tried to import a non-existent class
named ChordEngine. The application itself correctly imports AnalysisResult and
analyse_audio. Build 020 tests those exact real names and also compares the
main-window imports with the actual chord-engine exports before proceeding.

The EAA design is unchanged:
Banjofy sends the selected URL to the separate Acquisition folder, receives
the completed local media file, then performs analysis and Practice locally.

Keep the Acquisition folder beside Banjofy.exe.
