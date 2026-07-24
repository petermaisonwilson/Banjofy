BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 024

Build 023 proved the compiled provider generated and returned a real PO Token.
The workflow printed that the provider probe passed, but PowerShell still ended
the step with yt-dlp's earlier native exit code 1.

Build 024 explicitly clears that accepted native exit state and exits the
provider-probe step with code 0.

No EAA runtime logic has changed. This is a precise GitHub workflow correction.
