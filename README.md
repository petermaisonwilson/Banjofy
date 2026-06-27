# Banjofy

## Build 002.6 - Loop Selection and Navigation

Changes in Build 002.6:

- On-screen version now says **Banjofy 0.2.6 - Build 002.6 Loop Select + To Start**.
- Loop start/end are now selected by clicking a beat in the grid.
- **Select Start**: click a beat/bar to set the loop start.
- **Select End**: click a beat/bar to set the loop end.
- Pressing Play with a loop selected jumps to the loop start, then starts the count-in.
- Added **To Start** button.
  - No loop: jumps to the first beat of the song.
  - Loop active: jumps to the first beat of the loop.
- Back no longer wraps from the first beat to the final beat.
- The 3-bars-across layout remains unchanged.

Note on audio:

- There is still no real sound playback in this build. The app is currently testing timing-grid behaviour only.

Note on Concert Chords vs Banjo Shapes:

- **Banjo Shapes** shows the chord shape name being played.
- **Concert Chords** shows the chord that would be heard after applying the capo.
- At this stage this is only basic display logic. Full capo/chord-engine behaviour will come later.
