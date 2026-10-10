# Pekkis goes to movies

All Finnish cinema showtimes on one site. Find a film by time and place ("what's on in Tampere tonight?") or start from the film ("where and when can I see X?").

For now the repository contains the data collection: BioRex and Finnkino showtimes are fetched, normalized into a typed model, matched to films on TMDB and stored in PostgreSQL with history. The user interface comes later.

## Usage

You need Node 24, pnpm 12, Docker, Google Chrome (for Finnkino) and a [TMDB](https://www.themoviedb.org/settings/api) API Read Access Token.

```sh
pnpm install
cp .env.example .env   # add TMDB_APIKEY
pnpm db:up             # PostgreSQL in Docker
pnpm migrate           # create the schema
pnpm pull              # fetch BioRex and Finnkino, normalize, match to TMDB → data/
pnpm ingest            # load data/ into PostgreSQL
pnpm showtimes odyssey # any film, fuzzily: info + today's screenings in all cinemas
pnpm check             # types, lint, formatting and tests (needs the database)
```

More: [AGENTS.md](AGENTS.md) (layout and conventions), [docs/data-model.md](docs/data-model.md), [docs/data-sources.md](docs/data-sources.md) and [docs/database.md](docs/database.md).

## Data and fair use

- Showtime data belongs to the cinemas. It is not committed (`data/` is gitignored). Test fixtures contain a small, trimmed sample.
- Sources are read rarely and at a measured pace, with an identifiable User-Agent. Ticket purchase and payment APIs are never called.
- If you represent a cinema and would rather not be included, open an issue and we will remove the source.

## Acknowledgements

- [Leffavuoro / Shady-Dev/kino](https://github.com/Shady-Dev/kino) (AGPL-3.0) served as a map of the ticketing platforms.
- Film data and images come from [TMDB](https://www.themoviedb.org/).

  This product uses the TMDB API but is not endorsed or certified by TMDB.

## License

    Pekkis goes to movies
    Copyright (C) 2026  Pekkis goes to movies contributors (Mikko "Pekkis" Forsström et al)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

Full text: [LICENSE](LICENSE). The license covers the code, not the cinemas' or TMDB's data.
