import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex_deps"))

from ytmusicapi import YTMusic


ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("MUSIC_WORK_DIR", ROOT / "library-audit-work"))
INPUT = Path(os.environ.get("RECOVERY_INPUT_PATH", WORK / "unresolved-missing-tracks.json"))
OUT = Path(os.environ.get("RECOVERY_OUTPUT_PATH", WORK / "missing-track-recovery-results.json"))
TEMP_ROOT = WORK / "RecoveredTracksTemp"


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\b(remaster(?:ed)?|expanded|deluxe|edition|explicit|clean|mono|stereo|official|audio|video)\b", " ", text)
    text = re.sub(r"[^a-z0-9$'&+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(value):
    text = re.sub(r'[<>:"/\\|?*]', "_", str(value or "").strip())
    text = re.sub(r"\s+", " ", text).strip().rstrip(". ")
    return text or "Untitled"


def title_score(expected, actual):
    expected_norm = normalize(expected)
    actual_norm = normalize(actual)
    if not expected_norm or not actual_norm:
        return 0
    if expected_norm == actual_norm:
        return 1
    if expected_norm in actual_norm or actual_norm in expected_norm:
        return 0.92
    expected_tokens = set(expected_norm.split())
    actual_tokens = set(actual_norm.split())
    intersection = len(expected_tokens & actual_tokens)
    union = len(expected_tokens | actual_tokens) or 1
    return intersection / union


def artist_score(expected_artist, result):
    expected_norm = normalize(expected_artist)
    names = []
    for artist in result.get("artists") or []:
        if isinstance(artist, dict):
            names.append(artist.get("name") or "")
        else:
            names.append(str(artist))
    joined = " ".join(names)
    joined_norm = normalize(joined)
    if not expected_norm or not joined_norm:
        return 0
    if expected_norm in joined_norm or joined_norm in expected_norm:
        return 1
    expected_tokens = set(expected_norm.split())
    actual_tokens = set(joined_norm.split())
    return len(expected_tokens & actual_tokens) / (len(expected_tokens) or 1)


def existing_indexes(album_dir):
    indexes = set()
    if not album_dir or not album_dir.exists():
        return indexes
    for file in album_dir.rglob("*.mp3"):
        match = re.match(r"^(\d{1,3})\s+-\s+", file.name)
        if match:
            indexes.add(int(match.group(1)))
    return indexes


def search_candidates(ytm, artist, track_title):
    queries = [
        f"{artist} {track_title}",
        f"{artist} {track_title} official audio",
        f"{track_title} {artist}",
    ]
    seen = set()
    candidates = []
    for query in queries:
        for search_filter in ("songs", "videos"):
            try:
                results = ytm.search(query, filter=search_filter, limit=8)
            except Exception:
                continue
            for result in results:
                video_id = result.get("videoId")
                if not video_id or video_id in seen:
                    continue
                seen.add(video_id)
                score = title_score(track_title, result.get("title")) + (0.35 * artist_score(artist, result))
                if score < 0.82:
                    continue
                candidates.append(
                    {
                        "videoId": video_id,
                        "title": result.get("title"),
                        "artists": result.get("artists") or [],
                        "duration": result.get("duration"),
                        "score": round(score, 3),
                        "query": query,
                        "filter": search_filter,
                    }
                )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def run_ytdlp(video_id, album_dir, track_number, track_title):
    target = album_dir / f"{track_number:02d} - {safe_filename(track_title)}.mp3"
    if target.exists():
        return {
            "ok": True,
            "skippedExisting": True,
            "targetPath": str(target),
            "returncode": 0,
            "stdoutTail": "",
            "stderrTail": "",
        }

    temp_dir = TEMP_ROOT / f"{int(time.time() * 1000)}-{video_id}-{track_number:02d}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output = temp_dir / "%(title).180B.%(ext)s"
    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--embed-metadata",
        "-o",
        str(output),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    mp3s = sorted(temp_dir.rglob("*.mp3"), key=lambda item: item.stat().st_mtime, reverse=True)
    moved = False
    if completed.returncode == 0 and mp3s:
        album_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(mp3s[0]), str(target))
        moved = target.exists()
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
    return {
        "ok": completed.returncode == 0 and moved,
        "targetPath": str(target),
        "tempDir": str(temp_dir),
        "returncode": completed.returncode,
        "stdoutTail": completed.stdout[-1200:],
        "stderrTail": completed.stderr[-1200:],
    }


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    ytm = YTMusic()
    results = []
    max_tracks = int(os.environ.get("RECOVERY_MAX_TRACKS", "0") or "0")
    attempted = 0

    for album in data["albums"]:
        album_dir = Path(album["partialRepairPath"]) if album.get("partialRepairPath") else None
        allow_empty = os.environ.get("RECOVERY_ALLOW_EMPTY_ALBUM", "").lower() in {"1", "true", "yes"}
        if not album_dir or (not album_dir.exists() and not allow_empty) or (album.get("partialRepairCount", 0) <= 0 and not allow_empty):
            continue
        album_dir.mkdir(parents=True, exist_ok=True)
        indexes = existing_indexes(album_dir)
        for track in album.get("missingTracks") or []:
            track_number = int(track["number"])
            if track_number in indexes:
                continue
            if max_tracks and attempted >= max_tracks:
                break
            attempted += 1
            print(f"[{attempted}] {album['artist']} - {album['title']} #{track_number}: {track['title']}", flush=True)
            candidates = search_candidates(ytm, album["artist"], track["title"])
            result = {
                "artist": album["artist"],
                "album": album["title"],
                "trackNumber": track_number,
                "trackTitle": track["title"],
                "originalVideoId": track.get("videoId"),
                "albumDir": str(album_dir),
                "candidates": candidates[:5],
                "downloaded": False,
                "chosen": None,
                "attempts": [],
            }
            for candidate in candidates[:5]:
                if candidate["videoId"] == track.get("videoId") and len(candidates) > 1:
                    continue
                attempt = run_ytdlp(candidate["videoId"], album_dir, track_number, track["title"])
                result["attempts"].append({"candidate": candidate, **attempt})
                if attempt["ok"]:
                    result["downloaded"] = True
                    result["chosen"] = candidate
                    break
                time.sleep(0.5)
            results.append(result)
            OUT.write_text(json.dumps({"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
            time.sleep(0.2)
        if max_tracks and attempted >= max_tracks:
            break

    OUT.write_text(json.dumps({"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"attempted": attempted, "downloaded": sum(1 for item in results if item["downloaded"])}, indent=2))


if __name__ == "__main__":
    main()
