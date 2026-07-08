BANJOFY 006.3.0 MODULE 7 BUILD 001 - BEAT GRID FRAMEWORK
=======================================================

Status
------
BUILD COMPLETE

Starting point
--------------
Confirmed Module 6 Build 001.

Added
-----
- Beat grid framework in Practice Studio.
- Grid uses saved estimated_bars from Library song record.
- Grid supports up to 300 bars.
- Four beat cells per bar.
- Cursor starts at Beat 1 when song loads.
- Cursor moves with playback position.
- Stop returns cursor to Beat 1.
- Grid auto-scrolls to keep current beat visible.

Not added yet
-------------
- Real chord names.
- Chord recognition.
- Key detection.
- Beat-accurate timing engine.
- Banjo chord diagrams.

Important
---------
Module 7 cursor movement is proportional across the whole song duration.
It is not yet beat-detected timing. Proper timing refinement comes later.

Acceptance test
---------------
PASS if:
- Search/download/analyse/save still work.
- Send to Practice still loads selected Library song.
- Practice player still works.
- Beat grid appears.
- Grid starts at Beat 1.
- Cursor moves during playback.
- Pause holds position.
- Stop returns cursor to Beat 1.
- Grid scrolls as playback progresses.
