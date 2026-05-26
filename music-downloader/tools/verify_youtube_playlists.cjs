const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const workDir = process.env.MUSIC_WORK_DIR || path.join(root, "music-download-work");
const rawPath = process.env.CATALOG_PATH || path.join(workDir, "ytmusic-catalog-raw.json");
const verificationPath = path.join(workDir, "playlist-verification.json");
const manifestPath = process.env.MUSIC_MANIFEST_PATH || path.join(root, "music-download-manifest.json");
const planPath = process.env.MUSIC_PLAN_PATH || path.join(root, "music-download-plan.md");

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/\b(remaster(?:ed)?|expanded|deluxe|edition|explicit|clean|mono|stereo|live|version|mix)\b/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function titleMatches(expected, actual) {
  const e = normalize(expected);
  const a = normalize(actual);
  if (!e || !a) return false;
  const eBase = normalize(String(expected).split("(")[0]);
  const aBase = normalize(String(actual).split("(")[0]);
  return e === a || a.includes(e) || e.includes(a) || (!!eBase && !!aBase && (eBase === aBase || eBase.includes(aBase) || aBase.includes(eBase)));
}

async function extractPlaylist(page, expectedCount) {
  await page.waitForTimeout(2500);
  let lastCount = -1;
  let stable = 0;
  for (let i = 0; i < 80; i += 1) {
    const count = await page.locator("ytd-playlist-video-renderer").count().catch(() => 0);
    if (count >= expectedCount) break;
    if (count === lastCount) {
      stable += 1;
    } else {
      stable = 0;
      lastCount = count;
    }
    if (stable >= 6) break;
    await page.mouse.wheel(0, 1400);
    await page.waitForTimeout(250);
  }

  return page.evaluate(() => {
    const rows = [...document.querySelectorAll("ytd-playlist-video-renderer")];
    const tracks = rows.map((row, index) => {
      const titleEl = row.querySelector("a#video-title");
      const bylineEl = row.querySelector("#byline a, #byline yt-formatted-string");
      const durationEl = row.querySelector("ytd-thumbnail-overlay-time-status-renderer #text");
      return {
        number: index + 1,
        title: titleEl ? titleEl.textContent.trim() : "",
        href: titleEl ? titleEl.href : "",
        byline: bylineEl ? bylineEl.textContent.trim() : "",
        duration: durationEl ? durationEl.textContent.trim() : "",
        text: row.innerText,
      };
    });
    const headerText = document.querySelector("ytd-playlist-header-renderer")?.innerText || "";
    return {
      pageTitle: document.title,
      headerText,
      tracks,
      bodyStart: document.body.innerText.slice(0, 1200),
    };
  });
}

async function verifyAlbum(page, artist, album) {
  const expectedTracks = album.expectedTracks || [];
  const expectedTitles = expectedTracks.map((track) => track.title).filter(Boolean);
  const expectedCount = Number(expectedTitles.length || album.expectedTrackCount || 0);
  const result = {
    artist: artist.name,
    title: album.title,
    year: album.year,
    url: album.url,
    expectedTrackCount: expectedCount,
    actualTrackCount: 0,
    matchedTrackCount: 0,
    missingTracks: [],
    extraTracks: [],
    pageTitle: "",
    headerText: "",
    verified: false,
    note: "",
  };

  if (!album.url) {
    result.note = "No playlist URL.";
    return result;
  }

  try {
    await page.goto(album.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    const rendered = await extractPlaylist(page, expectedCount);
    const actualTitles = rendered.tracks.map((track) => track.title).filter(Boolean);
    result.actualTrackCount = actualTitles.length;
    result.pageTitle = rendered.pageTitle;
    result.headerText = rendered.headerText.split("\n").slice(0, 8).join(" | ");

    const usedActual = new Set();
    for (const expected of expectedTitles) {
      const matchIndex = actualTitles.findIndex((actual, index) => !usedActual.has(index) && titleMatches(expected, actual));
      if (matchIndex >= 0) {
        usedActual.add(matchIndex);
      } else {
        result.missingTracks.push(expected);
      }
    }
    result.extraTracks = actualTitles.filter((_, index) => !usedActual.has(index));
    result.matchedTrackCount = usedActual.size;

    const countOk = result.actualTrackCount === expectedCount;
    const tracksOk = result.missingTracks.length === 0;
    const albumTitleOk = normalize(rendered.pageTitle).includes(normalize(album.title)) ||
      normalize(rendered.headerText).includes(normalize(album.title));

    result.verified = countOk && tracksOk && albumTitleOk;
    result.note = result.verified
      ? "Playwright-rendered YouTube playlist matched expected title, track count, and track titles."
      : `Mismatch: titleOk=${albumTitleOk}; countOk=${countOk}; missing=${result.missingTracks.length}; extra=${result.extraTracks.length}.`;
  } catch (error) {
    result.note = `Playwright verification failed: ${error.message}`;
  }

  return result;
}

function buildOutputs(catalog, verificationsByUrl) {
  const manifest = { artists: [] };
  const md = [
    "# Music Download Plan",
    "",
    `Generated: ${new Date().toISOString()}`,
    "",
    "Scope: official YouTube Music album-type playlist entries collected from the artists in `New-Artists.md`, excluding singles and requiring Playwright verification before download.",
    "",
  ];

  for (const artist of catalog.artists) {
    const artistEntry = { name: artist.name, aliases: [], albums: [] };
    md.push(`## ${artist.name}`);
    md.push("");
    if (artist.matchedArtist) md.push(`Matched YouTube Music artist/source: ${artist.matchedArtist}`);
    if (artist.notes?.length) md.push(...artist.notes.map((note) => `Note: ${note}`));
    md.push("");

    for (const album of artist.albums || []) {
      const verification = verificationsByUrl.get(album.url);
      const verified = Boolean(verification?.verified);
      const note = verification?.note || "Not verified.";
      artistEntry.albums.push({
        title: album.title,
        year: album.year,
        type: album.type || "Album",
        url: album.url,
        expectedTrackCount: (album.expectedTracks || []).filter((track) => track.title).length || album.expectedTrackCount,
        verified,
        verificationNote: note,
      });
      md.push(`- ${album.year || "????"} - ${album.title} (${album.expectedTrackCount} tracks)`);
      md.push(`  - URL: ${album.url}`);
      md.push(`  - Verified: ${verified ? "yes" : "no"}; ${note}`);
    }
    manifest.artists.push(artistEntry);
    md.push("");
  }

  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
  fs.writeFileSync(planPath, md.join("\n"), "utf8");
}

async function main() {
  const catalog = JSON.parse(fs.readFileSync(rawPath, "utf8"));
  let albums = catalog.artists.flatMap((artist) => (artist.albums || []).map((album) => ({ artist, album })));
  const start = Number(process.env.VERIFY_START || 0);
  const limit = Number(process.env.VERIFY_LIMIT || 0);
  if (start || limit) {
    albums = albums.slice(start, limit ? start + limit : undefined);
  }
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1365, height: 900 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  });
  const verifications = [];

  for (let i = 0; i < albums.length; i += 1) {
    const { artist, album } = albums[i];
    console.log(`[${i + 1}/${albums.length}] ${artist.name} - ${album.title}`);
    const result = await verifyAlbum(page, artist, album);
    verifications.push(result);
    fs.writeFileSync(verificationPath, JSON.stringify({ generatedAt: new Date().toISOString(), verifications }, null, 2), "utf8");
  }

  await browser.close();
  const byUrl = new Map(verifications.map((verification) => [verification.url, verification]));
  buildOutputs(catalog, byUrl);
  const verified = verifications.filter((verification) => verification.verified).length;
  console.log(`Verified ${verified}/${verifications.length} playlists.`);
  if (verified !== verifications.length) {
    process.exitCode = 2;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
