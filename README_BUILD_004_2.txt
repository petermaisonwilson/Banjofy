Banjofy Build 004.2 - YouTube Audio Download

Replace these files in GitHub:
- src/banjofy/ui/main_window.py
- src/banjofy/youtube/search.py
- src/banjofy/youtube/downloader.py   (new file)
- src/banjofy/youtube/__init__.py
- requirements.txt

Expected behaviour:
1. YouTube search still works.
2. Thumbnails still show.
3. Selecting a YouTube result enables Download Audio.
4. Download Audio downloads best available audio to a local cache:
   AppData/Local/Banjofy/audio_cache
5. Progress/status updates are shown.
6. If the same song is selected again later it should use the cached audio.

Not yet included:
- actual audio playback
- syncing the cursor to downloaded audio
- automatic chord analysis
