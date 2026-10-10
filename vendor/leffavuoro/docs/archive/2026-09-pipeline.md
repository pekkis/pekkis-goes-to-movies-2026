# Archive: pipeline decisions, to 2026-09-14

Dated decision records moved out of `IDEAS.md` on 2026-09-15, so that file can be a short
index of open work rather than a 4,937-line history. Each entry is the record as it was
written, heading unchanged, so a reference that used to name a heading in `IDEAS.md`
resolves here against the same text. Everything here is closed: built, reversed, or
decided against, and the entry says which.

The generic half: `scripts/providers/run.py`, `common.py`, the TMDB enrichment passes,
the shared price and poster steps, and the rules every adapter is held to. Per-provider
records are in [2026-09-providers.md](2026-09-providers.md).

Active and deferred work is in [IDEAS.md](../../IDEAS.md). The accepted working rules are
in [CLAUDE.md](../../CLAUDE.md), the visual contract in [DESIGN.md](../../DESIGN.md), and
the investigations these decisions rest on under [docs/research/](../research/).

---

## Token automation — how it works now
The token is fetched fresh at run time and used within seconds, so nothing has to survive
the 12 h JWT expiry.

- The local wrapper: get token → `scripts/fetch_data.py` → `scripts/providers/run.py` for
  the local modules → push data, posters and logs, then dispatch the cloud workflow.
- Both fetchers run inside a `set +e` window with `echo "exit=$?"` appended to their own
  log, so one failure cannot abort the push or take fresh Finnkino data with it.
- The wrapper hard-resets the clone to `origin/main` before every run, so a manual edit
  inside `repo/` is destroyed at the next slot. Test edits belong in a separate clone.
- The TTL guard runs before `cd repo`, so a bad Finnkino token aborts the whole script.
- No cloud fallback. `.github/workflows/fetch.yml` was deleted 2026-08-27: a runner cannot
  obtain a token (www.finnkino.fi answers Cloudflare 403 to datacenter IPs) and the stored
  `FINNKINO_SECRET` was stale within 12 hours, so it had failed on every push for two days,
  which hid the run that broke. A stale Finnkino shows in the app's own health line.
- `get_token()` reads `FINNKINO_TOKEN` from the environment first; that path must not be
  removed. The direct-fetch fallback only works from an ordinary connection.

Machine setup, schedule, token retrieval and credentials live in local private notes.
Superseded: pushing the token into repository secrets and rotating it.

### Synopses and enrichment
`scripts/providers/enrich_tmdb.py` runs last in the cloud workflow and merges into
`data/films-extra.json` — it never overwrites text a provider already supplied.

Priority: the cinema's own text (Finnkino `films.json`, or provider page text merged via
`scripts/providers/synmerge.py`) > TMDB Finnish > TMDB English.

- `films-extra.json` is keyed by normalised title. **Three implementations of that
  normalisation must agree**: `enrich_tmdb.norm()`, `synmerge.norm()` and `normTitle()` in
  index.html. A mismatch fails silently with no synopsis and no error.
- The two Python ones strip `_` explicitly (`[^\w\s]|_`). `\w` counts the underscore as a
  word character, `\p{L}\p{N}` in the client does not, so a title containing one would
  have keyed two different ways and lost its synopsis with nothing in the log. No title
  has used one yet — checked at the change, 90 keys in each cache, zero underscores — so
  this is a latent divergence closed before it fires, not a bug fix.
- Synopses live in that one file rather than on each show: a 300-char synopsis repeated
  across BioRex Tripla's 158 showtimes would add ~50 kB to a single venue file.
- Provider helper fields `_syn` / `movieUrl` are stripped before area files are written.
- BioRex fetches ~28 film pages per run (0.4 s apart) for synopsis, runtime and genres.
- Kinoset's API `description` is mostly empty and it only tags genres on some shows, so
  those fall back to TMDB.
- **Match on the title, not on TMDB's popularity order** (2026-08-27). `hits[0]` sent
  Orion's "Mother" to the poster for "Mother Mary": TMDB search sorts by popularity, so
  a short generic title lands on whatever is trending. `pick()` prefers a hit whose
  `title` or `original_title` normalises exactly to the query and only then falls back to
  the popularity order, because a Finnish distributor title often matches nothing exactly
  and a weak match still beats no film. Fallbacks are named in `run-enrich.log` as
  **weak match**, which is the list to read when a poster looks wrong.
- **A title can carry two strand prefixes, and `split()` takes one per call.** Orion
  published "Espoo Ciné: Artist in Focus: Mare's Nest": the festival, then its section.
  The adapter's own `split_strand` took "Espoo Ciné" and stopped, so the section stayed
  in the title, TMDB matched nothing and the film lost its poster, rating, trailer, genre
  ids and merge-by-id — all four, not just the poster that made it noticeable.
  `run.py` applies `strands.apply` centrally *after* the adapter, so a second known
  prefix does come off, which is why adding "artist in focus" to `EVENT_PREFIXES` is the
  whole fix here. A provider that does not also split in its own adapter gets one pass
  only and would still need a loop. Not looping in `split()` on purpose: one call, one
  prefix keeps the exact-list guarantee easy to reason about, and two-prefix titles are
  so far a single showtime.
- **A programme is not a film and will never match.** "Follow The Plants" (Orion, a
  curated multi-artist assembly) and the Gilda playback nights sit in the no-match list
  permanently and correctly. The list is for finding *missed* films; entries that belong
  there are not a backlog.
- **Both passes must log the titles that match nothing, not just the weak ones.**
  `fetch_data.py` printed weak matches and held-back ratings but never a no-match list, so
  "Ryhmä Hau: Dinoelokuva" sat with an empty id for a day — no rating, no genres, a clean
  log. A weak match is at least visible; a missing one was not. Both passes now print it.
- **Search with `language=fi-FI`, or the exact-title test can never fire on a Finnish
  title** (2026-08-27). Without it TMDB answers in English, so `pick()` compared
  "Autofiktio" against "Bitter Christmas", "Kuopus" against "The Little Sister" and
  "Kummisetä osa II" against "The Godfather Part II" — and wrote all three off as weak
  matches. The ids were right the whole time; TMDB has registered Finnish titles and
  had matched them. The cost of the mistake was not a wrong film but a missing one:
  a weak entry gets no `tmdbId` and no `gids`, so 29 films were excluded from cross-chain
  merging and from genre-based filtering for no reason.
  `language` localizes the response, it does not widen which titles are searched, so this
  is presentation rather than matching — the fix is one query parameter, not 29 aliases.
  **Verify before writing aliases**: a "weak match" line is a claim about the comparison,
  not about the film.

### The score ring (2026-08-27)
The score is a ring: arc length for the glance, the number inside, the vote count beside
it, since 7.1 from 41 votes and 7.1 from 15 000 are different claims. A rating under
`VOTE_SOLID` = 25 votes is dimmed rather than hidden.

Two departures from TMDB's widget: one hue, not green/amber/red, since colour is spent on
chain identity and red-vs-green is the classic colourblind failure; and not a copy of
their component, which would imply an endorsement. IMDb's ratings dataset names
"where/what/how to watch applications" as a licensed commercial use, so it is out; Trakt
and Leffatykki are unexplored alternatives.

- A rating needs votes: `vote_average` written straight through showed ★10 on a festival
  premiere with three votes. Ratings come from the movie detail call and are stored only
  above `MIN_VOTES` = 25; the count lives in the cache as `n`, held-back ratings are
  logged. The cache was rebuilt once when `pick()` landed.
- The search loop tries every candidate until one matches exactly and keeps the first
  hit as the fallback: "Die Hard 2 - Die Harder" returned *Die Hard* on candidate 1 while
  candidate 2 matched exactly.
- Film identity across chains is the TMDB id: BioRex publishes "Mutiny", Finnkino "Mutiny
  - Lavastettu syylliseksi". Both passes write `tmdbId`, only for an exact match (`x` in
  both caches), since a weak id would fold two films into one. Dropping everything after a
  dash in `mergeKey()` was rejected: it would merge "Mission: Impossible - Dead Reckoning"
  into "Mission: Impossible".
- Reissue markers belong in `mergeKey()`: `(re-release)`, `(uudelleenjulkaisu)`, `(uusi
  kopio)` alongside `(suomeksi)`, and `PAREN_NOISE` gained `uudelleenjulkaisu`.
- Name merging is still required for films where one chain got no exact match.
- Finnkino publishes the bar-screening attributes; `EVENT_ATTRS` keeps `Annisk_K18`,
  `Anniskelu` and `EventCine`, and `Annisk_K18` sets `age`. Dropped attributes are logged.
- The release-year filter defeats aliases and reissues: `Autot (uudelleenjulkaisu)`
  carries the reissue year. The search retries without the year whenever it produced no
  exact match, and never applies a year to an alias search string.
- `fetch_data.py` needs candidate queries too: `_queries()` yields the de-noised title,
  the raw title, then the head before a dash. Never before a colon, which would search
  "Mission" for "Mission: Impossible - Dead Reckoning". `enrich_tmdb.queries()` still
  splits on a colon, which is worth watching.

### Strand prefixes are split off centrally (2026-08-27)
`scripts/providers/strands.py` owns the exact list and the split. `enrich_tmdb.clean()`
imports the list for the TMDB search; `run.py` applies the split to every adapter's shows
and `fetch_data.py` to Finnkino's, so a strand goes to `method` and the bare film title
stays in `title`. Only `orion.py` did this before, which left Gilda selling
"Seniorikino: Hetki Ennen Valoa" as a film of its own — fragmented from the plain title,
unmatchable on TMDB, and sharing an initials tile with every other Seniorikino screening.

- **Exact list, never a `^\w+:` pattern.** In one day's data the colon prefixes are
  "Spider-Man:" ×443, "Ryhmä Hau:" ×272, "Insidious:" ×159 against "Seniorikino:" ×4 and
  "Pieni elokuvakerho:" ×3. A pattern would behead every franchise in the schedule.
- Real strands are rare (about 10 showtimes a day, Gilda and Riviera), so this is
  structure rather than volume: a new adapter inherits it without knowing it exists, and
  a new strand is one line that fixes the search, the merge and the tile at once.

### Genres come from TMDB ids (2026-08-27)
Provider genre strings are unusable as data: four spellings for the family genre, trailing
spaces, Orion publishes none, and in English mode they stay Finnish. Both TMDB passes keep
the genre ids from the `/movie/{id}` response they already fetch; ids land on each show as
`gids`, and `data/tmdb-genres.json` holds the id -> name map for `fi`, `sv` and `en`.

- TMDB's Finnish genre names are real translations: 18 of 19 differ from English.
- The kids filter cannot whitelist Animation and Family: TMDB tags "Marsupilami" as
  Adventure, Comedy. The rule: rating gate first, then ids `16`/`10751` mean kids,
  `99`/`18` without them mean not kids, no ids means rating alone.
- Provider strings stay as the fallback. Entries without `g` count as incomplete.
- Film facts fold from every showtime; screening facts from the surviving ones. Toggling
  "Suom. puhe" changed a card's genres because Finnkino and Gilda disagree on "Laula
  minulle Arja". `tmdb`, `tr`, `img`, `len`, `genres`, `rating` and `original` fold from
  the unfiltered set, genres taking the longest string; `lang` stays on the filtered set.
- Chains disagree more than expected: for one documentary Kotkan Leffat published `SV-S`,
  which the client's `LN` map keyed on `SE` rendered as a bare "SV". Fixed in `etiketti.py`.
- The sheet's chain key is sticky (`position:sticky; top:0` with negative side margins).
  Day headings are not, since the legend wraps at narrow widths.
- The times list carries the venue on the meta line as a `.theatre-tag` in a combined
  view, and the stub gains the chain tint.
- English titles resolve through `_eid`: `disp()` looked up `films.json` with the merge
  key and showed the Finnish title in every combined view. `filmEntry()` scans the
  group's showtimes for the Finnkino member and falls back to the show's `original`.
- Never translate `s.title` itself: it is the key for `mergeKey()`, `normTitle()`, the
  TMDB title cache and `tmdb-aliases.json`. English titles are a render-time substitution.
- Merge on the union of both signals: keying by `tmdbId` when present unmerged "Maailman
  rikkain nainen", which had an id at Gilda and none at Finnkino. `mergeIds()` unions the
  title key with the id key.
- A merged card folds metadata by first non-empty, not from `times[0]`.
- `tmdb-aliases.json` is read by both passes; an alias id triggers a `/movie/{id}` call in
  `fetch_data.py` so the vote floor still applies. Aliases are keyed by the title as each
  chain publishes it (`autot re release`, `autot uudelleenjulkaisu` both map to `Cars`).
- The two TMDB passes stay separate and agree on the rules (exact-match preference,
  `MIN_VOTES` = 25, `n` and `x` in both caches) but fetch at different times, so the same
  film can briefly carry two ratings. A single shared pass is not written.

### A language marker in the title blocked the TMDB search (2026-09-14)
Bug: `clean()` took `suomeksi` off the search string in all three positions it occurs in
and took none of its counterparts off any of them, so a cinema selling the dubbed and the
subtitled run as two films had one searchable and the other not. Measured over the
committed data: one film, Coyote vs. Acme, is published under eight spellings by nine
chains, and 44 showtimes across 13 titles and 11 cache keys could not be searched at all,
every one of them cached unmatched or never searched. Laitilan Kino added a second shape,
a strand in a trailing parenthesis, and it is not one title but every title that cinema
publishes: its whole fortnightly programme is "<film> (Kahvi ja Kino)".
Fix: `PAREN_NOISE` gains `englanniksi`, `på svenska` and `suomeksi puhuttu`,
`TRAIL_NOISE` gains `englanniksi`, and `clean()` takes a trailing parenthesis off when its
content is in `strands.EVENT_PREFIXES`, which gains "kahvi ja kino". One list, both
positions. A parenthesis holding anything else is left alone, checked against the four in
the data: an original title, two anniversary editions and a subtitle note. The published
title never moves, so every cache key, `normTitle` key and merge key stands.
Two the cleaned search still cannot settle are aliased with their evidence in the file:
"Matka Piemonteen" has no Finnish title on TMDB at all (Resan till Piemonte, 1545391,
identified from the cinema's own film page by its director and five of six billed actors),
and BioRex's "Avengers: Endgame Re-release (encore)" matched 24428, The Avengers (2012),
weakly, so the trust gate withheld its metadata and 50 showtimes went scoreless while
every other chain matched 1769545 exactly.
Tests: `tests/test_tmdb_queries.py`, 12 added, 11 mutations red. No data change: only the
search string moves, and an unmatched entry takes its daily retry on the next cloud run.

### The TMDB search reads the original title and the published year (2026-09-13)
Three Regina films sat unmatched: "Lucky luke sotapolulla" (La ballade des Dalton, 1978),
"Rakasta tai tuhoudu" (All Night Long, 1962), "Prinssi ja revyytyttö" (The Prince and the
Showgirl, 1957). `queries()` searched the Finnish title alone, the show's `original` was
never a candidate for any provider, and no year reached the search, so "All Night Long"
would have taken the 1981 film first in TMDB's popularity order. Approximate count at
c621b0cf: 29 of Regina's 96 titles had no id, 8 were weak.

`enrich_tmdb.py` now: `gather()` collects per title the `original` and the year its shows
carry (the optional `year` field, or a trailing "(1996)" read before `clean()` strips it;
never the screening date), and uses either only when every show agrees. `queries()` puts
the cleaned original second, after the published title, deduplicated, so a film that
already matched keeps its match. With a year the search sends `primary_release_year`
(a string parameter per TMDB's /3/search/movie reference, checked 2026-09-13), retries
unfiltered when nothing exact came back, and `pick()` accepts an exact title only within
`YEAR_TOL` = 1 of the published year, the year itself ahead of a neighbouring one and the
published original title breaking a same-year tie; two different ids still standing is a
tie and stays weak whatever order TMDB listed them, logged as "several films match the
title and year, none trusted". An exact title further off is a weak fallback logged as
"year mismatch, exact title refused". Without a year the first exact hit wins as before.
An alias string is never filtered, same rule as the Finnkino pass.

Cache: an entry records the evidence it was judged on (`o`, `y`). `reconsider()` drops an
entry whose current evidence is nonblank and differs, exact matches and unmatched titles
alike, at most `KINO_TMDB_RECONSIDER` = 25 a run in key order, aliases excluded; the rest
wait untouched. Weak ids were already dropped on every load. Unmatched titles were left
to their daily retry at first, which is why the three films above stayed unmatched on
2026-09-13: the 00:55 UTC run had searched them, the 02:00 local run then published their
original titles and years, and the 02:55 cloud run skipped them as checked today
(f8647014). Fixed the same day; an unchanged unmatched title keeps the daily retry only. Not done: the
Finnkino pass in `fetch_data.py` already filters on OCAPI's year and keeps its own loop;
no client change, the field is not rendered. `tests/test_tmdb_matching.py`, 37 tests, 18
mutations red.

Regina publishes both on the film page the adapter already reads: the heading inside
`#main-content` ("LUCKY LUKE SOTAPOLULLA (1978)") gives `year`, and `span.original-name`
lists the other-language titles slash-separated, original first. For a Finnish film the
span holds the Swedish title alone, so the first segment is `original` only when the Maa
row is present, names no Finnish share, and the span lists at least two titles; a
co-production in either order, a missing country or a lone segment leaves `original`
empty and keeps the year. Checked on five saved pages 2026-09-13: 1978 / La ballade
des Dalton, 1962 / All Night Long, 1957 / The Prince and the Showgirl, 1970 / The Music
Lovers, and 1966 with no original for Käpy selän alla. Nothing reads the ticket page for
this. Regina is on the local half, so the fields reach `data/` with the next local run and
the search uses them on the cloud run after it. What the three films then match is for
`run-enrich.log` to say: they are re-judged, not promised an id, and an unresolved tie is
a valid outcome. No TMDB id was checked from here; the ids in the tests are fixture
values. `tests/test_regina.py` `FilmIdentityTest`, 14 tests, nine mutations red, plus
`tests/test_tmdb_matching.py` tie cases (41 tests).

### Only a trusted TMDB match publishes metadata (2026-09-13)
Bug: a weak candidate withheld `tmdbId` only. Poster, rating, votes, trailer, gids and
synopses of the wrong film went onto shows and into films-extra.json, and `run.py`'s
carry-over kept them run after run ("Naisen kasvot" -> Obsession). At d2a41e21: 20 weak
titles, 102 shows, 22 files, 31 films-extra keys. Same in `fetch_data.py`, which also let
TMDB's trailer replace Finnkino's.

Fix: `enrich_tmdb.trusted()` (`x` and an id) gates every write in both passes. Untrusted
entry: `unpublish()` strips `tmdb votes tr gids tmdbId` and a TMDB poster; `merge_extra`
clears `r tr img en` for every untrusted key, `fi` only when equal to the candidate's own
overview (79 other texts checked, all cinema copy). Posters carry `isrc: "tmdb"` (set by
the pass and by the `run.py` carry); a trusted entry replaces a marked stale poster, an
untrusted one drops it. An unmarked mirrored poster is left alone: the path cannot tell a
cinema's poster from a pre-mark TMDB one, only the next `run.py` run of that adapter can
(adapter publishes a poster: remote URL, cinema's; none: carried and marked). Cloud files
got that at c228d2b6, the local half at 7c96e583 + a91eda3d: Regina (publishes no
posters) 112 marked, all the trusted entry's own, Naisen kasvot on 76848's poster, Faust
and The Time That Remains blank, no marked poster on an untrusted show; Engel, Akseli,
Cine, Savon Kinot, Star and Joutsa kept their own posters unmarked. Verified 2026-09-13.
The carry itself stays: 208 trusted shows sat on one. Cache, budgets, picker unchanged.
The 2026-08-27 "weak match still beats no film" rule now covers the search only.
Tests: `test_tmdb_trust.py` 20 / 20 mutations red, `test_finnkino_trust.py` 4 / 5,
`test_run_partial.py` +1.

### A region city is backed by the data or an adapter; the two agree after a run (2026-09-12)
`tests/test_regions.py` gained a second test on 2026-09-07 meant to bound the adapter half
of the check: a region city missing from the data had to belong to a provider with no venue
file at all, "so a cinema dropped from a provider that has one still fails". It could not:
`run.py` writes `data/venues-{provider}.json` from SITES on every successful run of the
site, city included, so a venue dropped from SITES leaves the adapters and, on the next run,
the data together. Between the edit and the run the stale venue file keeps backing the
city, and that window is the same one every provider addition passes through. On the day
of the review every region city was in the data and the test's loop body never ran.

The decision is now one function, `dead_entries()`, with fixture cases for a fetched
provider, one that has not run, a typo, and the dropped-venue window left open on purpose.
Closing that window means comparing SITES to the venue files directly, which fails each
addition until the pipeline has run; not done. The contract the file relies on, that the
venue file carries each city verbatim from SITES, is pinned in `tests/test_run_partial.py`.

## Refactor to do before adding more providers
Adding a venue to an existing platform is one line. Adding a platform used to cost four
files plus five frontend edits; all fixed:

- [x] `data/providers.json`, generated by `scripts/build_providers.py` from
      `scripts/providers/registry.py`. The frontend derives every label, host, accent and
      footer verb from it. No `generated` field, so identical bytes mean no diff. index.html
      keeps a hardcoded fallback list for a missing file or a stale service worker.
- [x] One generic runner, `scripts/providers/run.py <module>... | --where cloud|local`.
      Every adapter exposes `SITES` and `fetch_site(site) -> {venue_id: [shows]}`.
- [x] The cloud workflow loops over `registry.py --cloud`. Failure flags go to
      `$RUNNER_TEMP`, never into a commit; data is committed before the failure check so one
      dead provider still publishes the rest. The enrich gate reads its exit code from
      `$RUNNER_TEMP` rather than grepping `exit=0` out of a log that also carries film
      titles and TMDB error text.
- [x] `riviera.py` is parameterised by base URL.
- [x] Repertory titles: `clean()` in enrich_tmdb strips a trailing "(YYYY)", bracketed
      format noise, a trailing ", suomeksi" and a known-list event prefix. Only the search
      string is cleaned; `norm()` still keys on the published title.
- [x] `venues-{provider}.json` lists every venue of the site, and a venue with no shows and
      no file gets an empty one (2026-08-28). The file is written only when at least one
      venue produced shows.
- [x] A whole site parsing zero showtimes fails the run; `common.EmptyProgramme` on positive
      evidence of an empty listing is counted as `empty`. `tests/test_empty_programme.py`.

## Pipeline
- [x] **TMDB cannot be searched by Finnish distributor title.** Probed 2026-08-27:
      "Maailman rikkain nainen" gives 0 hits and `&language=fi-FI` also gives 0, while the
      original "La femme la plus riche du monde" gives exactly 1. `language` localises the
      *response* only; it does not widen the match, which covers original + English +
      registered alternative titles. Escape hatch: `scripts/providers/tmdb-aliases.json`,
      keyed by `norm()` of the published title, valued either a TMDB id (skips the search)
      or a replacement search string. `run-enrich.log` now names every title that found
      nothing, which is the input to that file. Wikidata (P4947 = TMDB id, matched on the
      Finnish label) is the automated version if this outgrows a hand list.
- [x] **MovieXchange API credentials, decided against 2026-08-29.** Server-side
      client_credentials would have moved the whole pipeline back to Actions. Not requested:
      an approach to a third party with no promise of free access. Reopen only if
      MovieXchange publishes open access terms. Consequence: the split pipeline is the final
      architecture. The MX CDN is a public read reached through Finnkino's own
      `moviexchangeReleaseId` and never needed credentials.
- [x] **Cinema Niagara, Tampere (built and live 2026-09-02).** The one eTiketti host the
      2026-08-30 sweep left behind: the same platform in a second template. Re-probed as a
      visitor: nginx, no Cloudflare, robots.txt disallows `/salikartta`, `/tili` and
      `/ostoskori`, which this repo never reads. Each film page renders its screenings as
      `<div\n class="item tampere date-3.9.2026">` with `<div class="time"><span>16.15`,
      `<div class="show-price"> 13,00€`, `Paikkoja vapaana: 126/127`, tags in `movie-specs`
      and no place line, where Kotka prints `KE 2.9. klo 20.00`, `TRIO 123 | SALI 2<br>
      Lippu 15,00€<br> Vapaat paikat 27/35`. Labels carry no colon; genres sit under a
      label reading `genre`. `/?shows=all` renders every screening twice (desktop and
      mobile wrappers).
      **Design.** A `SITES` entry with `etiketti.py` taught the second template: every
      regex is an alternation of exactly the two shapes; the place falls back to the item's
      place class (`tampere`) so `match` still selects the venue; `movie-specs` tags go into
      `method`; `_lang` reads Finnish language names through `LANG_NAMES`, the inverse of
      the client's `LN.fi` and asserted equal to it, matched on the first four letters.
      Shows are keyed on the `/salikartta?id=` href so a duplicated surface cannot double a
      show; a row without an id is keyed on film, start, place and auditorium, recorded
      only once a registered venue took the row. The ticket href is never fetched. Registry:
      `id="niagara"`, `book="buy"`, `module="etiketti"`, venue `cn-tampere`, accent
      `#6A4FBF` (47.0 / 68.1 / 60.6 dE00 against Finnkino; greens fail deutan). Seats are
      read only to derive `soldOut`; counts stay unpublished.
      **Tests:** `tests/test_etiketti_templates.py`, 32 tests; seventeen mutations red.
      **Live** (first cloud run 2026-09-02 10:40Z, data commit a7b2b8f7): 47 showtimes, 12
      dates, 0 failures, no `/salikartta` request; poster, runtime, genres and language on
      47 of 47, TMDB id on 39; language codes DA, EN, ES, FI, FR, IT, NO, SV, TR, every one
      the client names. Counts: providers 33, venues 75, canonical pages 170, sitemap 171.
      Deferred: seat counts on screen; credits.
- [x] **Language codes normalised end to end (code landed 2026-09-02, sw.js v99; closed
      2026-09-15).** Four codes in the data were not in the client's name table: `TU-A` 62
      rows and `MA-A` 3 rows (Finnkino's Turkish and Malayalam), `XX-S` 46 rows (Nexxo's
      "no subtitles"), `LT-A` 1 row (Lithuanian). `fetch_data.lang_tag` maps through
      `FINNKINO_LANG` (`SE`→`SV`, `TU`→`TR`, `MA`→`ML`), never touching the role letter;
      `nexxo._lang` drops `XX` from the subtitle role; the client's `LN` gains `LT` and
      `ML` in all three languages, and the generator's mirror too. The landing pages kept
      `CODE_ALIAS`, `NO_SUBTITLES` and `LN_EXTRA` meanwhile, so no page showed a raw code
      while the adapters turned the committed data over. After the 2026-09-02 cloud run
      `XX` was gone; `TU-A` and `MA-A` waited on a local run. **Closed 2026-09-15.**
      Measured twice, parsing each `lang` value with `LANG_RE` and splitting compounds
      rather than grepping: first at `bb409cc0` over 86 area files and 4,178 shows, then
      again at `887a7988` after a cloud push landed under the rebase, over 86 files and
      4,262 shows. Same verdict both times: `TU`, `MA` and `XX` absent in both roles, no
      value failing `LANG_RE`, and no code without a name in `LN`. At `887a7988` the
      published set is AR, DA, DE, EN, ES, FI, FR, IT, JA, KO, LT, NO, SV, TR; `NO` did
      not appear in the first measurement and is already named in `LN`, `ML` is absent
      from the data entirely, and `LT` carries three rows. All three constants deleted
      from `build_pages.py`; `lang_parts` is now one lookup,
      `LN[lang].get(x) or x`, so an unmapped code renders as itself and is
      visible on the page rather than lost. That is exactly the client's rule: `langTxt`
      in `index.html` reads `LN[state.lang][x] || x` and never had an alias
      layer, so while the three constants stood the generator was the more forgiving of
      the two and a page said "turkki" where the app said "TU". They agree again. Tests
      narrowed, not dropped wholesale: `GeneratorAliasTest` went, and so did the four
      constant pins in `test_landing_pages.py` and the four TU/MA/XX cases in
      `StubShapeTest`. Those four were not one kind. `TU-A` and `MA-A` now pass through
      exactly as the unmapped-code case does, so they were duplicates of it. The two `XX`
      ones were not: they pinned suppression of the subtitle role, which that case never
      pinned, and deleting `NO_SUBTITLES` removed the rule rather than a duplicate.
      Measured on both implementations: an `XX-S` tag rendered nothing at all and now
      renders the code, so a fi page that said only "suomi" would now add "tekstitys: XX".
      That is safe only because no committed area file carries `XX` and `nexxo._lang`
      still drops it at the adapter, and it is fail-visible rather than silent. So the
      unmapped-code case was widened from `ZZ-A, FI-S` to `ZZ-A, YY-S` to hold
      the S role the `XX` cases used to hold. The committed-data coverage check stays with
      `known` rebuilt from `bp.LN` alone. Preserved deliberately: `FinnkinoLangTagTest`
      (TU/MA at the adapter), `NexxoLangTest` (XX in the subtitle role) and
      `NameTableTest` (LT/ML rendering), because the adapter fixes are what keep the data
      clean and deleting their tests would remove the reason the aliases could go.
      Break-verified, five mutations on `build_pages.py`, none void: dropping `LT` from
      `LN` reddens the coverage check, the client-mirror check and both rendering tests;
      dropping `TR` reddens the coverage check and the client-mirror check; dropping `ML`
      reddens the client-mirror check and the generator rendering test; making an unmapped
      code vanish in both roles reddens the case table; and reinstating suppression for
      the subtitle role alone reddens it too, which is what verifies the widened case
      rather than assuming it. Source restored byte-identical. Suite 1,574 tests OK, 5
      Pillow skips. Regenerating twice with `--date recorded`: 0 files written, 201
      unchanged, so no generated page changed. `tests/test_lang_normalization.py`,
      `tests/test_landing_pages.py`.
- [ ] Move the local fetch off the laptop onto an always-on box on the same network.
      Cloud VMs are not an option for the eight providers that block datacenter IPs
      (Finnkino, Kino Akseli, Kino Engel, Joutsan Kino, Savon Kinot since 2026-09-04,
      Kino Regina since 2026-09-06, Cine and Elokuvateatteri Star since 2026-09-08), and
      with the MovieXchange route closed above there is no other way off the laptop at
      all. 30 of 82 venues ride on that machine, counted from the registry and the venue
      files on 2026-09-13.
- [x] Finnkino ratings whitelisted to `S` and `K-n` (2026-08-28). The OCAPI
      classification text passed through raw when it did not start with a digit, and the
      live values include "Tulossa" and "-" (verified in committed data: 5 and 7
      showtimes), which rendered inside the age-limit chip and silently failed every
      `rating ===` comparison. Same bug class as the Vista "K-7 (4)" gotcha. Anything
      else now blanks; "coming soon" is premiere-chip material, not a rating.
- [ ] Finnkino prices. **Probed 2026-09-01 and blocked by the access rule rather than
      by difficulty**; see the entry below. The programme response the adapter already
      reads carries no price field anywhere, the obvious ticket-type read paths under the
      same API all answer 404, and the remaining route is the seat-selection flow, which
      this repo does not call or inventory. Left open only because a visitor-facing price
      *page* would be a legitimate source, and that has not been looked at.
- [x] **Commit run.log only on failure -- decided against 2026-09-01.** Across the last
      300 commits no routine run produced a log-only commit; logs ride inside data commits
      that happen anyway, and an unchanged log is not committed. A green run that commits
      nothing would leave the last red log on `main` forever, so `check_runs.py` would
      report the same failure every day (the `run-vista.log` incident). And the green logs
      are the record: the per-venue counts in a successful log are the only place a soft
      regression is visible. Reopen only if run logs start forming commits of their own.
- [x] Finnkino no longer publishes an empty area file when a venue returns no shows: it
      keeps the previously committed one, matching `run.py`. A file is still written when
      none exists, because `areas.json` lists every site regardless of shows and the picker
      would otherwise link to a 404. New log line: `N venue files written, M kept as-is`.
- [x] Dropped `data/attrs.json` and `data/film-sample.json`: written every Finnkino run,
      read by nothing.
- [x] Retry/backoff for transient API errors (2026-08-28). One transient 502 counted as a
      total site failure with the next cron four hours away. Shared
      `providers/common.py::fetch(url, headers, data, tries=3, backoff=5, opener)`, named
      `common` because a local `http.py` would shadow the stdlib. All nine adapters migrated
      one per commit, each keeping its own timeout and backoff (Vista 40 s, Gilda 45 s, Nexxo
      backoff 6). `common.fetch` retries only the request, not the parse: a 200 with a
      non-JSON body is a shape change to look at.
- [x] **Refresh on resume, not only on date rollover** (2026-08-28). An installed PWA is
      resumed, not reloaded, so `providerMeta` stayed frozen while the age counted up. The
      threshold is 10 minutes because Pages serves data with `max-age=600`.
      `fetchVenueLists` was split out of `loadAreas` so a refresh does not bounce the reader
      off their venue. Still open: a tab left visible all day never fires
      `visibilitychange`; a timer was not added.
- [x] Search input debounced 120 ms (2026-08-28): every keystroke rebuilt the whole list
      through innerHTML — ~90 cards in a combined Helsinki view — and the intermediate
      frames were discarded anyway. 120 ms is below the point where the list feels
      detached from the typing. Keyed DOM reuse is the real fix and was rejected: at this
      list size it buys nothing and costs a rewrite of the render path.
- [x] `fetchJSON` aborts after 8 s (2026-08-28): `fetch()` has no timeout, so a connection
      that opens and then stalls — a phone walking out of coverage, not a refused one —
      never settled and never rejected. The spinner ran forever with no error and nothing
      to retry, which reads as a broken app rather than a broken network. AbortController
      lets the existing `netErrorHtml` catch fire. 8 s because the files are small and a
      slow 3G first byte is still well inside it.
- [x] Atomic data writes (2026-08-28): every writer went through bare `write_text`, so a
      run killed mid-write left truncated JSON. Harmless on Actions (ephemeral runner),
      real locally: the wrapper writes into a checked-out repo and the next run's
      `git add data` would commit the torn file — and cancel-in-progress means
      mid-run kills happen. `common.write_json` / `write_text_atomic`
      (sibling .tmp + os.replace, atomic on one filesystem on both platforms) used by
      run.py, synmerge, enrich_tmdb and fetch_data. *.tmp gitignored for the narrow
      window between write and replace.
- [x] enrich_tmdb checkpoints its cache (2026-08-28): `tmdb-titles.json` and
      `films-extra.json` are written every 25 titles, not only after the loop. Each
      per-title body already catches its own exceptions, but anything raised outside one
      — the two genre-list calls, the area-file write pass, a cancelled runner — skipped
      the single end-of-run write and discarded every lookup of the run, ~300 TMDB
      requests on a cold cache, to be spent again four hours later. Cheap because the
      writes are atomic and the cache is idempotent: a partial write is simply a warmer
      start. Every 25 rather than every title because films-extra.json is re-read and
      rewritten whole on each flush.
- [x] **A cached TMDB rating stops being permanent** (2026-09-01). The skip was `complete
      and (c.get("v") or c.get("c") == today)`, so a trailer stopped an entry ever being
      read again. Measured on 2026-09-01: 156 entries, 96 with a trailer, 71 of those last
      read on 2026-08-27. Now age decides: `due()` fetches uncached or incomplete entries,
      keeps the daily no-trailer check, and re-reads a complete entry once it is
      `RATING_MAX_AGE` (7) days old, `REFRESH_BUDGET` (12) a run. The budget bounds the
      catch-up, since without it the first run re-reads all 71 at once and they come due
      together for ever; what it defers is printed.
      Three review findings fixed with it. The success path wrote the old rating stamped
      with today's date when both localized detail requests failed, and emptied the cached
      text: synopsis slots are now seeded from the cache and only a response that arrived
      replaces them, and `c` moves to today only when a detail response carried rating and
      vote data. The queue is ordered on `a`, the last attempt, not `c`: an unreadable id
      would otherwise outrank everything for ever. `a` is recorded even when the title
      aborts after its detail read, from the `except`, so a failing title cannot camp at the
      head. A rating needs both halves of the pair: a response carrying only `vote_count`
      had set the rating to 0 over a real one; zero counts as usable.
      `tests/test_tmdb_recheck.py`, 22 tests against a fabricated cache and `main()` with
      TMDB stubbed by URL; twenty-six breaks red.
- [x] **The same defect on the Finnkino path, fixed 2026-09-01.** `data/tmdb.json` had
      the same rule (46 of 59 entries frozen, 45 last read on 2026-08-28), and its detail
      request was conditional on `not votes or not gids`, so an age rule alone would have
      fetched nothing. The schedule is `providers/refresh.py`, shared by both passes; the
      Finnkino cache passes in its own `complete` predicate, since it carries no synopsis or
      poster. A failed video read no longer writes an empty string over a cached trailer.
      Tested with the pass lifted into `enrich_cached_ratings()` and TMDB stubbed by URL;
      the first fixture omitted `y` and every cached-entry test passed anyway, which an
      uncached film caught with `KeyError: 'y'`. The next local run is the operational
      check.
- [x] **Independent hosts are fetched at the same time** (2026-09-01). `run.py` pools
      over *hosts*, not over sites, and each host is still read by one thread at the pace
      its adapter sets. See "A run reads unrelated hosts at once" below for the host
      sharing that makes the site the wrong unit, the four hazards and what each cost.
- [ ] README workflow badge
- [ ] Credential hygiene and rotation: tracked in local private notes

### Every adapter is held to one show contract, at the boundary (2026-09-14)
Bug: the show dict had no written shape. Twelve modules measured, eleven emitted the same
seventeen keys and BioRex emitted no `price`; the client survived on `r.price || ''`.
Fix: `common.Show`, a stdlib `TypedDict`, names the keys; `common.check_shows` is the
runtime rule and `run_site` applies it to what `fetch_site` returned before any write: a
missing key, a wrong type, a blank `start`, or a show filed under another venue fails the
site like a parse error, so the previous files stay and the log names venue and key. BioRex
writes `price: ""`. Extras stay allowed: `_`-prefixed, `age`, `year`, `movieUrl`.
Tests: `test_show_contract.py` parses each of the twelve modules' own fixtures (reused from
their adapter tests; BioRex, Engel and Kino Akseli gained a minimal one) and checks every
show: keys, types, an aware ISO `start`, an absolute `url`, `provider` and `venue` of the
fixture's site, no duplicate screening. A registry module without a sample fails. Five
breaks red: Orion dropping `url`, Riviera misfiling a venue, BioRex `soldOut` as a string,
Engel a naive `start`, run.py skipping the check. The fake adapters in the run tests now
emit full shows. Not done: a dataclass for the fetch result; run.py already models it.

### Secondary page fetches have a ceiling (2026-08-30)
Adapters that read a listing and then fetch one page per film iterated whatever the listing
contained, 15 to 31 films today and unbounded in principle. `common.PAGE_BUDGET` is 120,
about four times the largest real figure, overridable with `KINO_PAGE_BUDGET`.

The two loops are not the same loop, which tripping the cap showed: with the budget forced
to 2, eTiketti went to zero showtimes at Kinopalatsi Kotka and 6 of 34 at Trio 123, and
would have published both, because its film pages carry the screenings, while BioRex and
Engel use film pages only for metadata. `common.capped()` trims and logs, for enrichment
loops; `common.budget_or_raise()` raises, for a loop whose pages are the schedule, so
`run.py` writes no file and the previous data stands. A venue publishing half its day is
worse than one publishing nothing, because half a day looks complete.

### Response bodies have a ceiling too (2026-08-31)
The request count was bounded while each response was read with a bare `r.read()`. Found
by an external review. `common.fetch` reads in 64 KB chunks against a cap (`max_bytes` per
call, `MAX_BODY` 20 MB by default, `KINO_MAX_BODY`) and raises `BodyTooLarge` past it.

- 20 MB is headroom; the largest body legitimately read is a poster source image of a few
  MB.
- A Content-Length past the cap is refused before the body is read, and the chunked loop
  enforces the cap whether or not a header was sent.
- Never retried: the oversize answer is deterministic.
- One cap in `fetch` covers adapters, enrichment and `mirror_posters.download()`; an
  oversize poster lands in the `failed` dict like any other bad download.

Covered in `tests/test_common_fetch.py` against the real local server, including a response
with no Content-Length; each guard break-verified.

### The pipeline identifies itself (2026-08-30)
Every adapter sent `Mozilla/5.0 ... Chrome/126.0.0.0`, an automated reader claiming to be a
person, which made the ethics section's claim untestable by a cinema. Now `Leffavuoro/1.0
(+https://leffavuoro.fi)` everywhere, including `fetch_data.py` and the TMDB pass.

Probed first against every provider: each answers the honest string byte-for-byte
identically to the Chrome string; Finnkino answers 403 to curl under either. Engel's film
page differed between the two agents and also between two requests with the same agent (a
cache-buster in a script URL): a difference is not evidence of discrimination until the same
request twice is ruled out. If a provider ever refuses the honest string, record it here and
keep the browser string for that host deliberately. The URL in the string is where a cinema
that wants out is supposed to look; the contact route closed that on 2026-08-30.

### Conditional GETs, and what the providers actually support (2026-08-30)
`common.fetch(cache=True)` sends a stored `ETag` / `Last-Modified` back as `If-None-Match`
/ `If-Modified-Since`, and a 304 returns the stored body. Verified live against Cinema
Orion: the second fetch was a 304 and 118 kB was not resent.

Measured before building it: only Cinema Orion sends a validator.

| origin | ETag | Last-Modified | Cache-Control |
|---|---|---|---|
| cinemaorion.fi | no | **yes** | – |
| kotkanleffat.fi (eTiketti) | no | no | `no-store, no-cache, must-revalidate` |
| kinoset.fi (Nexxo) | no | no | `no-store, no-cache, must-revalidate, max-age=0` |
| biorex.org, kinoengel.fi, gilda.fi, rivieracinemas.fi | no | no | – |
| savonkinot.fi (Vista) | no | no | `private` |

So this saves about one request per run. It stays because it is the correct way to ask,
costs nothing where the origin offers nothing, and picks up a provider that starts sending
validators. `run.py` prints the shape of every run so the claim can be checked:

    [run] http: 1 revalidated (304), 85 full, 48 not stored (origin said no-store),
          0 cache entries written

Rules: a response marked `no-store` or `no-cache` is never written to disk, and neither is
one without a validator. The cache lives in `.http-cache/`, gitignored, never committed
(it holds verbatim third-party pages, the `probe/` rule). The workflow restores it with
`actions/cache`. Never enabled on a POST: `fetch` forces `cache=False` when `data` is
given, since a POST response is not addressed by its URL alone.

### Retry-After is honoured on the interval the upstream names (2026-08-30)
`common.fetch` retried every HTTP error on the same fixed `backoff * n`, so a provider
answering `429 Retry-After: 60` got three more requests inside 15 seconds. A 429 or 503
carrying `Retry-After` is now retried on the interval named. A 500, a reset, a 429 without
the header and a 403 keep the fixed backoff.

Two ceilings, because "sleep as long as you are told" hands a stranger a lever on the
pipeline: `RETRY_AFTER_MAX` (120 s) bounds one wait and `RETRY_AFTER_BUDGET` (300 s) the
whole process. Past either, the request fails, `run.py` keeps the previous file and the
health line ages. Both overridable (`KINO_RETRY_AFTER_MAX`, `KINO_RETRY_AFTER_BUDGET`) so
tests can trip them. `Retry-After` is delta-seconds or an HTTP-date; a past date means
now; an unparseable value falls back to the fixed backoff.

    [run] throttled: 2 Retry-After responses, 60s waited, 1 not retried
          (asked for longer than a run can wait)

Printed only when it fires. Tested against a local server scripted to 429: the stated wait
is honoured, a `Retry-After: 9999` costs one request and no sleep, the budget refuses the
second of two 2-second asks under a 3-second budget, an HTTP-date is parsed, a past date
waits zero, a plain 500 still takes three tries.

Not covered: `enrich_tmdb.py` uses a bare `urlopen` with no retry, so a TMDB 429 skips
that title. Routing it through `common.fetch` is a separate change.

### A refusal has to say which layer refused (2026-08-30)
Cloud run #110 went red on `nexxo`: all three Kinoset venues answered 403. Nothing was lost
(previous files kept, venues published `stale`, commit before the gate, the next run 43
minutes later served everything), but the log said `HTTP Error 403: Forbidden` three times
and nothing else. An edge block and an origin throttle want opposite responses (move the
endpoint to the local half, or wait), and the block was gone before anyone read the log.

`common.fetch` prints one line for a request it gives up on:

    [http] 403 from kinoset.fi, gave up after 3 attempt(s) -- Server: LiteSpeed

- Three headers, never the body: `Server`, `CF-Ray`, `Retry-After`. The log is committed
  to a public repo and a third party's error page carries whatever they ship; one raw dump
  already put someone else's API key in here. `X-Powered-By` was dropped for that reason.
- Measured live: `kinoset.fi` answers `Server: LiteSpeed` with no `CF-Ray`, so a Kinoset
  403 is the origin refusing. `Server: cloudflare` would be a different event.
- One line per host per process, not per request: `mirror_posters` has had 185 failures
  against one host in a run. The ray id is unique per request, so its presence identifies
  the layer and the line carries the first value seen.

Rejected: deferring a failed venue to a second pass (an interface change across eleven
adapters, against a block that took under 43 minutes to clear); and not failing the
workflow when every venue kept usable data (a permanently dead provider would publish
green runs while the data aged). Six mutations red, including logging on success or once
per attempt.

### Six days out of seven is not a Finnkino schedule (2026-09-01)
`fetch_data.py` asks OCAPI for seven business dates, one request each. A request that
raised was logged and skipped, and the remaining days were written as a new snapshot with a
current timestamp and exit 0. `dates` is built from the shows that arrived, and the client
reads a date's absence as "not published yet", so one transient error took a whole day out
of all seventeen Finnkino venues with nothing to surface it. Reproduced with OCAPI stubbed
and day three raising.

Decision: all seven or none. On a failure the previous file stands, its age moves past
eight hours, and the non-zero exit turns `check_runs.py` red; a published six-day week
moves nothing a reader can see. The last day of the horizon is refused on the same terms.
`areas.json` moved down with the schedule files, since a run that published nothing still
stamped the one file whose age answers "when did Finnkino last refresh". Poster downloads
and the token fetch have already happened by then and are not rolled back.

Not retried before giving up: `api()` has no retry, unlike `common.fetch`. A separate
change.

Thirteen tests drive the real `main()` with OCAPI stubbed by URL. Break-verified six ways:
the guard removed (9 red), logging without returning (8), returning 0 after refusing (6),
aborting only when all seven fail (8), tolerating the last day (1), `areas.json` above the
loop (3).

### A provider is as fresh as its weakest venue (2026-08-30)
One venue of twelve parsing to nothing kept its previous file, and `venues-{provider}.json`
then stamped `generated: now` across all twelve, so the app said BioRex was an hour old
while one cinema sat on week-old showtimes.

`venues-{provider}.json` gains three additive fields: `oldest`, the minimum `generated`
across the provider's venue files, read off disk after the run and what the health line
ages on; `status`, `ok` or `partial`; `stale`, the venue ids whose previous file was kept.
`generated` keeps its meaning.

Stale, not failed: at this layer a broken parser and a cinema with nothing on today both
arrive as `[]`, so failing on a venue-level empty would fire on every Monday closure.
`[run] partial:` names the venues in the log and the status carries them to the client,
which shows `⚠ Riviera 119h (1/2)` rather than blaming the whole chain. A site where every
venue came back empty still fails.

Fixed the same day: age alone still hid a partial refresh. `healthState(m, ageH)` returns
`gone | behind | partial | ok` in severity order; `partial` is separate from `behind`
because two-hour-old data is not behind, and calling it that is the false alarm that
teaches people to ignore the line. Fourteen harness cases; reverting to age-only turns
four red. One term was unpinned at first (`m.unverified > 0` could be deleted with
everything green), found by deleting it.

Added the same pass: a venue that has never produced a showtime is `unverified`, not
`stale`. A new venue with no shows and no file fell through every branch and published
`status: "ok"`; on the next run its empty file existed, so it went down the stale branch
and its ageing `generated` dragged `oldest` down. The discriminator is whether the previous
file contains shows. An unverified venue's empty file is rewritten with a fresh
`generated`, `status` is `partial` while either list is non-empty, and it clears itself
when the venue starts producing. Not a failure: a venue added before its programme and a
parse that never worked look the same here.

Covered by `tests/test_run_partial.py` with three venues and the stale one in the middle;
two venues would let "the last venue's state" pass.

### A venue with no programme yet is not a failed refresh (2026-08-31)
Kino Metso Tikkakoski publishes into late October from day one, so it sat in the 21-day
window with zero showtimes for a month, and the health line read "⚠ Osa teattereista ei
päivittynyt: Kino Metso": the fetch was fresh, and a month-long warning teaches readers to
ignore the line.

`healthState` gained `pending` below `partial`: a quiet "Ei vielä ohjelmistoa: {venue}"
with no warning mark, named by venue since "Kino Metso" reads as the whole chain.

The first version quieted every `unverified` venue; a review caught that as overreach,
since run.py cannot tell "added before its programme" from "a parse that has never
worked". `pending` is granted only where the adapter has positive evidence: a module that
sets `EMPTY_VENUES_CONFIRMED` (nexxo, whose schema check means a venue with zero rows was
answered and listed empty) vouches for the venues it reported empty. eTiketti must not set
the flag: its venue match is a substring test over markup. Severity: stale and unverified
outrank pending, age outranks all three. The provider row's tooltip names each kind ("ei
päivittynyt", "ei ole vielä saatu näytöksiä", "ei vielä ohjelmistoa").

A second review tightened the evidence: nexxo's `parse()` silently skipped rows whose
start could not be read, so a renamed field would have emptied every row and read as
pending. It now raises when relevant rows exist and none produced a showtime; an empty
payload, a room filter owning no rows, and `isUpcoming` rows stay legitimate empties, and
one malformed row among parseable ones is still dropped. The runner's summary counts
pending with its own `[run] pending:` line. Nine guards, nine reds when broken.

### Confirmed empty beats kept data (2026-09-05, sw.js v107)
Kino Metso's Muurame had its last screening on 2026-09-04. The next cloud run found the
town empty and took the "no showtimes, keeping previous data" branch: the past show was
kept, the venue read `stale`, the provider `partial`, and `oldest` was pinned to an old
stamp while three venues were fresh. The 2026-08-31 rule honoured `EMPTY_VENUES_CONFIRMED`
only for venues that had never had data.

The order the loop checks now:

1. Confirmed empty from a successful adapter response (the module sets
   `EMPTY_VENUES_CONFIRMED` and reported the venue) publishes a fresh empty file and
   records the venue as `pending`, whether or not old data exists.
2. Zero rows without that confirmation keeps the previous file and marks the venue `stale`.
3. A fetch, schema or parse failure never reaches the loop: the site fails as a whole.

`pending` now means "no programme at the moment" rather than "not started": "Ei ohjelmistoa
juuri nyt", "Inget program just nu", "No programme right now". No new state, no schema
change. eTiketti does not set the flag and keeps rule 2.

`tests/test_run_partial.py`, `ConfirmedEmptyTest`: confirmed empty with and without an old
file, zero rows without the flag, a confirming module that did not report the venue, a
failing fetch, and Kino Metso's four-venue shape. Four mutations red.

### A classification published at one chain fills a blank at another (2026-09-07)
A cinema that publishes no age rating is not saying the film is unrestricted, it is saying
it publishes none, and 383 of 2916 showtimes were in that state. KAVI's classification is
national, so a cinema reports the same fact rather than forming an opinion. The tree agrees:
of 37 films rated at more than one chain, zero disagree.

`shared_ratings()` groups exact TMDB matches by `tmdbId` and publishes one classification
per film; `borrowed_rating()` decides what a single showing may take. Four rules, each
measured rather than assumed:

- **Exact matches only, on both sides.** A weak match neither donates nor receives, the
  same gate `tmdbId` already passes for the cross-chain merge. Thirteen titles were weak in
  the run this was written against, one of them "Kapina" matched to "Matilda ja lasten
  kapina"; a children's classification landing on that film fails in the unsafe direction
  for Lapsille.
- **Unanimity, or nothing.** A disagreement publishes no shared value and prints the film,
  the sources and the values. Strictest-wins was rejected: two cinemas disagreeing about a
  national classification means one is wrong, and the run should say so.
- **Runtime compatibility where both sides publish one.** Measured across the tree the gaps
  are 0 min (78 pairs), 1 min (3) and 20 min (10), with nothing between. The 20-minute
  cluster is Riviera's 110-minute "Practical Magic" against a 130-minute listing, an
  alternate cut. The tolerance is five minutes, sitting in that gap. A runtime missing on
  either side does not block: the rule is a veto on evidence of a different cut, not a
  requirement that both publish one.
- **A cinema's own rating is never replaced.** The shared value only fills a blank.

Measured on the committed data of 2026-09-07: 383 unrated showtimes to 292, 91 filled
across 23 titles, 10 refused by the runtime rule, 0 disagreements. These move with every
run and are kept here rather than in the code. Lapsille goes from 546 eligible showtimes
to 572. Riviera gains eight of them, "Hetki ennen valoa" and the Oasis documentary, both
K-7 elsewhere.

Provenance is kept because the UI cannot show it: a borrowed rating renders exactly like a
published one, so the show carries `rsrc: "shared"` and the films-extra entry carries `kr`
with `krs`, the chains it came from. Nothing else could tell them apart afterwards.

Two persistence bugs in the first cut, both about a second run rather than a first.
`run.py` keeps a stale venue's previous data, so a borrowed rating survives into the next
run; counting it as a source let a loan outlive its donor and then lend itself onward, so
`rsrc` now disqualifies a show from donating. And the value is re-decided from scratch each
run, cleared first, because nothing else writes anything when a donor leaves the programme.
The same held for `films-extra.json`: `kr` and `krs` are dropped from every entry before the
current set is written, and the write runs on an empty set, which is exactly the case where
every previous value has to go.

A third followed from the same shape: the show loop reaches `continue` when a title has no
cache entry, so clearing after that point never ran and a loan survived its own film being
retitled or pruned. The clear moved above the guard, which is also where it belongs: it
undoes this pass's own writing and does not need the cache to do it.

`tests/test_shared_rating.py`, 27 tests, ten mutations red. Most of them run `main()`
against a temporary tree and read the files back, including two runs with the donor removed
between them: the source-text checks the first cut used could only confirm the source says
what it says, which is the failure mode that shipped the /status/ refetch loop.

Two mutations stay VOID and the reason is worth keeping. The `x` checks in the pass cannot
be made to fail, because `main()` deletes every weak entry carrying an id as it loads the
cache, so one never reaches the pass. That deletion is documented as a one-off for a shape
change, so it is the wrong thing to depend on, and the checks are what remains if it goes.

No client change: the pass fills the show's own `rating`, which `passFilters` already reads.
Takes effect on the next cloud run.

### A failed site publishes its failure, not its last good state (2026-09-14)
Bug: `run_site` withheld `venues-<provider>.json` unless a venue went live or the adapter
confirmed every one empty, so a site that produced nothing left the previous file standing,
reading `status: ok` with an empty `stale`, and discarded the stale list it had just
computed. Measured on 3b62ea4f: four Nexxo sites 403ed at 16:30, six venues kept previous
data, and all four provider files still read ok on the 11:14 stamp. `healthState` checks
`stale` before age, so the only signal left was `oldest` crossing `STALE_H` = 8: eight
hours of a failing provider reading healthy.
Fix: the file is written whatever the outcome. `oldest` still comes from the venue files on
disk, so a dead site keeps the previous stamp and ages exactly as it did; what is new is
that `stale` names the venues and `status` reads partial at once. A fetch that raised still
writes nothing, because `run_sites` catches it above this.
Tests: the four that pinned the withheld file now pin the record, `oldest` included. Four
mutations, against `test_run_partial.py` and `test_etiketti_empty_venue.py`.

### An empty programme clears withdrawn screenings (2026-09-24)
Found by a review at c416446fd. Two defects that compound. Sixteen adapters raised
`common.EmptyProgramme`, or returned a venue `[]` under `EMPTY_VENUES_CONFIRMED`, on zero
parser matches while the page still listed films: Julia, Vaakuna, Kirkkonummi, TMB (four
cinemas), Bio-Kaari, Bio Savoy, Iso-Hannu, Cine Mäntsälä (a date without an offset
dropped until the list was empty), Nexxo (renumbered roomIds), eTiketti (a film page with
no block found), Tapiola, Kinotour, Alatalo, Kuvakukko, Heureka and Navettakino. And on
`EmptyProgramme` run.py left the files as they were, so a cinema that withdrew its
screenings kept them on the page with ticket links.

Fixed in that order. Each adapter now fails the site when film blocks, rows or listed
dates were seen and none parsed, and keeps `EmptyProgramme` or a confirmed `[]` only for an
empty state that is recorded, or for a venue beside rows parsed on the same page. Where no
empty state was ever seen, zero rows fails; the list is in
[docs/research/empty-states.md](../research/empty-states.md). Marita was audited and
already met the rule. TMB, Iso-Hannu and Tapiola lost `EMPTY_VENUES_CONFIRMED`: each
publishes one venue per site, so nothing on the page can vouch for it.

This reverses "A quiet week is not a broken parser" (2026-08-30), which kept previous data
"since the discriminator can be wrong". With the discriminator tightened to the upstream's
own empty state, it is the same evidence `EMPTY_VENUES_CONFIRMED` already acts on for one
venue, and "Confirmed empty beats kept data" (2026-09-05) settled that the evidence wins.
`run.publish_empty` publishes every venue empty and `pending`; the log still says `no
programme published`. `run_cloud.publish` does the same, and a failed write fails the site.

Gaps left inside the rule: a Nexxo town whose room alone is renumbered while another town
matches, and one Alatalo or Kuvakukko venue whose format changes while the other parses,
are still published empty. Kinotour and Alatalo now fail a table whose rows all sit in
undeclared towns.

Tests: every adapter's own file, on edited copies of its fixture, each reproduced red
before its fix; `test_empty_programme.py` and `test_cloud_pool.py` for the runner, four
mutations red there. Every mutation across the bundle went red; none VOID.

### Empty-state gaps closed (2026-09-24)
The three follow-ups "An empty programme clears withdrawn screenings" left open. In each,
one venue was published confirmed empty because its own rows stopped parsing, while another
venue on the same site parsed and kept the site green.

- **Nexxo** (eddb4f62a): a roomed venue with no row, while the payload carries rows in
  rooms no venue owns, is left out. A moved roomId and a new town beside a town between
  visits cannot be told apart.
- **Alatalo** (2015955b0): the digit check runs per town. A town with a date or a time under
  its own heading, the heading line included, and no row placed is left out. So is every
  empty town while a line sits under a heading no declared town owns, which closes an
  inflected heading vouching its own town empty. `EmptyProgramme` still needs no digit
  anywhere below the first town heading.
- **Kuvakukko** (45f4f5600): a cinema with no row is confirmed empty only when no line in
  its section opens with `Klo` and a digit, a weekday and `D.M`, or `D.M.`.

Left out, never a site failure, in all three. run.py keeps the venue's file while it has a
day ahead and publishes it empty as unverified after that; the provider reads `partial`.
Failing the site would withhold the other venues' screenings over one venue's rows, and
Alatalo's hand-typed page already took this line for unplaced `Klo` rows (329fed478).
Kuvakukko's "days listed and no row read" moved from a site failure to the same rule. The
cost: the run stays green, and the signal is the health line and the log line.

Genuine empty states kept: Kino Metso's three empty towns, with no unclaimed room in the
committed log; Toholampi, absent from the Alatalo page read 2026-09-24 with nothing on it
unaccounted for; a Manttu section holding only its notes, as read the same day. Toholampi
is confirmed by its absence from the operator's whole programme, not by a heading with
nothing under it. Reads: [docs/research/empty-states.md](../research/empty-states.md).

tribe.py and vpk.py publish one venue per site, so the gap cannot occur there; neither was
changed.

Tests: `test_nexxo_rooms.py`, `test_alatalo.py`, `test_kuvakukko.py`, on edited copies of
each fixture, two venues or more in each. Twenty mutations red, none VOID; eight were VOID
on the first pass and got the tests that now turn them red.

### The Events Calendar answer must carry its events list (2026-09-24)
Found reviewing tribe.py beside the gaps above. A 200 answer without an `events` list was
read as zero events, and the category endpoint, which a change to the events route does not
touch, then confirmed the venue empty; on page 2 the schedule published a page short at exit
0. `_page` now fails the site on it, as `nexxo.py` does without `shows`. Tähti Kino's live
empty answer, read 2026-09-24, carries `"events": []` and still publishes pending. Tests:
`test_tribe.py`, three shapes red before the fix, three mutations red, none VOID.

### A screening note is not a synopsis (2026-09-03)
Found by an external review: Cinema Niagara's sheet for "Keltaiset kirjeet" opened with
Gilda's senior-screening paragraph, its price and its coffee.

`films-extra.json` holds one Finnish synopsis per normalised title, filled by the first
provider to publish one. Gilda's MyCloudCinema `description` is HTML in paragraphs, and its
senior-screening entries open with the cinema's own paragraph (7 of 41 on 2026-09-03). The
adapter stripped tags and merged the whole thing under the plain key, and fill-if-empty
kept it there. Measured: 10 of 166 entries held a note, five under plain keys read by every
cinema, plus Bio Vuoksi's "Liput 8€ maksetaan Pennittömien edustajalle" as a whole text.

Two rules, at two layers:
- At the adapter, `synmerge.drop_notes_html(desc, names)` splits on `</p>` and drops a
  paragraph that quotes a price or names the cinema (stems as word prefixes, so "Gilda"
  catches "Gildan"). The paragraph is the source's own boundary; a sentence split would
  guess ("klo 18.15", "la 12.9." end sentences that are not).
- At the merge, `synmerge.is_note(text)` is true for a price in either order (`9€`,
  `€ 10`, `12 euroa`, `5 EUR`), and `merge()` refuses such text, counting it as
  `synopses skipped as screening notes (price): N`. The slot stays empty for TMDB.

Rejected: per-provider provenance, reusing text only for the supplying provider's cinemas.
That gives up the sharing, and the distributor's blurb is the same text at every cinema.
Accepted: Cinema Orion's "Ainoa näytös, klubialennus." lines carry no price and no cinema
name and still merge.

The cache was repaired in the same commit: the Gilda paragraph stripped from nine entries,
nouvelle vague blanked. `tests/test_synopsis_notes.py`; five mutations red.

### A refused request held its socket until the collector noticed (2026-09-01)
A suite run printed 24 ResourceWarnings. Thirteen were real: `urllib.error.HTTPError` is
the response object, and `common.fetch` kept the last one across the retry loop and raised
it, so every refusal left a socket open until garbage collection. Against a host refusing
everything (`mirror_posters` has had 185 failures against one host) that is 185 sockets.

`e.close()` on entering the handler. `code`, `reason` and `headers` survive the close, no
caller reads the body, and `close()` is idempotent. The other eleven were fixtures:
`shutdown()` leaves the listening socket open and two of the three local servers never
called `server_close()`.

`-W error::ResourceWarning` does not enforce this: the socket warnings are raised while
the interpreter shuts down, after the result is reported (measured 2026-09-01, exit 0 with
the leak reintroduced). `Checks` greps the captured suite output instead. Four new tests in
`test_common_fetch.py` go red with `e.close()` removed; `server_close()` removed puts the
warning back in the output the workflow reads.

### Seat counts are parsed and deliberately not published (2026-08-30)
README said the app shows "seat availability". It shows a sold-out mark. Finnkino gives an
`isSoldOut` boolean; eTiketti (`Vapaat paikat N / M`) and Riviera (`Varatut paikat: N / M`)
give counts, reduced to `soldOut: free == 0`; everyone else gives nothing.

The counts are thrown away on purpose. The data is refreshed a few times a day, so a count
is up to six hours old when read; "12 vapaata" can be zero by then and would be shown with
the authority of a figure. Sold-out survives staleness better. Do not restore the counts
without solving the staleness. 6 of 3059 showtimes were sold out on the day.

### A cancelled cloud run cost two venues every poster (2026-08-30)
Kino Engel and Kino Akseli rendered placeholder tiles for every film for hours. Three
causes lined up: the local half publishes those posters as the cinemas' own URLs and only
the cloud run mirrors them (38 of 38 Engel and 12 of 12 Akseli showtimes remote);
`cancel-in-progress: true` cancelled the run doing the mirroring when a manual dispatch
landed on a scheduled run, and nothing retries; and since v64 the client refuses a remote
poster, correctly. The normal window between publishing a remote URL and the cloud
rewriting it is a 2.7 minute median, 6.9 max; a cancellation stretched it to the next cron.

Two changes: `cancel-in-progress: false`, which keeps runs serialised and lets the queued
run finish; and `build_pages.py` prints the hosts and count of poster references still
remote (`78 poster references were still remote ... johku.com x58, kinoakseli.fi x20` on
the broken data). The state self-heals on any completed cloud run.

### The same asymmetry, one layer up: enrichment (2026-08-30)
After the poster fix, Kino Engel had no score rings: `enrich_tmdb.py` runs only in the
cloud, Finnkino has its own TMDB pass in `fetch_data.py`, and Engel and Kino Akseli had
neither. A local run took 38 of 38 Engel and 12 of 12 Akseli showtimes from a full set of
`tmdbId`, `tmdb`, `votes`, `tr` and `gids` to zero. `gids` drives the genre names and the
id half of the kids filter; `tmdbId` drives cross-chain merging.

Rejected: running `enrich_tmdb` on the local half. It writes three shared files that the
cloud pass also writes, and the wrapper pushes through `git pull --rebase`; a conflict in a
single-line JSON cache cannot auto-merge and would abort the run.

Decision: `run_site` reads the previous venue file and carries the five fields forward by
title, the key the TMDB pass uses. `setdefault`, so an adapter's own value wins and the
next enrichment pass overwrites all of it. This also covers a failed cloud enrichment and
the old trap of running `run.py` locally for a cloud provider, which once stripped 1201
showtimes of `tmdbId`. Four tests, break-verified.

The local half also runs `mirror_posters.py`. It rewrites only references still remote,
so pointing it at the whole `data/` directory touches Engel and Akseli and nothing else.
It needs Pillow: Akseli publishes 1984x2835 key art, 872 kB per poster against 57 kB
downscaled.

`mirror_posters` checks Pillow once, up front, by using it (open, convert, resize, save a
4x6 JPEG), since `from PIL import Image` succeeds on an install with an incomplete imaging
library. A missing or broken Pillow exits `CANNOT_RUN` (3): exit 0 had made "mirrored
everything" and "could not mirror anything" the same answer, and in the cloud Pillow is
installed inside the job, so a broken install would have gone green. A poster that fails
to download stays exit 0 (kinoakseli.fi fails every cloud run by design). No `--optional`
flag: neither caller stops on the exit code, since the cloud commits data before its gate
and the wrapper collects the code and carries on, so exit 0 only hid the degradation.
The wrapper prints `posters: DEGRADED` for 3 and `posters: FAILED` otherwise.

Covered by `tests/test_mirror_posters.py`. The Pillow-absent cases block the import
through `sys.meta_path`; two tests read `biorex.yml` to hold the mirror step recording
`$?` into `mirrorfail` and the gate comparing it to 0. Break-verified eleven ways. The
cases needing a real Pillow skip on the system interpreter; run them from the venv that
has it. That venv's path was written here once and removed the same day: CLAUDE.md forbids
machine-specific detail.

### Finnkino drops the odd character to "?" (2026-08-30)
The Vaiana live-action synopsis published "Catherine Laga?aia" and "Auli?i Cravalho"; both
names carry an okina (U+02BB). It is Finnkino's payload: `®`, `“ ”` and every `ä` in the
same sentence arrive intact, `json.loads` raises on malformed UTF-8, and the one decode in
`fetch_data.py` uses `errors="replace"`, which yields U+FFFD.

A "?" cannot be decoded back (apostrophe, okina, real question mark), so the repair
transcribes rather than guesses. `films-extra.json` already held the same 823-character
sentence from another chain with the okina intact. `synmerge.repair_from_twin` uses a
twin only when it has the same length and differs only where this text has "?"; a twin
that disagrees elsewhere is a different synopsis, and a genuine "Mitä?" is never touched.

- `tests/test_synopsis_repair.py` covers the refusals: a twin that differs elsewhere, a
  broken twin, a different-length twin, no twin, a real question mark.
- The lookup goes through `synmerge.norm()`, the key `films-extra.json` is written with.
- `data/films.json` was repaired in place in the same commit.
- The call site in `fetch_data.py` runs only from an ordinary connection; `[films] N
  character(s) restored from another chain's copy` in `run.log` confirms it.
- Left alone: `watch?v=` in YouTube URLs, and a missing space after a real question mark
  in a provider's prose.

### Where a run's time actually goes, and what could be taken back (2026-08-31)
Measured off one cloud run's committed logs: eTiketti is about 85% of a run, 185 requests
against 9 for Nexxo, 25 for BioRex, 6 for Gilda and 1 for Orion, about 3.5 minutes of
deliberate `sleep=1.2` between film pages.

Per-host pacing is the design and not negotiable. Serialising across unrelated hosts was
never a decision; it is how the loop was written when the module had two sites. The win
is a pool across hosts with the sleep kept within each host.

The first draft said "over sites", which is wrong: two Nexxo hosts serve two sites each,
so a pool keyed on the site doubles the request rate at those cinemas. The unit is the
host; the next entry is what landed. Hazards named here and resolved there: `common`'s
module-level counters, log interleaving, and the HTTP validator cache's per-URL writes.
Conditional GETs do not help: the eTiketti origins answer `no-store`.

### A run reads unrelated hosts at once (2026-09-01)
`run.py` fetches sites on different hosts concurrently and sites on one host one after the
other. `host_groups` groups by `urlsplit(site["base"]).netloc`, one thread per group, so
the sleep inside `fetch_site` still describes what a host experiences. Measured against
`SITES` on 2026-09-01: eTiketti is 17 sites on 17 hosts (16 read by the cloud); Nexxo is
8 sites on 6 hosts, because kinoaurora.fi serves kinoaurora and kinometso and kinohirvi.fi
serves kinohirvi and biosade. Keyed on the site, those pairs would be read at twice their
adapter's pace. `base` rather than `site`: Bio Säde's showtimes come from kinohirvi.fi
while its ticket links go to biosade.fi. Sites with no `base` share one group.

Hazards and decisions:

- Output is buffered per site and replayed in SITES order, both streams into one list, so
  the committed logs read chronologically. This also fixed the old buffering artefact
  where `run-nexxo.log` opened with the eighth site's stderr notice.
- `common`'s counters are locked. Nothing measurably went wrong under the GIL, but that is
  an implementation accident and false on a free-threaded build. The lock also lets the
  Retry-After ceiling be one decision: seconds are reserved before the sleep.
- `_write_slot` uses a per-thread temp name; two threads writing the same URL slot would
  otherwise truncate each other's `<hash>.tmp`.
- `synmerge.merge()` is a read-modify-write of the shared `data/films-extra.json`, called
  per site. It is serialised inside `merge()`, and the winner for a slot two sites fill in
  the same run is the earlier site in SITES order, tracked per run so the result is the
  same at every pool size. Text already in the file before the run is never touched.
  `synmerge.reset()` clears the map between modules. Probed with one slow and one fast
  site: `workers=1` and `workers=2` published different synopses before the fix.
- Everything else `run_site` writes was already single-writer: 57 venue ids and 31
  provider ids, each unique.
- The pool is 8 (`MAX_HOSTS`, overridable with `KINO_MAX_HOSTS`; 1 is the sequential
  path). It bounds this end only: open sockets and bodies in flight, at most
  `MAX_HOSTS * MAX_BODY` = 160 MB. "As many as there are sites" was rejected because it
  would raise the ceiling every time a cinema is added.
- A worker's exception is recorded and re-raised by the reader thread, which is where a
  sequential run would have raised it. Two earlier versions caught `BaseException` per
  site (a `SystemExit` read as a provider failure) or reported it as `not read` (the run
  exited 1 and still published). Ordinary failures stay per site. Teardown cancels queued
  hosts (`cancel_futures=True`) and waits for hosts in flight, so atomic writes finish.

Measured on the first pooled run: the "Fetch cloud providers" step took 186 s against a
562 s median across eight sequential runs (479-626 s), roughly 2.6-3.4x; one sample. Step
durations are job metadata, not Actions logs. Counters were unchanged for the same work
and every provider exited 0. One `run.py nexxo` from an ordinary connection into a scratch
directory matched the committed log; no second run was made to time it.

Covered by `tests/test_run_pool.py`, 22 tests against real localhost servers, and five for
the fatal path; seventeen break-checks red. Not changed: `fetch_site`, the workflow, the
site list. The local half's modules have one site each and read exactly as before.

Nexxo 403s, recorded so they are not blamed on the pool: the last sequential run before
this landed was refused by kinoset.fi, kinohirvi.fi (`Server: openresty`) and
kino-olympia.fi (`Server: Apache`), origin layer, no CF-Ray, while an ordinary connection
read them hours earlier. On 2026-09-05 the same three hosts refused again in the third
cloud run within 41 minutes, a manual dispatch stacked on two earlier runs. Rule until a
third point says otherwise: do not dispatch a cloud run within an hour of one that already
ran.

A Nexxo timeout, read from the runner on 2026-09-06 17:11 UTC (run 34047817637, `event:
schedule`, northcentralus). `jarvelankino.fi` (5.44.245.76) timed out after 15.3 s while the
module's five other hosts, probed from the same runner seconds later, all answered 200 in
under 3.3 s, `kinoaurora.fi` (5.44.244.43) on the neighbouring address among them. That
locates the fault on `jarvelankino.fi` or on the path to it and says nothing about what it
was: a timeout carries no mechanism, so it is no evidence of a refusal, a block or a rate
limit. The Regina reading differs exactly there, since a 167-byte 202 shell with SiteGround's
headers names itself. What this run had extra was a second sweep. A `workflow_dispatch` from
the local wrapper and a `schedule` run were created six seconds apart and `kino-data` ran them
back to back, 17:11:24 to 17:15:54 and 17:15:56 to 17:21:48, so the six hosts were swept twice
inside seven minutes and `jarvelankino.fi` was read at 17:13:19 and again after 17:16. Closely
spaced runs are the hypothesis that suggests, and nothing here tests it. The hour rule above
was written for a dispatch made by hand and nothing applies it to a queued run:
`cancel-in-progress: false` makes a duplicate wait instead of drop, which converts an overlap
into a back-to-back pair. Dropping a queued run is the owner's decision and is not made here.
A second paired timeout would repeat the whole uncontrolled setup rather than test the
pairing, and an unpaired one would weaken that explanation without ruling out limiting over a
window longer than the gap or on cumulative volume. What would discriminate is varying the
spacing deliberately and watching the host, which means probing a third party's server to
settle our own question. So this stays a standing observation, and a later run count does not
turn it into a finding. One thing it cannot answer: the cron is `30 2,6,10,14` UTC and that
`schedule` run was created at 17:11:27, delivered late by a margin nothing here measures. It
matters only because a late schedule is what landed on top of the wrapper's dispatch.

### A quiet week is not a broken parser (2026-08-30)
"A whole site parsing zero showtimes fails the run" catches a silently broken parser, and
after the eTiketti sweep eight sites are a single small venue (K-Kino 3 showtimes, Kino
Saimaa 2), so a quiet week turned the run red.

`common.EmptyProgramme` may be raised only after a listing was fetched and parsed and held
no films. A listing with films whose parse yields no showtimes keeps failing.

- No per-site "allow empty" flag: it would switch the check off permanently for the site
  most likely to need it. Emptiness is decided per run.
- An empty site writes no `venues-{provider}.json`, so the health line ages rather than
  going green on an empty answer.
- Previously published data is kept, since the discriminator can be wrong.
- The log line is `[provider] no programme published: ...` and the summary counts them.
- One break did not go red: removing `not venues` from the exit condition changed nothing,
  because an all-empty site is already counted earlier. That clause guards a module with
  no sites for this half, which must exit 0; it had no test until the break said so.

Covered by `tests/test_empty_programme.py`. Only `etiketti` raised it at the time; Nexxo
followed.

### Routing is per site, not per module (2026-08-30)
`where` on a registry entry decided which half fetched a whole adapter, so marking one
eTiketti provider local would have put all sixteen sites in both halves with two writers on
the same files. That is why Joutsan Kino was deleted, which was the wrong answer.

`run.py` filters `SITES` by each site's provider `where`.

- The half is derived, not passed: Actions sets `GITHUB_ACTIONS`, so the cloud workflow's
  bare `run.py <module>` keeps working without an edit to `biorex.yml`.
- Off Actions the default is `all`: `run.py etiketti` on a laptop exercises the adapter.
  The local wrapper says `--where local`, which keeps one writer per provider file.
- A site whose provider has no registry entry is kept in both halves;
  `tests/test_registry_sites.py` reports it.
- `tests/test_run_routing.py` asserts against the live registry that the halves are
  disjoint and complete.
- `run.py etiketti --half local` took `local` for a module name; `module_names()` is fixed
  and tested.
- The wrapper needs `run.py --where local` for the eTiketti module, or Joutsan Kino
  publishes nothing.

Joutsan Kino was fetched from an ordinary connection and committed with this change; its
posters stayed hot-linked until a cloud run mirrored them.

### Posters are mirrored (2026-08-29)
`scripts/providers/mirror_posters.py` runs after enrichment and before `build_pages`,
downloads every hot-linked poster into `data/posters/` and rewrites the `img` reference on
each show and in `films-extra.json`.

- The count was wrong by an order of magnitude: "1523 of 4279" counted references, not
  files. The data held 194 distinct remote URLs against 3494 references, a ~5 MB job.
- Everything is downscaled to 342 px wide: TMDB serves w342 at ~25 kB, MyCloudCinema only
  1080, Nexxo and Kino Akseli 1984x2835 key art. Pillow is installed in the workflow for
  this only.
- Named `sha1(url)[:16]`: seven hosts with no id namespace in common.
- A failure is logged and left hot-linked; a third party's uptime must not stop the
  pipeline publishing.
- Kino Akseli's posters mirror from a runner: the datacenter challenge is on its pages, and
  `wp-content/uploads/` served all six. "The site blocks datacenter IPs" is a claim about
  the endpoint that was tested.
- Nexxo publishes filenames with spaces, which urllib rejects; `fetch` goes through
  `request_url()`, and the cache key stays the published URL.
- The first run after this rewrote nearly every generated page as the `<img>` tags appeared.
- Open: nothing prunes a poster once its film stops screening; a few MB a year.
- `/data/` is disallowed in `robots.txt`, so the mirrored posters were unfetchable by
  Googlebot until `Allow: /data/posters/` overrode it.

### A Nexxo timeout recovered on its own (2026-09-14)

`run-nexxo.log` ended `exit=1` on the 20:37 UTC run: `jarvelankino locationid 1 FAILED:
<urlopen error timed out>`, previous data kept, which is the retention working. The 22:35
run read `[jarvelankino] Järvelän Kino (Järvelä): 8 showtimes` over 6 dates and the log
ended `exit=0`, 10 venues, 110 showtimes, 0 stale, 0 failures.
Nothing was changed for it and nothing here explains it: a timeout carries no mechanism,
which is the reading the 2026-09-06 entry above already records. Worth reopening only if
the same host fails again, since a second failure is the first evidence of a pattern.

### The strand comes off the original title too (2026-09-14)

Bug: `strands.apply()` split the strand off `title` and folded it into `method`, and never
touched `original`. Gilda publishes it in both, so six shows carried "Seniorikino: ..." as
their original title into `gather()`, which is where `enrich_tmdb` records the evidence an
entry was judged on, and into the search as its second query.
Fix: `apply()` splits `original` with the same exact list, so nothing new decides what a
strand is. What it deliberately does not do is copy `title` into `original`: a provider
publishing a real original-language title puts something else there, Kino Regina's
"La ballade des Dalton" against "Lucky luke sotapolulla", and overwriting it would cost the
match the original title exists to win. A strand on the original alone is split too,
without the clean title gaining a tag it never had.
Reconsideration checked rather than assumed: `reconsider()` re-judges a title when the
evidence moves from the strand-prefixed original to the clean one and leaves it alone when
the evidence is unchanged.
Tests: `test_vista.StrandTest`, 6 added, three mutations red including the original being
overwritten with the display title.
Published 2026-09-14 on the 23:18 UTC cloud run: no `original` in the data carries a strand.

### Myrskyn ikkuna is aliased, and TMDB simply has no Finnish title for it (2026-09-14)

Bug: 93 showtimes over 17 providers carried no `tmdbId`, so the film drew an initials tile
everywhere it played. The title is clean, so `clean()` left it and the search string was the
published title itself.
Cause, probed: `search/movie?query=Myrskyn ikkuna` returns 0 results with `language=fi-FI`
and 0 without. TMDB holds no Finnish title for the film at all, no `fi` entry in
`/translations` and no Finnish row in `/alternative_titles`. Search covers original, English
and registered alternative titles, so no query spelling, language parameter or year fallback
can reach it. Not a defect in normalisation, cache eligibility or the acceptance rules.
Identity verified before the id was written, because two 2026 films are called Pressure:
1318413 is 101 min against the 100 min all 17 providers publish, has 394 votes, and its
Latvian and Polish alternative titles name the Normandy D-Day story; 1701077 is a 5-minute
short with 0 votes.
Fix: one alias key, which both passes read. Tests pin the id and that both published
spellings normalise onto it, Gilda capitalising the second word.
Published 2026-09-14: the local run at 23:12 UTC gave Finnkino's 35 showtimes the id, and
the cloud run at 23:18 the other 58. A cloud run alone could not have shown the first,
which is why the check read show records on both halves rather than `run-enrich.log`.

### A language marker in the title blocked the TMDB search, closed (2026-09-15)

The fix `f3b61ee8` shipped on 2026-09-14 and could not be seen working for a day, because
`refresh.due` skips an entry already checked today and every affected key was stamped with
that date. Three runs went by skipping them, which reads exactly like a fix that does
nothing. The first cloud run on a new UTC date, `3d9a63c6` at 05:21 UTC on 2026-09-15,
searched them.
Published outcome, counted from that snapshot rather than against an earlier figure,
because screenings expire and appear between runs: **151 of 153** Kojootti vs. ACME
showtimes carry 1204680, across 26 title-and-provider combinations and every marker shape
the chains use: `(englanniksi)`, `ENGLANNIKSI`, `, englanniksi`, `(Dub)`, `(på svenska)`,
`(suomeksi puhuttu)` and the `suomeksi` family that already worked.
The two that do not are Gråben vs. ACME (på svenska) at Kino Marilyn, and they are not a
regression. The run searched them, `c` advanced to 2026-09-15, the search returned 1204680
as its only hit, and `x` stayed false because it is not an exact title: TMDB holds no
Swedish title for the film. `run-enrich.log` lists it under "weak match, no exact title",
so the trust gate withheld the id, which is the gate working. Not aliased: one weak hit is
not identity evidence, and aliasing on it would be exactly the shortcut the gate exists to
refuse.
Left behind: `kojootti vs acme eng` and `... sub` are orphaned cache keys from before the
eTiketti label strip. No show references them now, so nothing re-searches them and they age
out on their own.


### The year helper's claim was too strong, and its answer was unbounded (2026-09-15)

`common.resolve_year` was added earlier the same day and documented as a weekday
"determining" the year. Two corrections, both from the maintainer.

**The claim.** A published weekday **selects uniquely within the assumed three-year
window**; it does not independently establish the intended date. The uniqueness is real and
measured, 4,800 windows over 2000-2100 with no window where two candidates share a weekday.
What that buys is an unambiguous choice *given the window*, and nothing more. A page left up
for four years, or one with a mistyped weekday, still resolves to one of the three, and
neither the helper nor its caller can see that from the page. The wording is narrowed in
`common.py` and in all three adapters that use it.

**The bound.** The answer is now refused when it falls more than `MAX_AHEAD = 300` days
ahead or `MAX_BEHIND = 180` days behind. The failure this closes is specific: a wrong
weekday selects a candidate roughly 365 days away, and a phantom screening a year in the
future is shown to readers, while a stale row in the past is hidden by the client. That
asymmetry is why the bounds are asymmetric. They are wider than any programme these cinemas
publish -- the widest seen on 2026-09-15 reached 88 days ahead -- and far tighter than the
365 a weekday slip needs.

Concretely, read on 2026-09-15: `Ti 15.09.` resolves to 2026 and is published, while
`Ma 15.09.` and `Ke 15.09.` select 2025 and 2027, are refused, and leave the row skipped
and counted. Only three of the seven weekdays can be right for any day and month, and now
only one of those three is plausible.

Bio Savoy, added the same day, uses none of this: its rows carry a full ISO instant with an
offset, so nothing is resolved for it at all.

Tests: `tests/test_vaakuna.py` gained the bound cases and the three adapter tests that
asserted the unbounded behaviour were rewritten. Four mutations on the bound, all red:
removing it, widening it past a year, tightening it below a real programme, and ignoring
the weekday. The "too tight" mutation matters as much as "too wide": a bound that rejects
legitimate dates is the other way to get this wrong.

### The year helper resolved dates the documented rule never says (2026-09-15)

Two defects in `common.resolve_year`, both found by the maintainer against the committed
`3fa55a3b` with today = 2026-09-15, and both reproduced here before anything was changed.

**`resolve_year(18, 3, today)` returned 2027, 184 days ahead.** The nearest occurrence is
2026-03-18, 181 days back. The bound filtered candidates *before* the choice was made, so
the nearest was discarded and the next one substituted. That is not the nearest-occurrence
rule this function documents; it is a different rule nobody wrote down.

**`resolve_year(1, 6, today, weekday=Ti)` returned 2027, 259 days ahead.** 1 June is a
Monday in 2026 and a Tuesday in 2027, so a stale June listing carrying the wrong weekday
selected next year, and `MAX_AHEAD = 300` admitted it. The bound did not prevent the
failure it was added for.

**Fix, in order.** Selection happens first, under one rule: the weekday picks the single
candidate that can carry it, or nearest-occurrence wins with ties to the future. Only then
is the selected date accepted or refused against the window. It is never exchanged for
another year.

**The window is the caller's, and each source's is measured.** Read live on 2026-09-15:
Kino Vaakuna +0..+9 days over 10 dates, Kino Kuvakukko +0..+9 over 9, Kino Manttu -4..-2
(its fortnightly weekend already past), Kino Kirkkonummi -1..+9 over 8. All three adapters
pass `(30, 60)`, several times the observed span in both directions and far short of the
365 a weekday slip needs. `MAX_AHEAD`/`MAX_BEHIND` are gone; a single constant chosen to
make examples pass was the wrong shape for this.

**What this does not settle.** The window cannot tell a genuine far-future screening from a
mistaken one. A cinema announcing a Christmas gala in October would fall outside it and be
dropped, named in the adapter's log rather than published on a date it may not mean. If any
of these three starts publishing further ahead, the log says so and the number moves with
new evidence.

**A property worth recording**, found by a mutation that scored VOID: at a window narrower
than about 183 days, filtering before selecting and selecting before filtering are
*equivalent*, because anything inside the window is necessarily the nearest candidate, the
others being 365 days away. So the ordering defect is unreachable at (30, 60) and was only
ever reachable at the (180, 300) it shipped with. The test pins the ordering at (180, 300)
for that reason; testing it at the production window would prove nothing.

Tests: `tests/test_vaakuna.py::ResolveYearTest` gained both reported cases, the ordering
case, and the span check against what these sources actually publish. Seven mutations, all
red: reintroducing the filter-before-select bug, ignoring the window, widening it past a
year, tightening it below a real programme, turning nearest into next-occurrence, ignoring
the weekday, and dropping an adapter's window argument.

### One pool across every cloud module, not one per module (2026-09-15)

`biorex.yml` ran `run.py "$m"` once per cloud module, in a shell loop. Each of those
processes pooled *its own* sites by host, so 2026-09-01's win stopped at the module
boundary: eTiketti's twenty sites all finished before BioRex's first request, however many
of the other 25 hosts were idle. `scripts/providers/run_cloud.py` is the same host-keyed
pool, once, over all 48 cloud sites.

**Not by backgrounding the module commands**, which is the obvious version and is wrong.
They share `data/films-extra.json` and `synmerge`'s lock is a `threading.Lock`: across
processes it does nothing, so two merges would each write back a document built from what
they read and the second would drop the first's synopses silently. Separate processes also
each hold their own claim table and their own stdout, so the synopsis precedence and the
per-module log would both come apart.

**The shape.** Modules come from the registry in its order, sites from `run.sites_for`, so
routing is unchanged. Work items keep module order, site order, provider and host. They are
grouped by host **across modules**, so one host is one thread whether its sites belong to
one module or two. One ceiling, `MAX_HOSTS`, for the whole run; this replaces `run_sites`
rather than wrapping it, so there is no inner pool to multiply. Workers fetch and parse.
The coordinator publishes on one thread, in module order and then site order, which is the
order the per-module processes published in: `run_site` split into a fetch and
`run.publish_site`, which is the contract check, the strand split, the synopsis merge, the
enrichment carry-forward, the stale/pending/unverified decision and the file writes.
`synmerge.reset()` at each module boundary, as `run_sites` does.

**What had to be kept, and how.**

- *The Retry-After budget was per module*, because a module was a process.
  `common.accounting(name)` is a thread-local scope: `_stats` and `_throttle` are charged
  to the process and to the scope, the budget ceiling reads the scope's figure when there
  is one, and `run-{module}.log` reports the scope. `_diag_seen` is keyed by scope too, so
  a host refusing two modules names itself in both logs instead of only the first.
- *The committed log.* One `Recorder`, installed once rather than per module: a worker's
  output is captured per site and replayed whole into its module's file when its turn
  comes, and the coordinator's own lines go to the same file through a thread-local sink.
  Both streams land in one file, which is what `> run-$m.log 2>&1` did to them. Each log
  keeps its summary line and its `exit=N`; `check_runs.py` is unchanged.
- *Bounded buffers.* A global pool fetches ahead of the publication order, so results and
  captured text pile up behind the slowest early site. Capture is capped per site at 1 MiB
  (`KINO_MAX_CAPTURE`) and says so when it trims; `logs/run-cloud.log` reports the peak
  number of fetched-but-unpublished sites and bytes held. No response body is ever written
  anywhere but the existing validator cache.
- *Cancellation.* `shutdown(wait=True, cancel_futures=True)`, and a `SystemExit` out of
  adapter code is recorded and re-raised on the coordinator thread, as in `run_sites`. A
  module the run never reached has the abort and `exit=1` appended to its log, so a fatal
  cannot leave a previous `exit=0` standing and read as a success.

**Buffered results: measured at today's programme, 2026-09-15.** Ordered publication lets
the pool fetch ahead, so a slow early module leaves later modules' schedules waiting in
memory. The shape of the worst case is every site fetched and none published, which is the
whole cloud half at once; the size of it is whatever the half's programme happens to be. At
2026-09-15 that is 48 sites, 71 venue files, 3,312 showtimes, 1.83 MB of committed JSON --
**5.45 MB** held as the Python dicts a fetch returns, plus at most 1.72 MB of `_syn` that
`strip_helpers` removes at publication and about as much again in duplication across
venues, so under 10 MB against a runner's 16 GB.

**That is an estimate of today, not a bound.** It scales with the number of cinemas and the
length of their programmes, both of which grow, and nothing in the code caps it -- a
blocking permit would deadlock, since the site the coordinator is waiting for may be the one
that cannot get one. What makes the figure honest is that `logs/run-cloud.log` reports the
peak actually held on every run, so it is re-measured rather than asserted once. Captured
log text is the part that *is* bounded, at 1 MiB a site.

**The host audit, done before the overlap was enabled.** Every cloud adapter was read for
the hosts it can request, its module-level mutable state, its threads and its writes. None
uses threads. None mutates module-level state during a fetch; the only shared state is
`common`'s counters and `synmerge`'s claim table, both locked, and the latter now only
touched from the publication thread. The cross-module imports are constants
(`heureka` <- `etiketti.LANG_NAMES`, `cinemantsala` and `kinola` <- `gilda`). `prices.py`
writes `data/prices-{provider}.json` from the fetch, which is one writer per file and was
already concurrent inside a module.

**No two cloud sites of different modules share a registrable domain**, measured
2026-09-15; the pairs that do share a host (kinoaurora.fi twice, kinohirvi.fi twice) are
both inside `nexxo` and already share a `base`. `tests/test_cloud_pool.py` asserts that over
the live registry, so a provider landing on another module's domain fails a test rather
than quietly doubling the rate at one server, and `run_cloud.SHARED_UPSTREAMS` is where a
verified conflict `base` cannot express would go. It is empty.

**Secondary hosts, and the correction this entry needed.** It first said a page-derived URL
was "as true of the per-module pool, and nothing here changes it". That is wrong in the
direction that matters: while each module was its own process only sites of *one* module
could collide on such a host, and the coordinator overlaps every module, so the exposure is
new. Three things carry it now.

- **Declared.** A site names every host it knows it reads: `base`, plus `reads` for any
  other. `run.hosts_of` folds them together and `run.group_indices` makes the groups the
  connected components of sites and hosts, so a site naming two hosts joins every site
  naming either. One declaration exists today, Riviera's `tickets.rivieracinemas.fi`, which
  `prices.run` GETs and which `base` does not name.
- **Verified.** The four page-derived readers were read as a visitor on 2026-09-15 and every
  destination names the site's own host: BioRex 197 `movieUrl`s all on biorex.fi (read
  through `fetch_venue` with the film-page loop capped to none), Cinemahouse 21, 18 and 13
  tile links each on its own host, Tapiola 27 row hrefs all absolute and all
  www.kinotapiola.fi, Kinola 57 and 47 title hrefs on their own hosts. That is a third
  party's markup answering on one day, not a property of the code.
- **Claimed at run time.** `common.reading` claims whatever host a fetch actually goes to,
  for as long as that site keeps reading it, so an undeclared shared host is read by one
  site at a time whatever the href said. A site that cannot get the claim within
  `HOST_CLAIM_WAIT`, 60 s by default, **fails before the request is sent**: `HostBusy`,
  raised ahead of the socket, the previous files kept, and both sites named. That line is
  the signal to declare the host in `reads`, which moves the serialisation into the
  grouping where it costs nothing.

  **Going ahead after the wait was the first answer here and it was wrong.** It dropped the
  guarantee at exactly the moment it was needed -- when the other site is slow -- and a log
  line does not make two concurrent requests at one cinema's server acceptable. Failing is
  what the rest of the pipeline already does with a site it cannot read properly, so there
  is nothing new to reason about, and it does not deadlock either: two adapters holding each
  other's hosts wait at most one ceiling, and whichever gives up first releases on the way
  out, which usually lets the other claim what it was waiting for and finish. One of them
  fails, not necessarily both -- both only if they time out together. Bounded either way,
  where waiting is not, and visible, where proceeding is not. An adapter that catches
  broadly around its own fetches would have turned a refusal into a partial publish, so the
  refusal is recorded when raised and re-raised when the site's fetch ends, whatever the
  adapter did with the exception.

Every module's log now ends with the hosts its requests were aimed at, so a collision
appears in the committed record instead of being argued about. **Attempted, not reached:**
the host is recorded when the request goes out, so a refused connection counts the same as a
body, and the line is evidence about where a module aimed rather than about what answered.
That is the question `reads` has to answer, so it is the right one to record.

**BioRex and Cinema Orion now name their host.** Neither carried a `base` and neither reads
one; both build every URL from a module constant, verified before the key was added. Left
alone they would have shared the conservative base-less group with each other -- the two
heaviest single-site modules read one after the other for no reason. No cloud site is
base-less now, and a test says so.

**Measured: nothing in production.** The fixtures show two modules on different hosts
overlapping, one host never overlapping across modules, the ceiling holding, and one worker
and eight writing identical files and identical logs. That is equivalence and isolation, not
a speedup: a localhost server with a 50 ms delay is not eTiketti. The production figure
waits for an ordinary scheduled run, and the open item is in `IDEAS.md`.

Tests: `tests/test_cloud_pool.py`, 57, reusing `test_run_pool`'s local HTTP servers because
overlap is the property under test and a mock would encode the answer. Two modules on one
undeclared host are shown not to overlap on it while overlapping on the hosts they do
declare, which is the control that keeps the first assertion meaningful, and the ceiling is
shown to send nothing at all when it gives up. 29 mutations, all red; one survived
first -- releasing a site before the exception it died on is recorded, which a real run
never reproduces because the coordinator is not scheduled inside those few bytecodes, so it
is asserted directly on `read_host` instead of through the pool.

### What the cloud run's slowdown was attributed to, corrected (2026-09-15)

The 2026-09-15 session read two cloud runs and attributed the gap between them. The
readings stand; the arithmetic on top of them did not, and it is corrected here rather than
carried forward. The timings are Actions step durations, which is the only place they
exist; everything in this repo's committed logs is unchanged by the correction.

**The fetch step is about 56% of the increase, not about 90%.** Total 4.9 min to 10.5 min
is 294 s to 630 s, +336 s. The fetch step 247 s to 435 s is +188 s. 188/336 = 56%. The
other 148 s is somewhere else in the run -- enrichment, poster mirroring, page building,
checkout, commit -- and was never attributed.

**The 104 s between a 331 s reading and the 435 s one does not isolate Kinola.** The two
runs differ in more than one provider, so the difference between them is the difference
between the runs, not the cost of the module that happened to be added.

**Kinola's own deliberate waiting is 48.0 s and 27.6 s, and those do not add.**
`fetch_site` sleeps 1.2 s before every film page but the first, and `logs/run-kinola.log`
records 41 pages for Kilta and 24 for Laika: 40 x 1.2 = 48.0 s and 23 x 1.2 = 27.6 s. The
two sites are on different hosts, so `run.py` reads them in parallel and has since
2026-09-01, which makes their sum of 75.6 s worker time and not elapsed anything.

**And 48 s is not the elapsed contribution either**, which is how this was first written.
It is the explicit sleeping inside one site, interleaved with 41 requests: a lower bound on
that site's own duration, since the requests and the parsing are on top of it, and no
statement at all about how much the site adds to the run. What it adds depends on whether
it was on the critical path, and the per-module logs carried no timing before
`run_cloud.py` added one. Nothing measured to date isolates it.

**Conditional GETs do not shorten it.** See the entry in
[2026-09-providers.md](2026-09-providers.md) for why: a 304 is still a request and the
1.2 s pacing is not conditional on anything.

**The enrichment and poster spikes are per batch of new films, not once and for all.** A
run that meets a set of films it has not seen enriches and mirrors them; the next such run
does it again for the next set. Calling them one-off reads as "this will not recur".

**~70 s of the increase appeared before any new provider landed and is still
unattributed.** Do not guess a cause for it.

What follows from all of this is the entry above: the fetch step is the largest single
piece of the increase and was being spent one module at a time. That is what `run_cloud.py`
addresses, and the production figure for it is not measured either -- see `IDEAS.md`.

### The cloud pool, measured in production (2026-09-16)

The open item this closes asked for one thing: the coordinator's cost on an ordinary
scheduled run, against the **fetch step** it replaced, 247 s and 435 s. Two runs now carry
`run_cloud.py` and both are green. The figures are from the committed logs, not from
Actions.

| | `0b4a167f`, committed 23:18 UTC | `e9b4e85d`, committed 00:39 UTC |
|---|---:|---:|
| wall | 175.6 s | 147.5 s |
| fetching summed across overlapping workers | 926.0 s | 863.4 s |
| sites fetched | 48 | 48 |
| peak sites fetched and unpublished | 45 | 43 |
| peak captured log held | 2,370 B | 2,229 B |

Both read 20 modules, 48 sites, 46 host groups, pool of 8.

**The two figures measure different things.**
247 s and 435 s are Actions *step* durations for a shell loop that started twenty Python
processes. `[cloud] … wall` is measured inside one process, from after the registry is read
and the host groups are built to after the last module is published, so it excludes the
interpreter's own startup and the imports, and the step around it is higher than 147.5 s by
however much that is. Nothing here measures that overhead. What can be said without it: the
step was 247 s at its cheapest reading and the work inside the process is now 147.5 s and
175.6 s, so the gap against the cheaper baseline is about 70–100 s and against the dearer
one about 260–290 s, on a sample of two runs of each.

**What 5.3 and 5.9 are.** 926.0/175.6 and 863.4/147.5 are the average amount of
overlapping fetch work per second of wall. They are not a ratio against anything that was
ever run: the per-module processes already overlapped the sites *inside* a module, sixteen
of them in eTiketti alone, so no sequential 926 s run exists to divide by. The figure says
how much concurrency the pool sustained, and nothing about what it saved.

**The queue waits show contention for slots.**
46 host groups against a pool of 8, so 38 of them wait for a slot at the start. What the
logs report is one number per module, that module's longest wait, and on the later run
those run from 0.0 s -- BioRex and Nexxo, which are among the eight that start immediately
-- to 89.6 s for Kinola. No per-site distribution was recorded, so "most sites wait about a
minute" is not a claim these logs support. Fetching sets the run's length: BioRex is one
site at 94.6 s and eTiketti's sixteen span 92.7 s, while the eight workers are eight
cinemas' servers read at once. Raising `MAX_HOSTS`
buys wall time by adding simultaneous load on unrelated third parties, which is the thing
the pacing exists to limit. It stays at 8.

**The buffering estimate was close to the actual case.** The 2026-09-15 entry called the
worst case "every site fetched and none published" and sized today's programme at about
10 MB. The runs held 43 and 45 of 48 sites, so the worst case is roughly the ordinary case
and the estimate stands as written. The captured log is the part that is bounded, and the
run held 2,229 and 2,370 bytes of it in total across every waiting site -- the 1 MiB cap is
per site and applies to the largest single capture, which these totals put an upper bound
on rather than measure, so nothing came within reach of trimming.

**What two runs leave open.** They differ by 28.1 s and read different programmes, so what
separates them is the programme and the moment. Neither figure measures variance. Neither is compared against a per-module run of the same day,
because the code that would produce one is gone.

**A third run, 2026-09-16, the first not used to write this entry.**
`c796413c`, committed 05:16 UTC: 158.0 s wall, 928.8 s of fetching summed across
overlapping workers, 48 sites, peak 45 held and 2,465 bytes of captured log. It falls
between the other two, so three runs now span 147.5 s to 175.6 s. That is still three
samples of a run whose programme changes under it. It settles that the first two were not
a lucky pair. The 247 s reading of the old fetch step stays the nearest thing to a
baseline.

### An opera relay's season is the part the title cannot show (2026-09-16)

Kino Tapiola's `The Royal Opera: Carmen`, one screening on 2026-12-13, shipped an initials
tile and no synopsis. TMDB registers the event as `Royal Ballet & Opera 2026/27: Carmen`,
so the exact-title rule refused it and `data/tmdb-titles.json` kept the weak match 1702759
with `x:false`. That is the gate working, and the alias file is the documented way out.

Aliased: `the royal opera carmen` -> `1702759`, the id read off `/movie/1702759`. The
record is the 2026/27 season, the opera the cinema names, first released 2026-11-10 in
Germany, and Tapiola relays it five weeks later.

**Only Carmen. Tosca shows why.** The cinema publishes three more of these, and the
same weak search found an id for each. `The Royal Opera: Tosca` is relayed 2027-06-06, and
its weak match, 1482356, is the **2025/26** season record, 3h30, released 2025-10-01 -- the
right opera, the right house, the wrong year's production, which is a wrong poster on the
row where there had been a missing one. A relay's title carries the work and the company.
The season separates two records, and only the date shows the season. `Cosi fan Tutte` (1702775,
released 2027-02-23, relayed 2027-04-04) and `Götterdämmerung` (1702769, released
2027-02-03, relayed 2027-02-28) are 2026/27 records whose dates fit, and they are left
unaliased because nobody asked for them. The evidence for them held.

Tests: `tests/test_tmdb_matching.py` gains one, pinning the id, the norm key and Tosca's
absence. Four mutations, all red: the alias dropped, the id swapped for the 2025/26 Tosca
record, Tosca aliased to it, and the key written as the published title rather than its
norm.

### An exact title match put the 1998 film on 256 showtimes (2026-09-16)

`Practical Magic: Lumotut sisaret` is how thirty-two providers publish the 2026 sequel,
and it is also the title TMDB holds for the 1998 original, 6435. The matcher did not fail:
it found an exact title and wrote the id with `x: True`, which is the strongest verdict it
has. 256 showtimes across 46 venue files then carried 1998's poster, its 6.8 from 1853
votes and its trailer, on a run of screenings from 2026-09-15 to 2026-10-01 that publishes
129 or 130 minutes where it publishes a runtime at all.

**What settles the identity.** Two
chains publish the title with a `2` in it -- Bio Savoy's `PRACTICAL MAGIC 2` and Kino
Akseli's `Practical Magic 2: Lumotut sisaret` -- and both matched 1302904 from the start,
on the same data, with no alias. The records read off TMDB: 1302904 is *Practical Magic 2*
(2026), 2h10, released 2026-09-11 in Finland, five days before the screening that surfaced
this; 6435 is *Practical Magic* (1998), 1h44, released here in February 1999.

**An alias alone could not have fixed it.** `main` dropped an
aliased entry only when it was **not** exact, on the reasoning that an alias exists because
the search could not settle a title. That reasoning holds for a weak match and fails for
this one: a Finnish distributor title that is another film's registered title produces a
confident wrong answer, and the entry would have been skipped before the alias was read.
`alias_supersedes` now also replaces an exact entry whose id disagrees with a bare-id
alias. A search-string alias still leaves an exact entry alone: it is a better query, with
no id in it to disagree with the matcher's.

Aliased: `practical magic lumotut sisaret` and
`practical magic lumotut sisaret k18 anniskelunäytös` to `1302904`. The second is Kino
Tar's, which appends its strand as a *suffix*; `run.py` splits prefixes only, so that
spelling normalises to its own key.

**The cost:** a repertory screening of the 1998 film
published under the bare Finnish title would now take the sequel's id. Nothing in the data
does that today, and the alternative is 256 rows that are wrong now.

Tests: `tests/test_tmdb_matching.py` gains four -- the override, the agreeing alias that
must *not* churn a good entry every run, the search-string alias that must not unseat an
exact one, and all three published spellings pinned to the sequel. Five mutations, all
red: the old weak-only rule, every alias dropping its entry, a search-string alias
unseating an exact entry, the Kino Tar spelling left out, and the alias pointed at 6435.

### A guard states what it observed (2026-09-16)

Four cloud modules failed in the 17:17 UTC run -- `cinemahouse`, `tmb`, `kirkkonummi` and
`nexxo` -- across seven independent domains, having all been green at 11:16 and 15:10.
Only Nexxo's log named a cause anyone could act on: `403 from kinoset.fi`, `403 from
kinohirvi.fi`, `403 from kino-olympia.fi`, openresty and Apache. The other three said the
template had changed, `cinemahouse` most flatly: "no cr-movies-filter-select on the page:
the template changed".

**Seven operators did not change their templates in one afternoon.** Every one of those hosts was read from an ordinary connection minutes later and
served its real page with the marker present: toijalan-kino.info 23,187 B with
`Valkokankaalla`, kinosampo.info 22,945 B, kinokirkkonummi.fi 268,581 B with its icon list,
www.kinopiispanristi.fi 176,986 B with `cr-movies-filter-select`, kinoset.fi 40,415 B. So
the parsers are right, the templates are unchanged, and the reading side is the cause --
which is CLAUDE.md's standing rule about datacenter addresses, arriving as a failure that
blamed the cinemas instead.

**A missing marker says the marker is missing.** It cannot distinguish a changed template
from a challenge page, an error page or a holding page, and none of these guards recorded
what arrived, so the run left no evidence to tell them apart. `common.served` returns the
two facts that do, without keeping anything: how many bytes came back and what the document
calls itself. A programme is tens of kilobytes titled after the cinema; a challenge is
about a kilobyte titled "Just a moment...". The title is a third party's text going into a
committed log in a public repo, so it is unescaped, collapsed to one line and cut to 70
characters -- never the body, which this repo does not keep.

The three adapters that failed this way now state it, and `cinemahouse`'s three messages
lost the cause they asserted. The wording the others already used -- "treating it as a
fetch or template failure rather than a cinema with nothing on" -- was honest and is kept;
it just never said what was served.

**What this does not do.** It does not stop the failure, and it should not: a site that
cannot be read fails, keeps its previous data and is named in the log. That is what
happened. It also does not decide whether those providers belong on the local half. That is
one run's evidence and a maintainer's call, and it is in `IDEAS.md`.

Tests: `tests/test_cinemahouse.py` 47, `test_tmb.py` 37, `test_kirkkonummi.py`. Five
mutations, all red: the title uncut, uncollapsed and unescaped, a page with no title
reporting nothing, and the guard naming a cause again. Two tests that pinned the string
"screening template changed" now assert the failure and its evidence instead, which is the
distinction that let the wrong claim stand.

### Each area file is read once per build (2026-09-17)

`build_pages.load_shows` parsed a venue's `area-{id}.json` for the venue's own page and
again for its city's, where the city has more than one venue: 47 of 101 venues on the day
this was written, 148 calls over 101 files. It is cached now, keyed by the file's path,
mtime and size rather than by the venue id, because the tests build from temp roots and
from data they rewrite between builds, and a key on the id alone hands the second build the
first one's schedule.

**Measured before it was changed.** The whole build runs in about 0.19 s and this is a
fraction of that, so it is no speedup. It is kept because the second read is waste. The
commit message says the same, so no performance claim is read into it later.

Callers must not mutate what they get back, and none does: the city pass copies every show
it keeps and `group_by_day` only sorts and groups. Tests: one read per file, a rewritten
file read again, and a missing file not cached as empty, in `tests/test_landing_pages.py`.
Three mutations, all red -- no cache, keyed by the venue id, and keyed without the mtime.

### The city-link check reuses the build's venue list (2026-09-17)

The second half of the same waste the entry above removed. `main` ends a build by checking
`index.html`'s city links against the data, and `sync_home` called `home_cities()` with no
argument, which called `load_venues()`. So a process holding all 101 venues in memory read
them again from disk: `data/areas.json` and 55 `venues-*.json`, 18,326 bytes, measured on
the day this was written.

`sync_home` takes a `venues` argument now and main passes the list it built at the top.
`--home` passes none and still reads the files, because it is a separate invocation with
nothing loaded.

**Why the two lists agree.** `home_cities` calls `city_of` on each venue, and main has
already written `city_of(v)` into `v["city"]` by the time it checks. `city_of` returns
`v["city"]` when that key is set, so a second reading gives what the first one wrote. The
other two keys main adds, `label` and `slug`, are not read by `home_cities`, whose slug is
the city's own.

No speedup is claimed and none was measured. The whole build is about 0.19 s. The reason
is that the second read is waste, the same reason recorded for the area-file cache.

Tests: three in `tests/test_landing_pages.py` -- a whole build loads the venues once,
`--home` on its own still loads them, and the list main holds names the same cities as a
fresh read. Four mutations, all red: `sync_home` ignoring its argument, main not passing
one, `home_cities` reloading unconditionally, and `city_of` made non-idempotent, which
reds the third test and four older count tests with it.

### Seven venues the runner could not read, and it cleared by itself (2026-09-19)

Moved out of `IDEAS.md` with its heading, once there was more than one run's evidence.

The 17:17 UTC run of 2026-09-16 failed `cinemahouse`, `tmb`, `kirkkonummi` and `nexxo`
together over seven domains, after two green runs the same day; every one of those hosts
served its real page to an ordinary connection minutes later. The entry left the maintainer
two ways out: either it clears by itself, as the Nexxo timeout of 2026-09-14 did, or the
four move to `where="local"` and take about a dozen venues onto the laptop.

**It cleared.** Measured 2026-09-19 over the committed logs, which is the only record this
repo keeps: each of the four has 15 logs since 2026-09-16 17:00, of which exactly one is
non-zero, the 17:17 run itself, and the 13 runs after it all end `exit=0`. Nothing was
changed for them. The 403s were `Server: openresty` at the origin on kinoset.fi, so the
reading stays what the guard entry above says: a refusal that names the layer, on an
address the origin declined that afternoon.

What the episode did leave behind is `common.served`, which records how many bytes came
back and what the document calls itself, so a missing marker can no longer be reported as
a changed template. That is the entry "A guard states what it observed" and it stands.

---

## films-extra.json is one line, and both halves rewrite it
**Built 2026-09-19.** `biorex.yml` pushes with `pull --rebase` and three retries,
deliberately without `-X theirs`. `data/films-extra.json` was 346 kB on one line, written
by three passes and rewritten by both halves within the few minutes that separate their
commits; a one-line file cannot content-merge, so a local push landing mid-run fails all
three attempts identically and the cloud run's whole commit is lost with it.

Measured 2026-09-19 before the change, and **no occurrence was found**. Of 27 recorded
failures of the fetch workflow, 24 were the provider gate, which runs after the commit,
and three the commit step: 2026-08-26 and twice on 2026-08-30, all before `ref: main` and
`rebase --abort` landed on 2026-08-31. None since. No committed `run-cloud.log` carries
"could not push", which is weak evidence on its own: a run dying at the push commits no
log. The exposure was structural rather than observed, the local half committing three to
five minutes before each cloud commit by design, and it recurs with every simultaneous
pair of halves.

**What was built.** One emitter, `common.write_films_extra`, with `indent=1`,
`sort_keys=True`, `ensure_ascii=False` and a trailing newline, used by all three writers:
`synmerge.merge`, `enrich_tmdb.merge_extra` and `merge_shared`, and `mirror_posters`. A
shared function rather than three call sites passing the same keywords, because three
copies of a keyword pair is the shape that drifts.
`tests/test_films_extra_format.py` drives two of the three writers for real and compares
their bytes with the emitter's, and holds the committed file to the same output, which is
what catches the third.

**Cost, measured.** 346 351 bytes on one line becomes 361 666 over 4370 lines, 4.4%
larger. `sort_keys` makes the order a function of the content rather than of whichever
pass wrote it last, so the emitter stays deterministic. The generated pages are unchanged
by it: `build_pages.py` reads the file's content, and the content did not move.

**What was checked outside this repo.** The local wrapper does not parse this file. It
stages it with the rest of `data/` and, on a conflict in it, refuses to resolve one
unattended rather than picking a side, which would drop a synopsis. That behaviour is
still correct and needed no change; one key per line only makes the conflict rarer.

### The fi-FI search hides TMDB's English title, and one en-US search settles it (2026-09-19)

Closed. `search` runs with `language=fi-FI` so `pick()` can compare TMDB's Finnish title
against the Finnish one a cinema publishes, which is what made "Autofiktio", "Kuopus" and
"Kummisetä osa II" match at all. The cost is the mirror case: where TMDB holds no Finnish
translation the response falls back to the **original** title, so a cinema publishing
TMDB's own English title can never match exactly. Measured over the 36 weak cache entries
of `73a075acc`, ten would become exact with an en-US comparison. Evidence:
[docs/research/tmdb-matching.md](../research/tmdb-matching.md).

**Decided by the maintainer, with bounds.** A second search in en-US runs only for a title
the fi-FI pass left unmatched or weak, which is the only state it can improve. An exact
en-US match fills an empty or weak slot. It never replaces a cached id, and structurally
cannot: the whole branch sits inside `if not mid`. A candidate whose id disagrees with the
weak one is logged to stderr and left for the alias file rather than published, which is
the `black magic rites` case the research file records, where an exact en-US match lands on
a different id than the cache holds and an exact match is trusted. No re-judging pass is
added. One request per title, counted in the log.

**What it settled on the day it shipped: nothing, and that is the expected number.** The
committed weak list went 5 to 5, with 5 asked, 0 settled and 0 disagreeing. The ten cases
the decision was measured on had been aliased by hand the night before, 24 keys in
`tmdb-aliases.json`, so the work this would have done was already done. What the change
buys is the next one: a title published under TMDB's English title now settles without an
alias, and one that would settle on a different id is named instead of shipped.

Covered by `EnglishSecondSearchTest`: the settle, the one-request budget, that an exact
fi-FI match never reaches it, the disagreement being named and not published, an empty slot
filled, and the counter appearing whatever it found. Four mutations go red.

### LI is Finnkino's fourth private language code (2026-09-22)
`test_every_code_in_the_committed_data_is_known` was red on `main`: `data/area-1100.json`
carried `EN-S, FI-S, LI-A` on the two "Sve\u010dias \u2013 The Visitor" rows at Kinopalatsi
Helsinki, and `LI` is in no name table, so the app drew the bare code and the page's
language phrase read "LI". ISO 639-1 `LI` is Limburgish; the film is Lithuanian, and
Finnkino means `LT`.

The same fix as `SE`, `TU` and `MA` before it, in the same place: one entry in
`FINNKINO_LANG`, so `lang_tag()` maps it before anything downstream sees it and no name
table gains a code that is not ISO. The two committed rows were repaired by hand, because
`fetch_data.py` cannot run on a runner and the data would otherwise carry `LI` until the
next local run; the two pages that render them were regenerated in the same commit.

Found while establishing a baseline for the `docs/research/flow-review.md` work, not by that review.

Break-verified with three mutations: the entry removed and the entry pointed at the wrong
language, each turning `tests/test_lang_normalization.py` red, and the repaired rows put
back, which turns `tests/test_landing_pages.py` red.

### Two decorations on a title, and the cache entries no rule could reach (2026-09-23)
Reported from the live site: "Päivien lumo + tekijävierailu" at Kino Tapiola drew an
initials tile with no poster and no score, while the bare "Päivien lumo" matched 1563565
at Kino Laika, Kino Kilta and Kino Regina. The suffix was the whole problem, and the same
shape sat on two more rows at Kino Aurora.

`clean()` gained two anchored rules on the search string, both naming what they strip:

- `TRAIL_EVENT`, for an event attached to the screening rather than to the film:
  `+ tekijävierailu`, `(+leffalukupiiri)`, `(+keskustelutilaisuus)`. Each noun is named
  because "+" belongs to real titles. "Romeo + Juliet" holds 454 at Cinema Niagara and
  Kino Regina's double bill "Sylvi + anna-liisa" is two works; both keep every word.
- `TRAIL_FORMAT`, for a bare format token with no brackets. Two titles carried one, and
  the second was the worse: "Spider-Man: Brand New Day 2D" at Kino 123 and Trio 123 held
  **557**, Raimi's Spider-Man (2002), so seven showtimes carried the wrong film's poster
  and rating while 39 other cinemas matched 969681. The client has read these four tokens
  as noise in `mergeKey` for longer than the search string has.

Neither reached the Spider-Man row on its own. Its cache entry predated `q`, the field
`reconsider()` compares to notice that `clean()` moved, and a missing `q` read as
"unknown, re-judge nothing". That reading froze the entry on whatever a long-gone cleaner
decided, permanently and invisibly: 262 of 609 entries were in that state. A missing `q`
now reads as due. The objection it answered, that the pass introducing `q` would
re-search everything at once, is already answered by `RECONSIDER_BUDGET`: 25 a run in key
order. The backlog drained over six local runs here and the entry came back 969681.

Measured, before and after: showtimes with no `tmdbId` 274 -> 272, distinct titles 87 ->
85, and one wrong id replaced by the right one. The weak-match list is unchanged at 12, so
nothing was closed by accepting a weak candidate. "Suomi radalla (+keskustelutilaisuus)"
and "Sylvi + anna-liisa" have no TMDB record either way and stay correct absences, as does
"Avengers: Endgame Encore 2D" once its token is off.

`tests/test_tmdb_matching.PublishedCoverageTest` is the standing guard, and it is the part
worth keeping: over the committed data, no unmatched title may open with the whole cleaned
search string of a title that did match. Both of these would have failed it before they
were fixed, which is what the third test in that class asserts. It accuses only what it
can prove, suggests no id, and its allowed list is empty. 557 joined the wrong-id table.

Break-verified with six mutations: each rule removed, the format rule's word guard
dropped, the event rule widened to eat everything after a "+", a missing `q` reading as
unknown again, and a published row decorated and unmatched in the committed data.

### Riviera's screening language from the ticket page the price pass reads (2026-09-23)
Riviera published `lang: ""` for every screening, so its tickets drew no audio or
subtitle language beside Finnkino's and Gilda's. Its ticket page states both, and
`prices.enrich` already fetches that page for the price, so the language comes off the
same response: a `fields` parser whose answer is cached beside the price and put on rows
with no value of their own. The endpoint and the pages are the ones the price pass
already reads; what changes is timing. An entry cached before this is due once more,
after the never-read keys and ahead of its 48 h expiry: 82 on the day, read at most 40 a
run, so the first runs make up to that many extra reads. Until an entry is re-read, and
if the re-read fails, it keeps its price. A parser that raises records nothing and leaves the price.

A line is published only when every word in it names a language, through
`etiketti.lang_codes` for Finnish names and a table of the client's English names for the
page that printed "Spanish"; "Alkuperäinen", "-" or an unknown word publishes nothing for
that line, and a missing subtitle line is not "no subtitles". Sample and capped run in
[docs/research/screening-language-sources.md](../research/screening-language-sources.md):
of 12 pages read through the adapter, 11 gave a language and all 79 cached prices were
unchanged. The other 70 fill at 40 pages a run.

Break-verified with eight mutations: old entries never re-read, a raising parser uncaught,
a row's own value overwritten, the read order ignoring missing fields, half a line
published, an English name missing, the adapter not wired, and a failed re-read dropping
the cached price.

### The cloud run commits the Swedish pages (2026-09-23)
The Swedish pages shipped on 2026-09-22 under `sv/`, and the cloud job's `git add` still
listed `teatteri kaupunki en`. Every run rebuilt them and committed none: the bot commit
of 15:11 UTC that day changed 47 English pages and no Swedish one, and the only commits
touching `sv/kaupunki/helsinki/` were code pushes. Live Swedish pages therefore held
whatever the last code push had built, and the first code push after a data run failed
the drift check on them. The list now names `sv`, the 54 pages that had fallen behind
are regenerated in the same commit, and `tests/test_pages_committed.py` derives the
directories from the sitemap so a new page directory cannot be left out again. The local
half's wrapper, outside this repository, carries the same list.

### Cinema Orion's language from each film's own page (2026-09-23)
The front-page table names no language; each film page it links to has `Kieli:` and
`Tekstitys:` rows, and all 18 read that day had both. `film_language` reads one page per
film through `prices.enrich`'s cache (data/film-lang-orion.json), cap (FILM_MAX 12 a run)
and pacing, with the same strict rule as Riviera, now shared as `etiketti.strict_codes`.
The value is the film's and goes on each of its screenings only when nothing suggests two
versions: rows of one film page that differ in title, or a title or note naming a version,
settle nothing and are counted in the log. No film on the day had either. The film-page
URL is the row's own link, carried as the `movieUrl` helper that publication strips.
A capped live run read 12 pages and each value matched its page; six waited for the next
run. Break-verified with six mutations, two of them added after the first pass let them
survive: the title guard and a row's own value.

### A changed TMDB id takes the old film's fields with it (2026-09-24)
Found in review. `merge_extra` filled `s.fi`, `s.en`, `tr`, `img` and `r` only into empty
slots and recorded no id, so an alias override, a `reconsider()` re-judge or a weak entry
turning into an alias kept the previous film's fields. "Ryhmä Hau: Dinoelokuva" and its
`suomeksi` key carried the synopsis, trailer and poster of TMDB 893723, the Mighty Movie,
under 1185806 (cache history: 893723 held that text at e57cbe432). On shows, `tmdb`,
`votes`, `tr`, `gids` and `oyear` were written only when truthy and run.py carried the old
values: Kapina showed 7.2 from 4929 votes at eight cloud venues while its entry held 14
votes, under the floor. Measured at 219818453: 22 trusted films-extra keys with `tr` off
the cached trailer, 47 with `img` off the cached poster; shows out of step on Kapina,
Stromboli, Fantom, Naisen kasvot and two Royal Ballet relays.

Decision. A films-extra entry records `id`, the entry its TMDB fields came from, and `ts`,
the synopsis slots the pass filled. TMDB-owned: `r`, `tr`, `img` (written by nothing else;
the mirrored copy of the entry's own poster counts as it) and the slots in `ts`. They
follow the current trusted entry every run and empty with it, which covers a changed id
and an emptied value with one rule. Cinema-owned: every slot not in `ts`, in fi, sv and en,
since adapters declare English too, and `kr`/`krs`, which stay merge_shared's. An untrusted
key loses `ts` slots and text equal to its candidate's own; `en` is no longer blanked
whatever wrote it, which had been wiping declared English for every unmatched film. An
entry with no `id` predates this: a slot equal to the entry's own text is adopted as TMDB's,
other text is taken as the cinema's. On a show every PUBLISHED field is the entry's value or
absent; no adapter writes any of them. The key stays the raw title.

Not changed. run.py's carry already holds its source id: the bundle carries `tmdbId` with
the fields, all from one pass, and the next pass now replaces them wholesale. fetch_data.py
rebuilds shows and films.json from the response each run and writes nothing TMDB-derived
into films-extra, so it carries nothing forward and already agrees.

Tests: `test_tmdb_identity.py`, 11 tests, 17 mutations, all red; one first-pass mutation
was equivalent (clearing `ts` slots on an id change, which following the entry already
does) and the block it hit was removed. A key merge_shared created holds no TMDB field
and is left alone, or a second pass would add `id` to it (`test_shared_rating`). Three `test_tmdb_trust.py` fixtures now seed
residue with `id`/`ts`, the shape the pass writes.

Data repair, same day. The code cannot tell a stale TMDB synopsis written before `id` from
a cinema's, so the committed data was cleaned once by provenance: every `fi`/`en` text any
entry of `tmdb-titles.json` held across its 226 revisions is TMDB's. Such text on a key
whose current trusted id held it was recorded in `ts` (102 fi, 237 en); on any other key it
was cleared, 25 slots: the Mighty Movie on three Ryhmä Hau keys, 1998's Practical Magic,
Obsession's English on Naisen kasvot, four other films' blurbs on Regina keys (Dumbo,
Juhlat, Niskavuoren naiset, The Time That Remains), and 15 English texts of earlier weak
candidates. Then a local TMDB pass, poster mirror and pages. After: 0 keys with `tr` or
`img` off the cache (22 and 47 before), no show field out of step, Kapina unrated in all 26
files, 444 of 543 entries carrying `id`.

### run.py drops a kept file whose every day has passed (2026-09-24)
Review finding #10 at c416446fd. `publish_site` kept any previous file for a venue that
came back with no shows and marked it stale, even when every screening in the file had
passed. The file's `generated` froze, so the provider read stale for as long as the venue
stayed empty, and every combined city view holding it aged on that stamp. `fetch_data.py`
had fixed this for Finnkino after Maxim Helsinki (2026-09-18); `has_future_shows` moved to
`common.py` and `publish_site` now applies it, with today taken in Helsinki from the run's
`now`. A spent venue is published empty, stamped fresh, and recorded `unverified`, which is
what the next run calls an empty file anyway, so the state does not flip between runs.
The provider therefore stays `partial` while the venue is empty: nobody vouches for the
emptiness. On the day, no committed provider file listed a stale venue, so the first run
changed no data. `SpentPreviousTest` in `tests/test_run_partial.py`, three venues; the
shared fixture's kept file moved to a day after the tests' NOW, because its only day had
been in the past, which is the case this changes. Five mutations, all red.

### Kino Engel declares each synopsis's language (2026-09-24)
Review finding #6 at c416446fd. `engel.details()` published every film page's synopsis as a
bare string, which synmerge files as Finnish. Read from an ordinary connection on the day:
the `BARNSÖNDAGAR` pages carry a Swedish synopsis and the rest a Finnish one, and neither
kind declares it (`<html lang="en-US">` and `og:locale en_US` on both). `KIELI: Ruotsi` is
the screening's audio, not the text's. Each text is now placed by `common.syn_language`,
the classifier kinola, johku, helios, tribe and kuusamotalo already use, and withheld when
it places nothing. Of the 12 films listed that day, 11 place as Finnish and Gråben vs Acme
as Swedish. Data repair by provenance: the commit introducing each text, then the carrier
in that commit's area files. Three `fi` slots held Engel's Swedish (Gråben vs Acme,
Minioner & Monster, PAW Patrol: Dinosaurie-filmen); all three moved to an empty `sv`, `id`
and `ts` unchanged. No page changed: the one screening still listed is outside the four-day
window. `EngelTest` in `tests/test_syn_declared.py`; three mutations, all red.

### Gilda and Savon Kinot declare each synopsis's language (2026-09-24)
Review finding #6 at c416446fd, where the review had inferred the source. Traced on the day
by running each adapter's own parse over a live read of the endpoint it uses and comparing
its `_syn` with the committed slot. Gilda's booking feed, keyed `"fi"` with no language per
text (`descriptions` and `content` empty on all 47 records): of 36 synopses, 26 place as
Finnish, 6 as English, 4 as nothing, one of those the placeholder "Not Supplied". Savon
Kinot's film pages: 20 Finnish, 1 English (Linkin Park: Unshatter), 3 unplaced. Every
flagged slot equalled the adapter's text byte for byte. Both now place each text with
`common.syn_language` and withhold what it cannot place. eTiketti declares per site, as
Kinola does: Niagara's blurbs are Finnish then Swedish in one text and would be outvoted
into Swedish, so the other nineteen keep the bare string. Cost: 3 Gilda and 3 Savon Kinot
Finnish texts withheld today; each already holds its slot, so nothing changed. Data repair:
11 slots, 7 moved to an empty `en`, 4 cleared (the placeholder, and three whose `en` held
TMDB's text), `id` and `ts` unchanged. No page carried any. Korjaamo, a Vista site, wrote
ten more English `fi` slots, traced the same way, and is not in this change. `GildaTest`
and `EtikettiTest` in `tests/test_syn_declared.py`; eight mutations, all red.

### Kino Kilta's site menu cleared from 46 Finnish synopses (2026-09-24)

`kinola.py` read an SVG `<path>` as a paragraph (finding in
[docs/research/kinola.md](../research/kinola.md)), so `films-extra.json` entries held
Kilta's menu, both titles and one strand line as their Finnish synopsis: 39 when first
counted, 46 by the time the repair was applied on 2026-09-24, the cloud runs in between
having added seven with the unfixed parser. The slot is keyed by title, so the text reached
every chain showing the film: 22 generated pages carried it in 26 paragraphs, city pages
and Finnkino theatres included.

Repair: every `fi` slot beginning with the exact menu string was emptied, 46 entries,
nothing else touched; `id`, `ts` and the other languages are unchanged. None of these slots
was TMDB's (`fi` in no entry's `ts`). A slot filled before a run stands in `synmerge`, so
the fixed parser could not have replaced them; the next cloud run fills each one Kilta
still lists. Pages rebuilt with `--date recorded`: 22 written, and each equals its old copy
with the menu paragraphs removed.

Keys: `agentti o s s 117 iskee`, `akira kurosawan unet`, `anni tahtoo äidin ja kala`, `aurinko ei mahdu sur rurin ensimmäiset 30 vuotta`, `begyndelser`, `daughters of darkness`, `departures`, `dialogpolisen`, `free at heart`, `hiljaiset sillat`, `i am going to miss you`, `i rarely wake up dreaming`, `idän soturit`, `ihmistenmetsästäjät`, `iván hadoum`, `kaupungin synty`, `kinokopla alpha`, `kinokopla dig xx`, `kinokopla orava`, `kinokopla se oli pelkkä sattuma`, `kinokopla the drama`, `kinokopla tie pimeään`, `kinokopla vasenkätinen tyttö`, `kolme väriä sininen`, `liekki ja nuoli`, `lyhytelokuvakooste havun kaiho`, `montreal my beautiful`, `pieni kauhukauppa`, `saapasrasvaa`, `she killed in ecstasy`, `suburbia`, `suden hetki`, `the babadook`, `the last paradise on earth`, `the secret reading club of kabul`, `tiger on the beat`, `tuhkimo`, `turku aiheisia lyhytelokuvia`, `vinokino departures`, `vinokino free at heart`, `vinokino i am going to miss you`, `vinokino i rarely wake up dreaming`, `vinokino iván hadoum`, `vinokino lyhytelokuvakooste havun kaiho`, `vinokino montreal my beautiful`, `vorosen perhe ja kyttäjahti`.

### Korjaamo's English synopses moved out of the Finnish slot (2026-09-24)

`vista.py` published every synopsis as a bare string, which `synmerge` files as Finnish.
It now places each with `common.syn_language` and withholds one none settles. Ten
`films-extra.json` entries held English in `fi`, every one first written by `1eb2bb0d5`,
the commit that added Korjaamo (traced with `git log -S` on each text): `fez summer 55`,
`hijacked twice`, `my father s scent`, `one more show`, `rose water` and `helaff short
films` 1 to 5. Each text moved to its empty `en` slot and `fi` was emptied; no other
field changed and no film is listed today, so no page changed. Korjaamo's feed on
2026-09-24, read through the adapter's getter (it asks for XML; the same URL answers JSON
to a request without that `accept`), held 17 synopses, all Finnish. The seven other `fi`
slots the classifier places as English or Swedish open in Finnish and stay, as recorded
for bundle 5.

### Elokuvateatteri Star declares its synopses' language (2026-09-24)

The controller check of the 08:13 local run found `hanuman ansh`'s `fi` slot holding
English again, the text the TMDB repair had cleared; `[star] synopses merged: 1` in
`logs/run-etiketti-local.log` wrote it back. Star published bare strings, which
`synmerge` files as Finnish, because bundle 5 turned `declare_syn` on for Savon Kinot
only. Star's 24 film pages read on 2026-09-24: 22 Finnish, 1 English, 1 no language
settles (Avengers: Endgame Encore, whose `fi` slot another chain already fills); none
mixes Finnish with Swedish. Star now declares, and the one `fi` slot was emptied; its
`en` slot, TMDB's (`ts`), is unchanged. One page changed: Kino Myyri's, which drew the
English paragraph as the Finnish synopsis.

### Kilta's synopsis read by section, and two Nordic films repaired (2026-09-24)

The longest-paragraph rule of the same morning filed the Swedish text of `begyndelser` and
`vorosen perhe ja kyttäjahti` as Finnish in the 14:17 cloud run: Kilta writes the Finnish
synopsis in two paragraphs and the Swedish in one longer one after `---`. The maintainer
rejected "longest Finnish paragraph, else longest" in favour of reading Kilta's sections
and withholding one whose language is not settled; the page structure and the 40-page
read are in [docs/research/kinola.md](../research/kinola.md). Repair, those two entries
only: the Swedish text moved to the empty `sv` slot as it was, and `fi` holds the whole
Finnish section from the live page read that day (823 and 841 characters). No page
changed: both films screen outside the pages' four-day window.

### Three Nordic films' mixed Finnish and Swedish text split (2026-09-24)

`beginnings begyndelser` (Cinema Niagara, 2026-09-02), `kuukauden pohjoismainen the last
paradise on earth` (Kino Iiris, 2026-09-14) and `the love that remains ástin sem eftir er`
(Niagara, listed today) held the cinema's whole blurb in `fi`: a Finnish section, a `***`
or `--` line, a Swedish section, as one bare string. Identity: each key is the title the
cinema published and the text matches the film; the Niagara entry equals film 107's live
page section for section, read 2026-09-24. Each text was split at its one separator:
`fi` keeps the Finnish section and the empty `sv` takes the Swedish, prize headlines,
strand label and source credits dropped. A merge of Niagara's current mixed string over
the result writes nothing, since both slots are filled; the other two are listed nowhere.
Niagara still publishes the mixed string for new films: a follow-up for its adapter.


### Without a year, the published runtime breaks a same-title tie (2026-09-24)
Replaces "Without a year the first exact hit wins as before" from 2026-09-13 in
`enrich_tmdb`. Found through Cinema Sheryl's "Happy Together", aliased the same day
(record in [2026-09-providers.md](2026-09-providers.md)). Sheryl publishes 96 min and no
year. TMDB's first exact hit was Damski's 1989 comedy (102 min), and Wong Kar-Wai's 1997
film (96 min) was no candidate at all: under fi-FI TMDB titles it "Happy Together –
viimeinen tango Buenos Airesissa".

**Rule.** When a title has no published year but has a published runtime (`gather()` now
collects every one as `m`) and its search returns an exact title, `with_rivals()` runs the
same query in the other language and adds that language's exact hits. If two or more
films are left, each one's runtime is read from `/movie/{id}`. `pick()` then takes the
film nearest any published runtime within `TIE_RUNTIME_TOL_MIN` = 10, and TMDB's order
decides an equal distance. When no film is within 10, or no runtime is known, TMDB's order
stands as before. The en-US second pass follows the same rule. A published year still
decides first. Each decision is logged as "runtime decides".

**Measured 2026-09-24**, 157 committed titles matched exact with no year but with a runtime:
38 had two or more exact films. The largest gap to the right film was 10 (Kino Kilta's
84-minute Tuhkimo against TMDB's 74). Two live matches were wrong and are re-judged in
this change, both at Cinema Niagara, whose film pages give the 1980 releases: Prom Night
(Paul Lynch, 1 h 32 min) had 8617, the 2008 remake at 89, and now has 36599 at 93.
Without Warning (Greydon Clark, 1 h 29 min) had 25494, a 1952 film at 75, and now has
44932 at 89. Their cache entries were deleted by hand so the new rule could judge them,
because a settled exact entry is never searched again.

**Rejected: refusing when no film is near.** Measured on the same set, it would have
blanked The Shining, published at the European cut's 119 minutes against TMDB's 144, and
Riviera's 413-minute Twin Peaks season. Neither case gives it anything to decide, so the
old behaviour is kept for both.

**What it does not catch.** A right film offered in neither language, next to a wrong one
within 10 min. Before the English rival was added, "Happy Together" was that case: 102
against 96. The Finnkino pass (`fetch_data._pick`) is separate and unchanged.

### A weak TMDB candidate stays cached and is retried daily (2026-09-25)
Found in review (#8, #25). `enrich_tmdb.main()` deleted every entry with an id and `x`
false as the cache loaded, a sweep written as a one-off for the fi-FI search change. The
same ten titles were searched from scratch on every cloud run. Measured 2026-09-25 on the
committed tree, real TMDB, nothing else due: 56 requests a run, 53 of them for those ten
(28 searches, 25 detail and video calls), 3 genre lists.

**Rule.** A weak entry stays in the cache, still untrusted, and is searched again once its
attempt date `a` is `WEAK_RETRY_DAYS` = 1 old, the daily retry an unmatched title already
gets. Until then it gets no request, rating refresh included. `reconsider()` now re-judges
it on changed `q`, `o` or `y` the same day, and an alias still supersedes it at once. A
weak entry records its candidate's title in `t`, for the log line "weak candidate kept",
and a string alias it was searched with in `al`, so an alias that still finds nothing
exact waits for the schedule instead of re-searching every run. A weak entry taken out for
a search that raises goes back with today's `a`. An exact entry an alias id overrides is
still not restored: it is known wrong.

**unpublish_extra.** Same removal path. Its comparison against the candidate's own text
covers entries written before `ts`; with the entry deleted on load, a weak film that had
left the programme had nothing to compare with. The entry now persists, so it does. No
such residue in the committed data today.

**Measured after**, same inputs: 3 requests on a day the retry is not due; 53 once on the
day it is. Same-day output identical to the committed data, key order included (the sweep
reordered ten keys every run). Retry day against the old code: area files and films-extra
identical, the cache differs by ten `t` fields only.

Tests: `test_tmdb_weak_retry.py`, 12 tests on a pinned clock; 13 mutations, all red. Three
older tests pinned the sweep and were re-pointed. `fetch_data.py` keeps its own sweep; the
Finnkino cache holds no weak entry today.

### A colon head is trusted only on an agreeing year or runtime (2026-09-25)

Audit finding E1, P0. `queries()` searches the part of a title before a colon as a
fallback, and `pick()` judged an exact match against that candidate, so a head that is
another film's whole title was trusted. Live at 65f24acfb: "Teatteri: The Audience", a
149-minute National Theatre Live relay, carried Keaton's 1921 short *The Play House*
(TMDB fi title "Teatteri", 24 min) on three Savon Kinot rows; Orion's truncated "Oasis:
Don" carried a 1955 "Oasis"; Riviera's "Twin Peaks: Kausi 1 (1990)" and "Kausi 2" carried
the 116-minute 1989 pilot against 465 and 413 published minutes. `fetch_data._queries`
never searches a colon head, for the same reason (2026-08-27 entry above).

The head stays a candidate, because it rescues a title the distributor punctuated
differently, but `colon_head()` names it and `head_agrees()` holds an exact hit on it to
the published evidence: every piece both sides carry has to agree (year within
`YEAR_TOL`, runtime within `TIE_RUNTIME_TOL_MIN`), and at least one has to be there. The
runtime costs one `/movie/{id}` request, only for a colon-head exact hit. A refused hit
becomes the weak fallback and is logged as "colon head matched, not backed by year or
runtime, refused". Requiring every present piece to agree, rather than either one, is
what refuses Kausi 1: its year agrees with the pilot's and its runtime does not.

Scan before purging: every exact cache entry for a published colon title (55) was read off
`/movie/{id}` in fi-FI and en-US; six carried the head's film and not the whole title's.
Four are the rows above, purged with the stale `oasis dont look back in anger` (same 1955
id, not published today) and re-enriched: all four now weak, no id, rating, year or TMDB
poster. Two stay: "Late Lammas- elokuva: Hämäräpuuhissa" (81 min against 85, agrees), and
Kino Akseli's "Practical Magic 2: Lumotut sisaret", which publishes neither year nor
runtime and got an alias to the id it already had, 1302904, so the sequel match the
2026-09-16 alias comment relies on stays.

`test_tmdb_queries.py` pinned the head as a fallback and still does; its docstring now
says the fallback is corroborated. Tests: 3 in `test_tmdb_queries.py`, 3 in
`test_tmdb_matching.py`, 8 mutations, all red.

### A dateless TMDB hit never wins against a published year (2026-09-25)

Audit finding E2, prior review #7. `pick()` counted a hit with no release date as
plausible for any published year, since "unknown cannot contradict". Kino Regina's
"Stromboli", published as 1950 and 107 minutes, took 1443988: a dateless five-minute short
about the volcano with 0 votes, its poster and its plot in the `en` slot. With a year
published, a dateless hit now cannot confirm it and never enters the tier, so it is only
ever the weak fallback, logged as "no release date to check the published year against,
refused". Without a year it is judged as before.

Scan: every exact cache entry with a published year and no recorded release year (56) was
read off `/movie/{id}`; Stromboli was the only dateless one and none was more than a year
off. Purged and re-enriched: 4173, Rossellini's *Stromboli* (1950-02-15, 107 min, Ingrid
Bergman), rating 7.1 from 235 votes; the poster is mirrored. No page changed: both rows
are in November, outside the pages' window.

`test_tmdb_matching.py` pinned the old acceptance (`..._cannot_contradict_the_year`); it now
pins the refusal. Tests: 4 in that file; restoring the old `pick()` body turns two red.

### An alias is found on the cleaned title too, and replaces a disagreeing Finnkino entry (2026-09-25)

Audit finding E3, prior review #8. Both passes looked an alias up on the published
title's key only. Kotkan Leffat's "Avengers: Endgame Encore 2D" searches "Avengers: Endgame
Encore", itself an alias key for 299534, and held a two-vote record (1777404, since deleted
by TMDB) exact on 7 rows. Finnkino's "Avengers: Endgame Encore" had the alias on its raw
key, but the Finnkino sweep only dropped non-exact entries, so a one-vote record (1774125)
stood on 96 rows. The other 135 rows carried 299534, 8.2 from 28,693 votes.

`enrich_tmdb.alias_of` reads the title's own key, then `norm(clean(title))`; the reconsider
guard, the supersede sweep (on the entry's recorded `q` and `y`) and the search loop all
use it. The fallback is skipped when the title publishes a year: "Faust (2011)" cleans to
"Faust", and the bare "faust" alias pins Murnau's 1926 film (the accepted cost recorded on
2026-09-19 stays confined to the bare title). `fetch_data.alias_overrides` applies
`alias_supersedes`, the cloud pass's rule, so an alias id that disagrees replaces an exact
Finnkino entry; only a year printed in the Finnish title stops the cleaned lookup there,
since OCAPI's year is the release date.

Cloud half re-enriched here: the Kotka rows carry 299534 and six pages changed. The
Finnkino half needs a run from an ordinary connection and lands at the next local run.
Tests: 3 in `test_tmdb_matching.py`, 4 in `test_finnkino_trust.py`; 6 mutations, all red.

### A cinema's synopsis replaces a slot TMDB filled (2026-09-25)

Audit finding E4. `synmerge.merge` read any text in a slot as spoken for, so once the
TMDB pass had filled one (recorded in `ts`), no cinema's own synopsis could replace it,
against the rule the same file states: the provider's own synopsis beats TMDB's. A film
first shown by a chain with no `_syn` kept TMDB's text after Gilda or anyone else
published its own, with "synopses merged: 0" as the only trace. At 65f24acfb, 84 live
titles held TMDB's Finnish text, 64 of them at chains whose adapter publishes `_syn`, an
upper bound since `_syn` is not persisted.

A slot listed in `ts` is now open to a cinema's text, which takes the slot out of `ts`
(and drops `ts` when it was the last) so `sync_extra` leaves it alone on the next pass.
The SITES-order tie-break inside a run is unchanged. The failing test was written first
and went red on the unfixed code. No data is changed here; the swap lands as each chain's
next run merges. Tests: 2 in `test_synopsis_lang.py`; 3 mutations, all red.

### An unreadable films-extra.json fails the step and stays as it was (2026-09-25)

Audit finding C5. `synmerge.merge`, `enrich_tmdb.merge_extra` and `merge_shared` each read
films-extra.json with `except Exception: doc = {}` and then wrote the file back, so one
stray comma from a hand edit had the first site to publish cut 568 entries to 1: every
cinema `sv` slot, hand-cleaned text, `id`, `ts` and `kr` lost until something re-supplied
them. `synmerge.read_extra` is now the one reader for all three: a missing file is an empty
one, anything else raises (a parse error, or a document that is not an object). On the
run.py path the raise lands before `commit_staged`, so the site fails with its venue files
discarded and the previous ones live; the enrich pass exits non-zero, which the workflow
records and turns red after the commit step. `fetch_data.py` only reads the file for the
"?" repair and never writes it, so it keeps its fallback.
The tests were written first and failed on the unfixed code (two failures, one error).
Tests: 4 in `test_synopsis_lang.py`; 5 mutations, all red.

### A screening with no title is dropped and counted, never published as "?" (2026-09-25)

Audit finding A6, inferred and reproduced first. eTiketti (`meta["title"] or "?"`), Nexxo
(`movieTitle or title or "?"`), BioRex (`movieName or "?"`) and the Finnkino pass
(`title or "?"`) would put every row out titled "?" with real times and exit 0 if the H1
moved or the key was renamed; these four serve 70 of 134 venues. A test per adapter
published "?" on the unfixed code. Each now drops the row and logs "N row(s) with no
title, dropped", and none of them can turn that into an empty programme: Nexxo counts the
row as broken, so a venue whose every row went raises its "none parseable" error rather
than reaching `EmptyProgramme`; eTiketti clears `complete`, so no venue is confirmed empty
and a site with no live venue fails in run.py; BioRex has no confirmation to give. The
Finnkino whole-run check for the same case is its own item (A2). No "?" row is in the
committed data. Tests: `test_missing_title.py`, 5 tests; 5 mutations, all red.

### The zero-showtime rule is tested, and holds for the Finnkino pass (2026-09-25)

Audit finding Q and A2. The run-level backstop in `run.Tally.site` (a site with no live
venue its adapter did not confirm empty counts as a failure) survived a mutation against
the whole suite: every test reaching it had a second reason to fail, usually the run's own
"no venue at all" check. `test_zero_showtime_rule.py` runs two sites through `run.main`,
one live, so only the backstop can fail the run; a confirmed-empty site and an
`EmptyProgramme` still exit 0, as CLAUDE.md describes. The mutation is now red, and so is
one that confirms every site.

`fetch_data.main()` had no whole-run check: with OCAPI's `showtimes` renamed, seven dates
answered, nothing parsed, and the seventeen venues were published under a fresh
`areas.json`. It now fails before writing anything when no date lists a screening, so every
venue keeps its file and `areas.json` its age. Finnkino gets no `EmptyProgramme` case: no
empty OCAPI listing has been seen. The Finnkino half needs a run from an ordinary
connection to be exercised live. Tests: 5; 3 mutations, all red.

### A refused host claim stays a failure whatever the adapter raises after it (2026-09-25)

Audit finding C3. `common.reading` re-raised a swallowed `HostBusy` only when the body
returned normally, so any other exception took its place, including `EmptyProgramme`,
which since 43fb0b0c8 publishes every venue empty and pending: an adapter that caught the
refused listing fetch and found no film marker in the empty result would clear its data
and exit 0 on either runner. The body's exception is now caught: with a refusal recorded
it becomes `HostBusy` chained from it, so the site fails and its previous files stand; an
interrupt or an exit still passes through untouched. None of the six adapters that raise
`EmptyProgramme` wraps its listing fetch today. Test: the contended two-module pool in
`test_cloud_pool.py`, adapter swallowing the refusal and then raising `EmptyProgramme`, red
on the unfixed code; 2 mutations, both red.

### run.py releases a site's host claims before it publishes (2026-09-25)

Audit finding C2. `run_sites` wrapped the whole of `run_site`, fetch and publish, in
`common.reading`, so a `HostBusy` an adapter swallowed (etiketti catches around a film page)
was re-raised only after the site's area files and `venues-{p}.json` with `status: ok` were
live, while the log said FAILED. `run_cloud` already fetched inside the claim and published
outside it. `run_site` now takes the claim as an argument and wraps only the fetch with it,
so the refusal comes back before anything is written. Latent on the local half: no two
local sites contend for a host today, but any module run by hand could. Test:
`test_run_host_claim.py`, a host held by another site beforehand so nothing is sent, red on
the unfixed code (three files written); moving the publish back inside the claim turns it red.

### The shared fetch refuses a redirect from https to http (2026-09-25)

Audit finding C7. `common.fetch` opened with `urllib.request.urlopen`, whose redirect
handler follows `https:` to `http:`, so a WordPress site whose `siteurl` is http:// would
have its programme read over cleartext with nothing logged, against CLAUDE.md's rule never
to follow such a redirect. `NoDowngradeRedirect` refuses it with `DowngradeRefused`, which
`fetch` raises at once rather than retrying, since the same request gets the same answer.
`fetch` now opens with `make_opener()`, and the two adapters that build their own opener
use it too: BioRex's cookie jar and Johku's interim-response HTTPS handler. Upgrades and a
plain-HTTP host's own redirects (Bio Savoy, Alatalo) are followed as before; a real local
server confirms the http-to-http path end to end. `enrich_tmdb`, `indexnow` and
`ci_verified` call fixed https endpoints with their own `urlopen` and are unchanged. Tests:
`test_redirect_downgrade.py`, 6 tests, red on the unfixed code (no handler); 5 mutations,
all red.

### A cloud site's fetch has a wall-clock deadline, and a failed fetch step still commits (2026-09-25)

Audit finding C1. Nothing bounded a request, a site or a run in wall-clock time: `timeout`
is per socket operation, page loops catch and go on, and a host that answered its listing
and then stalled cost 105 s per film page (3 x 30 s plus backoffs). The only bound was the
job's 30 minutes, and Actions cancels before "Commit data and logs", so no cloud site's
data or logs were committed while the host stayed stalled.

`common.site_deadline(seconds)` bounds one site's fetch on its thread: every request's
socket timeout is capped at what is left, a request or a retry sleep that would start past
it raises `SiteDeadline` without being sent, and the body is read with `read1` and checked
between chunks, so a host dripping one byte at a time ends too. An adapter that swallows it
has it re-raised when the fetch ends, the rule `reading` follows for `HostBusy`.
`run_cloud` wraps every site in `SITE_DEADLINE`, 300 s (`KINO_SITE_DEADLINE`, 0 turns it
off): the longest site in 76 pooled runs to 2026-09-25 took 108 s. The site past it fails
and keeps its files, and the rest publish, as around any failed site.

`biorex.yml`: the fetch step gets `timeout-minutes: 20`, which fails the step instead of
running into the job cap, and enrich, mirror, pages and commit run on `!cancelled()`, so a
failed or timed-out fetch step still publishes what it finished while a cancelled run
commits nothing. That a step timeout is a failure and not a cancellation is from GitHub's
documentation; no run was dispatched to see it. Tests: `test_site_deadline.py`, a stalling
and a dripping local server, 4 tests; 6 mutations, all red.

### The Finnkino poster download checks its id and its body (2026-09-25)

Audit finding E5. `download_poster` put OCAPI's release id into the file path and the CDN
URL unchecked (a rid of `../../escape` wrote two levels above data/posters), saved any body
over 500 bytes without decoding it (`common.fetch` returns a body cut short of its
Content-Length without raising), wrote in place, and returned an existing file on every
later run with no request, broken or not. Now the id must be a moviexchange release UUID,
the shape all 84 committed Finnkino posters are named by; the request brief said numeric,
and a numeric check would have refused every one of them, so the measured shape is what is
checked. A body is decoded before it is kept, through a temp file and a rename, and a file
on disk that does not decode is fetched again. Decoding is Pillow's where it is installed
and, on an interpreter without it, which is how the system python3 runs, a JPEG must open
with SOI and close with EOI, which a truncated body loses; all 84 committed files pass both.
The Finnkino half needs a run from an ordinary connection. Tests: `test_finnkino_poster.py`,
5 tests, red on the unfixed code; 5 mutations, each decode branch red on the interpreter
that runs it and VOID on the other.

### The Finnkino pass keeps a weak candidate too (2026-09-25)
Follow-up to the record above, for `data/tmdb.json`. `fetch_data.main()` swept weak
entries on every load the same way. Removing the sweep alone would not have been enough:
a weak entry carries `n`, `x` and `g`, so `_tmdb_complete` calls it complete and
`refresh.due()` would park it for a week with a trailer, daily without, and the loop,
seeing a cached id, would re-read the wrong film instead of searching.

**Rule.** Inside `enrich_cached_ratings`, a weak entry leaves the cache for a search when
its daily retry is due or when OCAPI's query or release year differs from the `q`/`y` it
recorded; until then it is outside `refresh.due()` and gets no request. The alias
override moved into the pass from `main()`, with the cloud pass's `al` exemption and the
same restore: a weak entry whose search raises goes back with today's `a`. Weak entries
also record `t` for the kept-list log line. Publishing is unchanged: only `x` and an id
publish.

Measured: the Finnkino cache held no weak entry on 2026-09-25, so no request count moves
today. Tests: `test_finnkino_weak_retry.py`, 12 tests; 12 mutations, all red, the sweep
removed alone among them (7 red). Needs a local run from an ordinary connection to be
exercised live.

### "(Neulekino)" comes off the TMDB search string (2026-09-25)

Elokuvateatteri Star published its knitting screening as "Presidentin kyyditys
(Neulekino)" beside the plain title, and the row drew no TMDB match while the plain one
matched 1412214 (Samuli Valkama, 87 min, the runtime Star publishes for both). That made
`test_tmdb_matching.PublishedCoverageTest` fail on the committed data. `PAREN_NOISE` now
takes a bracketed "(Neulekino)" off the search string only; the published title, the cache
key and films-extra's key keep it. It is not in `strands.EVENT_PREFIXES`, because run.py
would then also split a published "Neulekino: X" and change what a visitor reads; Savon
Kinot already files the word in `method`. Re-enriched: the row carries 1412214, the same id
and the same held-back score as the plain title. No page changed (the screening is on
8.10.). Tests: 3 in `test_tmdb_queries.py`, one of them over real titles carrying the word;
2 mutations, both red.

### An aborted cloud run replaces an unreached module's log (2026-09-25)

Audit finding C4, the `run_cloud` part of prior review #35. When a run stopped early, each
module it never reached had the abort line and `exit=1` appended to the log the previous
run committed, so a stale `[pb] FAILED: 403` and `exit=0` stood above it and
`check_runs.py` named that old failure as this run's cause. A module now records when
this run opens its log; an unreached one gets the abort line in a fresh file, and one
stopped part-way keeps what this run wrote and gets the line appended. Tests: two in
`FatalTest` (`test_cloud_pool.py`), a seeded stale log and a module whose first site
published before its second was fatal; 3 mutations, all red.

### check_shows refuses a start with no offset and a url that is not http(s) (2026-09-25)

Audit finding C6. `common.check_shows` checked that each `Show` key is present with the
right type, and nothing about the two values the contract states a form for: `start` is
ISO 8601 with an offset, and `url` absolute http(s). A start such as `2026-09-26 18:00`
would have been published and read by the client in the viewer's zone, and a bare
`/checkout/{uuid}` left to `safeUrl()`, which accepts a scheme-less URL (IDEAS Deferred).
Both now fail the site before anything is written; `url` may still be `""`, the contract's
empty value, and `http` stays accepted for the two hosts with no TLS. The committed data
has no case of either: all 5,778 starts carry an offset, and 5,733 urls are https and 45
http. Tests: three in `CheckShowsAtTheBoundaryTest`; 5 mutations, all red.

### A title of two letters or fewer no longer aborts its TMDB pass (2026-09-25)

Audit finding E6, prior review #32. `queries()` drops every candidate of two characters
or fewer, so "Up", "It" or "M" with no longer original title has none; the fi-FI loop never
runs and its `else` took `queries(...)[0]` for the en-US search, which raised IndexError.
The title logged "list index out of range", got no cache entry, and was retried and left
unpublished on every run. The en-US step now asks only when there is a candidate, and the
title is cached as no match like any other. No live title is that short today. Tests:
`ShortTitleTest` in `test_tmdb_trust.py`, reproduced red first; 2 mutations, both red.

### The TMDB pass skips Finnkino's files by their numeric id (2026-09-25)

Audit finding E8. `enrich_tmdb.py` left Finnkino's area files to `fetch_data.py` by the
filename prefix `area-1`, which matched Finnkino's ids (1004 to 1166 today) and would also
have matched any future venue id starting with a 1, such as "1kino": that venue would get
no TMDB pass and no unpublish, with nothing in a log. The pass now skips `area-<digits>.json`
only, and `test_registry_sites.py` fails on a SITES venue id that is all digits. The set of
files read is unchanged today: 17 numeric Finnkino files, no other id starting with a
digit. Tests: `FinnkinoFilesTest` in `test_tmdb_trust.py` and the registry check; 3
mutations, all red.

### The Finnkino pass searches the cloud pass's cleaned title (2026-09-26)

Prior review #33. `fetch_data._queries` cleaned the search string with its own bracket
list, `_Q_NOISE`, which lacked `englanniksi`, `på svenska`, `puhumme suomea`, `suomeksi
puhuttu`, the `EN dub` form and every non-bracket rule, so the two TMDB passes could search
one film differently. It now searches `enrich_tmdb.clean()` first and `_Q_NOISE` is gone;
its dash-only head and the raw title as a fallback stay. Measured on the committed data:
none of Finnkino's 54 title strings searches differently today; run over all 481 committed
titles, 30 would, each now matching the cloud pass. A title that really ends in a bare
marker word is searched without it first, as the cloud pass already did, and the published
title stays a candidate. `FinnkinoQueryTest` in `test_tmdb_queries.py` also holds eleven
real titles whole; 6 mutations, all red. Compile-checked and tested offline; a local run
proves it.

### areas.json carries Finnkino's oldest venue stamp (2026-09-26)

Prior review #17. `fetch_data.py` wrote areas.json with `generated` = now on every
publishing run, a venue kept from an earlier run included, and the status page read that
as Finnkino's age, so a kept venue's older data was never reported. areas.json is now
written after the venue files and adds `oldest`, the minimum `generated` over the venue
files on disk, which is `run.py`'s rule for every other provider. `generated` stays the
time of the publish, because `check_staleness.py` reads it as "a run happened". The status
page reads `oldest`; a file written before the field falls back to `generated` in
`normalise()`, and the redundant fallback first added in `fromAreas` was removed as an
equivalent mutant. Not in today's data: all 17 venue files carry the areas.json stamp.
Tests: two in `SpentFileTest` (site 2 kept with a 2020 stamp while site 1 refreshes, and
nothing kept), one scenario in `status_store_harness.js`; 6 mutations, all red.
Compile-checked and tested offline; a local run proves it.

### films-extra.json carries TMDB's fields only for a showing film (2026-09-26)

Audit item E10, option 2 of `docs/research/films-extra-retention.md`, on the maintainer's
decision. Nothing pruned films-extra: a dormant entry, one for a film no area file lists,
held TMDB's slots, rating, trailer and poster, and the client never reads it. `merge_extra`
now projects tmdb-titles.json only for keys some area file shows, Finnkino's included, and
`strip_extra` takes the `ts` slots, `r`, `tr` and `img` off every other entry. Every slot
outside `ts` stays byte for byte, and so does `id`, the record that those slots are not
TMDB's; an entry left with no text goes. An unreadable area file makes liveness unknown and
strips nothing. tmdb-titles.json is unchanged, so a returning film gets its fields back
from the cache with no request. Applied to the committed data: 72 entries removed, 123
slimmed, 171,416 to 152,955 B gzipped. Tests: `test_films_extra_retention.py`, 11; two
existing tests now state whether their film is showing. 8 mutations, all red.

### The Finnkino pass judges hits with `enrich_tmdb.pick()` (2026-09-27)
Prior review #33, the rest of it. `fetch_data._pick` took the first exact title or else
the first hit. It is gone: `_judge` calls `pick()` with OCAPI's year and the original
title on the year-filtered search, so a second film of that title and year is a tie and
stays weak, and the original title breaks one. OCAPI's year is the Finnish release date,
a reissue's included, so it never refuses a hit: the unfiltered retry runs only when the
filtered answer holds no exact title, and is judged as a title with no year, where the
published runtime decides between films sharing it (`with_rivals` takes the pass's own
fetcher). Tests: `test_finnkino_pick.py`, 5 tests; 6 mutations, all red. A local run is
the operational check.

**Measured**, live TMDB, 2026-09-27: the 55 films in data/films.json replayed under both
rules, 84 requests with each URL asked once. 3 differ, all from exact to a same-year tie:
The Odyssey (rivals at 86 and 92 min against the published 172; the match is 173), One
Night Only (a 10-minute rival) and Obsession (2- and 3-minute rivals). All three are
cached exact and the pass never re-searches an exact entry, so today's data is unchanged;
a new film with such a namesake would be weak. Whether a runtime should break a
same-year tie in both passes is in IDEAS.

### "(Poistuu ohjelmistosta)" comes off the search string (2026-09-27)
Bio Marilyn marks a film's last week in the title: "Avengers Endgame Encore (Poistuu
ohjelmistosta)" and "Presidentin kyyditys (Poistuu ohjelmistosta !)", both unmatched
while the plain titles match. `PAREN_NOISE` takes the bracketed note, as it takes
"(Neulekino)"; the published title and its key keep it, and the words outside a bracket
stay. `PublishedCoverageTest` had flagged it on the committed data, so the suite was red
on origin/main before this. `LastWeekMarkerTest`; 3 mutations, all red. The rows match on
the next enrichment pass.

### The 2026-09-27 no-match list, worked (2026-09-27)
From `run-enrich.log`'s 77 no-match titles: three strands (`kinokopla`, `hyvät
kuvat-kerho`, `ennakkoensi-ilta`), thirteen aliases with their evidence in
tmdb-aliases.json, and the Bio Marilyn note above. Kinola, Nexxo and Kuvakukko were re-read
so the strands split the titles, then one enrichment pass, posters and pages. Every
resulting id was checked against the record read beforehand. Before and after, non-Finnkino
area files: showtimes with no `tmdbId` 241 and 212, titles 94 and 72; the pass's no-match
count 77 and 56, weak kept 16 and 15 (DIG! XX, unpublished), no weak candidate accepted.
Left open: Liisa ihmemaassa at Aurora (1951 and 1949 both fit), DIG! XX (TMDB has only the
2004 cut) and Viikinkien kosto (1961) (no record by that title). Lectures, workshops,
talks and concerts have no film and stay. One cache entry was deleted by hand: an
unmatched entry whose cleaned title now reaches an alias is neither overridden, which
reads the entry's old `q`, nor reconsidered, which skips a key with an alias, so it would
have waited for its daily retry.

### A synopsis that is only the title is no synopsis (2026-09-27)
Page audit: Cinema Niagara's Romanovin kivet carried "Romanovin kivet" as its synopsis.
Niagara's film page, read 2026-09-27, prints the title where its description goes, so the
adapter copied what the source says. `synmerge.merge` now skips a text whose normalised
form is the title's, leaving the slot to TMDB, and five such slots were cleared by hand
(Black Magic Rites, Bussipysäkki, Opimmeko rakastamaan, Romanovin kivet, Romeo + Juliet).
`test_synopsis_notes.py`; 2 mutations, all red.

### An alias a new cleaning rule reaches is taken the same day (2026-09-27)
The gap recorded in the entry above. The override reads an alias through the entry's
stored `q`, before the titles are gathered, and `reconsider()` skipped every aliased key.
`reconsider()` now marks an aliased key due when the alias would replace its entry (not
exact, or a different id), unless the entry is weak and was already searched with that
string alias. The override drops every entry its stored `q` reaches first, so only the
entries it could not see remain. An id alias re-judges with no search. On the committed
data it marks nothing due. `AliasReachedByCleanTest`; 3 mutations red, a stale-`q`
guard removed as equivalent.

### Finnkino's synopses are placed by language in films.json (2026-09-27)
On 2026-09-27 "fi" held English for NT LIVE: All My Sons, LINKIN PARK: UNSHATTER and
Ooppera: Così Fan Tutte, and five "en" slots held only the title (Pressure, The Dog Stars,
The Furious, Insidious 6, A Brief Affair). The pages skipped them; the app sheet showed
them as the slot's language. `fetch_data.place_syn` applies the pages' rule at the source:
three words or fewer is dropped, `common.syn_language` moves a text to its language's slot,
and a text it cannot settle stays put. On the committed data it changes those 8 entries.
`test_finnkino_syn_slots.py`; 6 mutations, all red. Proven by the next local run.

### The three rows the no-match pass left open (2026-09-27)
Liisa ihmemaassa at Kino Aurora is aliased to 12092: Aurora's own row names the 1951
Disney directors, year and 75 min. DIG! XX stays open: Kino Kilta links IMDb tt30843675,
the 2024 140-min cut, and TMDB has no record for it; 1843 is the 2004 film. Viikinkien
kosto (1961) screened 2026-09-26 and has left the data. Unmatched showtimes 226 -> 225,
titles 68 -> 67; no weak match accepted.
Hopeatähti-sarja: Rose at Kuvakukko is aliased to 1176962 the same day: Kuvakukko's
Hopeatähti page gives the director, three cast, the countries, 2026 and 94 min. TMDB has
no Finnish overview, and the page's Finnish blurb shares its paragraphs with the credits,
quotes and an award line, so it is not published. Unmatched 225 -> 224 showtimes.

### Two exact matches a fresh search would lose, pinned (2026-09-28)
A read-only replay of the Finnkino search over the 50 cached films found two exact entries
a fresh fi-FI search no longer reaches: The Furious (TMDB's fi-FI title for 1280738 is now
"火遮眼", so 1510055, a different film, came back weak) and The Ice Tower (1143440 answers
as "La Tour de glace", weak). Both are aliased on director and cast from Finnkino's own
text, and for The Ice Tower Ritz's page. With each cache entry removed, the Finnkino pass
and the cloud pass both rebuilt the intended id as exact; without the aliases the Finnkino
pass took 1510055 and a weak 1143440. 1510055 joins the wrong-id pins. The three same-year
ties (One Night Only, Obsession, The Odyssey) are left to the runtime decision.

### eTiketti places every site's synopsis, paragraph by paragraph when mixed (2026-09-28)
18 of the 20 sites published a bare `_syn`, filed as Finnish; Savon Kinot and Star
declared. Read on 2026-09-28 from an ordinary connection, all 243 film pages: before, 193
bare, 46 fi, 2 en, 2 withheld; after, 230 fi, 2 en, 1 fi+sv, 10 withheld. The `declare_syn`
flag is gone: every site places its text with `common.syn_language`. A description whose
`<br>`-separated paragraphs place in two languages is split, each language keeping its own
paragraphs, and unplaced ones (headlines, source lines, `***`) dropped. That is Niagara's
The Love That Remains, and the split equals the 2026-09-24 hand repair byte for byte.
Withheld: 4 Niagara titles-as-description (synmerge already skipped them), the tagline
"Hämärän pelottavat varjot", Kinopirtti's "Lisätietoja tulossa myöhemmin", two Kotkan
Leffat closure notices listed as films, and Savon Kinot's two as before. synmerge over a
copy of films-extra.json writes nothing with either version: every slot is filled.
`EtikettiTest` in `tests/test_syn_declared.py`; 6 mutations, all red.

### A strand in brackets keeps the operator's exclamation mark off the search (2026-09-28)
Kino Tapiola published "Matka Piemonteen (ennakkonäytös!)" in bot commit 9bdf19cea; it drew
an initials tile while "Matka Piemonteen" matched 1545391, and `test_tmdb_matching` went red
on main's own data. "ennakkonäytös" is already a strand, but `PAREN_STRAND` required the
bracket to hold exactly a listed strand, so the "!" kept it on the search string. The "!"
before the closing bracket is now matched with it, as `puhumme suomea!?` already is. Over
the 1,151 committed and cached titles it changes that one search string. An enrichment pass
on a copy of data/ re-judged it on the changed `q` and took 1545391 exact, with its poster;
the next cloud run does the same, so no data is committed. 3 mutations red.

### A bare trailing "tekijävierailulla" comes off the search (2026-09-29)
Kino Lumo and Kino Piispanristi published "Pirjo i Sverige TEKIJÄVIERAILULLA", an initials
tile while every other cinema's "Pirjo i Sverige" matched 1729175, and
`test_tmdb_matching` went red on the bot's data. `TRAIL_EVENT` took the visit only after a
"+". `TRAIL_VISIT` takes the bare word at the end of the title, after whitespace, and
nowhere else. Over 1,184 committed and cached titles it changes that one search string. An
enrichment pass on a copy of data/ re-judged it on the changed `q` and gave both rows
1729175 with a poster; the next routine run does the same, and the suite reads the result
from the data. 4 mutations red.

### "No subtitles" is a stated fact, `XX-S` (2026-09-29, sw.js v271)
Reported by the maintainer: Kino Engel's Gråben vs Acme page says "TEKSTITYS: Ei
tekstitystä", and the ticket showed only "ruotsi". `XX` was Nexxo's code for the same
thing and was dropped on 2026-09-15 because it rendered raw. It returns with a meaning, in
the subtitle role only: `engel._langs` adds `XX-S` when the field is exactly that
statement, and an empty or unknown field stays blank. The app's `langParts` and the pages'
`lang_parts` show it in words where no subtitle language is named: "ei tekstitystä",
"ingen textning" ("Ingen textning" opening the line) and, in each one's own English,
"no subs" on a ticket and "no subtitles" on a page. The committed-codes test accepts `XX`
in that role. Regina, Gilda and Nexxo state it too and are left for later. Engel's data
takes it on the next local run. 10 mutations red.
The app's English changed to "no subtitles" the same day on the maintainer's instruction
(sw.js v272), so the app and the pages say the same in all three languages. A named
subtitle language keeps the app's "subs Finnish".

### Nexxo's IW is Hebrew (2026-10-03)
Kino Aurora published "Naza" as `IW-A, EN-S`; IW is the ISO 639-1 code for Hebrew withdrawn
in 1989, and no name table carried it. `nexxo.CODE_FIX` maps it to HE beside SE to SV, and
the committed row was corrected by hand (21.10., outside every generated page's window).

### "+ohjaajavierailu" and two bracketed second titles (2026-10-03)
Four rows drew initials tiles while their bare titles matched elsewhere. `TRAIL_EVENT`
gains "ohjaajavierailu" (Kino Aurora, 1753057 and 1635591). Ritz Vaasa's "Two Seasons, Two
Strangers (Tabi to hibi)" and Cinema Sheryl's "Verity (Verityn varjo)" are aliased to
1462735 and 1283515, each verified on its record; a bracket rule was refused because some
real titles hold one. Enriched locally with posters and pages in the same commit.

### Two unpriced note shapes are screening notes (2026-10-04)
Savon Kinot's and Cinema Niagara's screening notes sat in shared `fi` slots on
2026-10-04. Savon Kinot ends each note with "||"; Niagara's announced a "tekijävierailunäytös".
Neither quotes a price, so `is_note` let both through. `NOTE_RE` adds the two shapes, and
every adapter filter built on `is_note` drops them too. Of 803 committed slot texts it
matches 6, all notes. The merge log reads "synopses skipped as screening notes: N".
4 mutations red.

### eTiketti strips only the age statement off a synopsis (2026-10-04)
`AGE_BOILER_RE` removed any two sentences after "Elokuva on", so a synopsis opening
"Elokuva on saanut innoituksensa ..." (Savon Kinot's Ortotopologia) lost its first two.
It now takes the age statement, "Elokuva on K16." or "Elokuva on sallittu yli
16-vuotiaille.", and only an "Ikärajoista ..." or "Sisältää ..." sentence after it. Kotka's
current wording read 2026-10-04. 5 mutations red.

### eTiketti drops a screening-note paragraph from the synopsis (2026-10-04)
Savon Kinot heads films with a note paragraph ending "||", and the whole description,
note included, was published. `parse_movie` now drops any paragraph `is_note` flags, as
Gilda's feed does, and builds the text from the rest. Savon Kinot's Ortotopologia page,
read 2026-10-04, still carries such a note above its synopsis; it now yields the synopsis
alone. 2 mutations red.

### eTiketti does not score parenthesised titles when placing a paragraph (2026-10-04)
Unohdettu saari's Finnish cast paragraph on kiertue.cine.fi lists English titles in
parentheses, and their function words placed it as English: the `en` slot of both
Unohdettu saari keys held Finnish, for 37 upcoming screenings at 13 providers
(measured at adc1b6e9b).
`syn_value` scores each paragraph and the whole text with `(...)` asides removed. Over the
803 committed slot texts this changes 3 verdicts, these two and Heart of the Beast's
Swedish text, which now places. Kept to eTiketti: `syn_language` also decides pages and
Finnkino slots. 3 mutations red.

### Shared synopsis slots repaired by hand (2026-10-04)
After the four rules above, the 24 slots found bad on 2026-10-04.
Measured at adc1b6e9b.
- Savon Kinot's "||" note cut off, synopsis kept: `fi` of Kerro kaikille (48 upcoming
  screenings, 18 providers), Ortotopologian loputtomat alkeet (17, 2), Ooppera Don
  Giovanni and Teatteri: The Audience, `en` of Linkin Park: Unshatter. Kerro kaikille now
  equals Savon Kinot's page as read that day.
- Bio Savoy's genre items cut off 15 `sv` slots; Digger equals its fixed parse.
- Emptied for the next run to refill: `fi` of Don Quijote Barcelonassa (Niagara's note
  opening the text), `en` of Verity (Verityn varjo) (Sheryl's 2026-09-21 page dump; the
  cause closed in `881ec574e`), `en` of both Unohdettu saari keys. The TMDB cache holds an
  overview for each. The fill-only rule is unchanged. 10 pages regenerated.

### Kino Kilta's double bill aliased; DIG! XX left (2026-10-04)
With Kilta's stills gone, two films had no TMDB id. "Anni tahtoo äidin ja Kala" found no
match: Kilta's page names Anssi Mänttäri's Anni tahtoo äidin (1989, 68 min) and Kambuzia
Partovi's Kala (1989, 70 min). The maintainer named 599152, verified as Anni (1989, 68
min, Mänttäri), so the row carries the first film's poster. "DIG! XX" was a weak match to
1843, Dig! (2004), which lists "DIG! XX" as an alternative title; left unaliased on the
maintainer's decision, so its 2 screenings on 1.11. draw an initials tile. Both rows are
cloud-half and outside every generated page's window; the next cloud run applies it.

### Kino Iiris's admission lines are screening notes (2026-10-04)
The maintainer's decision. Junat's eTiketti page, read 2026-10-04, opens with three lines
of its own before the synopsis: "VAPAA PÄÄSY!", "Näytökseen ei voi varata lippuja
etukäteen." and "Vain englanninkieliset tekstitykset.", and all three reached the shared
`fi` slot. `NOTE_RE` takes the booking phrase anywhere and the other two as whole
paragraphs only, so eTiketti drops each line and keeps the description. Of 800 committed
slot texts it matches 3, all notes: Junat, Hyvä talo from the same series, and Järven
ääni. 4 mutations red.
Repaired the same day after the rule: Junat's and Hyvä talo's `fi` slots lose the three
lines and keep the rest, which equals what the fixed parser reads from both pages. Hyvä
talo is included because the identical lines from the same series sat in it. Both
screenings are outside the generated pages' window, so no page changed.

### Fill-only kept, and the repaired slots checked against their sources (2026-10-04)
The maintainer's decision: no automatic replacement of a filled shared slot. Checked the
same day after the cloud run: every slot repaired that morning is clean, and four of them
(Don Quijote Barcelonassa `fi`, Verity `en`, both Unohdettu saari `en`) were refilled by
TMDB, which is the case a provider's text may replace. Re-read with the current code, the
sources yield no note: Cine's Unohdettu saari gives Finnish only, Sheryl's Verity page no
synopsis, Savon Kinot's Kerro kaikille and Ortotopologia clean text, and Niagara no longer
lists Don Quijote, whose note shape `test_synopsis_notes` holds. No gap, so no new test.

### Screening-note sentences leave a synopsis at the merge (2026-10-04)
The maintainer's decision. Fourteen shared slots, read 2026-10-04, held a film's description
with one cinema's screening notes inside it: free entry ("Näytökseen on vapaa pääsy."),
booking ("Huom! Näytökseen ei voi varata lippuja etukäteen."), when and with whom ("Näytös
järjestetään KE 7.10. klo 19:00.", "... yhteistyössä Lahti-Seura ry:n ... kanssa."), a free
screening announced, admission to a guest's talk, a voluntary fee, and the English
equivalents. `drop_note_sentences` removes those sentences, twelve shapes, before every
provider's text is merged, so none can return; the rest of the text stays, and "Huom!" goes
with its sentence. Over the 800 stored slot texts it removes 29 sentences in 20 slots, all
notes. Similar sentences about the film stay ("Elokuva on toteutettu yhteistyössä ...",
"Admission to the academy is free ..."). The merge log counts them. 15 mutations red.
Repaired the same day after the rules, 17 texts in 14 slots, each the stored text with the
note sentences, Star's literal tags and K-Kino's facts block taken out: `fi` of Järven
ääni, Anttilanmäen kyläjuhla, Filminor, Follow the Plants, Käpy selän alla, Lahden
videokuvaajat 70v, Minikino: Pat & Mat, Pirjo i Sverige – Vauvakino, Vanhustenviikon
näytös, Tiedettä elokuvissa and Pia Långbacka; `fi` and `en` of El espíritu de la colmena,
Casper and Ghost. Twelve equal the fixed parse of the cinema's page that day; the other five
are films no longer listed. Left as they are, the boundary not clear from the text: the
guest talk inside Casper's and Ghost's synopses, "Näytöksessä 16.9.2026 klo 16:00 nähdään
neljä historiallista lyhytelokuvaa ...", "Näytöksen tarjoaa ... Lasten Lysti" run into Pat
& Mat's first sentence, and "Elokuva on tekstitetty englanniksi." Two Orion pages changed.

### "(viimeinen esitys)" comes off the TMDB search string (2026-10-05)
The maintainer's decision. Bio Grani published "Hetki ennen valoa (viimeinen esitys)" in the
cloud data of 2026-10-04, and the row drew no TMDB match while every other spelling matched
1015881, which kept `PublishedCoverageTest` red. Bio Grani's film page, read 2026-10-05,
gives Klaus Härö, 1 h 27 min and a 11.09.2026 premiere; the record, opened the same day, is
Klaus Härö, 2026-09-11, 87 min, Laura Birn. The parenthetical names the last screening, as
"(Poistuu ohjelmistosta)" names the last week, so `PAREN_NOISE` takes it off the search
string and the published title keeps it. The same words outside brackets stay. 2 mutations red.
Re-enriched the same day: the row now carries 1015881 and the plain title's mirrored
poster in its slot. The pass also re-read 12 ratings due that day; those were left for the
next routine run so this commit holds the one row. Its screening, 11.10., is outside the
pages' window.
A sentence also starts at "Näytös järjestetään" (2026-10-05): Metsäsota ja rauha's Finnish
text ran the note on after a quote's attribution with no stop ("– Erkki Lähde 2026 Näytös
järjestetään ke 30.9. klo 17:15 ..."), so the rule could not see it. Capital N only; the
words mid-sentence stay. 2 mutations red.
"The screening will be held on ..." is the same note as "... will take place on ..."
(Ghost in the Machine's English text, read 2026-10-05). "The screening will be held in
secret" stays. 2 mutations red.
Repaired 2026-10-05, after the rules, 10 texts in 8 slots. The dated screening sentence out
of Ghost in the Machine (`fi`, `en`), Jazz Suomi 100 vuotta, Natalia and Metsäsota ja rauha
(`fi`, `en`); Star's literal `<b>` and `<p>` out of Marsupilami (dub), Presidentin kyyditys
(Neulekino) and Star House Movie: Ortotopologian loputtomat alkeet; Alt Skal Bort's `en`,
Ritz's whole description from before its facts rule, down to the synopsis Ritz's rule reads
today. Six equal the fixed parse of the cinema's page that day; Jazz Suomi 100's page has
since changed its list of shorts; Metsäsota is no longer listed. Left as they are: the
post-screening discussion and guest lines (Ghost in the Machine, Metsäsota, Natalia's guest
line fused into the critic's attribution) and the Neulekino format sentence. One Star page
changed. After this no stored slot text holds a sentence the rule removes.

### "(org)" comes off the TMDB search string (2026-10-05)
In the cloud data of 2026-10-05 Kino Myyri lists its English-language screening (EN-A,
FI-S, SV-S) as "Ryhmä Hau: Dinoelokuva (org)". It got no TMDB match although the plain
title matches 1185806, and the nearest weak candidate was 893723, which is already listed
as a wrong id. `PublishedCoverageTest` failed on main because of it. `TRAIL_VERSION` now
removes "(org)" from the end of the search string, the same way as "(eng)" and "(sub)".
The published title is unchanged. 2 mutations red.

### A bracketed "tekijävierailunäytös" note comes off the TMDB search string (2026-10-07)
Kino Kuvakukko published "Sopeutumaton (tekijävierailunäytös, paikalla ohjaaja ... +
keskustelua)" in the cloud data of 2026-10-06. It drew no match while the plain title did,
which turned `PublishedCoverageTest` red on main. `TRAIL_VISIT_NOTE` removes a closing
bracket that starts with that word. The same word mid-title or in an open bracket stays,
and the published title is unchanged. 2 mutations red.

### Kinopirtti's "DUP." comes off the TMDB search string (2026-10-09)
Kinopirtti published "Unohdettu saari DUP.", its abbreviation of "dubattu". The row drew no
match while the plain title matched 1465063, which turned `PublishedCoverageTest` red on
main. `TRAIL_DUB` removes " DUP." from the end of the search string, dot required; the
published title is unchanged. 3 mutations red.

### Bio Säde's festival bracket comes off the search string, and an alias can say "no record" (2026-10-09)
Bio Säde in Mänttä publishes five films with "(Taidekaupungin elokuvajuhlat)" after the
title. On the maintainer's instruction `TRAIL_FESTIVAL` removes that exact bracket from the
end of the TMDB search string, and the published titles keep it. Each film was then
checked against TMDB and against the cinema's own runtime and age limit, which are the only
facts its Nexxo source carries. Four matched. "The Painter" (S, 95 min) did not: TMDB's only
feature of that name is a 2024 action thriller, and the rest are shorts. An alias value of
"-" now means TMDB holds no record of a title. The title is never searched, and an id
already cached for it is dropped. 3 + 2 mutations red.

### Bio Säde's "The Painter" is Hirschbiegel's Der Maler (2026-10-09)
A correction to the record above. The festival's own announcement names *Der Maler* (2021),
which Oliver Hirschbiegel made with Albert Oehlen, the guest of honour. IDFA lists it as
"The Painter", 2021, 95 minutes, which is Bio Säde's runtime. TMDB 893149 is the same film:
original title Der Maler, Hirschbiegel, Ben Becker, 94 minutes, dated 2023 for its German
release. The "-" marker was replaced with that id. TMDB did have a record; a title search
did not find it because the search returns a 2024 thriller of the same name first. The "-"
value stays for titles whose absence has been checked. 2 mutations red.
