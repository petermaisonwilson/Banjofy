BANJOFY BEATNET LISTENING LABORATORY 002

This is a clean rebuild of BeatNet Lab 001.

The GitHub workflow now:
- installs PyAudio explicitly on Windows
- verifies PyAudio import
- verifies BeatNet import
- creates a real synthetic audio file
- runs BeatNet in offline DBN mode
- checks that increasing beat times and downbeats are returned
- packages the Windows application only after that test passes

This remains a separate timing experiment. Existing Banjofy chord detection and
the earlier SAL selector are unchanged.
