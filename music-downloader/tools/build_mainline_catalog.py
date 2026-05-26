import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "music-download-work"
RAW = WORK / "ytmusic-catalog-raw.json"
OUT = WORK / "mainline-catalog.json"
SUMMARY = WORK / "mainline-catalog-summary.md"


EXCLUDE_WORDS = [
    "acoustic", "advanced edition", "anthology", "best of", "b-sides", "box set",
    "collector", "collection", "compilation", "complete", "covers", "deep cuts",
    "essential", "greatest", "instrumental", "karaoke", "live",
    "lofi", "lo-fi", "mixtape", "mtv unplugged", "platinum", "playlist",
    "radio broadcast", "remix", "sessions",
    "soundtrack to the apocalypse", "sped up", "slowed", "super deluxe",
    "tribute", "unplugged", "very best",
]

EXCLUDE_TITLES = {
    "Childish Gambino": {"Heartbeat (Remix Bundle)", "Kauai"},
    "Blood Stain Child": {"THE LEGEND", "CYBERIA"},
    "Radiohead": {"I Might Be Wrong", "Com Lag: 2+2=5", "In Rainbows (Disk 2)", "TKOL RMX 1234567", "KID A MNESIA", "Hail to the Thief (Live Recordings 2003-2009)"},
    "Persona 5": {"PERSONA5 ORIGINAL SOUNDTRACK", "Persona 5 (Original Motion Picture Soundtrack)", "Persona 5: Dancing in Starlight Soundtrack", "Persona Dancing 『P3D』＆『P5D』 Soundtrack –ADVANCED EDITION-", "Persona 5 Tactica Original Soundtrack", "Video Game LoFi: Persona 5 EP (Lo-Fi Edit)"},
    "Metallica": {"Garage, Inc.", "S&M", "Lulu", "The Metallica Blacklist", "The Metallica Collection", "Metallica Through The Never (Music from the Motion Picture)", "Helping Hands…Live & Acoustic At The Masonic", "S&M 2", "ReLoad"},
    "Busta Rhymes": {"The Abstract Dragon", "Extinction Level Event 2: The Wrath of God (Reloaded)", "BLOCKBUSTA (Slowed & Reverb)", "BLOCKBUSTA (Sped Up)"},
    "JID": {"Spilligion", "God Does Like Ugly (Alternate Version)", "God Does Like Ugly (Preluxe Edition)"},
    "Rage Against the Machine": {"Live & Loud ‘93 (live)", "Live at the Grand Olympic Auditorium", "The Battle Of Mexico City (Live)", "Paintings Of Rebellion", "Live & Rare", "Live On Tour 1993"},
    "Pantera": {"Official Live: 101 Proof", "The Best of Pantera: Far Beyond the Great Southern Cowboy's Vulgar Hits", "Far Beyond Bootleg - Live from Donington '94"},
    "Nirvana": {"Incesticide", "Nevermind Madrid 1992 (live)", "Live and Loud 1993 (live)", "MTV Unplugged In New York", "MTV Unplugged In New York (25th Anniversary)", "From The Muddy Banks Of The Wishkah (Live)", "Nirvana", "Sliver - The Best Of The Box", "Live at Reading", "With The Lights Out - Box Set", "Live And Loud", "Live At The Paramount", "Choice Is Yours", "Jam On Sunset"},
    "Alice in Chains": {"Bleed The Freak 1990 (live)", "Jar Of Flies", "Unplugged", "Music Bank", "Nothing Safe - The Best Of The Box", "Live", "Greatest Hits", "The Essential Alice In Chains", "Live At The Palladium Hollywood 1992"},
    "Tool": {"Starplex Dallas '93 (live)"},
    "Megadeth": {"Hammersmith Odeon London 1987 (Live)", "Way Back When", "Hidden Treasures", "Still Alive... And Well?", "Greatest Hits: Back To The Start", "Warchest", "Anthology: Set The World Afire", "Rude Awakening (Live)", "Countdown To Extinction: Live", "Warheads On Foreheads", "That One Night: Live In Buenos Aires", "Unplugged in Boston (Live 2001)"},
    "Sublime": {"Jah Won't Pay The Bills", "Second-Hand Smoke", "Stand By Your Van - Live!", "Sublime Acoustic: Bradley Nowell & Friends", "Greatest Hits", "20th Century Masters: The Millennium Collection: Best Of Sublime", "Gold", "Everything Under The Sun", "Playlist Your Way", "3 Ring Circus - Live At The Palace", "Sublime Meets Scientist & Mad Professor Inna L.B.C.", "Roots Of Sublime", "$5 At The Door (Live at Tressel Tavern, 1994)", "study and chill with sublime", "Look At All The Love We Found: A Tribute To Sublime (Reworked and Remastered)"},
    "KRS One": {"A Retrospective", "Shadup Ya Face / Yes, Yes, Y'all (Music from the Motion Picture Soundtrack Once in the Life)", "Strickly for Da Breakdancers & Emceez", "The Mix Tape", "D.I.G.I.T.A.L.", "Playlist: The Very Best Of KRS-One", "Meta-Historical (Instrumental)", "Royalty Check (Canadian Edition)", "The B.D.P. Album (Special Edition)", "The Essential Boogie Down Productions / KRS-One", "King of the Ol' Skool"},
    "Slipknot": {"9.0 Live", "Rock in Rio Brazil 2011", "Antennas to Hell", "The Studio Album Collection (1999 - 2008)", "Day Of The Gusano (Live)"},
    "Avenged Sevenfold": {"Waking The Fallen: Resurrected", "Hail to the King: Deathbat (Original Video Game Soundtrack)", "Diamonds in the Rough", "Live in the LBC"},
    "Deftones": {"White Pony (20th Anniversary Deluxe Edition)", "B-Sides & Rarities", "Covers", "The Studio Album Collection"},
    "AC/DC": {"If You Want Blood You've Got It (Live)", "Live", "Bonfire", "Backtracks", "Iron Man 2", "Live at River Plate", "River Plate 1996: Live Radio Broadcast"},
    "Slayer": {"Live Undead", "Live Undead / Haunting the Chapel", "Reign In Blood (Expanded)", "Live: Decade Of Aggression", "Argentina 94 (live)", "Soundtrack To The Apocalypse", "The Repentless Killogy (Live at the Forum in Inglewood, CA)", "Live in Paris '91 (live)", "Damnation's Edge"},
    "Helloween": {"The Best, the Rest, the Rare (The Collection 1984-1988)", "High Live", "Treasure Chest (Bonus Track Edition)", "Unarmed", "Unarmed: Best of 25th Anniversary", "My God-Given Right (Track Commentary Version)", "Live on 3 Continents", "Ride the Sky: The Very Best of 1985-1998", "United Alive in Madrid (Live)", "Live At Budokan", "March of Time (1984-1998)"},
    "Stratovarius": {"Intermission (Deluxe Version)", "Under Flaming Winter Skies - Live in Tampere (The Jörg Michael Farewell Tour)", "Elements, Pt. 1&2 (Complete Edition)", "Best Of", "Visions of Europe (2016 Remaster (Live))", "Enigma: Intermission 2"},
    "Dance Gavin Dance": {"Downtown Battle Mountain (Instrumental)", "Dance Gavin Dance (Instrumental)", "Happiness (Instrumental)", "Downtown Battle Mountain ll (Instrumental)", "Acceptance Speech 2.0", "Acceptance Speech 2.0 (Instrumental)", "Instant Gratification (Instrumental)", "Mothership (Instrumental)", "Tree City Sessions (Live)", "Artificial Selection (Instrumental)", "Afterburner (Instrumental)", "Tree City: Sessions 2", "Jackpot Juicer (Instrumental)", "Tree City Sessions 3"},
    "Blink-182": {"Buddha", "The Mark, Tom And Travis Show (The Enema Strikes Back!) (Live)", "Greatest Hits", "Enema Of The State / Take Off Your Pants And Jacket / Blink-182", "ONE MORE TIME... PART-2"},
}


INCLUDE_TITLES = {
    "Persona 5": {"Persona 5 Royal: Original Soundtrack", "『ペルソナ５ スクランブル　ザ ファントム ストライカーズ』 オリジナル・サウンドトラック"},
    "Queen": {"Flash Gordon (Original Soundtrack)"},
}

EXTRA_EXCLUDE_TITLES = {
    "Doja Cat": {"Scarlet 2 CLAUDE"},
    "Metallica": {"Load (Remastered Deluxe Box Set)", "ReLoad (Remastered Deluxe Box Set)"},
    "Queen": {
        "At The BBC",
        "Queen Rock Montreal",
        "Forever",
        "Forever (Deluxe Edition)",
        "A Night at the Odeon",
        "Queen On Air",
        "Bohemian Rhapsody (The Original Soundtrack)",
        "Queen I (2024 Mix)",
        "Queen I (Collector's Edition)",
        "Queen II (2026 Mix)",
        "Queen II (Collector's Edition)",
    },
    "The Rolling Stones": {
        "The Rolling Stones In Mono",
        "The Rolling Stones Rock And Roll Circus (Expanded)",
        "Hot Rocks 1964-1971",
        "Licked Live In NYC",
        "GRRR Live!",
        "Hackney Diamonds (Live Edition)",
        "Live At The Wiltern",
        "Welcome To Shepherds Bush (Live)",
        "Black And Blue (Super Deluxe)",
        "Black And Blue (2025 Mix)",
    },
    "Pantera": {"Reinventing the Steel (20th Anniversary Edition)"},
    "Slayer": {"Hell Awaits (40th Anniversary Edition)"},
    "Helloween": {"Keeper of the Seven Keys, Pt. 2 (Expanded Edition)"},
    "Megadeth": {"Countdown To Extinction (Expanded Edition - Remastered)"},
    "Blink-182": {"ONE MORE TIME... PART-2"},
}


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_mainline(artist_name, album):
    title = album["title"]
    if title in INCLUDE_TITLES.get(artist_name, set()):
        return True
    if title in EXCLUDE_TITLES.get(artist_name, set()):
        return False
    if title in EXTRA_EXCLUDE_TITLES.get(artist_name, set()):
        return False
    lowered = normalized(title)
    if any(word in lowered for word in EXCLUDE_WORDS):
        return False
    return True


def main():
    catalog = json.loads(RAW.read_text(encoding="utf-8"))
    out = {"artists": []}
    lines = ["# Mainline Album Scope", ""]
    total = 0
    for artist in catalog["artists"]:
        albums = []
        seen = set()
        for album in artist.get("albums", []):
            if not is_mainline(artist["name"], album):
                continue
            key = (normalized(album["title"]), album.get("year"))
            if key in seen:
                continue
            seen.add(key)
            albums.append(album)
        total += len(albums)
        out["artists"].append({**artist, "albums": albums})
        lines.append(f"## {artist['name']}")
        for album in albums:
            lines.append(f"- {album.get('year') or '????'} - {album['title']} ({album.get('expectedTrackCount')} tracks)")
        if not albums:
            lines.append("- MISSING MAINLINE PLAYLISTS")
        lines.append("")
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(f"artists={len(out['artists'])} albums={total}")


if __name__ == "__main__":
    main()
