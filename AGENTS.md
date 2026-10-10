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

## Status (updated 2026-10-09)

- **BioRex and Finnkino adapters are done**, with tests: `pnpm pull` fetches both chains (12 + 17 cinemas) for 7 days into JSON and matches the films to TMDB.
- **License: AGPL-3.0-or-later** ([LICENSE](LICENSE)). Everything is published as open source.
- **Direction:** a better version of Leffavuoro (Shady-Dev/kino) in TypeScript, with a precise, typed data model and JSON output. Model: [docs/data-model.md](docs/data-model.md). The source of truth is [src/model/schema.ts](packages/fetcher/src/model/schema.ts).
- **Fetched data goes into PostgreSQL** (`pnpm ingest`), keeping history: screenings are never deleted. See [docs/database.md](docs/database.md).
- Data collection is written in TypeScript (strict). The frontend stack is still open, so do not add a UI framework until the maintainer decides.
- No design or user research yet. The focus is on technical groundwork.
- Data sources in scope for now: **only Finnkino and BioRex.** Other chains and independent cinemas come later.

## Commands

```sh
pnpm db:up                   # start Postgres in Docker (localhost:5432); needed by pnpm check too
pnpm db:psql                 # psql shell inside the Postgres container
pnpm migrate                 # apply migrations (--down one step; --test the test database)
pnpm db:types                # regenerate packages/backend/src/db/types.ts after a migration
pnpm pull                    # fetch all providers → data/raw/… + data/normalized/{provider}.json, then match to TMDB
pnpm pull --provider finnkino --days 3 --from 2026-10-10
pnpm pull --provider biorex --venue 13   # --venue takes source ids and needs exactly one --provider
pnpm match                   # re-run TMDB matching only (e.g. after editing aliases)
pnpm ingest                  # upsert data/normalized/*.json into Postgres
pnpm showtimes odysey        # fuzzy film search → film info + today's screenings everywhere (--date, --links, --min-score)
pnpm test                    # all packages; backend integration tests need the database
pnpm check                   # typecheck + lint + fmt:check + test (run before saying you are done)
pnpm fmt                     # oxfmt rewrites formatting
```

Typical run: `pnpm db:up && pnpm migrate && pnpm pull && pnpm ingest`.

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
packages/model/                @pgtm/model: the domain model (Zod schemas + types). Source-only, no build:
                               exports src/index.ts; Node 24, vitest and Vite consume TS directly
packages/fetcher/              @pgtm/fetcher: fetching, normalizing, TMDB matching → JSON
  src/lib/                     env, paths, http (ky + p-queue, per-host pacing), time, lang, cache
  src/providers/<id>/raw.ts    schemas of the source's raw responses (looseObject: only the fields we read)
  src/providers/<id>/fetch.ts  I/O only → raw snapshot
  src/providers/<id>/parse.ts  pure function: raw snapshot → ProviderBatch
  src/providers/finnkino/token.ts  Finnkino token via headed Chrome (Playwright), cached
  src/providers/registry.ts    list of adapters; the CLI runs them
  src/tmdb/                    TMDB client (cached), raw schemas, toFilm (pure)
  src/matching/                TMDB matching: score.ts (pure scoring), match.ts, catalog.ts (films.json)
  src/cli/fetch.ts, match.ts   CLIs (`pnpm pull`, `pnpm match`)
  config/tmdb-aliases.json     hand-maintained aliases, listing id → TMDB id (committed)
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
- Not yet: HTML parser, caching or search services. Data is stored **as JSON files on disk for now** and **in PostgreSQL later**.

## Data sources: summary

Detailed findings, sample payloads and references: [docs/data-sources.md](docs/data-sources.md).

| Source         | Method                                                                     | Auth                                                                 | Status                                  |
| -------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------- |
| BioRex         | Unofficial JSON (`webshop.biorex.fi/webservices/...`)                      | None                                                                 | ✅ Verified working                     |
| Finnkino       | Vista OCAPI JSON (`digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1/...`) | Public 12 h JWT from the front page; headed Chrome passes Cloudflare | ✅ Working, needs a desktop with Chrome |
| Finnkino (old) | XML API `finnkino.fi/xml/...`                                              | –                                                                    | ❌ Retired (2025–2026)                  |

Neither needs classic HTML crawling.

**Prior work:** [Leffavuoro / Shady-Dev/kino](https://github.com/Shady-Dev/kino) (AGPL-3.0) already covers about 230 cinemas. Since we are AGPL too, its adapters **may be ported**. Mark the origin at the top of a ported file, e.g. `// Ported from Shady-Dev/kino scripts/providers/etiketti.py (AGPL-3.0)`. Its published **data** (`data/*.json`, posters) is not used as a source, because the data is not covered by its license. See [docs/data-sources.md](docs/data-sources.md#prior-work-leffavuoro-shady-devkino).

### TMDB

- **Posters, synopses and trailers come only from TMDB, never from cinemas.** A film is linked only when the match is certain. Otherwise it stays unmatched and is fixed with an alias. Rules: [docs/data-model.md](docs/data-model.md#tmdb-matching).
- Unmatched films are listed in the `pnpm match` output and in the `unmatched` list of `films.json`, with candidates. **Verify an alias on TMDB (runtime, countries, year) before adding it**, and write the reasoning in its `note`.
- Do not loosen the matching rules without a regression test (`test/matching/score.test.ts`).
- Event cinema (`kind: "event"`: operas, concerts) is never reported as unmatched; do not spend effort aliasing it.
- TMDB's terms require attribution (logo and notice) in the UI.

### Architecture

- **One adapter per source** (chain, or platform: BioRex runs on MyCloudCinema) → shared model `Venue`, `Auditorium`, `FilmListing`, `Screening`.
- Films from different sources are linked through TMDB (`Film`), since source ids are not shared.
- **Fetch and parse are separate:** parsers are pure functions, tested against recorded responses without network access. The model is defined as Zod schemas. See [docs/data-model.md](docs/data-model.md).
- Source labels the parser does not recognize are not lost: they go into `unmappedLabels`.
- Fetch rarely (e.g. a few times a day) and cache. Do not hammer sources.

## Rules for agents

- **Database:** migrations are append-only; after adding one, run `pnpm migrate && pnpm db:types` and commit the regenerated `types.ts` (never edit it by hand). Tables plural, columns snake_case; TypeScript stays camelCase via `CamelCasePlugin`. The fetcher stays database-agnostic.

- **User-Agent:** use an identifiable User-Agent with contact details. No residential proxies, fingerprint spoofing or captcha solving. Never call ticket purchase or payment endpoints.
- **Politeness:** when probing external APIs, make few requests and only GETs. Do not try hard to get around Cloudflare.
- **Finnkino:** Cloudflare challenges every non-browser client (even from home) and headless Chrome. Only the token step needs a browser; never try to defeat the check by other means (no fingerprint spoofing, no captcha solving). Do not assume it works in the cloud or CI.
- **Contacting cinemas:** we have not contacted any source and do not need to while this is a course project. **If the service ever goes truly public, we notify every cinema and chain first** (what we read, how often, that every click goes to their own ticket page) and remove any that object. Do not expect API keys from them; the realistic risk is technical breakage (e.g. Cloudflare tightening), not a missing permission.
- **Verified vs. assumed:** always mark separately in the docs what was tested first-hand and what was inferred or read elsewhere.
- **Keep this file up to date:** update `AGENTS.md` when the stack, architecture or data sources change.
