# AGENTS.md – Pekkis goes to movies

Instructions for AI agents (and humans) working in this repository. Rules first, then how the code is built, then reference. Details live in `docs/`: [development.md](docs/development.md) (principles, testing, warnings, recipes), [data-sources.md](docs/data-sources.md), [data-model.md](docs/data-model.md), [database.md](docs/database.md), [api.md](docs/api.md), [cli.md](docs/cli.md), [web.md](docs/web.md), [deploy.md](docs/deploy.md).

## What this is

"Pekkis goes to movies" gathers the showtimes of all Finnish cinemas under one site. Users look for something to watch from two directions:

- **Time and place first**: "what's playing in Tampere tonight after 6 pm?"
- **Film first**: "where and when can I see film X?"

It is part of the user-centered design course at JAMK. License: **AGPL-3.0-or-later** ([LICENSE](LICENSE)); the repository is public.

## Current state

- **Data:** 143 venues in 100 cities from 91 providers on thirty-nine source types:
  - one chain: Finnkino (Vista OCAPI), and Vista's open public web services (Korjaamo Kino, Riviera Kallio and Punavuori, Bio-Kaari);
  - six multi-site platforms: MyCloudCinema (BioRex, Cine Mäntsälä, and Gilda through its own WordPress facade), Nexxo, eTiketti, Kinola, Johku, and The Events Calendar for WordPress (Ritz Vaasa, Tähti Kino Muhos);
  - the open Linked Events APIs of Helsinki and Espoo (Kino Helios in Malmitalo, Kino Kuutamo and HopeaCine in Kanneltalo and Vuotalo, Kannusali);
  - the My Calendar WordPress plugin's REST route (Pyhäsalmen VPK);
  - a town's Localhub event calendar (Kino Akustiikka, Ylivieska);
  - twenty-eight HTML sources: TMB Cinema (four cinemas), the WordPress `cinema-reservations` plugin (Kino Piispanristi, Kino Lumo, Laitilan Kino), Kino Tapiola's own theme, Kuvakukko's shared programme page (Kino Kuvakukko, Kino Manttu), Iso-Hannu's own site, Kino Engel's front page (home connection only), Julia's programme page, Kino Vaakuna's front page, Kino Kirkkonummi's one page, Bio Savoy's front page (HTTP only), Kino Akseli's front page (home connection only), Kino Hamina's page on the town's site, Kino Regina's programme (a read-only POST), Elävienkuvien teatteri's listing and film pages, Kino Kuusamotalo's WordPress posts, Lieksan Kino's page, Elokuvateatteri Marita's front page, Kino-Huovi's front page, Matin-Tupa's programme page, Navettakino's front page, Bio Pallas's Wix front page, Kurikan Kino's front page, KisaKino's film pages, Pajakkakino's WordPress posts, Bio Marlon's front page, Kino-Kuva's front page (ISO-8859-1), Cinema Levi Summit's show calendar, and the freehand programmes of Movie Company Alatalo (touring) and Huvimylly.

  Fetched into JSON (`pnpm pull`), matched to TMDB, stored with history in PostgreSQL (`pnpm ingest`).

- **Interfaces:**
  - the `showtimes` CLI;
  - a read-only HTTP API (Hono, OpenAPI), and an MCP server on it for chatbots (`/mcp/{MCP_TOKEN}`, off unless the token is set; internal testing);
  - a Flutter map app by a teammate in `apps/fpgm` (an early scaffold);
  - the public website in `apps/web-front`: Astro (SSR) + React + Vanilla Extract. City pages, venue pages and a venue map (MapLibre). See [docs/web.md](docs/web.md).

- **Visual style: a grey mockup, on purpose.** There is no visual identity yet; it comes after user testing. See the rule below.
- **Not started here:** design and user research. The course work happens outside this repository.
- **Backlog:** GitHub issues (`gh issue list`; labels `provider`, `tmdb`, `geo`, `backlog`).
- **Prior work:** [Leffavuoro / Shady-Dev/kino](https://github.com/Shady-Dev/kino) (AGPL-3.0, about 230 cinemas). A code-only copy is in [vendor/leffavuoro/](vendor/leffavuoro/UPSTREAM.md). Read it first when adding a platform; its adapters may be ported (credit them in the site file's header), its `data/` may not be used.

## Language

**English** for code, identifiers, comments, commit messages, documentation and discussion with the maintainer. No Finnish identifiers, ever. Finnish appears only as data: cinema and film names, Finnish words in lookup tables, test fixtures.

## Rules for agents

**Process**

- **Git:** `main` is protected (no direct pushes, force pushes or deletion, for everyone). Work on a branch, open a PR with `gh pr create`; no approval needed. **Commit only when the maintainer asks.**
- **`pnpm check` must pass** (typecheck, lint with **zero warnings**, format, the website build, tests) before you say you are done or open a PR.
- **Keep docs true:** update this file and `docs/` in the same change that makes them stale. Mark in docs what was verified first-hand ([V]) and what was assumed or read elsewhere ([A]).
- **Issues are public:** English, no secrets, no personal data.

**Secrets and data**

- Never print `TMDB_APIKEY` or `OMDB_APIKEY`. OMDb's key travels in the URL, so its errors are rethrown without the URL and its cache key leaves the key out; keep it that way.
- `.env` is gitignored; [.env.example](.env.example) lists variables with **empty** values only.
- Never commit `data/` (the cinemas' data). Never copy Leffavuoro's `data/` (not covered by its license). Never edit `vendor/leffavuoro/` by hand (it is overwritten on refresh).
- **Update the vendor copy only with `pnpm vendor:leffavuoro --sync`**: it syncs the pekkis/kino fork with upstream (`gh repo sync`), then copies; without `--sync` it stops if the fork is behind. Never clone, download or copy their files in by other means: the script keeps `data/` out (it never even downloads it) and records the commit in `UPSTREAM.md`. Refresh before comparing our findings with theirs, then commit the diff.
- Never hard-code anyone's contact details; the User-Agent's contact comes from `CONTACT` in `.env`.

**Sources: politeness and ethics**

- Identifiable User-Agent. **GET by default**: a read-only POST (the request the cinema's own listing makes) only for sources that offer nothing else, one at a time and with the maintainer; they are listed in the README's "Sources read with a POST" (`HttpClient.postForm`). Few, paced requests (see per-adapter pacing in the registry). No residential proxies, fingerprint spoofing or captcha solving; do not try hard to get around Cloudflare.
- Never call ticket purchase, booking or payment endpoints. Ticket links are **copied** from the source into `ticketUrl`, never constructed and never requested (eTiketti's `/salikartta`, Kinola's and Johku's `/checkout/…`).
- **Johku:** only storefronts whose own code reads the schedule anonymously. Never a widget's `X-ApiKey` (KuvaTähti loads its shows only that way, so it is out). Kino Engel and Kino Tapiola merely embed the Johku widget for tickets: their own server-rendered pages may be read like any HTML source (Engel challenges datacenter IPs; if it challenges us too, skip it).
- **Finnkino:** only the token step uses a (visible) browser; never defeat Cloudflare by other means. It does not run in CI or the cloud.
- **Posters, synopses and trailers come only from TMDB**, never from cinemas, and cinemas' texts stay out of test fixtures.
- **Coordinates never from Google Maps** (its terms forbid storing them). OpenStreetMap (ODbL, credit "© OpenStreetMap contributors"), Nominatim (1 request/s, cached), the cinema's own pages, or the maintainer.
- **Contacting cinemas:** not needed while this is a course project. **Before the service goes truly public, every cinema and chain is notified first** (what we read, how often, that every click goes to their ticket page), and any that object are removed.

**Visual style (until user testing)**

- **The website is a grey wireframe built of boxes.** It has no visual identity until user testing gives us one, so testers react to structure and content, not looks.
- **Allowed:** neutral greys only (the theme tokens in `src/styles/theme.css.ts`); plain rectangles with borders; system font; underlined links.
- **Not allowed:** brand or accent colors, rounded corners, shadows, gradients, illustrations, icons for decoration, custom fonts, animation.
- **Information is never carried by color alone:** use text, borders, weight and layout.
- **Required third-party content stays as it is:** the TMDB logo, map tiles (grey styles), attributions.
- When the visual identity arrives, it replaces the token values and recipes, not the components.

**User interface (website)**

- **Mobile first:** the phone layout is the default; wider layouts are added with `min-width` conditions.
- **Container queries, always when possible:** components adapt to their container, not the viewport (`minWidth()` from `src/styles/containers.ts`, sprinkles `wide`/`widest`). Viewport `@media` only where a container can't work.
- **Showtimes are live:** any component showing one uses `useShowStatus` (`src/components/clock.tsx`, a jotai atom ticking once a minute) inside an island rooted in `<ClockIsland>`: started, soon (within an hour) or later, kept current while the page is open. See [docs/web.md](docs/web.md#live-showtimes-one-clock-reusable).
- **Lists of films are alphabetical by title** (Finnish order, `byTitle` in `src/lib/films.ts`); showtimes within a film, and timetables of screenings, stay in time order.
- **The design system is the Vanilla Extract theme** (`src/styles/theme.css.ts`), the single source of truth. Every color, space, font size and weight, border and fixed size is a token. Components use `vars`, sprinkles and recipes, never literal values; a new value goes into the theme first.
- Details: [docs/web.md](docs/web.md#user-interface-rules).

**Data correctness**

- **Certain or nothing:** a film is linked to TMDB only when the match is certain; otherwise it stays unmatched and gets an alias (verified on TMDB, reasoning in its `note`). Never loosen matching without a regression test in `test/matching/score.test.ts`.
- **Unknown stays unknown:** an absent field (NULL in the database), never a guess. Labels the parser does not understand go to `unmappedLabels`; rows the config does not explain become **warnings**, which are to-dos for `sites.ts`.
- Venue slugs are part of ids (`{provider}:venue:{slug}`): never rename one, or its history is orphaned.
- **The website stays out of search engines** (`noindex` meta and `X-Robots-Tag`) until every cinema has been notified; only that production deployment sets `INDEXING=on`. Every page credits TMDB (logo and notice), OpenStreetMap and the Linked Events of the Cities of Helsinki and Espoo (CC BY 4.0: Kino Helios, Kannusali), and OMDb wherever scores show.
- **Ratings are opt-in** in every UI (the CLI shows them only with `--ratings` or a score filter): some people do not want critics' verdicts beforehand.
- **MCP:** the endpoint stays unlisted (behind `MCP_TOKEN`) until every cinema has been notified, like the website's `noindex`. Its tools are read-only, return the cinemas' own ticket links, and give critics' scores only with `include_ratings`.
- **API:** responses are the public shapes in `packages/backend/src/api/schemas.ts`, never database rows; change them deliberately (Flutter and React clients depend on them). Read-only, no auth. Keep the TMDB, OMDb, OpenStreetMap and Linked Events attributions in the OpenAPI description.
- **Database:** migrations are append-only and listed in `migrations/index.ts` (a test checks). After one, run `pnpm migrate && pnpm db:types` and commit the regenerated `types.ts` (never edit it by hand). The fetcher stays database-agnostic.

## How the code is built

The principles the code follows; [docs/development.md](docs/development.md) explains each with examples.

- **Fetch and parse are separate.** `fetch.ts` does I/O only and returns a raw snapshot (archived under `data/raw/`); `parse.ts` is a **pure** function from snapshot to `ProviderBatch`, tested against trimmed real responses without network.
- **Zod at every boundary:** raw responses (`raw.ts`, loose objects with only the fields we read), the model (`@pgtm/model`), env, CLI input, API requests and responses. Parsers `safeParse` each item and turn failures into `invalid-*` warnings.
- **A site is data, not code.** Multi-site platforms have one adapter per site, generated from the platform's `sites.ts`. Everything that differs between sites is a Zod-validated config field (named quirks with platform defaults, `verifiedAt`, `notes`), never an `if (site === "x")`.
- **Shared meaning, shared code:** Helsinki time, the programme day and calendar arithmetic (`@pgtm/model/time`, shared by every package), prices, seats, room ids and ordering (`providers/parsing.ts`), labels and version markers (`providers/labels.ts`), language codes (`providers/language-codes.ts`), venues from config (`providers/sites.ts`). A new parser uses these instead of its own copy.
- **Incomplete batches infer no removals:** data-missing warnings (`invalid-*`, `unknown-*`, `result-code`; `isIncomplete` in the model) stop ingest from marking absent screenings as removed; so does an empty batch with no warnings (a parser gone silent).
- **Native TypeScript first.** Node 26 runs `.ts` directly (no build step, except the API's Docker bundle). Erasable syntax only: no `enum`, `namespace` or parameter properties. Prefer built-ins (`toSorted`, `Object.groupBy`, `Set` methods, iterator helpers) over utility libraries; lookup tables keyed by outside text use `own()` (`lib/records.ts`).
- **Dates and times are Temporal** (no date library). Calendar and time-zone logic (Helsinki wall-clock time, the programme day, adding days, minutes until a show) lives in `@pgtm/model/time` and nowhere else. Plain `Date` only for timestamps and at library boundaries (`pg` returns `Date`); `currentInstant()` reads the clock through `Date.now()` so tests can fake it. The website loads `temporal-polyfill` (native where available; Safari lacks Temporal) and formats with `Intl` in `src/lib/time.ts`.
- `strict`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`: optional fields are spread in only when set (`...(x && { x })`).
- **Braces always:** every `if` / `else` / loop body goes in `{}` on its own lines, never `if (x) return y;`. Enforced by oxlint (`curly: all`, autofixable with `pnpm exec oxlint --fix`; oxfmt puts the body on its own line).
- **Modern React 19:** `use(Context)` instead of `useContext`, `<Context value>` instead of `<Context.Provider>`, `ref` as an ordinary prop (no `forwardRef`), function components only. Shared client state lives in **jotai** atoms (an atom's `onMount` subscribes to external sources, like the clock); each island root is a jotai `Provider`, so the server never shares a store between requests. Never `setState` in an effect to sync with the outside world. oxlint's React plugin checks the rules of hooks, effect dependencies and `setState` in effects.

## Commands

```sh
pnpm db:up / db:down         # Postgres in Docker (localhost:5432); pnpm check needs it too
pnpm migrate                 # apply migrations (--down one step; --test the test database)
pnpm db:types                # regenerate packages/backend/src/db/types.ts after a migration
pnpm db:psql                 # psql inside the container
pnpm pull                    # fetch every provider, 6 at a time, then match films to TMDB (~2 min)
pnpm pull --provider nexxo   # a provider id or a platform name; --days, --from, --venue: docs/cli.md
pnpm match                   # re-run TMDB matching only (after editing aliases)
pnpm ingest                  # upsert data/normalized/*.json into Postgres, keeping history
pnpm data:push               # ship data/normalized/ to the server and ingest it there (docs/deploy.md)
pnpm venues:locate           # suggest OSM coordinates; --address geocodes an address
pnpm showtimes odysey        # film search; with no film, everything on (--here, --after, …: docs/cli.md)
pnpm api:dev / api:up / api:down   # the HTTP API on :3000 (dev with reload / Docker)
pnpm web:dev / web:build     # the website on :4321 (API_URL points it at the API)
pnpm check                   # typecheck + lint (zero warnings) + fmt:check + web build + test
pnpm test / typecheck / lint / fmt / fmt:check
pnpm vendor:leffavuoro --sync   # sync the pekkis/kino fork with upstream, refresh vendor/leffavuoro
```

- First run: `pnpm db:up && pnpm migrate && pnpm pull && pnpm ingest`.
- **`pnpm fetch` is built into pnpm**, which is why the fetch script is `pull`.
- **Finnkino opens a visible Chrome window** for a few seconds when its 12-hour token needs renewing (cached in `data/cache/finnkino-token.json`).

**Daily routine:** the maintainer runs `pnpm pull && pnpm ingest` (and `pnpm data:push` for the server) by hand, about once a day (no scheduler: Finnkino needs a visible Chrome, and the laptop is often closed). Programmes change most on Tuesday and Wednesday; programme weeks run Friday to Thursday. Afterwards, check the run as listed in [docs/development.md](docs/development.md#after-the-daily-run):

- warnings and unmapped labels;
- unmatched films;
- providers whose count dropped;
- removals.

**Environment (`.env`, loaded by Node's `--env-file-if-exists`, no dotenv; validated by `loadEnv()` in each package):**

- `TMDB_APIKEY`: TMDB v4 read token. Needed by `pull` and `match`.
- `OMDB_APIKEY`: optional; enables Rotten Tomatoes, Metacritic and IMDb scores.
- `CONTACT`: optional; goes into the User-Agent.
- `DATABASE_URL`, `TEST_DATABASE_URL`.
- `PORT`, `HOST`, `CORS_ORIGINS`: for the API.
- `DEPLOY_TARGET` (home), `POSTGRES_PASSWORD`, `API_PORT`, `WEB_PORT`, `SITE_URL` (server): deployment, see [docs/deploy.md](docs/deploy.md).
- `MCP_TOKEN`: optional; turns on the MCP endpoint at `/mcp/{MCP_TOKEN}` (24+ random characters; redacted from logs).

## Layout

```
package.json, pnpm-workspace.yaml, tsconfig.base.json   workspace root; .oxlintrc.json, .oxfmtrc.json
compose.yaml, docker/           Postgres 18 (+ pgtm_test via docker/postgres/init); profile "app": migrate, api, web; profile "ingest": ingest
Dockerfile, .dockerignore       API image (serve, migrate, ingest): tsdown bundle + `pnpm deploy --prod` node_modules
apps/web-front/Dockerfile       website image (Astro standalone server); its own Dockerfile.dockerignore
.env, data/                     gitignored: secrets; raw/, normalized/, cache/ (tmdb, omdb, osm, geocode, token)
docs/                           development, data-sources, data-model, database, api, cli
vendor/leffavuoro/, scripts/    Leffavuoro reference copy (not built, linted or formatted) and its refresher
apps/fpgm/                      the teammate's Flutter app: own tooling, not in the pnpm workspace; do not edit unasked
apps/web-front/                 @pgtm/web-front: the website (Astro SSR, React, Vanilla Extract); see docs/web.md
  src/pages/, src/layouts/      thin .astro routes and layout; logic lives in src/lib/
  src/components/               React components; islands (client:idle) for live UI; clock.tsx: jotai clock atom, ClockIsland, useShowStatus
  src/styles/                   design system: theme.css.ts (all tokens), containers.ts, sprinkles, reset, recipes/
  src/lib/                      typed API client (hc<AppType>), page loaders, cities, time, text (Finnish UI text)
packages/model/                 @pgtm/model: src/schema.ts, the domain model (Zod + types); src/time.ts (`@pgtm/model/time`): Temporal dates and times; source-only
packages/fetcher/               @pgtm/fetcher: fetch, normalize, match → data/normalized/*.json
  src/lib/                      env, paths, http (ky + p-queue, per-host pacing; GET, and postForm for POST sources; text decoded by its stated charset), lang, cache, records
  src/providers/adapter.ts      Adapter (id, platform, pull), restrictToVenues
  src/providers/registry.ts     every adapter (one per site on platforms), pacing, selectAdapters
  src/providers/sites.ts        SiteBase, SiteVenue, defineSites, toVenue: the multi-site base
  src/providers/parsing.ts      toCents, availabilityFromSeats, slugify, byStartThenId, tally
  src/providers/labels.ts       LabelRule, title prefixes, version markers
  src/providers/language-codes.ts   FI / OV / FI-SE / XX codes (Nexxo, Johku)
  src/providers/overrides.ts    config/venue-overrides.json for chain venues; venue-without-geo warnings
  src/providers/<source>/       raw.ts, fetch.ts, parse.ts; sites.ts on platforms; finnkino/token.ts
                                (mycloudcinema [BioRex, Cine Mäntsälä], gilda [MyCloudCinema via WordPress], tmb [HTML], cinemahouse [HTML], vista [public JSON/XML], tapiola [HTML], kuvakukko [HTML], isohannu [HTML], tribe [Events Calendar REST], engel [HTML], linkedevents [City of Helsinki], julia [HTML], vaakuna [HTML], kirkkonummi [HTML], biosavoy [HTML], kinoakseli [HTML], hamina [HTML], elavienkuvien [HTML], kuusamotalo [WordPress REST], lieksa [HTML], marita [HTML], kinohuovi [HTML], matintupa [HTML], mycalendar [My Calendar REST], navetta [HTML], localhub [calendar search], biopallas [Wix HTML], kurikankino [HTML], kisakino [HTML], pajakkakino [WordPress REST], biomarlon [HTML], kinokuva [HTML], levisummit [HTML], alatalo [freehand HTML: Alatalo, Huvimylly], regina [form POST + film pages], finnkino, nexxo, etiketti [HTML, cheerio], kinola, johku)
  src/matching/                 TMDB matching: score.ts (pure), match.ts, titles.ts, aliases.ts, catalog.ts, run.ts
  src/tmdb/, src/ratings/       TMDB client and toFilm; OMDb ratings
  src/geo/                      Finland bounds and sources, Overpass, Nominatim, OSM matching (venues:locate)
  src/cli/                      fetch (pull), match, locate (venues:locate)
  config/                       tmdb-aliases.json, venue-overrides.json (hand-maintained, committed)
  test/                         mirrors src; fixtures/<source>/ trimmed real responses; fixtures.ts (loadFixture)
packages/backend/               @pgtm/backend: PostgreSQL (Kysely), ingest, search CLI, HTTP API
  migrations/                   append-only; index.ts lists them all
  src/db/                       createDb (CamelCasePlugin, timeouts), migrator, types.ts (GENERATED)
  src/ingest/                   rows.ts (pure model → rows), ingest.ts (upserts, history, removals)
  src/search/, src/geo/         showtimes CLI: fuzzy search, filters, formatting; --here / --address
  src/api/, src/queries/        Hono app (schemas.ts = public shapes, routes/); Kysely queries for it
  src/mcp/                      MCP server for chatbots: find_film, whats_on, list_venues (same queries)
  src/cli/                      migrate, ingest, db-types, showtimes, serve
  test/                         unit + integration tests against TEST_DATABASE_URL (global-setup rebuilds it)
```

## Testing

[docs/development.md](docs/development.md#testing) has the details. In short:

- **Parsers:** run against trimmed real responses in `test/fixtures/<source>/`. Keep one example per case; remove synopses, posters, images and personal data. Assert the output passes `ProviderBatch.parse` with no warnings, then assert each case.
- **Field parsers** (times across DST, language codes, labels) get table tests.
- **Every bug fix gets a test that fails without it.**
- **No network in tests.** HTTP clients are faked through the `HttpClient` type.
- **Backend tests** need Postgres (`pnpm db:up`) and run serially against `pgtm_test`, which global setup rebuilds from the migrations.
- **API routes** are tested in-process with `app.request()`. A typed-client test (`hc<AppType>`) guards the client types.
- **Website:** page loaders and helpers get unit tests with a fake `fetch`; React components get Testing Library tests (`// @vitest-environment happy-dom`); pages render through Astro's Container API with a fake API in `locals`.

## Tools

- **Node 26, managed by pnpm:** `devEngines.runtime` in `package.json` pins it, and pnpm downloads it for every script (`pnpm pull`, `pnpm test`, …), whatever `node` your shell has. Docker uses `node:26-alpine`.
- **pnpm 12**, configured in `pnpm-workspace.yaml`:
  - `minimumReleaseAge` 1 day
  - `trustPolicy: no-downgrade`
  - `blockExoticSubdeps`
  - `strictDepBuilds`
  - `allowBuilds`: `esbuild` allowed (Vanilla Extract), `sharp` refused (unused); add an entry with a reason if a dependency needs a build script
  - `trustPolicyExclude`: exact versions checked by hand, each with its reason (only with the maintainer's approval)
  - `engineStrict`
- **No npm or npx:** `devEngines` blocks them; use `pnpm exec`.
- **Adding dependencies:** a runtime dependency goes to its package (`pnpm --filter @pgtm/fetcher add …`), shared dev tooling to the root (`-D -w`).
- **Checks:** TypeScript (strict, `noEmit`), oxlint (correctness and suspicious categories plus `curly: all` and the React plugin's hook rules, warnings fail), oxfmt and vitest. No ESLint or Prettier.
- **Libraries:**
  - `zod` v4, `ky`, `p-queue`;
  - `cheerio` (eTiketti HTML);
  - `playwright` (Finnkino token only, the installed Chrome);
  - `kysely` + `pg` (+ `kysely-codegen`);
  - `hono` + `@hono/zod-openapi` + `@scalar/hono-api-reference`;
  - `tsdown` (Docker bundle only);
  - website: `astro` (+ `@astrojs/node`, `@astrojs/react`), `react`, `@vanilla-extract/*` (css, vite-plugin, sprinkles, recipes, dynamic), `hono/client`, `jotai` (shared client state), `maplibre-gl` (the map page only, with OpenFreeMap tiles). Interactive and live UI is React islands, rendered on the server first and hydrated `client:idle`; no hand-written DOM scripts for UI (the map excepted).
- **Website caveats:** `astro check` does not support TypeScript 7 yet, so `tsc` checks the `.ts`/`.tsx` files and `.astro` files stay thin. oxlint checks `.astro` frontmatter; oxfmt does not format `.astro` files.
- **No general utility library** (remeda, lodash, es-toolkit). Node 26's built-ins cover what the code needs (see development.md).
