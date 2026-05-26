---
name: music-downloader
description: Build and download verified music libraries from artist lists. Use when users provide artist names, Markdown checklist files such as New-Artists.md, or chunks of artists and want official album discographies, side-project coverage, verified YouTube album playlist links, and yt-dlp-based audio downloads into a local library.
---

# Music Downloader

Use this skill as a staged music-library workflow. Do not treat it as only a yt-dlp command reference: first research the catalog, then verify album playlists visually, then download from a complete manifest.

Default output root: `Downloaded` in the current repository/workspace. Use an absolute path when running scripts.

## Bundled Workflow Tools

This skill includes reusable workflow helpers under `tools/` in addition to the downloader under `scripts/`.

For future workspaces that do not already have the Library-Curator repo, copy the installed skill's `tools/` directory into the current workspace before running the catalog, verification, audit, or recovery workflow:

```powershell
Copy-Item -Recurse -Force -LiteralPath "$env:USERPROFILE\.codex\skills\music-downloader\tools" -Destination ".\tools"
```

The tools assume they are running from a workspace with `tools/` at the workspace root. They write to workspace-local files such as `music-download-work`, `library-audit-work`, `music-download-manifest.json`, and `music-download-plan.md`.

When Python helpers need `ytmusicapi`, install it into the workspace-local dependency folder so the bundled scripts can import it:

```powershell
python -m pip install --target .\.codex_deps -r "$env:USERPROFILE\.codex\skills\music-downloader\requirements.txt"
```

When JavaScript helpers need Playwright, install it in the workspace or use an available workspace Node dependency runtime:

```powershell
Copy-Item -Force -LiteralPath "$env:USERPROFILE\.codex\skills\music-downloader\package.json" -Destination ".\package.json"
npm install
```

Read `references/dependencies.md` when setting up a fresh workspace or when `ytmusicapi`, Playwright, `yt-dlp`, or `ffmpeg` is missing.

Use the bundled tools this way:

- `tools/collect_ytmusic_catalog.py`: parse artist input and collect YouTube Music album metadata.
- `tools/build_mainline_catalog_musicbrainz.py`: filter the raw catalog toward mainline albums with MusicBrainz checks.
- `tools/build_mainline_catalog.py`: older heuristic mainline filter; use only as a fallback or comparison.
- `tools/augment_catalog.py`: add targeted missing albums after manual search confirms them.
- `tools/verify_youtube_playlists.cjs`: render YouTube playlists with Playwright and compare visible tracks to expected tracklists.
- `tools/prune_verified_manifest.cjs`: build the strict download manifest and Markdown plan from verified playlists.
- `tools/compare_library_inventory.cjs`: compare a local music library inventory against the expected mainline catalog.
- `tools/build_library_repair_catalog.cjs`: create a repair download catalog for missing or incomplete local albums.
- `tools/apply_library_repair_moves.ps1`: apply reviewed repair move plans inside a music library root.
- `tools/recover_missing_album_tracks.py`: search and download individual missing-track candidates into a temporary recovery folder before moving accepted files.

## Phase 1: Parse Input And Build Scope

Accept any of these inputs:

- A Markdown checklist file such as `New-Artists.md`
- A pasted chunk of artist names
- A partial existing album/playlist manifest
- A single artist request

Normalize checkbox lines, bullets, and plain lines into artist candidates. Preserve the user's spelling in notes, but correct obvious entity names in the working manifest when research confirms the correction.

For ambiguous entries, research before asking. Examples:

- `Persona 5` is likely a soundtrack/franchise catalog rather than a performing artist.
- Parenthetical qualifiers such as `Bones (TeamSESH)` are disambiguation hints.
- Misspellings may be real artist names; verify before correcting.

## Phase 2: Research Official Album Catalogs

For each artist, create an ordered list of official albums and relevant side material. Use current web research with source attribution when available because discographies and reissues can change.

Clarify the desired scope before verification when the input could mean either "all official releases" or "mainline albums." If the user asks for mainline albums, keep the scope to studio albums for artists/bands and canonical official soundtrack albums for soundtrack/franchise entries. Exclude live albums, compilations, greatest-hits sets, EPs, singles, remix albums, instrumental versions, tribute albums, deluxe/anniversary/collector/box-set variants, and very large anthology playlists unless the user explicitly asks for those.

Include:

- Official studio albums in release order
- Official soundtrack albums when the input is a soundtrack/franchise/entity
- Albums released under known alternate names, side projects, groups, or aliases
- Important official collaborative albums when they are part of the artist's library

Separate or clearly label:

- EPs
- mixtapes
- live albums
- compilations
- deluxe editions and anniversary reissues
- remixes and unofficial collections

Prefer canonical tracklists from official artist sites, label pages, YouTube Music album pages, MusicBrainz, Discogs, Wikipedia only when corroborated, or other reliable catalog sources. Record the expected track count and track titles before searching for playlists.

Useful source workflow:

- Use MusicBrainz as the mainline-album filter when the user asks for "main line albums." It is useful for excluding live releases, compilations, remix releases, instrumentals, deluxe/anniversary sets, and unrelated YouTube shelf noise before the YouTube verification phase.
- Use YouTube Music metadata as the first pass for official album playlist IDs, especially `OLAK5uy_` playlists. `ytmusicapi` works well for artist shelves, album search, `browseId`, `audioPlaylistId`, and track lists.
- Do not trust an artist shelf blindly. It often includes live albums, compilations, clean/explicit duplicates, deluxe boxes, instrumentals, remasters, and unrelated soundtrack/tribute entries.
- Use targeted album searches when an artist shelf is empty or missing a mainline album. Some artist pages expose inline `albums.results` without a shelf `browseId`, and some albums only appear through search.
- For soundtrack/franchise inputs such as `Persona 5`, search exact soundtrack names and official composer/label entities instead of treating the entry as a performer.
- Avoid accepting very large playlists as "mainline" by default. Counts around 100+ tracks are usually box sets, collector editions, anthologies, or multi-disc soundtrack dumps unless the user explicitly requested them.
- Add explicit search aliases for typo-like or ambiguous artist inputs after confirming the intended entity. Bad examples observed in practice include `Limp Girl` resolving to Linkin Park and unrelated adult/novelty names resolving to irrelevant zero-album artist pages. Cut those from the manifest unless the intended artist is confirmed.

## Phase 3: Find And Visually Verify YouTube Playlists

For each album, find a full YouTube playlist URL. Prefer official YouTube Music album playlists and Official Artist / Topic uploads, especially playlist IDs that begin with `OLAK5uy_`.

Use the Playwright MCP server with the user's real browser for verification. Visually inspect each candidate playlist page before accepting it:

1. Open the playlist URL in Playwright.
2. Confirm the page title, channel/uploader, playlist count, and visible track list.
3. Compare the visible playlist tracks against the expected album tracklist.
4. Scroll or expand the playlist as needed until every expected track is accounted for.
5. Reject playlists with random extras, unrelated videos, missing album tracks, live substitutions, covers, commentary, reactions, or non-album uploads unless the user explicitly accepts that fallback.
6. Note any region-blocked, unavailable, hidden, duplicate, or reordered tracks.

Do not proceed to download an album unless it has a verified playlist URL. If Playwright MCP is unavailable, mark the playlist as unverified and stop before the download phase unless the user explicitly tells you to continue without visual verification.

Verification lessons that work well:

- Load `https://www.youtube.com/playlist?list=...` for visual verification. YouTube Music pages may reject headless/browser contexts with a deprecated-browser page even when regular YouTube renders correctly.
- Use a normal Chrome user agent when automating Playwright in headless mode if YouTube renders zero playlist rows.
- For rendered YouTube album pages, inspect `ytd-playlist-video-renderer` rows and compare the visible title, playlist count, and rendered track titles against the expected track list.
- Compare against the concrete expected track-title list, not only a metadata `trackCount`; metadata can disagree with the actual returned track array when hidden/unavailable tracks exist.
- Normalize benign title differences during comparison: brackets vs parentheses, compact ampersands such as `T&A` vs `T & A`, remaster/version suffixes, album-version suffixes, and reordered featured-artist names. Do not normalize away missing songs or extra unrelated tracks.
- YouTube rendered playlist pages can cap or fail to lazy-load very long album playlists. Treat that as a warning to re-check scope, especially when the user asked for mainline albums.

## Phase 4: Produce The Comprehensive Files

Create or update two files before downloading:

- A human-readable Markdown plan with each artist, aliases/side projects, ordered albums, expected track counts, selected playlist URLs, and verification notes.
- A machine-readable JSON manifest for `scripts/download-album-manifest.ps1`.

Use this manifest shape:

```json
{
  "artists": [
    {
      "name": "Jay-Z",
      "aliases": ["The Carters"],
      "albums": [
        {
          "title": "Reasonable Doubt",
          "year": 1996,
          "type": "studio album",
          "url": "https://www.youtube.com/playlist?list=OLAK5uy_lgp-WXLELSsU8wpwrXA9yqROtYgRuVnAE",
          "expectedTrackCount": 14,
          "verified": true,
          "verificationNote": "Visually matched expected album tracklist in YouTube playlist."
        }
      ]
    }
  ]
}
```

Keep the manifest strict JSON: no comments, trailing commas, or Markdown fences.

## Phase 5: Download Albums

Use `scripts/download-album-manifest.ps1` after every album in the manifest has `verified: true`.

Example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\music-downloader\scripts\download-album-manifest.ps1 -ManifestPath .\music-download-manifest.json -OutputRoot .\Downloaded
```

The script starts one PowerShell terminal process per artist and each process exits when its artist queue completes. It downloads one album at a time inside that artist process.

If the user asks for a dry run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\music-downloader\scripts\download-album-manifest.ps1 -ManifestPath .\music-download-manifest.json -OutputRoot .\Downloaded -PlanOnly
```

## Phase 6: Verify Download Results

After downloads finish, inspect `Downloaded` and the log files under `Downloaded/_logs`.

For each artist, check:

- The artist folder exists.
- Album playlist folders exist.
- Track files were created and have reasonable sizes.
- The log has no yt-dlp failures.

If an album fails, fix that album's playlist URL or retry only that artist/album rather than restarting the entire library job. For large artist runs, use the downloader's continue-on-album-error mode so one age-gated or unavailable track does not prevent later albums by the same artist from downloading; inspect the failed-album summary afterward and resolve only those items.

After a large run, reconcile the final manifest against files on disk by artist and total MP3 count before doing more retries. `yt-dlp` can return a non-zero album exit after downloading all available tracks, especially when a playlist contains one age-gated, unavailable, or copyright-removed video. If the user wants to cut problem tracks, map failed video IDs back to playlist titles with `yt-dlp --flat-playlist --dump-single-json`, decrement the affected album's expected count, record the exact cut tracks in the audit, and verify the final expected count equals the actual MP3 count. If a removed hidden playlist item does not reduce the kept expected count, record it as a warning rather than treating the whole album as missing.

When recovering individual missing tracks, download each candidate to a temporary folder first and then move the finished MP3 into the intended album folder with the expected playlist index. Do not point `yt-dlp -o` directly at a final Windows album path during recovery; yt-dlp can sanitize parent path components and create sibling folders when album names contain characters such as question marks. Keep candidate metadata in the audit, and reject very partial albums rather than adding folders with only a few tracks. A practical cutoff is to accept partial albums only when one or two problem tracks were cut, unless the user explicitly asks for rough/incomplete placeholders.

## yt-dlp Reference

Read `references/yt-dlp.md` when you need command variants, troubleshooting, or non-manifest single-download patterns.

Keep `yt-dlp` current before large library runs. If downloads fail with `Requested format is not available` even though Playwright verified the playlist, retry with a fallback format selector such as `bestaudio/best`; some YouTube album videos expose only combined fallback formats during SABR/JS-challenge changes. Do not treat this as playlist verification failure unless retrying with a current `yt-dlp` still cannot download the track.

Age-gated YouTube tracks need authenticated cookies. Prefer a user-exported Netscape cookies file or `--cookies-from-browser` only when it works in the current environment. On Windows, browser-cookie extraction can fail with DPAPI or locked-database errors; in that case do not keep rerunning the same playlist unauthenticated. Continue the rest of the artist, record the exact blocked video IDs, and ask for/export cookies or replace the source with a verified non-age-gated equivalent.

Always include the playlist index in the output filename for album downloads. Some albums contain repeated track titles, and a title-only template can silently overwrite one track with another.

Throttle large manifest downloads with `-MaxParallel` instead of starting every artist at once. Batches above a few dozen artists can otherwise create avoidable `yt-dlp`/`ffmpeg` contention and transient file-lock failures.
