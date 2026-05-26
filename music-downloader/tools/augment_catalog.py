import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex_deps"))

from ytmusicapi import YTMusic

from tools.collect_ytmusic_catalog import album_entry


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "music-download-work" / "ytmusic-catalog-raw.json"

ADDITIONS = [
    {
        "artist": "Persona 5",
        "query": "Persona 5 Original Soundtrack",
        "title": "PERSONA5 ORIGINAL SOUNDTRACK",
    },
    {
        "artist": "Persona 5",
        "query": "P5S Original Soundtrack",
        "title": "『ペルソナ５ スクランブル　ザ ファントム ストライカーズ』 オリジナル・サウンドトラック",
    },
    {
        "artist": "Blood Stain Child",
        "query": "Blood Stain Child Silence of Northern Hell",
        "title": "Silence Of Northern Hell",
    },
    {
        "artist": "Metallica",
        "query": "Metallica ReLoad",
        "title": "Reload",
    },
]


def find_album(ytm, query, title):
    for result in ytm.search(query, filter="albums", limit=10):
        if result.get("title") == title:
            details = ytm.get_album(result["browseId"])
            return album_entry(query, result, details)
    raise RuntimeError(f"Could not find album: {query} -> {title}")


def main():
    catalog = json.loads(RAW.read_text(encoding="utf-8"))
    by_artist = {artist["name"]: artist for artist in catalog["artists"]}
    ytm = YTMusic()
    for addition in ADDITIONS:
        artist = by_artist[addition["artist"]]
        existing = {album.get("playlistId") for album in artist.get("albums", [])}
        entry = find_album(ytm, addition["query"], addition["title"])
        if entry["playlistId"] not in existing:
            artist.setdefault("albums", []).append(entry)
            artist["albums"].sort(key=lambda a: ((a["year"] if a["year"] is not None else 9999), a["title"].lower()))
            print(f"Added {addition['artist']} - {entry['title']}")
        else:
            print(f"Already present {addition['artist']} - {entry['title']}")
        time.sleep(0.2)
    RAW.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
