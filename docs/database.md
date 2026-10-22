# Database

PostgreSQL 18 in Docker Compose ([compose.yaml](../compose.yaml)), accessed with [Kysely](https://kysely.dev) from [`@pgtm/backend`](../packages/backend/). The fetcher never touches the database: it writes JSON, and `pnpm ingest` upserts that JSON.

```sh
pnpm db:up        # start Postgres (localhost:5432; databases pgtm and pgtm_test)
pnpm db:psql      # psql shell inside the container (nothing to install)
pnpm migrate      # apply migrations (--down: one step back; --test: the test database)
pnpm db:types     # regenerate packages/backend/src/db/types.ts after a migration
pnpm pull         # fetch → data/normalized/*.json
pnpm ingest       # upsert data/normalized/*.json into Postgres
pnpm showtimes heart beast   # fuzzy film search: film info + today's screenings in all venues
```

For a nicer shell on the host, `pgcli postgres://pgtm:pgtm@localhost:5432/pgtm` (`brew install pgcli`: completes tables and columns as you type), or native psql from `brew install libpq`.

## Naming

- Tables are plural, columns snake_case and lowercase (`screenings.starts_at`). Otherwise names follow the model ([packages/model](../packages/model/src/schema.ts)).
- TypeScript stays camelCase: Kysely's `CamelCasePlugin` translates (`startsAt` ↔ `starts_at`). No hand mapping anywhere.
- Ids are the model's namespaced text ids: `biorex:show:436478`, `finnkino:venue:1004`, `tmdb:1185806`.
- `date` columns are read as `YYYY-MM-DD` strings, like the model; `timestamptz` columns as `Date`.

## Tables

| Table           | Holds                                                                                                                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `providers`     | chains/cinemas and their ticketing platform                                                                                                                                                                                                |
| `venues`        | cinemas: city, address, coordinates                                                                                                                                                                                                        |
| `auditoriums`   | screens: features, own age limit                                                                                                                                                                                                           |
| `films`         | canonical films from TMDB: `title_fi/sv/en`, `overview_fi/sv/en`, poster, trailers (`jsonb`), Finnish rating                                                                                                                               |
| `film_ratings`  | One score per film and source (`rotten-tomatoes`, `metacritic`, `imdb`, `tmdb`): `score` 0–100, `display` as the source shows it, `votes`. Primary key `(film_id, source)`. A snapshot: ingest replaces a film's ratings with the latest.  |
| `film_listings` | each provider's own film record, `film_id` → `films` (NULL when unmatched), `kind` film/event, `imdb_id` when the source gives one                                                                                                         |
| `series`        | the series screenings belong to: `id` (registry id or `{provider}/{slug}`), display `name`, `kind` (strand, festival, retrospective, club, distributor-series, theme-week). Upserted from each batch, so a renamed registry entry updates. |
| `screenings`    | showtimes, with history columns (below); `series` holds `series` ids (rows from before migration 0005 hold names; the API shows either), `labels` (jsonb) the raw labels                                                                   |

Model shapes are flattened: `presentation` → `projection`, `dimension`, `formats`; `subtitles` → `subtitles_kind` + `subtitles_languages`; `price` → `price_amount_cents`, `price_currency`, `price_note`; `geo` → `lat`, `lon`. Lists are `text[]`. Enum-like values are `text`, validated by Zod at ingest (Postgres enums are painful to change). An absent ("unknown") model field is `NULL`.

## History

Screenings are **never deleted**, so the data accumulates over time.

- `first_seen_at`: the first fetch that contained the screening.
- `last_seen_at`: the latest fetch that contained it. Fields such as `availability` are updated each time.
- `removed_at`: set when a later fetch **covered the screening's business date** (`ProviderBatch.window`) but no longer listed it, while it was still in the future (cancelled or rescheduled). Cleared if it reappears.
- Past screenings, screenings starting within 30 minutes of the pull (`REMOVAL_MARGIN_MINUTES`: sources drop a show once its online sales close, e.g. Finnkino left a 12:10 show out of a 12:05 answer, 2026-10-22 [V]) and dates outside the fetched window are never marked removed. Only the batch's own venues are considered.
- An **incomplete** batch (a data-missing warning, `isIncomplete` in the model) marks nothing removed: a failed payload must not look like a cancelled programme. `pnpm ingest` then prints "(incomplete batch: removals not inferred)".
- An **empty** batch (no screenings and no warning) marks nothing removed either [V, test]: a whole programme vanishing in silence is almost always a parser that stopped matching (eTiketti's `data-dates` rows, 2026-10-15), not a cinema cancelling everything. `pnpm ingest` prints "(empty batch: removals not inferred; check the source)". A cinema that truly cancels all its shows stays listed until they pass.
- A batch with **far fewer upcoming screenings** than the database holds for its venues and days (under half, and at least 10 fewer; `looksPartial`) marks nothing removed either [V, test]. That's a source answering in part, not a cinema cancelling: Cine Mäntsälä's API returned only today instead of the week on 2026-10-20. `pnpm ingest` prints "(far fewer upcoming screenings than before: removals not inferred; check the source)". Screenings a cinema really dropped are removed by the next full answer.
- A provider whose fetch **fails** (an HTTP error, a network error, a maintenance page) writes no batch at all, so its previous batch is ingested again, unchanged, and nothing is removed (2026-10-21: six sources under maintenance at once).

"Current programme" is `where removed_at is null and starts_at > now()`.

Ingest is idempotent: running it twice on the same files inserts and removes nothing.

## Migrations

- In [packages/backend/migrations](../packages/backend/migrations/), plain `.ts` run by Node through Kysely's `Migrator` (`kysely/migration` in Kysely 0.29).
- **Append-only:** never edit an applied migration; add a new one.
- After a migration: `pnpm db:types`, and commit the regenerated `src/db/types.ts`. Never edit that file by hand.

## Tests

The backend's integration tests run against `TEST_DATABASE_URL` (`pgtm_test`). Before each run the schema is dropped and rebuilt from the migrations. **`pnpm check` therefore needs `pnpm db:up` first.**

`pgtm_test` is created by an init script when the Postgres volume is first created. On an older volume, create it once: `pnpm db:psql -c "create database pgtm_test"`.

## Fuzzy search

`pnpm showtimes <name>` ([packages/backend/src/search](../packages/backend/src/search/)) uses the `pg_trgm` extension (migration `0002`). A film's score is the best `word_similarity` over its TMDB titles (fi/sv/en/original) and the titles cinemas list it under; listings without a TMDB film are searched by their own titles. Default threshold 0.5 (`--min-score`): typos like "odysey" score about 0.67, and unrelated titles stay below 0.45.

All options (time and place filters, ratings): [cli.md](cli.md#pnpm-showtimes-search-the-programme).

## Example

```sql
-- most shown films across all chains
select coalesce(f.title_fi, f.original_title) as film, count(*) as shows,
       count(distinct s.venue_id) as venues
from screenings s join films f on f.id = s.film_id
where s.removed_at is null
group by 1 order by 2 desc limit 10;
```
