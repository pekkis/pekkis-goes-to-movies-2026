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

| Table           | Holds                                                                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------ |
| `providers`     | chains/cinemas and their ticketing platform                                                                  |
| `venues`        | cinemas: city, address, coordinates                                                                          |
| `auditoriums`   | screens: features, own age limit                                                                             |
| `films`         | canonical films from TMDB: `title_fi/sv/en`, `overview_fi/sv/en`, poster, trailers (`jsonb`), Finnish rating |
| `film_listings` | each provider's own film record, `film_id` → `films` (NULL when unmatched), `kind` film/event                |
| `screenings`    | showtimes, with history columns (below)                                                                      |

Model shapes are flattened: `presentation` → `projection`, `dimension`, `formats`; `subtitles` → `subtitles_kind` + `subtitles_languages`; `price` → `price_amount_cents`, `price_currency`, `price_note`; `geo` → `lat`, `lon`. Lists are `text[]`. Enum-like values are `text`, validated by Zod at ingest (Postgres enums are painful to change). An absent ("unknown") model field is `NULL`.

## History

Screenings are **never deleted**, so the data accumulates over time.

- `first_seen_at`: the first fetch that contained the screening.
- `last_seen_at`: the latest fetch that contained it. Fields such as `availability` are updated each time.
- `removed_at`: set when a later fetch **covered the screening's business date** (`ProviderBatch.window`) but no longer listed it, while it was still in the future (cancelled or rescheduled). Cleared if it reappears.
- Past screenings and dates outside the fetched window are never marked removed.

"Current programme" is `where removed_at is null and starts_at > now()`.

Ingest is idempotent: running it twice on the same files inserts and removes nothing.

## Migrations

- In [packages/backend/migrations](../packages/backend/migrations/), plain `.ts` run by Node through Kysely's `Migrator` (`kysely/migration` in Kysely 0.29).
- **Append-only:** never edit an applied migration; add a new one.
- After a migration: `pnpm db:types`, and commit the regenerated `src/db/types.ts`. Never edit that file by hand.

## Tests

The backend's integration tests run against `TEST_DATABASE_URL` (`pgtm_test`). Before each run the schema is dropped and rebuilt from the migrations. **`pnpm check` therefore needs `pnpm db:up` first.**

## Fuzzy search

`pnpm showtimes <name>` ([packages/backend/src/search](../packages/backend/src/search/)) uses the `pg_trgm` extension (migration `0002`). A film's score is the best `word_similarity` over its TMDB titles (fi/sv/en/original) and the titles cinemas list it under; listings without a TMDB film are searched by their own titles. Default threshold 0.5 (`--min-score`): typos like "odysey" score about 0.67, and unrelated titles stay below 0.45.

Options: `--date YYYY-MM-DD` (default: today in Helsinki), `--links` (ticket URLs), `--min-score`.

## Example

```sql
-- most shown films across all chains
select coalesce(f.title_fi, f.original_title) as film, count(*) as shows,
       count(distinct s.venue_id) as venues
from screenings s join films f on f.id = s.film_id
where s.removed_at is null
group by 1 order by 2 desc limit 10;
```
