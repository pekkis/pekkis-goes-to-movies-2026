import { parseArgs } from "node:util";
import type { Kysely } from "kysely";
import type { DB } from "../db/types.ts";
import { createDb } from "../db/database.ts";
import { fromCoreLocation, fromIp, geocode, type Located } from "../geo/locate.ts";
import { loadEnv } from "../lib/env.ts";
import {
  parseLatLon,
  parseTime,
  resolveProviders,
  type ScreeningFilter,
} from "../search/filters.ts";
import { formatFilm, formatListing, formatScreenings } from "../search/format.ts";
import {
  DEFAULT_MIN_SCORE,
  filmDetails,
  helsinkiToday,
  listingDetails,
  screeningsFor,
  searchFilms,
} from "../search/showtimes.ts";

const USAGE = `Usage: pnpm showtimes [--movie NAME | NAME] [--date YYYY-MM-DD] [--after HH:MM] [--links]
                      [--provider ID ...] [--near LAT,LON | --address TEXT | --here] [--radius KM]
                      [--min-score 0..1]

With a film: fuzzy-searches films by any title (Finnish, Swedish, English, original, or as
cinemas list them) and prints each match with its screenings.
Without one: every screening that matches the other options, in start order ("what's on").
Default date: today in Helsinki.

  --movie     the film to look for; a plain argument works too (pnpm showtimes odyssey)
  --after     only shows starting at or after this time (shows after midnight are kept)

  --provider  only these providers: ids (finnkino, biorex, kinoaurora, …) or a platform
              (nexxo = every Nexxo cinema). Repeat for several.
  --near      only venues within --radius km (default 25) of a point, e.g. 62.24,25.75
              (a map link's "@62.24,25.75" works too); adds a distance column.
  --address   like --near, from an address or place in Finland ("Hämeenkatu 1, Tampere",
              "Kallio"), geocoded with OpenStreetMap's Nominatim.
  --here      like --near, from this machine's location: CoreLocationCLI on macOS if
              installed (brew install --cask corelocationcli), otherwise your IP address
              via ipinfo.io (city-level, sends your IP to them).

Examples:
  pnpm showtimes --here --after 18:00                  what's on near me tonight
  pnpm showtimes --movie odyssey --near 60.17,24.94 --radius 10 --provider finnkino
  pnpm showtimes odyssey --address "Seminaarinkatu 13, Jyväskylä" --radius 5
  pnpm showtimes odyssey --here`;

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    movie: { type: "string", short: "m" },
    date: { type: "string" },
    after: { type: "string" },
    "min-score": { type: "string", default: String(DEFAULT_MIN_SCORE) },
    links: { type: "boolean", default: false },
    provider: { type: "string", multiple: true },
    near: { type: "string" },
    address: { type: "string" },
    here: { type: "boolean", default: false },
    radius: { type: "string", default: "25" },
    help: { type: "boolean", short: "h" },
  },
});

const term = (values.movie ?? positionals.join(" ")).trim();
const after = values.after === undefined ? undefined : parseTime(values.after);
const minScore = Number(values["min-score"]);
const point = values.near === undefined ? undefined : parseLatLon(values.near);
const radiusKm = Number(values.radius);
if (
  values.help ||
  (values.movie !== undefined && (!term || positionals.length > 0)) ||
  (values.after !== undefined && !after) ||
  Number.isNaN(minScore) ||
  (values.date && !/^\d{4}-\d{2}-\d{2}$/.test(values.date)) ||
  (values.near !== undefined && !point) ||
  [values.near !== undefined, values.address !== undefined, values.here].filter(Boolean).length >
    1 ||
  (values.address !== undefined && !values.address.trim()) ||
  !(radiusKm > 0)
) {
  console.log(USAGE);
  process.exit(values.help ? 0 : 1);
}

/** The point to search around, from --near, --address or --here; undefined for none. */
const locate = async (contact?: string): Promise<Located | undefined> => {
  if (point) return { ...point, label: "the given point", approximate: false };
  if (values.address !== undefined) {
    const found = await geocode(values.address, contact);
    if (!found) throw new Error(`No place found for "${values.address}". Try adding the town.`);
    return found;
  }
  if (values.here) return (await fromCoreLocation()) ?? (await fromIp(contact));
  return undefined;
};

/** Prints the matches; returns the exit code. */
const run = async (db: Kysely<DB>, contact?: string): Promise<number> => {
  const date = values.date ?? (await helsinkiToday(db));
  const filter: ScreeningFilter = {};
  const where: string[] = [];
  if (after) {
    filter.after = after;
    where.push(`from ${after}`);
  }
  if (values.provider) {
    const { ids, unknown, known } = await resolveProviders(db, values.provider);
    if (unknown.length) {
      console.error(`Unknown provider: ${unknown.join(", ")}\nKnown: ${known.join(", ")}`);
      return 1;
    }
    filter.providerIds = ids;
    where.push(`at ${values.provider.join(", ")}`);
  }
  let located: Located | undefined;
  try {
    located = await locate(contact);
  } catch (error) {
    console.error((error as Error).message);
    return 1;
  }
  if (located) {
    const at = `${located.lat.toFixed(5)},${located.lon.toFixed(5)}`;
    console.log(`Searching within ${radiusKm} km of ${at}, from ${located.label}`);
    if (located.approximate) {
      console.log(
        "  Approximate (often only the town, sometimes your ISP's): consider a larger --radius,\n" +
          "  --address, or installing CoreLocationCLI for a precise position.",
      );
    }
    filter.near = { lat: located.lat, lon: located.lon, radiusKm };
    where.push(`within ${radiusKm} km`);
  }
  const scope = where.length ? ` ${where.join(", ")}` : "";

  if (!term) {
    const screenings = await screeningsFor(db, undefined, date, filter);
    const films = new Set(screenings.map((s) => s.film)).size;
    console.log(
      `\n  ${screenings.length} screenings of ${films} films on ${date}${scope}\n` +
        formatScreenings(screenings, values.links, { withFilm: true }),
    );
    return 0;
  }

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
    const screenings = await screeningsFor(db, hit, date, filter);
    console.log(
      `\n${header}\n\n  ${screenings.length} screenings on ${date}${scope}\n${formatScreenings(screenings, values.links)}`,
    );
  }
  return 0;
};

const env = loadEnv();
const db = createDb(env.DATABASE_URL);
try {
  process.exitCode = await run(db, env.CONTACT);
} finally {
  await db.destroy();
}
