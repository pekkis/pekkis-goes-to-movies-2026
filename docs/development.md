# Development guide

How the code is built and how to change it. [AGENTS.md](../AGENTS.md) has the rules; this page has the reasons and recipes.

## Principles

**Fetch and parse are separate.**

- `fetch.ts` does I/O and returns a raw snapshot: the responses as received, plus `fetchedAt`, `from` and `days`.
- The CLI archives every snapshot under `data/raw/{provider}/`.
- `parse.ts` is a pure function from snapshot to `ProviderBatch`. It can be re-run on archived snapshots without any network, which is how parser changes are checked against yesterday's real data.

**Zod at boundaries, types inside.**

- Raw schemas (`raw.ts`) are loose objects with only the fields we read, so an added upstream field breaks nothing.
- Each item is `safeParse`d. A failure becomes an `invalid-*` warning and the item is skipped; the rest of the batch survives.
- The model (`@pgtm/model`) is the contract between fetcher and backend, and `ProviderBatch.parse` guards it before a batch is written.

**Unknown stays unknown.**

- An optional field is absent when the source doesn't say: no subtitles listed is not "no subtitles", unless the source states it (`XX`, "Ei tekstitystä", Finnkino's `EiText`).
- The database stores absent fields as NULL; the API shows them as `null`.
- Labels we don't understand go to `unmappedLabels`.

**Warnings over guessing.**

- When the config does not explain a row (a room, a place line, a hall or a venue no configured venue owns), the parser skips the row and warns.
- A warning is a to-do: fix `sites.ts` or the parser, never guess in code.

**A site is data, not code.**

- Each multi-site platform has a `sites.ts` validated by `defineSites`, which checks unique providers, unique venue slugs, and a `geoSource` for every `geo`.
- Quirks are named optional fields with platform defaults and a doc comment, e.g. Nexxo's `showTypes`, eTiketti's `noSubtitlesUnreliable`, Kinola's `bareProductionsAreEvents`, Johku's `categories`.
- Every site has `verifiedAt`, the last time someone checked it against the live site as a visitor would.

**The source's own statements win.**

- Ticket links are copied, never built.
- The programme day (business date) comes from the source when it gives one (BioRex, Finnkino, Nexxo).
- Otherwise it is derived: shows before 05:00 belong to the previous day (`BUSINESS_DAY_CUTOFF_HOUR` in `@pgtm/model/time`).
- A price of 0 means free only where the source writes 0 for free (`toCents(…, { zeroIsFree })`).

**History is kept.**

- Screenings are never deleted. Ingest marks a future screening `removed_at` when a complete batch covering its venue and date no longer lists it, and clears the mark if it comes back.
- An **incomplete** batch (any data-missing warning; `isIncomplete` in the model) infers no removals, because a failed payload must not look like a cancelled programme.

**Shared meaning, shared code.**

When the same fact appears in several sources, it has one helper:

| Fact                                              | Helper                                                                                                                   |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Helsinki time, programme day, calendar arithmetic | `@pgtm/model/time` (`helsinkiShowTime`, `parseLocalDateTime`, `helsinkiShowTimeAt`, `addDays`, `isIsoDate`), on Temporal |
| Prices, seats, room ids, screening order          | `providers/parsing.ts`                                                                                                   |
| Title labels and version markers                  | `providers/labels.ts`                                                                                                    |
| Language codes                                    | `providers/language-codes.ts`                                                                                            |
| Venues from config                                | `toVenue` in `providers/sites.ts`                                                                                        |
| Lookups by outside text                           | `own` in `lib/records.ts`, so a label "constructor" finds nothing                                                        |

**Native TypeScript first.**

- Node 26 runs `.ts` directly: erasable syntax only, no build step except the API's Docker bundle.
- We use no general utility library (remeda, lodash, es-toolkit). Reviewed on 2026-10-12, the code's generic patterns (unique values, counts, chunks, sorting) are one-liners or Node built-ins: `toSorted`, `Object.groupBy`/`Map.groupBy`, `Set` methods, iterator helpers. The duplication worth removing was domain logic, which no library covers.
- Prefer `toSorted` over `sort` (oxlint enforces it).
- Reconsider a library only for something clearly beyond a one-liner.

## Warning codes

Printed by `pnpm pull` and stored in each batch. Codes marked **data missing** make the batch incomplete, so ingest infers no removals from it.

| Code                                                                                                                                                             | Meaning                                                                             | What to do                                                                         |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `invalid-response`, `invalid-envelope`, `invalid-showtimes`, `invalid-sites`                                                                                     | A whole payload did not match its schema (**data missing**)                         | Look at the raw snapshot; the API may have changed                                 |
| `invalid-show`, `invalid-showtime`, `invalid-event`, `invalid-entry`, `invalid-film`, `invalid-cinema`                                                           | One item did not match (**data missing**)                                           | Same, for one row                                                                  |
| `invalid-start`                                                                                                                                                  | A start time could not be read, or was impossible, e.g. 31.2. (**data missing**)    | Check the raw value                                                                |
| `invalid-row` (the HTML sources)                                                                                                                                 | A screening line was not understood, or its weekday fits no date (**data missing**) | Compare the line with the parser's patterns; the site may have changed its wording |
| `invalid-post`, `invalid-page` (WordPress REST, Localhub)                                                                                                        | One post or result page did not match (**data missing**)                            | Look at the raw snapshot                                                           |
| `invalid-film-page` (Elävienkuvien teatteri, KisaKino)                                                                                                           | A film page holding screenings failed or was not understood (**data missing**)      | Usually transient; check the page if it repeats                                    |
| `unknown-venue`, `unknown-film`                                                                                                                                  | A row referenced a venue or film the payload did not include (**data missing**)     | Usually an upstream inconsistency; recheck next run                                |
| `result-code`                                                                                                                                                    | The source reported an error in its response (**data missing**)                     | Retry; check the source                                                            |
| `unclaimed-room` (Nexxo), `unclaimed-place` (eTiketti, Linked Events), `unclaimed-venue` (Kinola, Alatalo), `unclaimed-hall` (Johku), `unclaimed-screen` (Gilda) | A row belongs to no configured venue (a deliberate skip)                            | Add the venue, or the room or place, to the platform's `sites.ts`                  |
| `venue-without-city`                                                                                                                                             | A chain venue lacked a city and was skipped                                         | Check the chain's data; add an override if needed                                  |
| `venue-without-geo`                                                                                                                                              | A venue has no coordinates                                                          | `pnpm venues:locate`, then `sites.ts` or `config/venue-overrides.json`             |
| `film-page-missing` (Kino Tapiola, Iso-Hannu, Kino Engel, Kuvakukko, Kino Regina)                                                                                | A film's own page failed; its details stay unknown, its screenings are complete     | Usually transient; check the page if it repeats                                    |
| `unclaimed-event` (Events Calendar)                                                                                                                              | An event outside the configured film category (a deliberate skip)                   | Check the site's category id in `tribe/sites.ts`                                   |
| `all-day-event` (Events Calendar)                                                                                                                                | An event without a time was skipped                                                 | Check whether it is a screening; usually not                                       |

## After the daily run

`pnpm pull && pnpm ingest`, then check. In a terminal the `pull` output is coloured (basic ANSI colours, readable on dark and light themes; plain when piped or under `NO_COLOR`):

- **red:** a provider that `FAILED`, a data-missing warning (`invalid-*`, `unknown-*`, `result-code`: screenings may be lost), the summary when anything failed;
- **yellow:** other warnings (deliberate skips, `venue-without-geo`), a provider with 0 screenings, unmatched films;
- **cyan:** unmapped labels and the alias hint, to-dos rather than faults;
- **green:** the summary when every provider pulled.

1. **Warnings and unmapped labels** in the `pull` output. Each is a to-do (see above). A new label needs a line in `LABELS` (`labels.ts`) when its meaning is general, in the site's config (`tags`, `showTypes`, `programs`, `titlePrefixes`) when only that cinema means it; a strand or festival goes to `config/series.json` (see the recipe).
2. **Unmatched films** (the end of `pull` or `pnpm match`). Add aliases to `config/tmdb-aliases.json` after verifying on TMDB (runtime, year, countries), with the reasoning in `note`. Event cinema is never listed.
3. **Counts per provider** in the `ingest` output.
   - A provider dropping to 0, or by a third, is suspect.
   - Large `removed` counts are suspect too; "(incomplete batch: removals not inferred)" means warnings stopped them; "(empty batch: …)" means a source returned nothing without saying why: check it, as a parser has probably stopped matching.
   - Removals that cover a single venue and day are usually the cinema's own change (e.g. BioRex Verkatehdas's Thursday, 2026-10-12).
4. **Sanity queries:** every venue has coordinates; every upcoming screening has an `https` ticket link; no shows between 02:00 and 05:00; prices between 0 and 60 €. Duplicates must be compared per hall: two versions of one film often start at the same time in different halls.
5. **Ground truth:** spot-check a cinema you can see in person (Kino Myyri for the maintainer) against the CLI: `pnpm showtimes --address "Kinorinne 6, Vantaa" --radius 1`.

## Testing

- **Where:** `packages/*/test/` mirrors `src/`. Fixtures are in `packages/fetcher/test/fixtures/<source>/`, named `<site>-<case>.json|html`, and loaded with `loadFixture()` (`test/fixtures.ts`). Imports use `../../../src/…/x.ts` with the extension.
- **Fixtures are trimmed real responses.** Keep one example per case and only the fields the parser reads. Remove synopses, posters and other images, descriptions, and personal data. Never invent a payload shape; take it from a real response. Small synthetic edits inside a test (removing a link, duplicating a row) are fine when they are named. HTML the formatter cannot parse stays as served (Kino Tapiola's `</br>`): its fixture folder is in `.oxfmtrc.json`'s `ignorePatterns`.
- **Parser tests:**
  1. The output passes `ProviderBatch.parse` with no warnings.
  2. A representative row is checked field by field.
  3. Each quirk, label and edge case has its own test.
  4. Broken input becomes warnings, not exceptions.
  5. Window filtering works.
- **Field parsers** (times across DST, codes, labels, prices) get `it.each` tables.
- **Bug fixes** come with the test that would have caught them.
- **No network.** Fetch logic takes an `HttpClient`, so tests can pass a fake one. Parsers never see the network.
- **Backend:**
  - Tests need Postgres (`pnpm db:up`). `test/global-setup.ts` drops and rebuilds `pgtm_test` from the migrations; without `TEST_DATABASE_URL` the whole backend suite stops.
  - Files run serially.
  - Model objects come from `test/factory.ts`.
  - API routes are tested in-process with `app.request()`.
- **If `pgtm_test` is missing** (a Postgres volume created before the init script existed): `pnpm db:psql -c "create database pgtm_test"`, then `pnpm migrate --test`.

## Recipes

**Add a cinema on an existing platform:** edit that platform's `sites.ts`. Platform specifics are in [data-sources.md](data-sources.md):

| Platform | What to configure                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------- |
| Nexxo    | API host and `locationId`s from `public_api.php`                                                        |
| eTiketti | each venue's part of the place line as `place`                                                          |
| Kinola   | `tenant` from the site's `media.kinola.ee/storage/{tenant}.kinola.ee` image URLs                        |
| Johku    | `shop` and film `categories` from the front page's `__NUXT_DATA__` keys, and the hall's `resource` name |

Then for every new venue:

1. `geo` (with its `geoSource`), address and `verifiedAt`.
2. `pnpm pull --provider <id>`; read the warnings and fix `sites.ts` until there are none.
3. `pnpm venues:locate` lists no venue of it.

**Add a label or a series** (an unmapped label in the `pull` output):

1. Decide what it says. A general fact (availability, language, an occasion, an audience) goes into `LABELS` in `providers/labels.ts`, with a row in the table test in `test/providers/labels.test.ts`. A phrase only one cinema uses in its own sense goes into that site's config.
2. A strand, festival, club or distributor series goes into `config/series.json`: a stable id (never renamed; it is in screening rows), the display `name`, the `kind`, other spellings in `aliases`, and a `note` saying where it was seen. A provider strand (`kinoregina/…`) is adopted the same way, with its name as an alias.
3. Something that cannot be classified with certainty stays unmapped; note it under "Open questions" in [classification.md](classification.md).

**Add a chain (a single source like BioRex or Finnkino):**

1. Profile real responses first; record findings in `data-sources.md`, marked [V] or [A].
2. Write `raw.ts`, `fetch.ts` and `parse.ts` using the shared helpers.
3. Add trimmed fixtures and tests.
4. Add the adapter to `registry.ts` with its pacing.
5. Chain venues usually carry their own coordinates; fix wrong ones in `config/venue-overrides.json`.

**Add a platform:** as for a chain, plus:

1. Add the name to `Platform` in `@pgtm/model`.
2. Write a `sites.ts` extending `SiteBase`/`SiteVenue` with `defineSites`.
3. Add an adapter factory in the registry, so that `--provider <platform>` selects every site.
4. Add a geo-coverage test in `test/providers/sites.test.ts`.
5. Add a section in `data-sources.md`, including how to add a cinema.

**Change the model:** `@pgtm/model` is the contract, so a new field usually needs four more changes:

1. a migration;
2. `src/ingest/rows.ts`;
3. `pnpm db:types`;
4. if clients should see it, `src/api/schemas.ts` and the queries.

Check `data-model.md` and `database.md` too.

**Add an API route:**

1. `createRoute` in `src/api/routes/` with Zod schemas from `schemas.ts`.
2. A query in `src/queries/`.
3. A test in `test/api/`.

The route then appears in `/openapi.json` and in the typed `hc<AppType>` client.
