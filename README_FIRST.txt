BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 012
COMPLETE CLEAN REBUILD

Build 012 is rebuilt from the complete confirmed Build 002 baseline.

DIRECTLY VERIFIED CORRECTION
Build 011 reached the confirmed ChordMini interface import and failed because
mir_eval was not installed. The complete confirmed Laboratory 016 requirements
were then opened and read directly.

Build 012 reproduces that exact Laboratory 016 model dependency set:
numpy 1.26.4, PyYAML 6.0.2, setuptools 80.9.0, torch 2.9.1,
librosa 0.10.1, scipy 1.13.1, soundfile 0.12.1, tqdm 4.67.1,
matplotlib 3.10.1, seaborn 0.13.2, mir_eval 0.8.2,
scikit-learn 1.6.1 and imageio-ffmpeg >=0.5.

It also uses Python 3.11, exactly matching the confirmed Laboratory 016
workflow, while retaining the verified Module 17 UI and downloader packages.

No downloader, timing or chord-analysis algorithm has changed.

INSTALLATION
Copy everything inside M17_B012 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-012-Windows
