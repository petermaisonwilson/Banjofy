BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 021
EXTERNAL ACQUISITION AGENT

ROOT-CAUSE CORRECTION
Build 020 proved the EAA itself was complete and ready. The workflow then
failed because an inline PowerShell/Python test over-escaped a Windows path.

Build 021 removes that inline quoted test completely.

It now runs eaa_release_gate.py, which:
- reads the real EAA health result;
- builds the real command;
- compares resolved pathlib paths;
- checks each required switch and its exact value;
- checks the provider configuration and selected URL;
- raises named RuntimeError messages rather than a bare AssertionError.

The External Acquisition Agent design and application code are unchanged.
