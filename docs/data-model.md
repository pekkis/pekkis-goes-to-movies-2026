# Data model (v1)

Goal: a precise, typed model that improves on the data model of Leffavuoro (Shady-Dev/kino). **The source of truth is [src/model/schema.ts](../src/model/schema.ts)**: Zod schemas from which the TypeScript types are inferred (`z.infer`) and from which a JSON Schema can be generated (`z.toJSONSchema`). This document explains why the model looks the way it does. Field-level details live in the code.

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

| Entity          | What                                                                                                           | Example id           |
| --------------- | -------------------------------------------------------------------------------------------------------------- | -------------------- |
| `Provider`      | A chain or cinema and its ticketing platform (`mycloudcinema`, `vista-ocapi`, …)                               | `biorex`             |
| `Venue`         | A cinema: city, address, postal code and coordinates                                                           | `biorex:venue:1`     |
| `Auditorium`    | A screen: features (`plus`, `prime`, `imax`, …) and its own age limit                                          | `biorex:screen:57`   |
| `FilmListing`   | The source's own film record, as is                                                                            | `biorex:film:1509`   |
| `Film`          | Canonical film **from TMDB**: titles (fi/sv/en), synopses, poster, backdrop, trailers, Finnish rating, IMDb id | `tmdb:1185806`       |
| `FilmCatalog`   | `films.json`: all `Film` records and the `unmatched` list                                                      | –                    |
| `Screening`     | A showtime                                                                                                     | `biorex:show:436478` |
| `ProviderBatch` | Everything one adapter run produces, including warnings                                                        | –                    |

### Design decisions

- **Ids have the form `{provider}:{kind}:{sourceId}`.** They are unique across entity types too: BioRex film 1509 and showtime 1509 cannot be confused.
- **Times:** `startsAt` and `endsAt` are Helsinki wall-clock times with an offset (`2026-10-09T20:00:00+03:00`). `businessDate` is the cinema's business day, so a show after midnight belongs to the previous day. `fetchedAt` is UTC.
- **Languages** are lowercase ISO 639-1 codes. An empty `audio` means the language is unknown. `dubbed: true | false` tells a dubbed version from the original; the field is absent when unknown.
- **Subtitles** are a discriminated union: `none`, `languages`, `unknown-language` (Leffavuoro's "XX-S") or `unknown`.
- **"Unknown" is expressed by omitting the field, never with an empty string or `false`.** For example, `licensed` (alcohol service) is absent when we do not know. The TS option `exactOptionalPropertyTypes` enforces this.
- **Age limits:** the film's classification is `FilmListing.rating` (and `Film.rating` from TMDB). Limits set by the screen or the screening are `Auditorium.ageLimit` and `Screening.ageLimit`; for example, BioRex's REX screens are K-18.
- **Availability:** `available`, `few-left`, `sold-out`, `not-bookable` or `unknown`. `ticketUrl` is set only while the screening is on sale.
- **`unmappedLabels`:** source labels the parser does not recognize (e.g. `version_hfr` or `title_extension:4DX`). They are never dropped silently.
- **Validation in two stages:**
  - Raw data is checked with source-specific schemas (e.g. [src/providers/biorex/raw.ts](../src/providers/biorex/raw.ts)). A broken row becomes a warning and does not abort the run.
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
output JSON (+ JSON Schema)
```

- **Fetch and parse are separate.** Parsers are pure functions, tested against recorded responses without network access. This is the biggest structural difference from Leffavuoro.
- Every adapter returns `ProviderBatch { provider, venues, auditoriums, listings, screenings, warnings }`.
- `unmappedLabels` and `warnings` make visible what the parser does not understand yet. New values are added to the mappings together with tests.

## TMDB matching

**Posters, synopses and trailers come only from TMDB, never from cinemas.** For a film that is not matched, only the name, runtime and age rating given by the cinema are shown.

**Principle: certain or nothing.** A wrong poster is worse than a missing one. Code: [src/matching/](../src/matching/).

1. **An alias** ([config/tmdb-aliases.json](../config/tmdb-aliases.json)) always wins. `"tmdb": null` means the film is not on TMDB, so it is no longer searched for.
2. **Search** (`language=fi-FI`, which also hits translated titles) runs with the full title and with the part before the subtitle (`"Practical Magic: Lumotut sisaret"` → `"Practical Magic"`). Details are fetched for the five most likely hits.
3. **Evidence** ([score.ts](../src/matching/score.ts)) for each candidate:
   - title: `exact` (including translations and alternative titles) / `prefix` / `none`
   - year: within current year −3…+1
   - runtime: ≤3 / ≤8 / >8 min apart
   - production countries: the cinema's Finnish country names are mapped to ISO codes.
4. **Tiers, strongest first** (`decide`):
   - `exact`: exact title, plausible year, and runtime or countries agree.
   - `prefix`: the same title with a sequel number, a brand-new film, and both runtime and countries agree.
   - `sparse`: exact title and a new film, but TMDB has neither runtime nor countries (small Finnish films).

   The strongest tier with any candidate decides. Two candidates in the same tier means no match.

5. **A contradiction always rejects:** runtime differs by more than 8 minutes, or the countries do not overlap at all.

Tested regression: "Ryhmä Hau: Dinoelokuva" (PAW Patrol: The Dino Movie) must **not** match "Ryhmä Hau: Mahtipennut" (2023). Another film in the same franchise is not a prefix match.

Result on 2026-10-09: of BioRex's 26 films, 24 matched automatically and 2 through an alias. The aliased ones were new films that do not yet have a Finnish title on TMDB.

TMDB's terms require attribution in the UI: the TMDB logo and the notice "This product uses the TMDB API but is not endorsed or certified by TMDB".

## Storage

- **Now:** `pnpm pull` writes
  - the raw snapshot to `data/raw/{provider}/{timestamp}.json`
  - the normalized `ProviderBatch` to `data/normalized/{provider}.json` (with `filmId`s after matching)
  - the film catalog to `data/normalized/films.json`
  - the TMDB cache to `data/cache/tmdb/` (searches 1 day, films 7 days).

  `data/` is gitignored, because the data belongs to the cinemas.

- **Later:** PostgreSQL. The entities and namespaced ids are designed to work directly as primary keys.

## Open questions

- Swedish titles (`Localized.sv`) from cinemas: which sources provide them? (TMDB already provides them for most films.)
