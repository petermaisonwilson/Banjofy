BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 010
COMPLETE CLEAN REBUILD

Build 010 is rebuilt from the complete confirmed Build 002 package.

ROOT-CAUSE CORRECTION
Build 009 reached PyInstaller but failed because the spec required a ChordMini
folder that the workflow had never cloned. The confirmed Laboratory 016 build
did clone ptnghia-j/ChordMini and verified the checkpoint, inference script and
configuration before packaging.

Build 010 restores that proven model-asset process and also stops PyInstaller
from blindly collecting the incompatible legacy banjofy.engine package.

MODEL ASSETS VERIFIED
- ChordMini/checkpoints/2e1d_model_best.pth
- ChordMini/src/evaluation/test.py
- ChordMini/config/ChordMini.yaml
- ChordMini/src/models/__init__.py
- ChordMini/src/evaluation/utils.py

The workflow records the exact cloned ChordMini commit in CHORDMINI_SOURCE.txt.

INSTALLATION
Copy everything inside M17_B010 into the root Banjofy GitHub folder, allow
merging/replacement, then commit and push.

EXPECTED ARTIFACT
Banjofy-006.4.0-Module-17-Integration-Build-010-Windows
