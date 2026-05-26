# Music Downloader Dependencies

Use this when setting up a fresh workspace for the `music-downloader` skill.

## Python

The Python catalog and recovery helpers require `ytmusicapi`.

Install into the workspace-local dependency folder expected by the bundled scripts:

```powershell
python -m pip install --target .\.codex_deps -r "$env:USERPROFILE\.codex\skills\music-downloader\requirements.txt"
```

## Node

The Playwright playlist verifier requires the `playwright` npm package.

Install into the workspace:

```powershell
Copy-Item -Force -LiteralPath "$env:USERPROFILE\.codex\skills\music-downloader\package.json" -Destination ".\package.json"
npm install
```

If Playwright browsers are missing, install Chromium:

```powershell
npx playwright install chromium
```

## Download Tools

The download script shells out to `yt-dlp`, and audio conversion/metadata embedding requires `ffmpeg`.

Recommended setup:

```powershell
python -m pip install -U yt-dlp
winget install Gyan.FFmpeg
```

Verify both commands are available:

```powershell
yt-dlp --version
ffmpeg -version
```
