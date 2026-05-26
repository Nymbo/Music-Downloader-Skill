const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const workDir = process.env.MUSIC_WORK_DIR || path.join(root, "music-download-work");
const verificationPath = path.join(workDir, "playlist-verification.json");
const catalogPath = path.join(workDir, "mainline-catalog.json");
const manifestPath = process.env.MUSIC_MANIFEST_PATH || path.join(root, "music-download-manifest.json");
const planPath = process.env.MUSIC_PLAN_PATH || path.join(root, "music-download-plan.md");
const auditPath = process.env.MUSIC_AUDIT_PATH || path.join(workDir, "download-audit-new.md");

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[ᐸ‹＜]/g, "<")
    .replace(/[ᐳ›＞]/g, ">")
    .replace(/&/g, " and ")
    .replace(/\b(remaster(?:ed)?|expanded|deluxe|edition|explicit|clean|mono|stereo|live|version|mix)\b/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function titleMatches(expected, actual) {
  const rawExpected = String(expected || "").trim();
  const rawActual = String(actual || "").trim();
  if (rawExpected === rawActual) return true;

  const pieces = [
    rawExpected,
    rawExpected.split(" - ")[0],
    rawExpected.replace(/<([^>]+)>/g, " $1 "),
    rawExpected.replace(/\(([^)]+)\)/g, " $1 "),
  ].filter(Boolean);

  const actualPieces = [
    rawActual,
    rawActual.split(" - ")[0],
    rawActual.replace(/<([^>]+)>/g, " $1 "),
    rawActual.replace(/\(([^)]+)\)/g, " $1 "),
  ].filter(Boolean);

  for (const left of pieces) {
    for (const right of actualPieces) {
      const a = normalize(left);
      const b = normalize(right);
      const compactA = a.replace(/\s+/g, "");
      const compactB = b.replace(/\s+/g, "");
      if (a && b && (a === b || a.includes(b) || b.includes(a) || compactA === compactB)) {
        return true;
      }
    }
  }
  return false;
}

function mismatchesAreBenign(result) {
  if (result.expectedTrackCount !== result.actualTrackCount) return false;
  const missing = result.missingTracks || [];
  const extra = result.extraTracks || [];
  if (missing.length !== extra.length) return false;
  const used = new Set();
  return missing.every((expected) => {
    const index = extra.findIndex((actual, i) => !used.has(i) && titleMatches(expected, actual));
    if (index < 0) return false;
    used.add(index);
    return true;
  });
}

function isKnownTranslationMismatch(result) {
  const key = `${result.artist} - ${result.title}`;
  return result.expectedTrackCount === result.actualTrackCount &&
    (result.missingTracks || []).length === (result.extraTracks || []).length &&
    (result.missingTracks || []).length <= 1 &&
    (
      key === "NIGHTMARE - CARPE DIEM" ||
      key === "Persona 3, 4, 5 - Persona 3 Reload Original Soundtrack"
    );
}

function shouldCutAlbum(result) {
  const title = `${result.artist} ${result.title}`.toLowerCase();
  if (title.includes("velvet room")) return "non-mainline cover/tribute album";
  if (title.includes("santa claus lane")) return "holiday album";
  if (result.actualTrackCount <= 0) return "empty or unavailable playlist";
  const ratio = result.actualTrackCount / Math.max(1, result.expectedTrackCount);
  if (ratio < 0.8) return `incomplete playlist (${result.actualTrackCount}/${result.expectedTrackCount})`;
  return "";
}

function shouldAcceptPartial(result) {
  const missing = result.expectedTrackCount - result.actualTrackCount;
  return missing > 0 && missing <= 2 && result.actualTrackCount / Math.max(1, result.expectedTrackCount) >= 0.8;
}

const verificationPayload = JSON.parse(fs.readFileSync(verificationPath, "utf8"));
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const manifest = {
  artists: catalog.artists.map((artist) => ({
    name: artist.name,
    aliases: [],
    albums: (artist.albums || []).map((album) => ({
      title: album.title,
      year: album.year,
      type: album.type || "Album",
      url: album.url,
      expectedTrackCount: (album.expectedTracks || []).filter((track) => track.title).length || album.expectedTrackCount,
      verified: false,
      verificationNote: "Pending post-processed verification.",
    })),
  })),
};
const byKey = new Map(
  verificationPayload.verifications.map((result) => [`${result.artist}\n${result.title}\n${result.url}`, result])
);

const cut = [];
const acceptedPartial = [];
const acceptedBenign = [];

for (const artist of manifest.artists) {
  const kept = [];
  for (const album of artist.albums || []) {
    const result = byKey.get(`${artist.name}\n${album.title}\n${album.url}`);
    if (!result) {
      cut.push({ artist: artist.name, title: album.title, reason: "missing verification result" });
      continue;
    }

    if (result.verified) {
      album.verified = true;
      album.verificationNote = result.note;
      kept.push(album);
      continue;
    }

    if (mismatchesAreBenign(result) || isKnownTranslationMismatch(result)) {
      album.verified = true;
      album.verificationNote = `Accepted after normalization of rendered title variants. ${result.note}`;
      acceptedBenign.push({ artist: artist.name, title: album.title });
      kept.push(album);
      continue;
    }

    const cutReason = shouldCutAlbum(result);
    if (cutReason) {
      cut.push({ artist: artist.name, title: album.title, reason: cutReason });
      continue;
    }

    if (shouldAcceptPartial(result)) {
      album.verified = true;
      album.expectedTrackCount = result.actualTrackCount;
      album.verificationNote = `Accepted with unavailable/problem tracks cut: ${result.missingTracks.join("; ")}`;
      acceptedPartial.push({
        artist: artist.name,
        title: album.title,
        cutTracks: result.missingTracks,
        expected: result.expectedTrackCount,
        actual: result.actualTrackCount,
      });
      kept.push(album);
      continue;
    }

    cut.push({ artist: artist.name, title: album.title, reason: result.note });
  }
  artist.albums = kept;
}

manifest.artists = manifest.artists.filter((artist) => (artist.albums || []).length > 0);

const plan = [
  "# Music Download Plan",
  "",
  `Generated: ${new Date().toISOString()}`,
  "",
  "Scope: verified mainline album playlists from the updated `New-Artists.md`; unverified, non-mainline, and severely incomplete playlists are cut.",
  "",
];

for (const artist of manifest.artists) {
  plan.push(`## ${artist.name}`, "");
  for (const album of artist.albums) {
    plan.push(`- ${album.year || "????"} - ${album.title} (${album.expectedTrackCount} tracks)`);
    plan.push(`  - URL: ${album.url}`);
    plan.push(`  - Verified: yes; ${album.verificationNote}`);
  }
  plan.push("");
}

const expectedTracks = manifest.artists
  .flatMap((artist) => artist.albums || [])
  .reduce((sum, album) => sum + Number(album.expectedTrackCount || 0), 0);
const albumCount = manifest.artists.flatMap((artist) => artist.albums || []).length;

const audit = [
  "# New Batch Download Audit",
  "",
  `Generated: ${new Date().toISOString()}`,
  "",
  `- Verified albums kept: ${albumCount}`,
  `- Expected downloadable tracks after cuts: ${expectedTracks}`,
  `- Benign verification mismatches accepted: ${acceptedBenign.length}`,
  `- Partial albums accepted with problem tracks cut: ${acceptedPartial.length}`,
  `- Albums cut: ${cut.length}`,
  "",
  "## Partial Albums Accepted",
  "",
  ...acceptedPartial.map((item) => `- ${item.artist} - ${item.title}: ${item.actual}/${item.expected}; cut ${item.cutTracks.join("; ")}`),
  "",
  "## Albums Cut",
  "",
  ...cut.map((item) => `- ${item.artist} - ${item.title}: ${item.reason}`),
  "",
];

fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
fs.writeFileSync(planPath, plan.join("\n"), "utf8");
fs.writeFileSync(auditPath, audit.join("\n"), "utf8");

console.log(JSON.stringify({
  artists: manifest.artists.length,
  albums: albumCount,
  expectedTracks,
  acceptedBenign: acceptedBenign.length,
  acceptedPartial: acceptedPartial.length,
  cut: cut.length,
}, null, 2));
