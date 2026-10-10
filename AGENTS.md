# AGENTS.md – Pekkis goes to movies

Instructions and context for AI agents (and humans) working in this repository.

## What this is

"Pekkis goes to movies" gathers the showtimes of all Finnish cinemas under one site.
Users can look for something to watch from two directions:

- **Time and place first**: "what's playing in Tampere tonight after 6 pm?"
- **Film first**: "where and when can I see film X?"

The project is part of the user-centered design course at JAMK.

## Language

**The project language is English**: code, identifiers, comments, commit messages, all documentation (README, AGENTS.md, `docs/`) and discussion with the maintainer. No Finnish identifiers, ever. Finnish appears only as data: cinema and film names, Finnish country and language names in lookup tables, and test fixtures.

## Status (updated 2026-10-10)

- **BioRex and Finnkino adapters are done**, with tests: `pnpm pull` fetches both chains (12 + 17 cinemas) for 7 days into JSON and matches the films to TMDB.
- **Nexxo is done** (2026-10-10): one platform adapter serving 8 independent cinema sites, 15 venues (Kinoset, Kino Aurora, Kino Hirvi, Bio Säde, Kino Marilyn, Kino Olympia, Järvelän Kino, Kino Metso's six towns). Sites are config: [src/providers/nexxo/sites.ts](packages/fetcher/src/providers/nexxo/sites.ts).
- **Next: eTiketti** (server-rendered HTML, many small cinemas), on the same site-config abstraction.
- **Every venue has coordinates** (2026-10-10), for the coming map UI. Chains supply their own; config venues get them by hand from OpenStreetMap (`pnpm venues:locate`). See "Venue coordinates" below.
- **Backlog lives in GitHub issues** (`gh issue list`; labels `provider`, `tmdb`, `backlog`). The repo is public: write issues in English and never put secrets or personal data in them.
- **License: AGPL-3.0-or-later** ([LICENSE](LICENSE)). Everything is published as open source.
- **Direction:** a better version of Leffavuoro (Shady-Dev/kino) in TypeScript, with a precise, typed data model and JSON output. Model: [docs/data-model.md](docs/data-model.md). The source of truth is [packages/model/src/schema.ts](packages/model/src/schema.ts).
- **Fetched data goes into PostgreSQL** (`pnpm ingest`), keeping history: screenings are never deleted. See [docs/database.md](docs/database.md).
- Data collection is written in TypeScript (strict). The frontend stack is still open, so do not add a UI framework until the maintainer decides.
- No design or user research yet. The focus is on technical groundwork.
- Data sources in scope: Finnkino, BioRex, and multi-site platforms (Nexxo done, eTiketti next).

## Commands

```sh
pnpm db:up                   # start Postgres in Docker (localhost:5432); needed by pnpm check too
pnpm db:psql                 # psql shell inside the Postgres container
pnpm migrate                 # apply migrations (--down one step; --test the test database)
pnpm db:types                # regenerate packages/backend/src/db/types.ts after a migration
pnpm pull                    # fetch all providers → data/raw/… + data/normalized/{provider}.json, then match to TMDB
pnpm pull --provider finnkino --days 3 --from 2026-10-10
pnpm pull --provider biorex --venue 13   # --venue takes source ids or slugs and needs exactly one provider
pnpm pull --provider nexxo   # a platform name selects all of its sites (kinoaurora, kinoset, …)
pnpm match                   # re-run TMDB matching only (e.g. after editing aliases)
pnpm venues:locate           # suggest OSM coordinates for venues without them; flag suspicious ones
pnpm venues:locate --address "Sahakatu 2, 32700 Huittinen"   # geocode an address (Nominatim)
pnpm ingest                  # upsert data/normalized/*.json into Postgres
pnpm showtimes odysey        # fuzzy film search → film info + today's screenings everywhere (--date, --links, --min-score)
pnpm test                    # all packages; backend integration tests need the database
pnpm check                   # typecheck + lint + fmt:check + test (run before saying you are done)
pnpm fmt                     # oxfmt rewrites formatting
```

Typical run: `pnpm db:up && pnpm migrate && pnpm pull && pnpm ingest`.

**Routine:** `pnpm pull && pnpm ingest` is run **manually, about once a day**, on the maintainer's laptop (no scheduler; Finnkino needs a visible Chrome). Gaps between runs are normal. Programmes change most on **Tuesday and Wednesday** (Finnkino runs a large batch update then); Finnish programme weeks run Friday–Thursday, so next week's shows usually appear midweek.

- **`pnpm fetch` is a built-in pnpm command.** That is why the fetch script is called `pull`.
- **Finnkino opens a visible Chrome window** for a few seconds when its 12-hour token needs renewing (about twice a day; cached in `data/cache/finnkino-token.json`). It needs Google Chrome installed and cannot run in CI. If one provider fails, the others still run and `pull` exits non-zero.
- **`.env`** (gitignored) is loaded by Node's own `--env-file-if-exists=.env` flag. **No dotenv.**
  - Variables are validated with Zod in [src/lib/env.ts](packages/fetcher/src/lib/env.ts) (`loadEnv()`), the only place that reads `process.env`.
  - `TMDB_APIKEY` (required): TMDB v4 read access token, used as a Bearer token. Never print it.
  - `CONTACT` (optional): URL or email added to the User-Agent. Never hard-code anyone's contact details.
  - `DATABASE_URL`, `TEST_DATABASE_URL`: the Compose Postgres (local, non-secret defaults in `.env.example`). Validated in `packages/backend/src/lib/env.ts`.
  - [.env.example](.env.example) lists the variables with empty values. Never put real values in it.

## Layout

A pnpm workspace. Shared tooling (TypeScript, oxlint, oxfmt, vitest) and settings live at the root; each package declares its own runtime dependencies. Root scripts delegate to packages (`pnpm pull` → `@pgtm/fetcher`), and `pnpm check` covers all of them.

```
package.json, pnpm-workspace.yaml, tsconfig.base.json   workspace root (packages extend tsconfig.base.json)
compose.yaml, docker/          local services (PostgreSQL 18)
.env, data/                    shared by all packages, gitignored
docs/                          project documentation (database: docs/database.md)
vendor/leffavuoro/             reference copy of Leffavuoro's code (AGPL), from our fork pekkis/kino;
                               not built, linted or formatted. See vendor/leffavuoro/UPSTREAM.md
scripts/vendor-leffavuoro.ts   refreshes it (`pnpm vendor:leffavuoro`)
packages/model/                @pgtm/model: the domain model (Zod schemas + types). Source-only, no build:
                               exports src/index.ts; Node 24, vitest and Vite consume TS directly
packages/fetcher/              @pgtm/fetcher: fetching, normalizing, TMDB matching → JSON
  src/lib/                     env, paths, http (ky + p-queue, per-host pacing), time, lang, cache
  src/providers/<id>/raw.ts    schemas of the source's raw responses (looseObject: only the fields we read)
  src/providers/<id>/fetch.ts  I/O only → raw snapshot
  src/providers/<id>/parse.ts  pure function: raw snapshot → ProviderBatch
  src/providers/finnkino/token.ts  Finnkino token via headed Chrome (Playwright), cached
  src/providers/adapter.ts     Adapter type (id + platform + pull), restrictToVenues
  src/providers/sites.ts       shared base for multi-site platforms: SiteBase, SiteVenue, defineSites
  src/providers/<platform>/sites.ts  the platform's site list (config, not code)
  src/providers/registry.ts    list of adapters (one per site for platforms); the CLI runs them
  src/tmdb/                    TMDB client (cached), raw schemas, toFilm (pure)
  src/geo/                     geo.ts (FinnishGeo, GeoSource, distance), osm.ts (Overpass), nominatim.ts, match.ts (pure)
  src/providers/overrides.ts   venue-overrides.json applied to every batch; warns about venues without geo
  src/matching/                TMDB matching: score.ts (pure scoring), match.ts, catalog.ts (films.json)
  src/cli/fetch.ts, match.ts   CLIs (`pnpm pull`, `pnpm match`)
  config/tmdb-aliases.json     hand-maintained aliases, listing id → TMDB id (committed)
  config/venue-overrides.json  hand-maintained fixes to chain venues (coordinates, addresses) (committed)
  test/                        tests mirror src; test/fixtures/<id>/ trimmed from real responses
packages/backend/              @pgtm/backend: PostgreSQL (Kysely), migrations, ingest; later the API
  migrations/                  Kysely migrations, plain .ts, append-only
  src/db/                      createDb (CamelCasePlugin), migrator, types.ts (GENERATED, do not edit)
  src/ingest/                  rows.ts (pure model → row mapping), ingest.ts (upserts, history)
  src/search/                  showtimes.ts (pg_trgm fuzzy film search, screenings), format.ts (pure text output)
  src/cli/                     migrate, ingest, db-types, showtimes
  test/                        unit tests + integration tests against TEST_DATABASE_URL
```

New packages go under `packages/<name>` with the `@pgtm/` scope, `"private": true`, and a `tsconfig.json` that extends `../../tsconfig.base.json`.

**Adding an adapter:**

1. Profile real data before writing the parser. Record the values you find in `docs/data-sources.md`.
2. Write `raw.ts`, `fetch.ts` and `parse.ts`.
3. Build fixtures that cover the different cases.
4. Write the tests.
5. Add it to `src/providers/registry.ts`.

**Multi-site platforms (Nexxo, eTiketti, …): a site is data, not code.**

- One adapter per _site_ (one provider id, one `data/normalized/{site}.json`), generated from the platform's `sites.ts`. `--provider <platform>` runs them all.
- Everything that differs between sites is a field of the site's config, validated by Zod (`defineSites` also rejects duplicate providers and venue slugs). Fixing a breakage or adding a cinema is an edit to `sites.ts`, never an `if (site === "x")` in the parser.
- **Quirks** are named, documented options with platform defaults that a site may override (Nexxo: `showTypes`, `titlePrefixes`, `apiBase`, per-venue `roomIds`/`page`). Add a new quirk as a new optional field with a doc comment, a default, and a test.
- Every site has `verifiedAt` (when someone last checked it against the live site, as a visitor would) and optional `notes` (why a quirk is set). Update `verifiedAt` when you re-check.
- Parsers report what the config does not explain (e.g. Nexxo's `unclaimed-room`: a room no venue owns) as warnings instead of guessing. A warning in `pnpm pull` output is a to-do for `sites.ts`.
- Venue slugs become ids (`{site}:venue:{slug}`): never rename one, or its history is orphaned.

## Tools and libraries

- **pnpm 12** (`packageManager` and `devEngines` in package.json). Settings live in [pnpm-workspace.yaml](pnpm-workspace.yaml), not in `.npmrc`:
  - `minimumReleaseAge`: 1 day
  - `trustPolicy: no-downgrade`
  - `blockExoticSubdeps`
  - `strictDepBuilds`
  - `allowBuilds`: empty
  - `engineStrict`

  If a new dependency needs a build script, add it to `allowBuilds` with a reason.

- **No npm or npx**: `devEngines` blocks npm, so use `pnpm exec <bin>`. Add a runtime dependency to its package (`pnpm --filter @pgtm/fetcher add <pkg>`), shared dev tooling to the root (`pnpm add -D -w <pkg>`). Node 24 runs `.ts` files directly, so there is no build step. Use erasable TS syntax only: no `enum`, `namespace` or parameter properties.
- **TypeScript** (strict) for type checking only (`tsc`, `noEmit`), per package via `pnpm -r typecheck`.
- **oxlint** for linting and **oxfmt** for formatting. **No** ESLint or Prettier.
- **vitest** for tests.
- Runtime libraries:
  - `ky`: HTTP
  - `zod` v4: schemas, types and JSON Schema
  - `date-fns` + `@date-fns/tz`: time zones (Europe/Helsinki)
  - `p-queue`: request pacing
- `playwright`: only for the Finnkino token, driving the installed Chrome (`channel: "chrome"`, no bundled browser download).
- `kysely` + `pg` (backend): typed SQL; `kysely-codegen` generates the database types from the migrated schema.
- Not yet: HTML parser (coming with eTiketti), caching or search services.

## Data sources: summary

Detailed findings, sample payloads and references: [docs/data-sources.md](docs/data-sources.md).

| Source          | Method                                                                               | Auth                                                                 | Status                                                         |
| --------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | -------------------------------------------------------------- |
| BioRex          | Unofficial JSON (`webshop.biorex.fi/webservices/...`)                                | None                                                                 | ✅ Verified working                                            |
| Finnkino        | Vista OCAPI JSON (`digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1/...`)           | Public 12 h JWT from the front page; headed Chrome passes Cloudflare | ✅ Working, needs a desktop with Chrome                        |
| Finnkino (old)  | XML API `finnkino.fi/xml/...`                                                        | –                                                                    | ❌ Retired (2025–2026)                                         |
| Nexxo (8 sites) | Nexxo Scope WordPress plugin JSON (`/wp-content/plugins/nexxo-scope/public_api.php`) | None                                                                 | ✅ Working; small hosts answer 403 if paced faster than ~2.5 s |
| eTiketti        | Server-rendered HTML on each cinema's site                                           | None                                                                 | ⏳ Next                                                        |

None of these needs HTML crawling; eTiketti will (it has no public API).

**Prior work:** [Leffavuoro / Shady-Dev/kino](https://github.com/Shady-Dev/kino) (AGPL-3.0) already covers about 230 cinemas. A code-only copy lives in [vendor/leffavuoro/](vendor/leffavuoro/UPSTREAM.md) (from our fork [pekkis/kino](https://github.com/pekkis/kino); the maintainer keeps the fork in sync, then `pnpm vendor:leffavuoro` refreshes the copy). **Read it there first** when adding a platform: `scripts/providers/<platform>.py` and `docs/research/`. Since we are AGPL too, its adapters **may be ported**. Mark the origin at the top of a ported file, e.g. `// Ported from Shady-Dev/kino scripts/providers/etiketti.py (AGPL-3.0)`. Its published **data** (`data/*.json`, posters) is not used as a source, because the data is not covered by its license. See [docs/data-sources.md](docs/data-sources.md#prior-work-leffavuoro-shady-devkino).

### TMDB

- **Posters, synopses and trailers come only from TMDB, never from cinemas.** A film is linked only when the match is certain. Otherwise it stays unmatched and is fixed with an alias. Rules: [docs/data-model.md](docs/data-model.md#tmdb-matching).
- Unmatched films are listed in the `pnpm match` output and in the `unmatched` list of `films.json`, with candidates. **Verify an alias on TMDB (runtime, countries, year) before adding it**, and write the reasoning in its `note`.
- Do not loosen the matching rules without a regression test (`test/matching/score.test.ts`).
- Event cinema (`kind: "event"`: operas, concerts) is never reported as unmatched; do not spend effort aliasing it.
- TMDB's terms require attribution (logo and notice) in the UI.

### Venue coordinates

- **Every venue needs `geo`** (the map UI depends on it). `pnpm pull` warns `venue-without-geo` otherwise; a test fails for any configured Nexxo venue without one.
- Chains (Finnkino, BioRex) supply coordinates in their APIs. Fix wrong ones in `config/venue-overrides.json`, with a `note` saying how it was checked.
- Config venues (Nexxo, eTiketti, …) carry `geo`, `geoSource`, `address` and `postalCode` in their `sites.ts`. Workflow: `pnpm venues:locate` suggests OSM cinemas (and flags existing points more than 300 m from any OSM cinema); halls OSM does not list as cinemas are geocoded with `--address`, using the address on the cinema's own page. **Check every point on openstreetmap.org before pasting it.**
- `geoSource` records where a point came from: `osm:node/…`, `nominatim`, `nls` or `manual`.
- **Never take coordinates from Google Maps**: its terms forbid storing them, even copied by hand.
- OSM data is ODbL: the UI must credit "© OpenStreetMap contributors". Overpass and Nominatim are shared community services: requests are cached (a week and a month), Nominatim is paced at one request per second.
- Postgres needs no geo extension: about 300 venues, `lat`/`lon` columns, bounding-box filters and haversine in SQL. Reconsider PostGIS only for polygons or routing.

### Architecture

- **One adapter per source** (chain, or platform site: BioRex runs on MyCloudCinema, Kino Aurora on Nexxo) → shared model `Venue`, `Auditorium`, `FilmListing`, `Screening`.
- Films from different sources are linked through TMDB (`Film`), since source ids are not shared.
- **Fetch and parse are separate:** parsers are pure functions, tested against recorded responses without network access. The model is defined as Zod schemas. See [docs/data-model.md](docs/data-model.md).
- Source labels the parser does not recognize are not lost: they go into `unmappedLabels`.
- Fetch rarely (e.g. a few times a day) and cache. Do not hammer sources.

## Rules for agents

- **Vendored code:** never edit `vendor/leffavuoro/` by hand (it is overwritten on refresh), and never copy their `data/` (showtimes, posters) into this repo: it is not covered by their license.
- **Database:** migrations are append-only; after adding one, run `pnpm migrate && pnpm db:types` and commit the regenerated `types.ts` (never edit it by hand). Tables plural, columns snake_case; TypeScript stays camelCase via `CamelCasePlugin`. The fetcher stays database-agnostic.

- **User-Agent:** use an identifiable User-Agent with contact details. No residential proxies, fingerprint spoofing or captcha solving. Never call ticket purchase or payment endpoints.
- **Politeness:** when probing external APIs, make few requests and only GETs. Do not try hard to get around Cloudflare.
- **Finnkino:** Cloudflare challenges every non-browser client (even from home) and headless Chrome. Only the token step needs a browser; never try to defeat the check by other means (no fingerprint spoofing, no captcha solving). Do not assume it works in the cloud or CI.
- **Contacting cinemas:** we have not contacted any source and do not need to while this is a course project. **If the service ever goes truly public, we notify every cinema and chain first** (what we read, how often, that every click goes to their own ticket page) and remove any that object. Do not expect API keys from them; the realistic risk is technical breakage (e.g. Cloudflare tightening), not a missing permission.
- **Verified vs. assumed:** always mark separately in the docs what was tested first-hand and what was inferred or read elsewhere.
- **Git workflow:** `main` is protected (ruleset "Protect main", 2026-10-10): no direct pushes, force pushes or deletion, for everyone including admins. Work on a branch, open a pull request (`gh pr create`) and merge it; no approval is required. Run `pnpm check` before opening a PR. Commit only when the maintainer asks.
- **Keep this file up to date:** update `AGENTS.md` when the stack, architecture or data sources change.
