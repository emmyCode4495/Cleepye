# YouTube link downloads

Cleepye uses **yt-dlp** to fetch public video links.

## Server env

```env
YOUTUBE_COOKIES_PATH=/app/data/youtube_cookies.txt
YOUTUBE_CONCURRENT_FRAGMENTS=1
MAX_DOWNLOAD_HEIGHT=1080
```

Keep **yt-dlp** updated:

```bash
pip install -U yt-dlp
```

## Cookies (optional)

For age-restricted or “sign in to confirm you’re not a bot” videos:

1. In a desktop browser, log into YouTube and open the video.
2. Export cookies as Netscape `cookies.txt` (e.g. “Get cookies.txt LOCALLY”).
3. Place the file on the server and set `YOUTUBE_COOKIES_PATH`.
4. Never commit cookies to git.

## If downloads still fail

Cloud hosts (Render, etc.) use datacenter IPs that YouTube often blocks.

- Prefer **file upload** for reliable mining.
- Or run the API on a residential network / VPS with less aggressive blocking.
- Do not share one cookies file across high-volume production traffic.

## User-facing errors

Failed link downloads return a clear job error (shown in the UI), e.g. rate limit, bot check, private video — and suggest uploading the file.
