# Music Downloader Skill

A skill for [Codex](https://github.com/openai/codex) and Claude that autonomously builds and downloads verified music libraries from a list of artists. Give it a text file of artist names, send it as a `/goal`, and come back to a fully downloaded, properly organized library.

## What It Does

Most "download a discography" workflows are one-liners that blindly grab whatever YouTube returns. This skill is a staged pipeline that treats correctness as a first-class concern:

1. **Researches** each artist's mainline discography using MusicBrainz and YouTube Music as authoritative sources, filtering out live albums, compilations, deluxe editions, and other non-studio noise
2. **Finds** official YouTube Music album playlists (`OLAK5uy_` IDs preferred) for each album
3. **Visually verifies** each playlist with headless Playwright — confirms the page title, uploader, track count, and every individual track title against the expected tracklist before accepting it
4. **Produces** a human-readable Markdown plan and a machine-readable JSON manifest
5. **Downloads** all verified albums in parallel batches via `yt-dlp`, one terminal process per artist
6. **Audits** your existing library and generates a repair catalog for missing or incomplete albums
7. **Recovers** individual missing tracks into a staging folder before committing them

If verification fails for an album, it stops. Nothing downloads unverified.

## Requirements

- Windows (PowerShell scripts; the Python/Node tools are cross-platform)
- [Codex CLI](https://github.com/openai/codex) or a Claude agent with shell access
- Python 3.x
- Node.js
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)
- [`ffmpeg`](https://ffmpeg.org/)

See [`references/dependencies.md`](music-downloader/references/dependencies.md) for full setup instructions.

## Installation

Install the skill into Codex:

```powershell
# From the repo root
Copy-Item -Recurse -Force -LiteralPath ".\music-downloader" -Destination "$env:USERPROFILE\.codex\skills\music-downloader"
```

Install Python and Node dependencies into your workspace before running:

```powershell
python -m pip install --target .\.codex_deps -r "$env:USERPROFILE\.codex\skills\music-downloader\requirements.txt"

Copy-Item -Force -LiteralPath "$env:USERPROFILE\.codex\skills\music-downloader\package.json" -Destination ".\package.json"
npm install
npx playwright install chromium
```

## Usage

Create a plain text file listing one artist per line:

```
Aphex Twin
Burial
Four Tet
Lone
Boards of Canada
```

Then send this as a `/goal` in Codex (or as a prompt to a Claude agent with shell access):

```
Use $music-downloader to research these artists, verify YouTube album playlists, and download the verified albums.

<paste your artist list here>
```

The agent will work through the full pipeline autonomously. For large batches, use Codex's `/goal` feature so it can run unattended across multiple turns.

### Output Structure

```
Downloaded/
├── Aphex Twin/
│   ├── Selected Ambient Works 85-92/
│   │   ├── 01 - Xtal.mp3
│   │   ├── 02 - Tha.mp3
│   │   └── ...
│   └── Richard D. James Album/
│       └── ...
├── Burial/
│   └── ...
└── _logs/
    ├── Aphex Twin-20250101-120000.log
    └── ...
```

Working files written to the workspace:

| File | Description |
|------|-------------|
| `music-download-plan.md` | Human-readable plan with verification status for every album |
| `music-download-manifest.json` | Machine-readable manifest consumed by the download script |
| `music-download-work/` | Intermediate catalog and verification output |

## Workflow Tools

The `tools/` directory contains reusable helpers for each pipeline stage:

| Tool | Purpose |
|------|---------|
| `collect_ytmusic_catalog.py` | Collect YouTube Music album metadata for each artist |
| `build_mainline_catalog_musicbrainz.py` | Filter raw catalog to mainline studio albums using MusicBrainz |
| `build_mainline_catalog.py` | Heuristic fallback filter (use if MusicBrainz coverage is thin) |
| `augment_catalog.py` | Add targeted missing albums after manual confirmation |
| `verify_youtube_playlists.cjs` | Headless Playwright verification of each album playlist |
| `prune_verified_manifest.cjs` | Build the strict download manifest from verified playlists |
| `compare_library_inventory.cjs` | Diff a local library against the expected mainline catalog |
| `build_library_repair_catalog.cjs` | Generate a repair catalog for missing or incomplete albums |
| `apply_library_repair_moves.ps1` | Apply a reviewed repair plan to an existing library root |
| `recover_missing_album_tracks.py` | Search and download individual missing tracks to a staging folder |

## Download Script

`scripts/download-album-manifest.ps1` drives the actual downloading. It spawns one parallel process per artist, each downloading one album at a time.

```powershell
# Full run
powershell -NoProfile -ExecutionPolicy Bypass -File .\music-downloader\scripts\download-album-manifest.ps1 `
  -ManifestPath .\music-download-manifest.json `
  -OutputRoot .\Downloaded

# Dry run (shows what would be downloaded without downloading)
powershell -NoProfile -ExecutionPolicy Bypass -File .\music-downloader\scripts\download-album-manifest.ps1 `
  -ManifestPath .\music-download-manifest.json `
  -OutputRoot .\Downloaded `
  -PlanOnly
```

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-ManifestPath` | required | Path to `music-download-manifest.json` |
| `-OutputRoot` | `.\Downloaded` | Root folder for downloaded files |
| `-MaxParallel` | `8` | Max concurrent artist processes |
| `-ContinueOnAlbumError` | off | Continue to next album if one fails |
| `-AllowUnverified` | off | Allow downloading unverified albums |
| `-PlanOnly` | off | Dry run; print planned paths without downloading |

## Notes

- **Scope defaults to mainline studio albums.** Live albums, compilations, deluxe editions, EPs, and remix albums are excluded unless you explicitly ask for them.
- **Verification is a hard gate.** The download script refuses to download any album not marked `verified: true` in the manifest unless `-AllowUnverified` is passed.
- **Parallel downloads are throttled.** The default of 8 concurrent artist processes avoids `yt-dlp`/`ffmpeg` contention. Tune `-MaxParallel` for your machine.
- **Age-gated tracks** require cookies. See [`references/yt-dlp.md`](music-downloader/references/yt-dlp.md) for cookie export options.
- **Keep `yt-dlp` current.** YouTube format changes break downloads. Run `pip install -U yt-dlp` before large jobs.

## License

MIT
