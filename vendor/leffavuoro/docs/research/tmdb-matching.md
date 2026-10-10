# TMDB matching: what the search can and cannot find

Probes of TMDB's search endpoint against the titles Finnish cinemas actually publish.
Written 2026-09-14. Nothing here is a rule; the open items it feeds are in
[IDEAS.md](../../IDEAS.md) and the decisions in
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md).

## Findings

**What the search index covers** (probed 2026-08-27, re-confirmed 2026-09-14). Original
title, English title, and *registered alternative titles*. A translation is not the same
field as an alternative title and is not searched. `language=fi-FI` localises the
**response** only; it does not widen the match. So a Finnish distributor title reaches a
film only when someone has registered it on TMDB as an alternative title.

**Pressure / Myrskyn ikkuna, read 2026-09-14.** 17 providers publish the film, 93
showtimes, every one with no `tmdbId`. The title is clean: no marker, no strand, no
parenthesis, so `clean()` leaves it and the search string is the published title.

| query | result |
|---|---|
| `search/movie?language=fi-FI&query=Myrskyn ikkuna` | **0 results** |
| `search/movie?query=Myrskyn ikkuna` | **0 results** |
| `movie/1318413/translations` | no `fi` entry |
| `movie/1318413/alternative_titles` | BR, US, SA, LV, PL only, no Finnish row |

So the cache entry reading `x:false` with no id is a search that ran and found nothing, not
a skipped search and not a candidate the acceptance rules rejected.

**Identity of the candidate**, checked before anything was written, because two 2026 films
are called Pressure:

| | 1318413 | 1701077 |
|---|---|---|
| runtime | 101 min | 5 min |
| votes | 390 | 0 |
| genres | Thriller, History, War, Drama | Horror, Thriller, Comedy |
| alternative titles | LV and PL both name the Normandy D-Day story | none |

All 17 providers publish 100 min and K-12. 1318413 is the film; 1701077 is a short.

**Every published Kojootti vs. ACME variant, measured 2026-09-14** against the committed
data and by searching with the string `queries()` actually produces. The earlier count of
"eight cache keys" came from a handover and understated the spread: the film is sold under
fourteen title shapes, and what separates them is the shape of the marker, not the chain.

| published shape | providers | showtimes | `clean()` gives | search |
|---|---|---:|---|---|
| `(suomeksi)`, `, suomeksi`, `SUOMEKSI`, `(orig)` | 6 | 31 | `Kojootti vs. ACME` | already matched |
| `(englanniksi)` | 3 | 18 | `Kojootti vs. ACME` | exact 1204680 |
| `ENGLANNIKSI` | 2 | 9 | `Kojootti vs. ACME` | exact 1204680 |
| `(Dub)` | 1 | 8 | `Kojootti vs. ACME` | exact 1204680 |
| `, englanniksi` | 1 | 5 | `Kojootti vs. ACME` | exact 1204680 |
| `(suomeksi puhuttu)` | 1 | 2 | `Kojootti vs. ACME` | exact 1204680 |
| `(på svenska)` | 1 | 1 | `Kojootti vs. ACME` | exact 1204680 |
| `DUB`, `ENG`, `SUB` | 2 | 10 | unchanged | **0 results** |
| `Gråben vs. ACME (på svenska)` | 1 | 2 | `Gråben vs. ACME` | 1 hit, **not exact** |

So three distinct outcomes, and the marker fix is not the whole story:

- **43 showtimes over six shapes will resolve** on the first run that re-searches them.
  They were skipped, not refused: `refresh.due` skips an entry already checked today and
  all of these were stamped `c: 2026-09-14`.
- **10 showtimes found nothing** because `DUB`, `ENG` and `SUB` are bare uppercase labels
  `clean()` does not touch. Fixed 2026-09-14 in `etiketti.py` instead, where the page's
  own language rows corroborate the label; see the entry in
  [docs/archive/2026-09-providers.md](../archive/2026-09-providers.md) once closed.
- **2 showtimes are correctly refused.** `Gråben vs. ACME` returns 1204680 as its only hit
  but not as an exact title, because TMDB has no Swedish title for the film, so the trust
  gate withholds the id. Not a marker problem and not something to alias: the identity
  evidence is a single weak hit.

## Inferences and open questions

- **The Gråben refusal is correct, not a gap.** No change to marker handling can alter it;
  only a registered Swedish alternative title would. It is deliberately not aliased: the
  identity evidence is one weak hit, which is not enough to write an id by hand.
- **The bare labels were fixed at the adapter, not in the shared cleaner.** `DUB`, `ENG`
  and `SUB` are ordinary words that can end a real title, so stripping them for every
  provider was refused. `etiketti.strip_version_suffix()` removes one only when the page
  also states a language of its own, which those two sites do. The uppercase requirement is
  what keeps "King of Dub" intact.
- **Whether a marker belongs in the title at all is the provider's choice**, and fourteen
  shapes for one film say the answer is no. Nothing here proposes normalising them further:
  each shape that matters is either handled by `clean()` or corroborated at an adapter.
- **`gilda.py` published `original` with the strand attached** on six shows. Fixed
  2026-09-14 in `strands.apply()`, which now splits both fields with the same exact list
  and never copies the display title over a real original-language one.

## Status and next step

All four changes are published and verified on show records, not on the log:

| change | outcome |
|---|---|
| alias 1318413 | **93/93** showtimes, 35 Finnkino (local run) and 58 cloud, 2026-09-14 |
| `etiketti` label strip | **no ENG, SUB or DUB title left**; those showtimes carry 1204680 |
| `strands` original split | **no `original` carries a strand** |
| marker re-search | **151/153** showtimes carry 1204680, cloud run `3d9a63c6` 2026-09-15 05:21 UTC |

Nothing here is open. The remaining 2 are Gråben vs. ACME (på svenska): searched on that
run, one hit, refused as not an exact title because TMDB holds no Swedish title for the
film. That is the trust gate working and not a defect to fix; it would take a registered
Swedish alternative title on TMDB, which is not ours to add. Deliberately not aliased,
since one weak hit is not identity evidence.

## The fi-FI response substitutes the original title, measured 2026-09-19

Read against the live API with the pipeline's own `search()` and `pick()`. `language=fi-FI`
localises the response, and where TMDB holds no Finnish translation the response's `title`
comes back as the **original** title, not as the English one. So a cinema publishing
TMDB's own English title fails the exact test just as a Finnish distributor title does.

| published | fi-FI `title` | en-US `title` |
|---|---|---|
| The Time That Remains | الزمن الباقي | The Time That Remains |
| Tiger on the Beat | 老虎出更 | Tiger on the Beat |
| Faust | Faust - Eine deutsche Volkssage | Faust |
| Berliinin sankari (original Berlin Hero) | Der Held vom Bahnhof Friedrichstraße | Berlin Hero |

This is most of the 33-entry weak list of the run committed at `73a075acc`. Twenty-four
keys were aliased by hand on 2026-09-19 rather than changing the search, and the reasoning
per id is in `scripts/providers/tmdb-aliases.json`'s own comments.

**What comparing the en-US title in `pick()` would do**, measured over all 36 weak cache
entries by replaying the searches: ten become exact with no alias. It is not free. One of
the ten becomes exact on a *different* id than the weak candidate, `black magic rites` on
59912 where the cache holds 331647, and an exact match is trusted and publishes, so the
change would ship an unchecked id. 59912 is in fact the right film, which is the point:
nothing in the mechanism checked it.

**Shipped 2026-09-19 with that case as its bound.** The second search runs only where the
fi-FI pass matched nothing exactly, fills an empty or weak slot, and never replaces a
cached id. An exact en-US hit on a *different* id than the weak candidate is written to
stderr and left for the alias file rather than published, so `black magic rites` is named
and not shipped. Measured on the committed weak list the day it went in: 5 titles asked, 0
settled, 0 disagreed, the weak list unchanged at 5, because the ten cases above were
aliased by hand the night before. The record is in
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md).

## The Gråben refusal stands, and a sibling key does not fall under it

Re-read 2026-09-19. TMDB still registers no Swedish title for 1204680, so the premise of
the 2026-09-14 refusal holds and `gråben vs acme på svenska` is still not aliased.

What is new is a second key at a different cinema. Bio Savoy Mariehamn publishes the film
as `GRÅBEN vs ACME (COYOTE vs ACME)`, and its own film page carries the IMDb id
`tt1756855`, which `/find?external_source=imdb_id` resolves to 1204680 and to nothing
else. That is identity evidence from the cinema rather than from a weak hit, which is the
one thing the refusal says is missing, so that key is aliased and the `(på svenska)` one
is not. The two are different keys and the distinction is the evidence, not the spelling.

The lesson worth keeping is about verification rather than matching: for a day the fix was
indistinguishable from a broken one, because a skipped entry and a failed one look the same
in the cache and both are simply absent from the log. What separated them was the cache
date against the run's date, plus the log's own weak-match and no-match lists.

## The four largest unmatched rows, measured 2026-09-19

247 showtimes over 77 titles carried no `tmdbId` at this tree. The four largest, searched
once each against `search/movie` and `search/tv` in `fi-FI`:

| title | rows | provider | movie hits | tv hits |
|---|---:|---|---:|---:|
| Asteroid Quest | 64 | Heureka | 0 | 0 |
| The Stellars - Tähtijengi | 50 | Heureka | 0 | 0 |
| Salatut elämät 5000 -erikoisnäytös | 32 | Finnkino | 0 | series 14610 |
| Ooppera: 20 Years of the Met in Cinemas | 14 | Finnkino | 1703617 | 0 |

Three are real absences and one is an alias.

- **The two Heureka rows are planetarium shows**, and TMDB holds no record of either under
  its own name or under `Tähtijengi`. Nothing to alias, which is the state the Heureka
  poster entry in `IDEAS.md` already describes: no weak match, so no wrong poster.
- **`Salatut elämät 5000 -erikoisnäytös`** is an episode of a television series screened in
  cinemas. TMDB holds the series, 14610, and no film. This repository matches
  `/movie/{id}`, so a series id would be the wrong kind of record and none is written.
- **The Met gala is a real film record** with a poster, registered with the number spelled
  out, which is why a search on the published title finds nothing. Aliased to 1703617.
  It is a Finnkino row, so `fetch_data.py` applies it on the next local run rather than
  `enrich_tmdb.py` on a cloud one.

**Method note.** The worklist in `run-enrich.log` and the set of showtimes carrying no
`tmdbId` are not the same set: the Met row was never in the log's "no TMDB match" list,
because the log is written by the cloud pass and the row belongs to the local one. Count
rows out of `data/area-*.json` when sizing this work, not out of the log.
