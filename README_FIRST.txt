BANJOFY 006.3.0 MODULE 8A BUILD 001 - PLAYBACK AND KEY DISPLAY FIX
=================================================================

Status
------
BUILD COMPLETE

Starting point
--------------
Module 8 Build 001.

Fixes
-----
- Stop now resets audio position, slider, time label and grid cursor to Beat 1.
- Play safely restarts if position is at the end.
- Library list shows Key field.
- Practice info panel shows Key field.
- Chord names on bar starts are retained.

Accuracy note
-------------
Key Unknown is expected until the real key/chord engine is built.

Acceptance test
---------------
PASS if:
- Search/download/analyse/save still work.
- Library list shows Key.
- Practice info panel shows Key.
- Grid shows chord names on bar starts.
- Play works.
- Pause holds position.
- Stop returns audio, slider and cursor to Beat 1.
- Play works again after Stop.
