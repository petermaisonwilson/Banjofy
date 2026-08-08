BANJOFY BEATNET LISTENING LABORATORY 006

Minimal clean rebuild from Build 005.

ONLY FUNCTIONAL CHANGE
The Windows packaging-tools step now installs:
imageio-ffmpeg==0.4.9

The workflow immediately imports imageio_ffmpeg and resolves its bundled FFmpeg
executable before running PyInstaller.

WHY
beatnet_lab.spec imports imageio_ffmpeg and calls get_ffmpeg_exe() so the FFmpeg
binary can be included in the portable application. Build 005 had not installed
that Python package.

UNCHANGED
The real madmom + BeatNet offline proof and all three BeatNet model tests run
before packaging exactly as in Build 005.
