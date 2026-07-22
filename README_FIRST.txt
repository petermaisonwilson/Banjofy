BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 011
COMPLETE CLEAN REBUILD

Build 011 is rebuilt from the complete confirmed Build 002 baseline.

DIRECTLY EVIDENCED CORRECTION
Build 010 cloned ChordMini successfully but then failed because it required two
extra physical paths that were not part of the confirmed Laboratory 016 build:

- ChordMini/src/models/__init__.py
- ChordMini/src/evaluation/utils.py

Build 011 reproduces the confirmed Laboratory 016 physical-asset checks exactly:

- ChordMini/checkpoints/2e1d_model_best.pth
- ChordMini/src/evaluation/test.py
- ChordMini/config/ChordMini.yaml

After dependency installation, it retains the confirmed Laboratory 016 Python
interface checks:

- from src.evaluation.utils import quality_analysis
- from src.models import load_model

The Module 17 chord engine independently verifies the same three runtime assets
that it actually uses.

No downloader, timing or chord-analysis algorithm has changed.

INSTALLATION
Copy everything inside M17_B011 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-011-Windows
