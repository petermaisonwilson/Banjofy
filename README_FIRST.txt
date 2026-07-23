BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 017
COMPLETE CLEAN REBUILD

Build 017 is rebuilt from the complete confirmed Build 002 baseline.

BUILD 016 FAILURE
The exact bgutil plugin modules were staged successfully:
- getpot_bgutil.py
- getpot_bgutil_http.py
- getpot_bgutil_script.py

Build 016 then incorrectly used `yt-dlp --verbose --version` as a plugin
initialisation test. The version-only command printed the pinned version and
exited without initialising extractors, so it could not report plugin
directories.

BUILD 017 CORRECTION
- Retains the confirmed plugin staging and portable artifact layout.
- Activates the portable plugin path through yt-dlp's actual Python API:
  yt_dlp.globals.plugin_dirs.value followed by
  yt_dlp.plugins.load_all_plugins().
- Imports all three staged bgutil modules immediately and fails if any cannot
  load.
- Uses `--verbose --list-extractors` only as a second extractor-initialisation
  proof; this performs the initialisation that `--version` did not.
- Removes the unsupported YoutubeDL constructor `plugin_dirs` parameter.
- Retains Build 016 repeat corrections unchanged.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-017-Windows
