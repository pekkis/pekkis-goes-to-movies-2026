import { parseArgs } from "node:util";
import { createDb } from "../db/database.ts";
import { loadEnv } from "../lib/env.ts";
import { formatFilm, formatListing, formatScreenings } from "../search/format.ts";
import {
  DEFAULT_MIN_SCORE,
  filmDetails,
  helsinkiToday,
  listingDetails,
  screeningsFor,
  searchFilms,
} from "../search/showtimes.ts";

const USAGE = `Usage: pnpm showtimes <film name> [--date YYYY-MM-DD] [--min-score 0..1] [--links]

Fuzzy-searches films by any title (Finnish, Swedish, English, original, or as cinemas list them)
and prints each match with its screenings in all venues. Default date: today in Helsinki.`;

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    date: { type: "string" },
    "min-score": { type: "string", default: String(DEFAULT_MIN_SCORE) },
    links: { type: "boolean", default: false },
    help: { type: "boolean", short: "h" },
  },
});

const term = positionals.join(" ").trim();
const minScore = Number(values["min-score"]);
if (
  values.help ||
  !term ||
  Number.isNaN(minScore) ||
  (values.date && !/^\d{4}-\d{2}-\d{2}$/.test(values.date))
) {
  console.log(USAGE);
  process.exit(values.help ? 0 : 1);
}

const db = createDb(loadEnv().DATABASE_URL);
try {
  const date = values.date ?? (await helsinkiToday(db));
  const hits = await searchFilms(db, term, { minScore });
  if (hits.length === 0) {
    console.log(`No films match "${term}". Try a shorter name or --min-score 0.3.`);
  }
  for (const hit of hits) {
    let header: string | undefined;
    if (hit.kind === "film") {
      const film = await filmDetails(db, hit.id);
      if (film) header = formatFilm(film, hit.score);
    } else {
      const listing = await listingDetails(db, hit.id);
      if (listing) header = formatListing(listing, hit.score);
    }
    if (!header) continue;
    const screenings = await screeningsFor(db, hit, date);
    console.log(
      `\n${header}\n\n  ${screenings.length} screenings on ${date}\n${formatScreenings(screenings, values.links)}`,
    );
  }
} finally {
  await db.destroy();
}
