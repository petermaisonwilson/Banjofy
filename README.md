# Banjofy Build 003.1

This build restores the working demo-player behaviour from Build 002.6 and adds a responsive layout fix.

## Included

- Restored loop selection by clicking beat squares.
- Restored To Start navigation.
- Restored Back button clamp so it cannot jump from beat 1 to the final beat.
- Restored count-in before playback.
- Restored 3-bars-across beat grid.
- Improved resizing so the grid uses remaining space and avoids horizontal scrolling.
- Updated visible app name: `Banjofy 0.3.1 - Build 003.1 Restore 002.6 + Layout`.

## Not included yet

- Real YouTube search.
- Audio download.
- Sound playback.
- Automatic chord analysis.

Those should come next once the restored demo player is confirmed working again.

## GitHub upload

Upload/replace these items in the repository root:

- `src`
- `README.md`
- `requirements.txt`
- `Banjofy.spec`
- `.gitignore`

The `.github/workflows/windows-build.yml` file is included for completeness, but if your workflow is already working you do not need to change it.
