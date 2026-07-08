BANJOFY 006.3.0 MODULE 5C BUILD 001 - LIBRARY UI POLISH
======================================================

Status
------
BUILD COMPLETE

Starting point
--------------
Confirmed Module 5B Build 001.

What changed
------------
UI polish only:
- Added visible Library message label above the Library list.
- Refresh/select/send/save messages now appear in that Library message label as well as the bottom status bar.
- Thumbnail fixed at 320x180 so status text cannot crush it.
- Download/analysis status labels constrained to avoid pushing into artwork.
- Long audio folder path replaced with concise "Audio folder: ready" once set.

What was NOT changed
--------------------
- Search manager was not changed.
- Download manager was not changed.
- Analysis manager was not changed.
- Library save/load format was not changed.
- Practice screen was not added.
- Chord diagrams were not added.

Acceptance test
---------------
PASS if:
- Search/download/analyse/save still work.
- Refresh Library shows message visibly above Library list.
- Selecting Library song shows message visibly above Library list.
- Send to Practice placeholder message appears visibly above Library list.
- Thumbnail no longer gets crushed by status text.
