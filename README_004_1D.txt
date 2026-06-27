Banjofy Build 004.1D - Thumbnail URL Fix

Replace this file in GitHub:

src/banjofy/youtube/search.py

Expected behaviour:
- YouTube search still works.
- Search results should now provide thumbnail URLs to the existing thumbnail panel.
- If yt-dlp still cannot provide a thumbnail, the code falls back to the standard YouTube hqdefault.jpg thumbnail URL.

No UI layout changes in this patch.
