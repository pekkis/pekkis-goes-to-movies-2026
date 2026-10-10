import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { ProviderBatch } from "@pgtm/model";
import {
  candidatesFor,
  geoSnippet,
  suspiciousCoordinates,
  type LocatableVenue,
} from "../geo/match.ts";
import { geocode } from "../geo/nominatim.ts";
import { fetchOsmCinemas } from "../geo/osm.ts";
import { createDiskCache } from "../lib/cache.ts";
import { loadEnv } from "../lib/env.ts";
import { createHttpClient } from "../lib/http.ts";
import { DATA_DIR } from "../lib/paths.ts";

const USAGE = `Usage: pnpm venues:locate [--dir DIR] [--max-meters N]
       pnpm venues:locate --address "Sahakatu 2, 32700 Huittinen" [--address …]

Suggests coordinates from OpenStreetMap for venues without them, and flags venues whose
coordinates are far from any OSM cinema. Reads data/normalized/*.json, so run pnpm pull
after editing sites.ts. Prints suggestions only: check each on openstreetmap.org, then
paste it into the platform's sites.ts (or config/venue-overrides.json for chains).
--address geocodes addresses with Nominatim instead (for halls OSM does not list as cinemas).
Map data © OpenStreetMap contributors (ODbL).`;

const { values } = parseArgs({
  options: {
    dir: { type: "string", default: join(DATA_DIR, "normalized") },
    "max-meters": { type: "string", default: "300" },
    address: { type: "string", multiple: true },
    help: { type: "boolean", short: "h" },
  },
});
if (values.help) {
  console.log(USAGE);
  process.exit(0);
}

const env = loadEnv();
const http = createHttpClient({
  timeoutMs: 120_000,
  // Nominatim allows one request per second.
  intervalMs: 1_100,
  ...(env.CONTACT && { contact: env.CONTACT }),
});
const cache = createDiskCache(join(DATA_DIR, "cache", "osm"));

if (values.address) {
  for (const address of values.address) {
    console.log(`\n${address}`);
    const places = await geocode(http, cache, address);
    if (places.length === 0)
      console.log("  not found: try without the hall name, or place it by hand");
    places.forEach((place, i) => {
      console.log(`  ${i + 1}. ${place.label}${place.url ? `  ${place.url}` : ""}`);
      console.log(`     ${geoSnippet(place, "nominatim")}`);
    });
  }
  console.log("\nGeocoding © OpenStreetMap contributors (ODbL), via Nominatim.");
  process.exit(0);
}

const venues: LocatableVenue[] = [];
for (const file of (await readdir(values.dir)).filter((f) => f.endsWith(".json")).sort()) {
  if (file === "films.json") continue;
  const batch = ProviderBatch.safeParse(JSON.parse(await readFile(join(values.dir, file), "utf8")));
  if (batch.success) venues.push(...batch.data.venues);
  else console.warn(`skipping ${file}: not a provider batch`);
}

const cinemas = await fetchOsmCinemas(http, cache);
console.log(`${venues.length} venues, ${cinemas.length} OSM cinemas in Finland\n`);

const missing = venues.filter((v) => !v.geo);
console.log(`Without coordinates: ${missing.length}`);
for (const venue of missing) {
  console.log(`\n  ${venue.id}  ${venue.name}, ${venue.city}`);
  const candidates = candidatesFor(venue, cinemas);
  if (candidates.length === 0) {
    console.log("    no OSM candidate: geocode its address (nominatim, nls) or place it by hand");
  }
  candidates.forEach(({ cinema, nameScore, sameCity }, i) => {
    const where = [cinema.address, cinema.postalCode, cinema.city].filter(Boolean).join(", ");
    console.log(
      `    ${i + 1}. ${cinema.name ?? "(no name)"}${where ? ` (${where})` : ""}  ` +
        `name ${nameScore.toFixed(2)}${sameCity ? ", same city" : ""}  ${cinema.url}`,
    );
    console.log(`       ${geoSnippet(cinema, cinema.ref)}`);
  });
}

const suspects = suspiciousCoordinates(venues, cinemas, Number(values["max-meters"]));
console.log(`\nFarther than ${values["max-meters"]} m from any OSM cinema: ${suspects.length}`);
for (const { venue, nearest, distance } of suspects) {
  console.log(
    `  ${venue.id}  ${venue.name}, ${venue.city}: nearest OSM cinema ` +
      `${nearest?.name ?? "?"}${nearest?.address ? ` (${nearest.address}${nearest.city ? `, ${nearest.city}` : ""})` : ""} ` +
      `${(distance / 1000).toFixed(1)} km  https://www.openstreetmap.org/?mlat=${venue.geo!.lat}&mlon=${venue.geo!.lon}#map=17/${venue.geo!.lat}/${venue.geo!.lon}`,
  );
}
