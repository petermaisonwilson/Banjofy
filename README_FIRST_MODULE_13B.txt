BANJOFY MODULE 13B BUILD 001 - GITHUB DESKTOP

Copy these files into the local Banjofy repository:

1. tools/apply_module_13b.py
2. .github/workflows/windows-build.yml
3. MANIFEST_006_3_0_MODULE_13B_BUILD_001.txt

KEEP all earlier Module 11, 12, 12A, 13 and 13A patch files.

GITHUB DESKTOP SUMMARY
Banjofy 006.3.0 Module 13B Build 001 count-in startup fix

GITHUB DESKTOP DESCRIPTION
Fixes the Module 13A startup crash by initialising count-in state before any reset
method can run and making count-in cancellation defensive. Preserves adjustable
count-in, one-shot repeat sections and all confirmed Module 12A features.
