# Command-line tools

Every tool also prints its usage with `--help`. Commands run from the repository root.

## `pnpm pull`: fetch showtimes

Fetches every provider (or the selected ones), writes raw snapshots to `data/raw/{provider}/` and normalized batches to `data/normalized/{provider}.json`, then matches films to TMDB (`data/normalized/films.json`).

| Option              | Default           | Meaning                                                                                                                                            |
| ------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--provider ID`     | all               | A provider id (`finnkino`, `biorex`, `kinomyyri`, …) or a platform name (`nexxo`, `etiketti`, `kinola`, `johku`) for all of its sites. Repeatable. |
| `--from YYYY-MM-DD` | today in Helsinki | First programme day.                                                                                                                               |
| `--days N`          | 7                 | Number of programme days, 1–90.                                                                                                                    |
| `--venue ID`        | all               | Only these venues, by source id or slug. Needs exactly one provider. Repeatable.                                                                   |
| `--out DIR`         | `data/`           | Output directory.                                                                                                                                  |

- Six providers run at a time, each paced per host. All of them take about two minutes.
- If one provider fails, the others still run and the command exits non-zero. Matching runs when at least one provider succeeded.
- Finnkino opens a visible Chrome window for a few seconds when its 12-hour token needs renewing.
- Needs `TMDB_APIKEY`. `OMDB_APIKEY` adds Rotten Tomatoes, Metacritic and IMDb scores.

## `pnpm match`: re-run TMDB matching

Re-matches `data/normalized/*.json` without fetching, e.g. after editing `config/tmdb-aliases.json`. Option: `--out DIR`.

## `pnpm ingest`: load into PostgreSQL

Upserts `data/normalized/*.json` into the database and marks screenings that disappeared from a complete batch as removed. Option: `--dir DIR`. Prints inserted, updated and removed counts per provider.

## `pnpm migrate`

Applies pending migrations. `--down` reverts one step; `--test` targets the test database. After adding a migration, run `pnpm db:types`.

## `pnpm showtimes`: search the programme

Reads the database. With a film name, fuzzy-searches films by any title (Finnish, Swedish, English, original, or as the cinema lists it) and prints each match with its screenings. Without one, prints every screening that matches the other options, in start order.

| Option                                    | Default           | Meaning                                                                                                          |
| ----------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------- |
| `--movie NAME`, `-m`, or a plain argument | none              | The film to look for.                                                                                            |
| `--date YYYY-MM-DD`                       | today in Helsinki | Programme day.                                                                                                   |
| `--after HH:MM`                           | none              | Shows starting at or after this time. Shows after midnight are kept.                                             |
| `--before HH:MM`                          | none              | Shows starting before this time. Earlier than `--after` means the next morning (`--after 22:00 --before 02:00`). |
| `--ratings`                               | off               | Show Rotten Tomatoes, Metacritic, IMDb and TMDB scores.                                                          |
| `--min-rt N`                              | none              | Only films with at least this Rotten Tomatoes score (0–100). Turns on `--ratings`.                               |
| `--min-imdb N`                            | none              | Only films with at least this IMDb rating (0–10). Turns on `--ratings`.                                          |
| `--provider ID`                           | all               | Provider ids or platform names. Repeatable.                                                                      |
| `--near LAT,LON`                          | none              | Only venues within `--radius` of a point; adds a distance column. A map link's `@60.17,24.94` works too.         |
| `--address TEXT`                          | none              | Like `--near`, geocoded with OpenStreetMap Nominatim (cached in `data/cache/geocode/`).                          |
| `--here`                                  | off               | Like `--near`, from this machine's location (see below).                                                         |
| `--radius KM`                             | 25                | Radius for `--near`, `--address` and `--here`.                                                                   |
| `--links`                                 | off               | Print ticket links.                                                                                              |
| `--min-score 0..1`                        | 0.5               | Fuzzy-match threshold for film names. Lower it for short or misspelled names.                                    |

Ratings are opt-in on purpose: some people do not want to know critics' verdicts before seeing a film. A ratings filter leaves out films that have no such score.

Examples:

```sh
pnpm showtimes --here --after 18:00                # what's on near me tonight
pnpm showtimes --here --date 2026-10-13 --before 15:00
pnpm showtimes --here --after 18:00 --min-rt 85    # something good tonight
pnpm showtimes odyssey --address "Hämeenkatu 1, Tampere" --radius 5 --links
pnpm showtimes --provider nexxo --date 2026-10-14
```

### `--here` on macOS

`--here` uses [CoreLocationCLI](https://github.com/fulldecent/corelocationcli) when it is installed, for a position from Wi-Fi:

1. `brew install --cask corelocationcli`
2. Run `CoreLocationCLI --json` once. Allow it in System Settings → Privacy & Security, first under Gatekeeper ("Open Anyway"), then under Location Services.
3. Keep Wi-Fi on.

Without it, `--here` falls back to IP geolocation: it sends your public IP address to ipinfo.io, and the result is often only your ISP's town.

## `pnpm venues:locate`: coordinates for venues

Suggests OpenStreetMap cinemas for venues without coordinates, and flags venues more than `--max-meters` (300) from any OSM cinema. It reads `data/normalized/*.json` (`--dir`), so run `pnpm pull` after editing a `sites.ts`. It only prints suggestions: check each one on openstreetmap.org before pasting it.

`--address "Sahakatu 2, 32700 Huittinen"` geocodes addresses with Nominatim instead (repeatable), for halls OSM does not list as cinemas.

## API

`pnpm api:dev` serves the HTTP API on http://127.0.0.1:3000 with reload: docs at `/docs`, OpenAPI at `/openapi.json`. `pnpm api:up` runs it in Docker. See [api.md](api.md).
