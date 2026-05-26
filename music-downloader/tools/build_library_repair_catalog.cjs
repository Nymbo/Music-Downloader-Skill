const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const workDir = process.env.MUSIC_WORK_DIR || path.join(root, "library-audit-work");
const catalogPath = process.env.MUSIC_CATALOG_PATH || path.join(workDir, "mainline-catalog.json");
const comparisonPath = process.env.LIBRARY_COMPARISON_PATH || path.join(workDir, "library-mainline-comparison.json");
const outPath = process.env.LIBRARY_REPAIR_CATALOG || path.join(workDir, "library-repair-catalog.json");
const mdPath = process.env.LIBRARY_REPAIR_PLAN || path.join(workDir, "library-repair-plan.md");

const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const comparison = JSON.parse(fs.readFileSync(comparisonPath, "utf8"));

const catalogByArtist = new Map(catalog.artists.map((artist) => [artist.name, artist]));
const repairArtists = [];
let missingCount = 0;
let incompleteCount = 0;

for (const artistAudit of comparison.artists) {
  const sourceArtist = catalogByArtist.get(artistAudit.name);
  if (!sourceArtist) continue;
  const sourceAlbums = new Map((sourceArtist.albums || []).map((album) => [album.title, album]));
  const albums = [];

  for (const missing of artistAudit.missingAlbums || []) {
    const album = sourceAlbums.get(missing.title);
    if (!album) continue;
    albums.push({
      ...album,
      repairReason: "missing-local-album",
      localPath: null,
      localTrackCount: 0,
    });
    missingCount += 1;
  }

  for (const mismatch of artistAudit.trackMismatches || []) {
    if (Number(mismatch.localTrackCount || 0) >= Number(mismatch.expectedTrackCount || 0)) {
      continue;
    }
    const album = sourceAlbums.get(mismatch.expectedTitle);
    if (!album) continue;
    albums.push({
      ...album,
      repairReason: "incomplete-local-album",
      localPath: mismatch.localPath,
      localTitle: mismatch.localTitle,
      localTrackCount: mismatch.localTrackCount,
    });
    incompleteCount += 1;
  }

  if (albums.length) {
    repairArtists.push({
      name: sourceArtist.name,
      matchedArtist: sourceArtist.matchedArtist,
      artistBrowseId: sourceArtist.artistBrowseId,
      notes: sourceArtist.notes || [],
      albums,
    });
  }
}

const repair = {
  generatedAt: new Date().toISOString(),
  sourceCatalog: catalogPath,
  sourceComparison: comparisonPath,
  totals: {
    artists: repairArtists.length,
    albums: repairArtists.reduce((sum, artist) => sum + artist.albums.length, 0),
    missingLocalAlbums: missingCount,
    incompleteLocalAlbums: incompleteCount,
  },
  artists: repairArtists,
};

fs.writeFileSync(outPath, JSON.stringify(repair, null, 2) + "\n", "utf8");

let md = `# Library Repair Plan\n\nGenerated: ${repair.generatedAt}\n\n`;
md += `- Artists needing repair/additions: ${repair.totals.artists}\n`;
md += `- Albums to download: ${repair.totals.albums}\n`;
md += `- Missing local albums to add: ${repair.totals.missingLocalAlbums}\n`;
md += `- Incomplete local albums to replace after verification: ${repair.totals.incompleteLocalAlbums}\n\n`;

for (const artist of repairArtists) {
  md += `## ${artist.name}\n\n`;
  for (const album of artist.albums) {
    const reason = album.repairReason === "missing-local-album"
      ? "missing locally"
      : `incomplete locally (${album.localTrackCount}/${album.expectedTrackCount})`;
    md += `- ${album.year || "????"} - ${album.title} (${album.expectedTrackCount || "?"} tracks): ${reason}\n`;
    md += `  - URL: ${album.url}\n`;
    if (album.localPath) md += `  - Existing folder: ${album.localPath}\n`;
  }
  md += "\n";
}

fs.writeFileSync(mdPath, md, "utf8");
console.log(JSON.stringify(repair.totals, null, 2));
