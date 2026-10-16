# Data model (v1)

Goal: a precise, typed model that improves on the data model of Leffavuoro (Shady-Dev/kino). **The source of truth is [packages/model/src/schema.ts](../packages/model/src/schema.ts)** (`@pgtm/model`): Zod schemas from which the TypeScript types are inferred (`z.infer`). The fetcher produces it, and the backend ingests it. This document explains why the model looks the way it does. Field-level details live in the code.

## What we fix (findings from Leffavuoro's data, 7,643 showtimes, 2026-10-09)

| Leffavuoro                   | Problem                                                                                                                                                                                                            | Here                                                                                                                                                    |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `method: "Anniskelu · Plus"` | One field mixes formats (2D, 35 mm, IMAX), auditorium types (LUXE, Plus, iSense), alcohol service, events (premiere, preview, last screening), age recommendations ("Suositus yli 7 v") and series ("KEN RUSSELL") | Separate fields: `presentation`, `auditorium.features`, `licensed`, `tags`, `series`, `ageRecommendation`. Unrecognized values go into `unmappedLabels` |
| `lang: "EN-A, FI-S, SV-S"`   | A string that has to be parsed. `XX-S` means an unknown subtitle language                                                                                                                                          | `audio: Lang[]`, `subtitles: { kind, languages }`                                                                                                       |
| `len: "129"`                 | A number as a string                                                                                                                                                                                               | `runtimeMinutes: number`                                                                                                                                |
| `rating` + `age`             | The film's age rating and the screening's age limit are easy to mix up                                                                                                                                             | `film.rating` and `screening.ageLimit` (e.g. K-18 because of alcohol service)                                                                           |
| `price: ""`                  | An empty string means "unknown"                                                                                                                                                                                    | `price?: { amountCents, currency }`                                                                                                                     |
| Matching by `title`          | Films are matched by title                                                                                                                                                                                         | `FilmListing` (the source's own record) is separate from `Film` (canonical), with an explicit match method                                              |

## Entities

| Entity          | What                                                                                                                      | Example id           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| `Provider`      | A chain or cinema and its ticketing platform (`mycloudcinema`, `vista-ocapi`, …)                                          | `biorex`             |
| `Venue`         | A cinema: city, address, postal code and coordinates                                                                      | `biorex:venue:1`     |
| `Auditorium`    | A screen: features (`plus`, `prime`, `imax`, …) and its own age limit                                                     | `biorex:screen:57`   |
| `FilmListing`   | The source's own film record, as is; `kind` is `film` or `event`; `imdbId` when the source gives one (Kinola, Johku)      | `biorex:film:1509`   |
| `Film`          | Canonical film **from TMDB**: titles (fi/sv/en), synopses, poster, backdrop, trailers, Finnish rating, IMDb id, `ratings` | `tmdb:1185806`       |
| `Rating`        | One score on a film: `source` (`rotten-tomatoes`, `metacritic`, `imdb`, `tmdb`), `score` 0–100, `display`, `votes`        | –                    |
| `FilmCatalog`   | `films.json`: all `Film` records and the `unmatched` list                                                                 | –                    |
| `Screening`     | A showtime                                                                                                                | `biorex:show:436478` |
| `ProviderBatch` | Everything one adapter run produces: `fetchedAt`, the date `window` it covers, and warnings                               | –                    |

### Design decisions

- **Ids have the form `{provider}:{kind}:{sourceId}`.** They are unique across entity types too: BioRex film 1509 and showtime 1509 cannot be confused.
- **Times:** `startsAt` and `endsAt` are Helsinki wall-clock times with an offset (`2026-10-09T20:00:00+03:00`). `businessDate` is the cinema's business day, so a show after midnight belongs to the previous day. `fetchedAt` is UTC.
- **Languages** are lowercase ISO 639-1 codes (plus `zxx` for no dialogue). An empty `audio` means the language is unknown. `dubbed: true | false` tells a dubbed version from the original; the field is absent when unknown.
- **Subtitles** are a discriminated union: `none`, `languages`, `unknown-language` (Leffavuoro's "XX-S") or `unknown`.
- **"Unknown" is expressed by omitting the field, never with an empty string or `false`.** For example, `licensed` (alcohol service) is absent when we do not know. The TS option `exactOptionalPropertyTypes` enforces this.
- **Age limits:** the film's classification is `FilmListing.rating` (and `Film.rating` from TMDB). Limits set by the screen or the screening are `Auditorium.ageLimit` and `Screening.ageLimit`; for example, BioRex's REX screens are K-18.
- **Availability:** `available`, `few-left`, `sold-out`, `not-bookable` or `unknown`. `ticketUrl` is set only while the screening is on sale.
- **`unmappedLabels`:** source labels the parser does not recognize (e.g. `version_hfr` or `title_extension:4DX`). They are never dropped silently.
- **Validation in two stages:**
  - Raw data is checked with source-specific schemas (e.g. [src/providers/mycloudcinema/raw.ts](../packages/fetcher/src/providers/mycloudcinema/raw.ts)). A broken row becomes a warning and does not abort the run.
  - Finally, the whole result is checked against the `ProviderBatch` schema.

## Pipeline

```
fetch (I/O, polite, cached)  →  raw snapshot (stored; tests use these)
      ↓
parse (pure function: raw → ProviderBatch)  ←  unit tests against recorded responses
      ↓
validate (Zod)  →  a broken row does not abort the run: it is reported and skipped
      ↓
match (TMDB)  →  films.json, filmId on listings and screenings
      ↓
output JSON  →  pnpm ingest  →  PostgreSQL (history kept)
```

- **Fetch and parse are separate.** Parsers are pure functions, tested against recorded responses without network access. This is the biggest structural difference from Leffavuoro.
- Every adapter returns `ProviderBatch { provider, fetchedAt, window, venues, auditoriums, listings, screenings, warnings }`.
- A batch with a data-missing warning (`invalid-*`, `unknown-*`, `result-code`) is **incomplete** (`isIncomplete`): ingest stores it but infers no removed screenings from it. Neither does an empty batch with no warnings (a parser gone silent; see [database.md](database.md)). Codes: [development.md](development.md#warning-codes).
- `unmappedLabels` and `warnings` make visible what the parser does not understand yet. New values are added to the mappings together with tests.

## TMDB matching

**Posters, synopses and trailers come only from TMDB, never from cinemas.** For a film that is not matched, only the name, runtime and age rating given by the cinema are shown.

**Principle: certain or nothing.** A wrong poster is worse than a missing one. Code: [src/matching/](../packages/fetcher/src/matching/).

1. **An alias** ([config/tmdb-aliases.json](../packages/fetcher/config/tmdb-aliases.json)) always wins. `"tmdb": null` means the film is not on TMDB, so it is no longer searched for.
   **An IMDb id from the cinema** (Kinola, Johku) is looked up with TMDB's `/find` next (match method `imdb`). The cinema's **original title** is searched too and counts as a title match. Both are facts from the source, so they do not loosen the rules below.
2. **Search** (`language=fi-FI`, which also hits translated titles) runs with the title and with the part before the subtitle (`"Practical Magic: Lumotut sisaret"` → `"Practical Magic"`). A trailing qualifier in parentheses is dropped first (`"Vaiana (liveaction)"` → `"Vaiana"`). A year in those parentheses (`"NOSFERATU (1922)"`) is kept as the listing's year when the cinema states none, so a same-named film of another year is not chosen on title and runtime alone (a 2023 "Nosferatu" was, 2026-10-16; regression test in `test/matching/match.test.ts`). Details are fetched for the five most likely hits.
3. **Evidence** ([score.ts](../packages/fetcher/src/matching/score.ts)) for each candidate:
   - title: `exact` (including translations and alternative titles) / `prefix` / `none`
   - year: within current year −3…+1
   - runtime: ≤3 / ≤8 / >8 min apart
   - production countries: the cinema's Finnish country names are mapped to ISO codes (Finnkino publishes none)
   - Finnish rating: the cinema's vs. TMDB's Finnish certification (tie-breaker only).
4. **Tiers, strongest first** (`decide`):
   - `exact`: exact title, plausible year, and runtime or countries agree.
   - `prefix`: the same title with a sequel number, a brand-new film, and both runtime and countries agree.
   - `sparse`: exact title and a new film, but TMDB has neither runtime nor countries (small Finnish films).

   The strongest tier with any candidate decides. Within a tier, ties are broken by preferring the only candidate whose runtime is within 3 min, then the only one whose Finnish rating agrees ("The Furious", two 2026 films). A tie that remains means no match.

5. **A contradiction always rejects:** runtime differs by more than 8 minutes, or the countries do not overlap at all.
6. **Sibling pass:** a listing still unmatched after search is linked to the film another provider's listing was already linked to, if their titles (without qualifiers) are equal and runtimes are within 3 min. This reuses aliases across providers and covers Finnkino's missing countries.
7. **Events** (`FilmListing.kind: "event"`: operas, concerts, sports) are matched when possible but **never reported as unmatched**, since most of them are not on TMDB. **An event without a runtime is not searched at all:** an opera recording is one production among many of the same name, and a lone title hit is no evidence (Julia's "Don Giovanni (Vicenza festivaali / Mozart)" matched a 2023 Don Giovanni before this rule, 2026-10-15). Such events are aliased by hand.

Tested regression: "Ryhmä Hau: Dinoelokuva" (PAW Patrol: The Dino Movie) must **not** match "Ryhmä Hau: Mahtipennut" (2023). Another film in the same franchise is not a prefix match.

Result on 2026-10-09: BioRex 26 films (24 auto, 2 alias); Finnkino 59 listings (49 auto, 5 alias, 3 sibling, 1 opera skipped). Aliases were needed for new films without a Finnish title on TMDB, re-releases ("Autot (uudelleenjulkaisu)", "Avengers: Endgame Encore"), an extended cut, and an old concert film.

TMDB's terms require attribution in the UI: the TMDB logo and the notice "This product uses the TMDB API but is not endorsed or certified by TMDB".

## Storage

- **Now:** `pnpm pull` writes
  - the raw snapshot to `data/raw/{provider}/{timestamp}.json`
  - the normalized `ProviderBatch` to `data/normalized/{provider}.json` (with `filmId`s after matching)
  - the film catalog to `data/normalized/films.json`
  - caches under `data/cache/`: TMDB (searches 1 day, films 7 days), OMDb ratings, the Finnkino token, OSM and Nominatim (a week and a month).

  `data/` is gitignored, because the data belongs to the cinemas.

- **Then** `pnpm ingest` loads the batches into PostgreSQL, keeping history. The namespaced ids are the primary keys. See [database.md](database.md).

## Open questions

- Swedish titles (`Localized.sv`) from cinemas: which sources provide them? (TMDB already provides them for most films.)
