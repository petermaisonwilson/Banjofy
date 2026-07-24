BANJOFY 006.4.0 — MODULE 17 INTEGRATION BUILD 023

Build 022 successfully generated and returned a real player PO Token. GitHub
then failed because YouTube rejected the shared GitHub cloud IP with
LOGIN_REQUIRED.

Build 023 separates those two facts correctly.

GitHub must prove:
- portable Node starts;
- compiled provider starts;
- plugin loads;
- the provider generates a real PO Token;
- yt-dlp receives that token;
- Banjofy and the final Acquisition folder build correctly.

GitHub does not fail solely because YouTube rejects the shared GitHub cloud IP
after token generation. Peter's Windows connection remains the proper
end-to-end download acceptance test.

Keep the complete Acquisition folder beside Banjofy.exe.
