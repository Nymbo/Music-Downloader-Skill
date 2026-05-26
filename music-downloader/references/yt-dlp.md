# yt-dlp Audio Reference

Use these patterns when the manifest script is not the right fit, or when debugging a failed album download.

## Command Pattern

All yt-dlp audio downloads follow this structure:

```powershell
yt-dlp [FLAGS] -o "OUTPUT_TEMPLATE" "URL"
```

## Core Flags

| Flag | Purpose | Recommendation |
|------|---------|----------------|
| `-f bestaudio` | Select best audio stream | Always include |
| `--extract-audio` | Extract audio from video | Always include |
| `--audio-format mp3` | Output format | Use `mp3` for compatibility |
| `--audio-quality 0` | Quality, where 0 is best | Use `0` |
| `--embed-metadata` | Add title/artist metadata | Always include for library work |
| `--embed-thumbnail` | Add album art | Optional; can slow or fail postprocessing |
| `--download-archive downloaded.txt` | Avoid repeated downloads | Useful for retries |

## Common Commands

Single album playlist:

```powershell
yt-dlp -f bestaudio --extract-audio --audio-format mp3 --audio-quality 0 --embed-metadata -o ".\Downloaded\Artist\%(playlist_title)s\%(title)s.%(ext)s" "PLAYLIST_URL"
```

Single track:

```powershell
yt-dlp -f bestaudio --extract-audio --audio-format mp3 --audio-quality 0 --embed-metadata -o ".\Downloaded\Artist\%(title)s.%(ext)s" "URL"
```

Playlist range:

```powershell
yt-dlp --playlist-items 1-5 -f bestaudio --extract-audio --audio-format mp3 --audio-quality 0 --embed-metadata -o ".\Downloaded\Artist\%(playlist_title)s\%(title)s.%(ext)s" "PLAYLIST_URL"
```

Split by chapters:

```powershell
yt-dlp -f bestaudio --extract-audio --audio-format mp3 --audio-quality 0 --split-chapters -o ".\Downloaded\Artist\%(title)s.%(ext)s" "URL"
```

Extract a time segment:

```powershell
yt-dlp -f bestaudio --extract-audio --audio-format mp3 --external-downloader ffmpeg --external-downloader-args "ffmpeg_i:-ss 00:01:00 -to 00:05:00" -o ".\Downloaded\Artist\%(title)s.%(ext)s" "URL"
```

Use browser cookies for age-restricted content:

```powershell
yt-dlp --cookies-from-browser chrome -f bestaudio --extract-audio --audio-format mp3 --audio-quality 0 --embed-metadata -o ".\Downloaded\Artist\%(playlist_title)s\%(title)s.%(ext)s" "URL"
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `yt-dlp: command not found` | Install or update yt-dlp in the active shell |
| `ffmpeg not found` | Install ffmpeg and confirm it is on `PATH` |
| 403 Forbidden / unable to download | Upgrade yt-dlp, then retry |
| Rate limited / 429 | Add `--sleep-interval 5 --max-sleep-interval 15` |
| Geo-restricted | Try `--geo-bypass` |
| File already exists | Use `--no-overwrites` for safe retries or `--force-overwrites` when replacing |

Debug commands:

```powershell
yt-dlp -F "URL"
yt-dlp -v "URL"
yt-dlp --version
```
