import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex_deps"))

from ytmusicapi import YTMusic


ROOT = Path(__file__).resolve().parents[1]
ARTIST_FILE = Path(os.environ.get("MUSIC_ARTIST_FILE", ROOT / "New-Artists.md"))
OUT_DIR = Path(os.environ.get("MUSIC_WORK_DIR", ROOT / "music-download-work"))
OUT_DIR.mkdir(exist_ok=True)


SEARCH_ALIASES = {
    "Bones (TeamSESH)": "Bones",
    "Missy Elliot": "Missy Elliott",
    "Elliot Smith": "Elliott Smith",
    "Hillary Duff": "Hilary Duff",
    "Limp Girl": "Limp Bizkit",
    "Boddy Caldwell": "Bobby Caldwell",
    "keshl": "keshi",
    "KDA": "K/DA",
    "ITOWOKASAHI": "ITOWOKASHI",
    "Friedrich Habetier": "Friedrich Habetler",
    "NIGHTMARE": "NIGHTMARE ナイトメア",
}


MANUAL_ALBUM_SEARCHES = {
    "Persona 5": {
        "queries": [
            "Persona 5 Original Soundtrack",
            "Persona 5 Royal Original Soundtrack",
            "Persona 5 Strikers Original Soundtrack",
        ],
        "include_any": ["persona 5", "persona5", "ペルソナ５"],
        "exclude_any": ["dancing", "tactica", "phantom x", "lofi", "advanced edition"],
        "max_tracks": 90,
    },
    "JoJo's Bizarre Adventure": {
        "queries": [
            "JoJo's Bizarre Adventure Original Soundtrack",
            "JoJo's Bizarre Adventure Stardust Crusaders Original Soundtrack",
            "JoJo's Bizarre Adventure Diamond is Unbreakable Original Soundtrack",
            "JoJo's Bizarre Adventure Golden Wind Original Soundtrack",
            "JoJo's Bizarre Adventure Stone Ocean Original Soundtrack",
        ],
        "include_any": ["jojo", "bizarre adventure", "ジョジョ"],
        "exclude_any": ["cover", "lofi", "piano"],
        "max_tracks": 80,
    },
    "Warcraft 3, Frozen Throne": {
        "queries": [
            "Warcraft III Reign of Chaos Original Soundtrack",
            "Warcraft III The Frozen Throne Original Soundtrack",
        ],
        "include_any": ["warcraft"],
        "exclude_any": ["world of warcraft", "cover", "piano"],
        "max_tracks": 80,
    },
    "GTA 3, Vice City, Chinatown Wars, 4, 5": {
        "queries": [
            "Grand Theft Auto III soundtrack",
            "Grand Theft Auto Vice City soundtrack",
            "Grand Theft Auto Chinatown Wars soundtrack",
            "Grand Theft Auto IV soundtrack",
            "Grand Theft Auto V soundtrack",
        ],
        "include_any": ["grand theft auto", "gta"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
    "Sid Meier's Civilization 3, 4, 5, 6, 7": {
        "queries": [
            "Sid Meier's Civilization III soundtrack",
            "Sid Meier's Civilization IV soundtrack",
            "Sid Meier's Civilization V soundtrack",
            "Sid Meier's Civilization VI soundtrack",
            "Sid Meier's Civilization VII soundtrack",
        ],
        "include_any": ["civilization"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
    "CSGO music kits (Desert Fire)": {
        "queries": [
            "Counter-Strike Global Offensive Desert Fire music kit",
            "CSGO Desert Fire music kit",
        ],
        "include_any": ["desert fire", "counter strike", "csgo", "global offensive"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 40,
    },
    "The Elder Scrolls Oblivion, Skyrim": {
        "queries": [
            "The Elder Scrolls IV Oblivion Original Game Soundtrack",
            "The Elder Scrolls V Skyrim Original Game Soundtrack",
        ],
        "include_any": ["elder scrolls", "oblivion", "skyrim"],
        "exclude_any": ["morrowind", "guild wars", "cover", "piano"],
        "max_tracks": 80,
    },
    "Fallout 3, 4, 76, New Vegas": {
        "queries": [
            "Fallout 3 Original Game Soundtrack",
            "Fallout New Vegas Original Game Soundtrack",
            "Fallout 4 Original Game Soundtrack",
            "Fallout 76 Original Game Soundtrack",
        ],
        "include_any": ["fallout"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
    "Persona 3, 4, 5": {
        "queries": [
            "Persona 3 Original Soundtrack",
            "Persona 3 Reload Original Soundtrack",
            "Persona 4 Original Soundtrack",
            "Persona 4 Golden Original Soundtrack",
            "Persona 5 Royal Original Soundtrack",
            "Persona 5 Strikers Original Soundtrack",
        ],
        "include_any": ["persona 3", "persona3", "persona 4", "persona4", "persona 5", "persona5", "ペルソナ3", "ペルソナ4", "ペルソナ５"],
        "exclude_any": ["dancing", "tactica", "phantom x", "lofi", "advanced edition"],
        "max_tracks": 90,
    },
    "Minecraft": {
        "queries": [
            "Minecraft Volume Alpha",
            "Minecraft Volume Beta",
            "Minecraft Nether Update Original Soundtrack",
            "Minecraft Caves & Cliffs Original Soundtrack",
            "Minecraft Trails & Tales Original Soundtrack",
            "Minecraft Tricky Trials Original Soundtrack",
        ],
        "include_any": ["minecraft"],
        "exclude_any": ["dungeons", "legends", "education", "live", "mini game", "mythology", "caller"],
        "max_tracks": 80,
    },
    "Hotline Miami 1, 2": {
        "queries": [
            "Hotline Miami Original Soundtrack",
            "Hotline Miami 2 Wrong Number Original Soundtrack",
        ],
        "include_any": ["hotline miami"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
    "God of War (2018 and Ragnarok)": {
        "queries": [
            "God of War 2018 Original Soundtrack Bear McCreary",
            "God of War Ragnarok Original Soundtrack Bear McCreary",
        ],
        "include_any": ["god of war"],
        "exclude_any": ["ghost of sparta", "god of war iii", "cover", "piano"],
        "max_tracks": 80,
    },
    "Shadow the Hedgehog": {
        "queries": [
            "Shadow the Hedgehog Original Soundtrack",
            "Shadow the Hedgehog Lost and Found Original Soundtrack",
        ],
        "include_any": ["shadow the hedgehog"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
    "Sonic Adventure 1, 2": {
        "queries": [
            "Sonic Adventure Original Soundtrack",
            "Sonic Adventure 2 Original Soundtrack",
        ],
        "include_any": ["sonic adventure"],
        "exclude_any": ["cover", "piano"],
        "max_tracks": 80,
    },
}


def safe_get_album(ytm, browse_id, notes, context):
    try:
        return ytm.get_album(browse_id)
    except Exception as exc:
        notes.append(f"Skipped album fetch for {context}: {type(exc).__name__}: {exc}")
        return None


def parse_artist_file(path: Path):
    artists = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        text = re.sub(r"^- \[[ xX]\]\s*", "", text)
        text = re.sub(r"^[-*]\s*", "", text)
        if text:
            artists.append(text)
    return artists


def clean_track(track):
    return {
        "number": track.get("trackNumber"),
        "title": track.get("title"),
        "duration": track.get("duration"),
        "videoId": track.get("videoId"),
        "available": track.get("isAvailable"),
        "artists": [a.get("name") for a in track.get("artists", []) if a.get("name")],
    }


def album_entry(source_artist, album, album_details):
    playlist_id = album.get("playlistId") or album.get("audioPlaylistId") or album_details.get("audioPlaylistId")
    tracks = [clean_track(track) for track in album_details.get("tracks", [])]
    title = album_details.get("title") or album.get("title")
    year_raw = album_details.get("year") or album.get("year")
    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        year = None
    return {
        "title": title,
        "year": year,
        "type": album_details.get("type") or album.get("type") or "Album",
        "url": f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else "",
        "playlistId": playlist_id,
        "browseId": album.get("browseId"),
        "expectedTrackCount": album_details.get("trackCount") or len(tracks),
        "expectedTracks": tracks,
        "verified": False,
        "verificationNote": "Pending Playwright verification.",
        "source": source_artist,
    }


def get_artist_albums(ytm, artist_name):
    notes = []
    search_name = SEARCH_ALIASES.get(artist_name, artist_name)
    try:
        candidates = ytm.search(search_name, filter="artists", limit=5)
    except Exception as exc:
        return {
            "name": artist_name,
            "matchedArtist": None,
            "artistBrowseId": None,
            "artistSearchCandidates": [],
            "albums": [],
            "notes": [f"Artist search failed for {search_name}: {type(exc).__name__}: {exc}"],
        }
    chosen = candidates[0] if candidates else None
    if not chosen:
        return {
            "name": artist_name,
            "matchedArtist": None,
            "artistBrowseId": None,
            "artistSearchCandidates": candidates,
            "albums": [],
            "notes": ["No YouTube Music artist match found."],
        }

    try:
        artist = ytm.get_artist(chosen["browseId"])
    except Exception as exc:
        return {
            "name": artist_name,
            "matchedArtist": chosen.get("artist") or chosen.get("name"),
            "artistBrowseId": chosen.get("browseId"),
            "artistSearchCandidates": candidates,
            "albums": [],
            "notes": [f"Artist fetch failed for {search_name}: {type(exc).__name__}: {exc}"],
        }
    albums_ref = artist.get("albums") or {}
    shelf = []
    if albums_ref.get("browseId"):
        try:
            shelf = ytm.get_artist_albums(albums_ref["browseId"], None)
        except Exception as exc:
            notes.append(f"Album shelf fetch failed: {type(exc).__name__}: {exc}")
    elif albums_ref.get("results"):
        shelf = albums_ref["results"]

    entries = []
    seen = set()
    for album in shelf:
        # Artist album shelves sometimes omit `type` on inline results while
        # the expanded shelf labels albums and singles explicitly.
        if album.get("type") and album.get("type") != "Album":
            continue
        browse_id = album.get("browseId")
        if not browse_id or browse_id in seen:
            continue
        seen.add(browse_id)
        details = safe_get_album(ytm, browse_id, notes, album.get("title") or browse_id)
        if not details:
            continue
        entry = album_entry(artist_name, album, details)
        if entry["expectedTrackCount"] and entry["expectedTrackCount"] > 1 and entry["url"]:
            entries.append(entry)
        time.sleep(0.15)

    entries.sort(key=lambda a: ((a["year"] if a["year"] is not None else 9999), a["title"].lower()))
    return {
        "name": artist_name,
        "matchedArtist": artist.get("name") or chosen.get("artist"),
        "artistBrowseId": chosen.get("browseId"),
        "artistSearchCandidates": candidates,
        "albums": entries,
        "notes": ([f"Artist search alias used: {search_name}"] if search_name != artist_name else []) + notes,
    }


def search_soundtrack_albums(ytm, artist_name, spec):
    entries = []
    notes = []
    seen_playlists = set()
    include_any = [term.lower() for term in spec.get("include_any", [])]
    exclude_any = [term.lower() for term in spec.get("exclude_any", [])]
    max_tracks = spec.get("max_tracks")
    for query in spec["queries"]:
        results = ytm.search(query, filter="albums", limit=8)
        for result in results:
            title = result.get("title", "")
            title_lower = title.lower()
            if include_any and not any(term in title_lower for term in include_any):
                continue
            if exclude_any and any(term in title_lower for term in exclude_any):
                continue
            browse_id = result.get("browseId")
            if not browse_id:
                continue
            details = safe_get_album(ytm, browse_id, notes, title or browse_id)
            if not details:
                continue
            playlist_id = result.get("playlistId") or details.get("audioPlaylistId")
            if not playlist_id or playlist_id in seen_playlists:
                continue
            track_count = details.get("trackCount") or len(details.get("tracks", []))
            if max_tracks and track_count and track_count > max_tracks:
                continue
            seen_playlists.add(playlist_id)
            entry = album_entry(artist_name, {**result, "playlistId": playlist_id}, details)
            if entry["expectedTrackCount"] and entry["expectedTrackCount"] > 1:
                entries.append(entry)
            time.sleep(0.15)

    entries.sort(key=lambda a: ((a["year"] if a["year"] is not None else 9999), a["title"].lower()))
    return {
        "name": artist_name,
        "matchedArtist": f"{artist_name} soundtrack/franchise search",
        "artistBrowseId": None,
        "artistSearchCandidates": [],
        "albums": entries,
        "notes": ["Handled as soundtrack/franchise catalog via targeted album searches."] + notes,
    }


def write_outputs(output):
    (OUT_DIR / "ytmusic-catalog-raw.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = [
        {
            "name": artist["name"],
            "matchedArtist": artist.get("matchedArtist"),
            "albumCount": len(artist.get("albums", [])),
            "albums": [f"{album.get('year') or '????'} - {album['title']} ({album['expectedTrackCount']})" for album in artist.get("albums", [])],
            "notes": artist.get("notes", []),
        }
        for artist in output["artists"]
    ]
    (OUT_DIR / "ytmusic-catalog-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ytm = YTMusic()
    artists = parse_artist_file(ARTIST_FILE)
    output = {"artists": []}
    for artist_name in artists:
        print(f"Collecting {artist_name}...", flush=True)
        try:
            if artist_name in MANUAL_ALBUM_SEARCHES:
                artist_entry = search_soundtrack_albums(ytm, artist_name, MANUAL_ALBUM_SEARCHES[artist_name])
            else:
                artist_entry = get_artist_albums(ytm, artist_name)
        except Exception as exc:
            artist_entry = {
                "name": artist_name,
                "matchedArtist": None,
                "artistBrowseId": None,
                "artistSearchCandidates": [],
                "albums": [],
                "notes": [f"Unhandled collection failure: {type(exc).__name__}: {exc}"],
            }
        output["artists"].append(artist_entry)
        write_outputs(output)
        time.sleep(0.4)

    summary = write_outputs(output)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
