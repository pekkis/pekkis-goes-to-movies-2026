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

- **The BioRex adapter is done**, with tests: `pnpm pull` fetches all 12 cinemas for 7 days into JSON and matches the films to TMDB. Finnkino is not done yet.
- **License: AGPL-3.0-or-later** ([LICENSE](LICENSE)). Everything is published as open source.
- **Direction:** a better version of Leffavuoro (Shady-Dev/kino) in TypeScript, with a precise, typed data model and JSON output. Model: [docs/data-model.md](docs/data-model.md). The source of truth is [src/model/schema.ts](src/model/schema.ts).
- Data collection is written in TypeScript (strict). The frontend stack is still open, so do not add a UI framework until the maintainer decides.
- No design or user research yet. The focus is on technical groundwork.
- Data sources in scope for now: **only Finnkino and BioRex.** Other chains and independent cinemas come later.

## Commands

```sh
pnpm pull                    # fetch BioRex → data/raw/… + data/normalized/biorex.json, then match to TMDB
pnpm match                   # re-run TMDB matching only (e.g. after editing aliases)
pnpm pull --days 3 --cinema 13 --from 2026-10-10
pnpm test                    # vitest, no network
pnpm check                   # typecheck + lint + fmt:check + test (run before saying you are done)
pnpm fmt                     # oxfmt rewrites formatting
```

- **`pnpm fetch` is a built-in pnpm command.** That is why the fetch script is called `pull`.
- **`.env`** (gitignored) is loaded by Node's own `--env-file-if-exists=.env` flag. **No dotenv.**
  - Variables are validated with Zod in [src/lib/env.ts](src/lib/env.ts) (`loadEnv()`), the only place that reads `process.env`.
  - `TMDB_APIKEY` (required): TMDB v4 read access token, used as a Bearer token. Never print it.
  - `CONTACT` (optional): URL or email added to the User-Agent. Never hard-code anyone's contact details.
  - [.env.example](.env.example) lists the variables with empty values. Never put real values in it.

## Layout

```
src/model/schema.ts           domain model (Zod) — all types come from here
src/lib/                      env, http (ky + p-queue, per-host pacing), time (Helsinki times), lang (ISO 639-1), cache
src/providers/<id>/raw.ts     schemas of the source's raw responses (looseObject: only the fields we read)
src/providers/<id>/fetch.ts   I/O only → raw snapshot
src/providers/<id>/parse.ts   pure function: raw snapshot → ProviderBatch
src/tmdb/                     TMDB client (cached), raw schemas, toFilm (pure)
src/matching/                 TMDB matching: score.ts (pure scoring), match.ts, catalog.ts (films.json)
config/tmdb-aliases.json      hand-maintained aliases, listing id → TMDB id (committed)
src/cli/fetch.ts, match.ts    CLIs (`pnpm pull`, `pnpm match`)
test/fixtures/<id>/           fixtures trimmed from real responses
test/…                        tests mirror the src layout
data/                         fetched data (gitignored)
```

**Adding an adapter:**

1. Profile real data before writing the parser. Record the values you find in `docs/data-sources.md`.
2. Write `raw.ts`, `fetch.ts` and `parse.ts`.
3. Build fixtures that cover the different cases.
4. Write the tests.
5. Wire the adapter into the CLI.

## Tools and libraries

- **pnpm 12** (`packageManager` and `devEngines` in package.json). Settings live in [pnpm-workspace.yaml](pnpm-workspace.yaml), not in `.npmrc`:
  - `minimumReleaseAge`: 1 day
  - `trustPolicy: no-downgrade`
  - `blockExoticSubdeps`
  - `strictDepBuilds`
  - `allowBuilds`: empty
  - `engineStrict`

  If a new dependency needs a build script, add it to `allowBuilds` with a reason.

- **No npm or npx**: `devEngines` blocks npm, so use `pnpm exec <bin>`. Node 24 runs `.ts` files directly, so there is no build step. Use erasable TS syntax only: no `enum`, `namespace` or parameter properties.
- **TypeScript** (strict) for type checking only (`tsc`, `noEmit`).
- **oxlint** for linting and **oxfmt** for formatting. **No** ESLint or Prettier.
- **vitest** for tests.
- Runtime libraries:
  - `ky`: HTTP
  - `zod` v4: schemas, types and JSON Schema
  - `date-fns` + `@date-fns/tz`: time zones (Europe/Helsinki)
  - `p-queue`: request pacing
- Not yet: HTML parser, Playwright, database library. Data is stored **as JSON files on disk for now** and **in PostgreSQL later**.

## Data sources: summary

Detailed findings, sample payloads and references: [docs/data-sources.md](docs/data-sources.md).

| Source         | Method                                                                     | Auth                                     | Status                             |
| -------------- | -------------------------------------------------------------------------- | ---------------------------------------- | ---------------------------------- |
| BioRex         | Unofficial JSON (`webshop.biorex.fi/webservices/...`)                      | None                                     | ✅ Verified working                |
| Finnkino       | Vista OCAPI JSON (`digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1/...`) | JWT from the front page HTML, Cloudflare | ⚠️ Fragile, not yet verified by us |
| Finnkino (old) | XML API `finnkino.fi/xml/...`                                              | –                                        | ❌ Retired (2025–2026)             |

Neither needs classic HTML crawling.

**Prior work:** [Leffavuoro / Shady-Dev/kino](https://github.com/Shady-Dev/kino) (AGPL-3.0) already covers about 230 cinemas. Since we are AGPL too, its adapters **may be ported**. Mark the origin at the top of a ported file, e.g. `// Ported from Shady-Dev/kino scripts/providers/etiketti.py (AGPL-3.0)`. Its published **data** (`data/*.json`, posters) is not used as a source, because the data is not covered by its license. See [docs/data-sources.md](docs/data-sources.md#prior-work-leffavuoro-shady-devkino).

### TMDB

- **Posters, synopses and trailers come only from TMDB, never from cinemas.** A film is linked only when the match is certain. Otherwise it stays unmatched and is fixed with an alias. Rules: [docs/data-model.md](docs/data-model.md#tmdb-matching).
- Unmatched films are listed in the `pnpm match` output and in the `unmatched` list of `films.json`, with candidates. **Verify an alias on TMDB (runtime, countries, year) before adding it**, and write the reasoning in its `note`.
- Do not loosen the matching rules without a regression test (`test/matching/score.test.ts`).
- TMDB's terms require attribution (logo and notice) in the UI.

### Architecture

- **One adapter per source** (chain, or platform: BioRex runs on MyCloudCinema) → shared model `Venue`, `Auditorium`, `FilmListing`, `Screening`.
- Films from different sources are linked through TMDB (`Film`), since source ids are not shared.
- **Fetch and parse are separate:** parsers are pure functions, tested against recorded responses without network access. The model is defined as Zod schemas. See [docs/data-model.md](docs/data-model.md).
- Source labels the parser does not recognize are not lost: they go into `unmappedLabels`.
- Fetch rarely (e.g. a few times a day) and cache. Do not hammer sources.

## Rules for agents

- **User-Agent:** use an identifiable User-Agent with contact details. No residential proxies, fingerprint spoofing or captcha solving. Never call ticket purchase or payment endpoints.
- **Politeness:** when probing external APIs, make few requests and only GETs. Do not try hard to get around Cloudflare.
- **Finnkino:** Cloudflare blocks datacenter IPs. Do not assume fetching works from the cloud or CI.
- **Legal:** both APIs are undocumented and we have no permission to use them. Point this out when planning production use.
- **Verified vs. assumed:** always mark separately in the docs what was tested first-hand and what was inferred or read elsewhere.
- **Keep this file up to date:** update `AGENTS.md` when the stack, architecture or data sources change.
