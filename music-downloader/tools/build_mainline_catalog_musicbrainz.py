import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("MUSIC_WORK_DIR", ROOT / "music-download-work"))
RAW = WORK / "ytmusic-catalog-raw.json"
OUT = WORK / "mainline-catalog.json"
SUMMARY = WORK / "mainline-catalog-summary.md"
MB_REPORT = WORK / "musicbrainz-mainline-report.json"

USER_AGENT = "Library-Curator/1.0 (local codex workflow)"

SEARCH_ALIASES = {
    "Bones (TeamSESH)": "Bones",
    "Eve": "Eve rapper",
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

SOUNDTRACK_ENTRIES = {
    "JoJo's Bizarre Adventure",
    "Warcraft 3, Frozen Throne",
    "GTA 3, Vice City, Chinatown Wars, 4, 5",
    "Sid Meier's Civilization 3, 4, 5, 6, 7",
    "CSGO music kits (Desert Fire)",
    "Team Fortress 2",
    "The Elder Scrolls Oblivion, Skyrim",
    "Fallout 3, 4, 76, New Vegas",
    "Persona 3, 4, 5",
    "Persona 5",
    "Minecraft",
    "Hotline Miami 1, 2",
    "God of War (2018 and Ragnarok)",
    "League of Legends",
    "Shadow the Hedgehog",
    "Sonic Adventure 1, 2",
}

EXCLUDE_TERMS = [
    "acoustic",
    "anniversary",
    "anthology",
    "best of",
    "b sides",
    "b-sides",
    "bootleg",
    "box set",
    "christmas",
    "collector",
    "collection",
    "compilation",
    "commentary",
    "covers",
    "demo",
    "demos",
    "essential",
    "greatest",
    "holiday",
    "instrumental",
    "karaoke",
    "live",
    "lofi",
    "lo fi",
    "mixtape",
    "mtv unplugged",
    "piano",
    "playlist",
    "radio broadcast",
    "remix",
    "remixes",
    "sessions",
    "single",
    "slowed",
    "sped up",
    "super deluxe",
    "tribute",
    "tour",
    "unplugged",
    "very best",
]

SOUNDTRACK_EXCLUDE_TERMS = [
    "cover",
    "covers",
    "deluxe",
    " ep",
    "guitar",
    "goes metal",
    "inspired by",
    "lofi",
    "lo fi",
    "lullabies",
    "music box",
    "piano",
    "redux",
    "reimagined",
    "tribute",
]

TITLE_EXCLUDES = {
    "NSYNC": {"Home For Christmas", "The Winter Album"},
    "Backstreet Boys": {"A Very Backstreet Christmas"},
    "Britney Spears": {"Lucky"},
    "Shakira": {"The Remixes"},
    "Gwen Stefani": {"You Make It Feel Like Christmas"},
    "Vashti Bunyan": {"Some Things Just Stick In Your Mind (Singles And Demos 1964 To 1967)"},
    "Billie Piper": {"The Very Best Of Billie Piper"},
    "MYTH & ROID": {"MYTH & ROID BESTアルバム「MUSEUM-THE BEST OF MYTH ＆ ROID-」"},
    "WagakkiBand": {"KISEKI BEST COLLECTION＋"},
    "Hillary Duff": {"Santa Claus Lane"},
    "Minecraft": {"Minecraft Reimagined", "Music Inspired by C418's \"Minecraft (Volume Alpha\")", "Minecraft (Volume Alpha New Edition)", "Minecraft Jungle - Volume Alpha", "A Minecraft Movie (Original Motion Picture Soundtrack)"},
    "Hotline Miami 1, 2": {"Hotline Miami Goes Metal", "Hotline Miami Goes Metal, Vol. 2", "Hotline Miami: Redux-Redux Vol. 1"},
    "God of War (2018 and Ragnarok)": {"God of War Ragnarök: Valhalla (Original Soundtrack)"},
    "Sonic Adventure 1, 2": {"Sonic The Hedgehog \"Passion & Pride\" Anthems with Attitude from the Sonic Adventure Era - Vox Collection"},
}


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def canonical_title(value):
    text = normalized(re.sub(r"\([^)]*\)", " ", str(value)))
    drop = {
        "bonus",
        "clean",
        "deluxe",
        "digital",
        "edition",
        "expanded",
        "explicit",
        "remaster",
        "remastered",
        "special",
        "version",
    }
    return " ".join(part for part in text.split() if part not in drop)


def has_excluded_term(title, soundtrack=False):
    terms = SOUNDTRACK_EXCLUDE_TERMS if soundtrack else EXCLUDE_TERMS
    text = normalized(title)
    return any(term in text for term in terms)


def album_penalty(album):
    title = normalized(album.get("title", ""))
    penalty = 0
    for term in ["deluxe", "expanded", "remaster", "remastered", "bonus", "special", "clean", "explicit"]:
        if term in title:
            penalty += 1
    count = album.get("expectedTrackCount") or 0
    if count > 35:
        penalty += 1
    return penalty


def musicbrainz_get(path, params):
    query = urllib.parse.urlencode({**params, "fmt": "json"})
    req = urllib.request.Request(
        f"https://musicbrainz.org/ws/2/{path}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_musicbrainz_artist(name):
    search_name = SEARCH_ALIASES.get(name, name)
    data = musicbrainz_get("artist/", {"query": f'artist:"{search_name}"', "limit": 5})
    artists = data.get("artists", [])
    if not artists:
        return None, search_name, []
    return artists[0], search_name, artists


MB_ALBUM_CACHE = {}


def get_musicbrainz_albums(artist_id):
    if artist_id in MB_ALBUM_CACHE:
        return MB_ALBUM_CACHE[artist_id]

    groups = []
    offset = 0
    while True:
        data = musicbrainz_get(
            "release-group/",
            {"artist": artist_id, "type": "album", "limit": 100, "offset": offset},
        )
        batch = data.get("release-groups", [])
        groups.extend(batch)
        if offset + len(batch) >= data.get("release-group-count", len(groups)):
            break
        offset += len(batch)
        time.sleep(1.1)

    albums = []
    for group in groups:
        if group.get("primary-type") != "Album":
            continue
        if group.get("secondary-types"):
            continue
        title = group.get("title")
        if not title or has_excluded_term(title):
            continue
        albums.append({
            "title": title,
            "year": int(group.get("first-release-date", "9999")[:4]) if group.get("first-release-date", "")[:4].isdigit() else None,
            "musicbrainzId": group.get("id"),
        })
    albums.sort(key=lambda album: ((album["year"] if album["year"] is not None else 9999), normalized(album["title"])))
    MB_ALBUM_CACHE[artist_id] = albums
    return albums


def find_best_musicbrainz_artist(name, yt_albums):
    search_name = SEARCH_ALIASES.get(name, name)
    data = musicbrainz_get("artist/", {"query": f'artist:"{search_name}"', "limit": 5})
    candidates = data.get("artists", [])
    best = None
    best_albums = []
    best_matches = -1

    for candidate in candidates:
        albums = get_musicbrainz_albums(candidate["id"])
        matches = sum(1 for album in albums if choose_youtube_album(album["title"], yt_albums))
        candidate_score = int(candidate.get("score", 0))
        if matches > best_matches or (matches == best_matches and best and candidate_score > int(best.get("score", 0))):
            best = candidate
            best_albums = albums
            best_matches = matches
        time.sleep(1.1)

    if best_matches <= 0:
        return None, search_name, candidates, []

    return best, search_name, candidates, best_albums


def choose_youtube_album(mb_title, yt_albums):
    target = canonical_title(mb_title)
    candidates = []
    for album in yt_albums:
        title = album.get("title", "")
        candidate = canonical_title(title)
        if candidate == target or candidate.startswith(target) or target.startswith(candidate):
            if has_excluded_term(title):
                continue
            candidates.append(album)
    if not candidates:
        return None
    return sorted(candidates, key=lambda album: (album_penalty(album), len(album.get("title", ""))))[0]


def build_soundtrack_albums(artist):
    albums = []
    seen = set()
    for album in artist.get("albums", []):
        title = album.get("title", "")
        if title in TITLE_EXCLUDES.get(artist["name"], set()):
            continue
        if artist["name"] == "Sonic Adventure 1, 2" and "vol" in normalized(title):
            continue
        if has_excluded_term(title, soundtrack=True):
            continue
        if artist["name"] != "CSGO music kits (Desert Fire)" and album.get("expectedTrackCount", 0) < 4:
            continue
        if album.get("expectedTrackCount", 0) > 90:
            continue
        key = canonical_title(title)
        if key in seen:
            continue
        seen.add(key)
        albums.append(album)
    return albums


def build_fallback_albums(artist):
    albums = []
    seen = set()
    for album in artist.get("albums", []):
        title = album.get("title", "")
        if title in TITLE_EXCLUDES.get(artist["name"], set()):
            continue
        if has_excluded_term(title):
            continue
        if album.get("expectedTrackCount", 0) > 45:
            continue
        key = canonical_title(title)
        if key in seen:
            continue
        seen.add(key)
        albums.append(album)
    return albums


def main():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    out = {"artists": []}
    report = []
    lines = ["# Mainline Album Scope", ""]
    total = 0

    for artist in raw["artists"]:
        name = artist["name"]
        selected = []
        missing_mb_titles = []
        matched_source = "fallback"
        mb_artist = None

        if name in SOUNDTRACK_ENTRIES or any("targeted album searches" in note for note in artist.get("notes", [])):
            selected = build_soundtrack_albums(artist)
            matched_source = "targeted soundtrack"
        else:
            try:
                mb_artist, search_name, candidates, mb_albums = find_best_musicbrainz_artist(name, artist.get("albums", []))
                time.sleep(1.1)
                if mb_artist:
                    matched_source = f"MusicBrainz: {mb_artist.get('name')}"
                    used_playlists = set()
                    for mb_album in mb_albums:
                        yt_album = choose_youtube_album(mb_album["title"], artist.get("albums", []))
                        if not yt_album:
                            missing_mb_titles.append(mb_album["title"])
                            continue
                        if yt_album.get("playlistId") in used_playlists:
                            continue
                        used_playlists.add(yt_album.get("playlistId"))
                        selected.append(yt_album)
                else:
                    selected = build_fallback_albums(artist)
            except Exception as error:
                matched_source = f"fallback after MusicBrainz error: {error}"
                selected = build_fallback_albums(artist)

        total += len(selected)
        out["artists"].append({**artist, "albums": selected})
        report.append({
            "name": name,
            "matchedSource": matched_source,
            "matchedMusicBrainzArtistId": mb_artist.get("id") if mb_artist else None,
            "selectedAlbumCount": len(selected),
            "selectedAlbums": [album.get("title") for album in selected],
            "missingMusicBrainzTitles": missing_mb_titles,
        })

        lines.append(f"## {name}")
        lines.append(f"Source: {matched_source}")
        for album in selected:
            lines.append(f"- {album.get('year') or '????'} - {album['title']} ({album.get('expectedTrackCount')} tracks)")
        if not selected:
            lines.append("- MISSING MAINLINE PLAYLISTS")
        if missing_mb_titles:
            lines.append("Missing on YouTube Music shelf:")
            for title in missing_mb_titles[:20]:
                lines.append(f"- {title}")
        lines.append("")

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    MB_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"artists={len(out['artists'])} albums={total}")


if __name__ == "__main__":
    main()
