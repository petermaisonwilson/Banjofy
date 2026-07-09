BANJOFY 006.3.0 MODULE 8 BUILD 001 - ANALYSIS DATA TO GRID
=========================================================

Status
------
BUILD COMPLETE

Starting point
--------------
Confirmed Module 7 Build 001A.

Added
-----
- Analysis records now include key field.
- Analysis records now include chords_by_bar field.
- Library song records now store key and chords_by_bar.
- Existing saved songs remain backward compatible.
- Practice screen displays saved key.
- Beat grid displays chord names on bar starts.

Important accuracy note
-----------------------
This build proves the data plumbing from Analysis -> Library -> Practice Grid.

It does NOT yet claim accurate chord/key recognition.
Current key is Unknown.
Current chord progression is provisional test data.
The real audio-based BPM/key/chord engine comes next.

Not added yet
-------------
- Real chord detection.
- Real key detection.
- Beat-accurate timing.
- NOW/NEXT chord boxes.
- Banjo chord diagrams.

Acceptance test
---------------
PASS if:
- Search/download/analyse/save still work.
- Analysis status includes Key.
- Save to Library works.
- Library list shows Key.
- Send to Practice works.
- Practice shows Key.
- Beat grid shows chord names in the first beat of bars.
- Cursor still moves and scrolls as in Module 7.
