BANJOFY 006.3.0 MODULE 8B BUILD 001 - DATA DISPLAY AND SAFE SEEKING
========================================================================

Status
------
BUILD COMPLETE

Starting point
--------------
Confirmed-good Module 7 Build 001A.

Added
-----
- Honest key field: "Not analysed yet".
- Key shown in analysis status, Library list and Practice info.
- Provisional chord data stored in Analysis and Library records.
- Provisional chord names shown at bar starts.
- Safe slider seeking using press/preview/release.
- Existing Library files remain backward compatible.

Not claimed
-----------
- No real audio key detection yet.
- No real audio chord detection yet.
- BPM remains the existing placeholder estimate.

Acceptance test
---------------
PASS if:
- Search/download/analyse/save still work.
- Analysis says Key: Not analysed yet.
- Library list shows Key: Not analysed yet.
- Practice info shows Key: Not analysed yet.
- Play/Pause/Stop behave exactly as Module 7.
- Stop returns cursor to Beat 1.
- Play works after Stop.
- Dragging and releasing slider changes audio position.
- Grid shows provisional chord names and cursor still moves.
