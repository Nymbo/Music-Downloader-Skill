const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const workDir = process.env.MUSIC_WORK_DIR || path.join(root, "library-audit-work");
const inventoryPath = process.env.LOCAL_LIBRARY_INVENTORY || path.join(workDir, "local-library-inventory.json");
const catalogPath = process.env.MUSIC_CATALOG_PATH || path.join(workDir, "mainline-catalog.json");
const reportPath = process.env.LIBRARY_AUDIT_REPORT || path.join(workDir, "library-mainline-comparison.json");
const markdownPath = process.env.LIBRARY_AUDIT_MD || path.join(workDir, "library-mainline-comparison.md");

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[：:]/g, " ")
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[‐‑‒–—]/g, "-")
    .replace(/[⧸/\\]/g, " ")
    .replace(/\b(album|official|soundtrack|original|motion picture|expanded|edition|explicit|clean|remaster(?:ed)?|deluxe|bonus|anniversary|mono|stereo)\b/g, " ")
    .replace(/\b\d{4}\b/g, " ")
    .replace(/\([^)]*\)/g, " ")
    .replace(/\[[^\]]*\]/g, " ")
    .replace(/[^a-z0-9$'&+]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenSet(value) {
  return new Set(normalize(value).split(" ").filter(Boolean));
}

function jaccard(a, b) {
  if (!a.size && !b.size) return 1;
  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) intersection += 1;
  }
  return intersection / (a.size + b.size - intersection);
}

function findAlbumMatch(expected, localAlbums, usedIndexes) {
  const expectedNorm = normalize(expected.title);
  let best = null;
  localAlbums.forEach((album, index) => {
    if (usedIndexes.has(index)) return;
    const localNorm = normalize(album.title);
    let score = 0;
    if (expectedNorm === localNorm) {
      score = 1;
    } else if (
      expectedNorm &&
      localNorm &&
      expectedNorm.length >= 12 &&
      localNorm.length >= 12 &&
      Math.min(expectedNorm.length, localNorm.length) / Math.max(expectedNorm.length, localNorm.length) >= 0.82 &&
      (expectedNorm.includes(localNorm) || localNorm.includes(expectedNorm))
    ) {
      score = 0.92;
    } else {
      score = jaccard(tokenSet(expected.title), tokenSet(album.title));
    }
    if (!best || score > best.score) {
      best = { album, index, score };
    }
  });
  return best && best.score >= 0.72 ? best : null;
}

const inventory = JSON.parse(fs.readFileSync(inventoryPath, "utf8"));
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const localByArtist = new Map(inventory.artists.map((artist) => [artist.name, artist]));

const artists = [];
let missingAlbumCount = 0;
let trackMismatchCount = 0;
let matchedAlbumCount = 0;
let localExtraCount = 0;

for (const expectedArtist of catalog.artists) {
  const localArtist = localByArtist.get(expectedArtist.name);
  const localAlbums = localArtist ? localArtist.albums : [];
  const used = new Set();
  const missingAlbums = [];
  const trackMismatches = [];
  const matchedAlbums = [];

  for (const expectedAlbum of expectedArtist.albums || []) {
    const match = findAlbumMatch(expectedAlbum, localAlbums, used);
    if (!match) {
      missingAlbums.push(expectedAlbum);
      missingAlbumCount += 1;
      continue;
    }
    used.add(match.index);
    matchedAlbumCount += 1;
    const localTrackCount = Number(match.album.trackCount || 0);
    const expectedTrackCount = Number(expectedAlbum.expectedTrackCount || 0);
    const matched = {
      expectedTitle: expectedAlbum.title,
      localTitle: match.album.title,
      expectedTrackCount,
      localTrackCount,
      score: Number(match.score.toFixed(3)),
      localPath: match.album.path,
      url: expectedAlbum.url,
    };
    matchedAlbums.push(matched);
    if (expectedTrackCount && localTrackCount !== expectedTrackCount) {
      trackMismatches.push(matched);
      trackMismatchCount += 1;
    }
  }

  const localExtras = localAlbums
    .map((album, index) => ({ album, index }))
    .filter(({ index }) => !used.has(index))
    .map(({ album }) => ({
      title: album.title,
      trackCount: album.trackCount,
      path: album.path,
    }));
  localExtraCount += localExtras.length;

  artists.push({
    name: expectedArtist.name,
    matchedArtist: expectedArtist.matchedArtist,
    expectedAlbumCount: (expectedArtist.albums || []).length,
    localAlbumCount: localAlbums.length,
    matchedAlbums,
    missingAlbums,
    trackMismatches,
    localExtras,
  });
}

const report = {
  generatedAt: new Date().toISOString(),
  localRoot: inventory.root,
  catalogPath,
  totals: {
    artists: artists.length,
    expectedAlbums: catalog.artists.reduce((sum, artist) => sum + (artist.albums || []).length, 0),
    localAlbums: inventory.albumCount,
    matchedAlbums: matchedAlbumCount,
    missingAlbums: missingAlbumCount,
    trackMismatches: trackMismatchCount,
    localExtras: localExtraCount,
  },
  artists,
};

fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + "\n", "utf8");

let md = `# Library Mainline Comparison\n\nGenerated: ${report.generatedAt}\n\n`;
md += `- Artists compared: ${report.totals.artists}\n`;
md += `- Expected mainline albums: ${report.totals.expectedAlbums}\n`;
md += `- Local album folders: ${report.totals.localAlbums}\n`;
md += `- Matched albums: ${report.totals.matchedAlbums}\n`;
md += `- Missing expected albums: ${report.totals.missingAlbums}\n`;
md += `- Matched albums with track-count mismatches: ${report.totals.trackMismatches}\n`;
md += `- Local extras outside expected mainline set: ${report.totals.localExtras}\n\n`;

md += "## Track Count Mismatches\n\n";
for (const artist of artists.filter((artist) => artist.trackMismatches.length)) {
  md += `### ${artist.name}\n\n`;
  for (const mismatch of artist.trackMismatches) {
    md += `- ${mismatch.expectedTitle}: local ${mismatch.localTrackCount}, expected ${mismatch.expectedTrackCount}; folder \`${mismatch.localTitle}\`\n`;
  }
  md += "\n";
}

md += "## Missing Expected Albums\n\n";
for (const artist of artists.filter((artist) => artist.missingAlbums.length)) {
  md += `### ${artist.name}\n\n`;
  for (const album of artist.missingAlbums) {
    md += `- ${album.year || "????"} - ${album.title} (${album.expectedTrackCount || "?"} tracks)\n`;
  }
  md += "\n";
}

fs.writeFileSync(markdownPath, md, "utf8");
console.log(JSON.stringify(report.totals, null, 2));
