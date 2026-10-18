# Classification

How we classify screenings and films: which facts we keep, where each comes from, and what is still to do. The goal is data as structured as the sources allow, for the long term. Facts marked [V] were checked first-hand against the data (survey of 2026-10-16: 102 providers, about 6,000 screenings over 7 days); [A] marks assumptions.

## Layers

1. **Raw labels** (`Screening.labels`, `screenings.labels` jsonb): every label a source printed, verbatim, as `{ source, text }` (`etiketti.tag`, `nexxo.showType`, `kinola.program`, `kinola.note`, `title.prefix`, `title.note`, `row.note`, `block.note`, `post.note`). Never lost, so a better classifier can be run over history later. Internal: not in the API.
2. **Classified facets:** closed vocabularies in the model (`@pgtm/model`): tags, availability, audio, subtitles, projection, age limit, the bar flag, series ids.
3. **Derived facets:** computed from other facts at pull time (`deriveTags` in `providers/labels.ts`), never scraped.
4. **Film enrichment:** TMDB on the canonical film (genres, collections, languages, release dates), later more (see the roadmap).

`unmappedLabels` is the subset of raw labels nothing understood: a to-do list, shown in the `pull` output.

## The label table

`LABELS` in [labels.ts](../packages/fetcher/src/providers/labels.ts) is the one place where a Finnish label phrase gets its meaning. The same phrase means the same thing on every platform. A `LabelRule` can set:

| Field                  | Meaning                                                           |
| ---------------------- | ----------------------------------------------------------------- |
| `tags`                 | screening tags (below)                                            |
| `series`               | a series name, resolved against the registry                      |
| `event`                | the listing is not a film (opera, ballet, concert)                |
| `licensed`, `ageLimit` | bar service, and the age limit it brings ("Anniskelunäytös K18")  |
| `availability`         | "Kiirehdi" → `few-left`, "Loppuunmyyty" → `sold-out`              |
| `audio`, `dubbed`      | "Puhuttu suomeksi" → `fi`, dubbed                                 |
| `subtitles`            | `none` or a language ("Ei tekstitystä")                           |
| `projection`           | `35mm`, `70mm`                                                    |
| `{}`                   | known and meaningless ("Erikoisnäytös"): not reported as unmapped |

- `findLabel(text, ...tables)` matches exactly, then without regard to case, surrounding punctuation and spacing (`labelKey`); tables are consulted in order, so a site's own rules (`tags`, `showTypes`, `programs`, `titlePrefixes`) come before `LABELS`.
- `labelEffects(rules)` merges several rules: tags and series deduplicated, single facts from the last rule that states one.
- Adapters on the table [V]: eTiketti (tags and title prefixes), Nexxo (show types), Kinola (programs and notes), Kaarre (row notes), Kino Rio (block notes), Kuvakukko (title notes), Pajakkakino (post notes); every adapter using `splitTitlePrefix`. Freehand parsers with their own small regexes move onto it as they are touched.

## Screening facets

| Facet         | Values                                                                           | Main sources                                                   |
| ------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| presentation  | `projection` digital/35mm/70mm/16mm, `dimension` 2d/3d, `formats` (IMAX, 4DX, …) | platform flags, title markers, labels                          |
| language      | `audio` (ISO 639-1, `zxx` no dialogue), `dubbed`, `subtitles`                    | platform fields, title markers ("(DUB)"), labels               |
| occasion      | tags `premiere`, `preview`, `last-screening`, `classic`, `event-cinema`          | labels, title prefixes, platform flags                         |
| audience      | tags `kids`, `baby`, `senior`                                                    | labels ("Vauvakino", "Seniorinäytös")                          |
| extras        | tags `guest`, `no-dialogue`                                                      | labels ("Tekijävierailu"); `no-dialogue` is derived from `zxx` |
| accessibility | tags `accessible`, `captions`, `audio-description`                               | labels ("Kuvaileva tekstitys", "Kuvailutulkkaus")              |
| price         | tags `free`, `discount`; `price`                                                 | labels ("Vapaa pääsy", "Edullinen päivänäytös"), price fields  |
| bar service   | `licensed`, and `ageLimit` K-18 when the label says so                           | platform icons, "Anniskelunäytös (K18)"                        |
| availability  | `available`, `few-left`, `sold-out`, `not-bookable`, `unknown`                   | seat counts, labels                                            |
| series        | ids into the series catalogue (below)                                            | labels, strand fields                                          |

`TAG_GROUPS` in the model maps each tag to its facet (occasion, audience, extras, accessibility, price); the API and the database keep `tags` as one flat array.

## Series

A series is something a screening belongs to beyond the film: a strand, festival, retrospective, club, distributor series or theme week (`SeriesKind`).

- **The registry** [config/series.json](../packages/fetcher/config/series.json): hand-maintained like `tmdb-aliases.json`. Each entry has a stable id (`kuvi-aluesarja`), a display `name`, a `kind`, `aliases` (other spellings: "Kuvin aluesarja", "Kuvi"), and a `note`. Validated by Zod in [src/series/registry.ts](../packages/fetcher/src/series/registry.ts) when loaded.
- **Provider strands:** a source field that is a strand by definition (Nexxo show types, Kinola programs, Vista `EventSeries`, Regina's themes, Kino-Kuva's headings) keeps any name the registry does not know as that provider's own strand, id `{provider}/{slug}` (`kinoregina/ken-russell`), kind `strand`. The registry can adopt one later with an alias.
- **Free text never becomes a series.** A label of mixed meaning (an eTiketti tag) becomes a series only if the registry knows it; otherwise it is reported in `unmappedLabels`. Before this, `series` held availability ("Kiirehdi"), audio ("Puhuttu suomeksi"), projection ("35mm") and more [V].
- **Series in titles:** a registered name works as a title label on every site, with no site config: "Kuukauden pohjoismainen: Knyckertz …" (Kino Iiris), "Geel + Cézanne on Art (Taidekaupungin elokuvajuhlat)" (Bio Säde), "… – Minikino". The name is stripped from the title, so the film can match TMDB, and becomes the series [V, 2026-10-16]. Site title rules and `LABELS` are consulted first.
- **A word that means a series at one cinema only** goes into that site's config, not `LABELS` or the registry: Cinema Niagara's tag "Puola" is its special series "PUOLALAISIA ELOKUVIA" (`tags` in `etiketti/sites.ts`; a provider strand), while elsewhere "Puola" could as well be a language [V, 2026-10-16]. Its "Cinemadrome" tag (a night of genre classics, 2026-10-24) is configured the same way.
- **Resolution** happens in `pull` (`resolveSeries`, after the parser): screening `series` become ids and the batch lists the catalogue entries it uses (`ProviderBatch.series`). Ingest upserts them into the `series` table; the API returns display names, so its shape did not change.
- Retrospectives at Regina ("KEN RUSSELL", "SUSAN SARANDON") are still provider strands of kind `strand`; promoting them is a registry edit.

## Listing and film facets

- **Kind:** `film` or `event`. An event type (opera, ballet, theatre, concert, album listening) is phase 3.
- **Age rating:** the cinema's own rating first (on 851 of 967 listings), TMDB's Finnish certification as a fallback (only 60 of 151 films) [V].
- **Genres:** TMDB's 17 genres on matched films are canonical. Cinemas' genres (551 listings) are mixed Finnish and English free text: kept raw on the listing, not a facet.
- **From the TMDB data we already cache** [V]: collections (25 of 151 films), spoken and original language, Finnish release dates (96).

## Derived facets

Computed, never scraped:

- `no-dialogue`: the screening's only audio is `zxx` (implemented).
- domestic: FI among production countries (to do).
- classic: years since release (to do; some cinemas already label it).
- new release: Finnish release date within a few weeks (to do).

## Roadmap

- **Phase 1 (done):** this document; `LABELS`; raw labels; the series registry and resolution; the `series` table; fixes found by the survey (`jp` → `ja`, K-18 on bar screenings at eTiketti and Kinola, Kuvakukko's guest and free notes, last screenings at Pajakkakino and Kino Rio, Kaarre's "kiirehdi", `no-dialogue`).
- **Phase 2:** one shared age-rating parser for every adapter (there are 41 rating tables); TMDB credits (directors), keywords, collections, external ids (IMDb, Wikidata); the Finnish certification as a fallback rating.
- **Phase 3:** KAVI content descriptors (several cinemas show them as images we drop: Marita, Pajakkakino, Kino-Kuva, Matin-Tupa); event types; cinema genres mapped to TMDB genres for unmatched listings; Wikidata and Elonet.

## Open questions

- Marathons and double features: an occasion tag, or a series?
- Food screenings (Leffabrunssi, Kahvikino, "3 Kaveria jäätelönäytös"): strands now; an `extras` tag as well?
