# Kinola: three templates, and telling a film from a concert

Research notes moved out of `IDEAS.md` on 2026-09-14, when nothing here was built.
**The adapter shipped on 2026-09-15**, `scripts/providers/kinola.py`, for Kilta and Laika,
and took Kino Myyri as a third tenant on 2026-09-18; Konepaja still has no registry entry,
re-read 2026-09-19. What it decided and what it measured are in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md) under "Kino Kilta and
Kino Laika: the Kinola adapter, under the adopted policy". The findings below are as they
were read and are not updated by it.

**The publication policy was decided on 2026-09-15** and the decision, with the reasoning
and the three corrections it made to the proposal below, is in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md) under "Kinola: the
publication policy, adopted". This file keeps the findings it always held, and its
inferences are now either superseded by that record or carried forward as build
requirements. Findings are dated and unchanged; the policy is not a finding.

Kinola is the platform behind Cinema Orion's ticketing. `scripts/providers/orion.py` reads
one of its three front-end templates; the other two belong to cinemas that are not
registered here.

---

## The three templates

**Findings** (read as a visitor, 2026-09-14)

| Site | Markup | Count that day |
|---|---|---|
| cinemaorion.fi | `table.kinola-day` rows | read today by `orion.py` |
| kinokilta.fi/naytokset/ | 56 × `li.kinola-event` | `.date` "TI 15.9.2026", `.time`, `.movie-subtitle`, `.duration-info` |
| kinolaika.fi/ohjelmisto/ | 47 × `div.kinola-event` | one `.kinola-event-date` "16/09/2026 14:00", a `.kinola-event-venue`, 4 sold-out rows |
| kinokonepaja.fi | none | lists no event at all |

- `.movie-subtitle` on Kilta carries a strand, not a subtitle: "Kahvikino",
  "Anniskelunäytös K18".
- Laika's four sold-out rows carry no checkout link.
- Neither Kilta nor Laika renders `kinola-day`, so `orion.parse` returns zero on both.
  That is the whole reason this is a new module rather than two `SITES` entries.

**Inferences and open questions**

- Reusable from `orion.py`: `_iso`, `_slug`, `_price`, the `/checkout/<uuid>` link resolved
  with `urljoin`, and the runner contract. Not reusable: the block, row and cell patterns,
  which are bound to the table.
- The shape that fits is **one `kinola.py` with a template per site named in `SITES`**
  (`table`, `kilta`, `laika`), not a copy of `orion.py`. That is a design proposal, not a
  measurement.

**Status and next step**

Built 2026-09-15 as one adapter with a handler per template, which is the shape this file
proposed. Konepaja was re-read that day rather than relied on: it renders the filters and
a "tulossa" grid of 44 film links, so a count of `kinola-event` occurrences looks like a
programme, and its screening list says "Ei tulevia tapahtumia." The 2026-09-14 reading
stands and it has no `SITES` entry.

**Re-read 2026-09-20.** `kinokonepaja.fi/naytokset/` now answers 301 to the front page,
which carries the same listing: one "Ei tulevia tapahtumia.", 40 `kinola-event` and 43
`kinola-film` matches in the coming-soon grid, and still no `kinola-events` container. The
site also states the cinema is shut and reopening shortly. That is the first stated reason
for the silence; until now it was only an absence, and an absence does not distinguish a
pause from a template this reader cannot parse. Still no `SITES` entry. The URL in the
table below records what was read on 2026-09-15 and is left as it was.

---

## The listing's own shape: what an empty programme looks like

**Findings** (read as a visitor, 2026-09-15, one GET each, nothing stored)

| Site | `kinola-event` blocks | `kinola-events` container | `Ei tulevia tapahtumia.` |
|---|---:|---|---|
| kinokilta.fi/naytokset/ | 57 | yes | no |
| kinolaika.fi/ohjelmisto/ | 47 | yes | no |
| kinokonepaja.fi/naytokset/ | 0 | **no container at all** | yes, after the filter widget |

- All three render the filter widget: `kinola-filters`, `kinola-filters-form`,
  `kinola-film-filter`.
- Konepaja's empty text sits in a bare `<div>` with no class of its own, immediately after
  the filter form closes. Konepaja also renders a `kinola-film` / `kinola-films` grid,
  which Kilta and Laika do not; that grid is the "tulossa" list of film pages and is not a
  screening list.
- **Every one of the 104 blocks on the two live listings carries `kinola-event` and no
  other class.** So a block with a second class is not something either site does today.

**Inferences and open questions**

- The events shortcode appears to render either the `kinola-events` container or that
  sentence, never both. That is an inference from one tenant in the empty state, which is
  the whole sample there is, and it is why the adapter requires all three conditions rather
  than the sentence alone.
- Whether Kilta or Laika would render the container empty rather than omit it is **not
  known**. If either does, the adapter fails that site rather than calling it empty, which
  is the conservative direction: the previous files stand and a person reads the log.

**Status and next step**

Implemented 2026-09-15 as `kinola.empty_programme_evidence`, and the class token as
`kinola.EVENT_RE`. Next step: none. If a Kilta or Laika listing ever fails with "the event
container rendered and held no readable screening", that is the second observation of the
empty state and this table gets a row.

## Films and other events

**Findings** (kinokilta.fi and kinolaika.fi, sampled 2026-09-14)

Concerts and films are **one WordPress `film` post type**. No taxonomy, tag, JSON-LD,
`og:type`, REST type or filter option separates them. Laika's own filter lists its
concerts under "Kaikki elokuvat". The film page is the only evidence there is.

- On 23 Laika pages: the 16 films carry `Ohjaus` and `Kieli`; the 7 concerts and events
  carry neither and read "Not rated" or K-18 with no director (Tuure Kilpeläinen, Arppa,
  Antti Autio, Knipi, Mariska, Livemusavisa, 50 vuotta rokkia).
- On Kilta: 37 pages, every one with `Ohjaus` or `Lajityyppi`.

**Inferences and open questions**

The rule this sample supports, stated conservatively so a wrong guess fails towards
publishing nothing rather than towards publishing a concert as a film. **Corrected
2026-09-15**, and the correction is part of the adopted policy:

- **Known film** only on structured film metadata, and **an age classification is not
  part of it.** The version of this list written on 2026-09-14 named "a classification"
  as sufficient, which contradicts both the finding above, where the non-films read
  "Not rated" or K-18, and the first fixture below, a film carrying K-16 that this file
  calls unresolved. A classification says a board rated something, not that the something
  is a film.
- **The predicate is a hypothesis, not a guarantee.** It rests on 7 sampled non-films.
  The presence of a field such as `Lajityyppi` is therefore not automatically sufficient,
  and which fields in which combination constitute film evidence is an implementation
  detail to validate against the fixtures and against the pages as they stand when the
  adapter is written.
- **Known non-film** only on an explicit event-level description of a live act: a
  performer billed as such, a gig, a quiz. **Never on a word**: a synopsis can say
  konsertti, and a concert film is still a screening. Explicit event-level evidence of a
  live act **prevents** automatic inclusion, even where generic metadata is present.
- **Unresolved** is everything else, and it stays unresolved. A log line records it; that
  does not make it a film.

**Decided 2026-09-15, no longer open:** unresolved rows are omitted, with evidence-backed
overrides in both directions. The record is in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md). The cost accepted
with it is that a sparsely described film is missing until an override is verified for it.

**Status and next step**

Requirement, not implementation. Fixtures the adapter has to carry, chosen because each
one breaks a rule that reads plausible:

1. a film with no metadata: *A Fox Under a Pink Moon*, 76 min, K-16, `Tekstitys` only;
2. a concert film: *Oasis: Don't Look Back in Anger*, `Ohjaus` present;
3. a film whose synopsis mentions a concert;
4. a billed live concert: *Arppa*, "Akustisesti saleissa", no film metadata.

Only the fourth is a non-film.

**Status: shipped 2026-09-15.** The predicate was validated over 65 film pages before the
adapter was written, and it is the labelled director or genre field alone: a runtime and an
age classification are not evidence, because Laika's live acts carry both. 53 pages
publish, 12 carry no field, eleven of those are billed live acts and one is a film. What
the policy omits was measured in films and in screenings and is in the archive entry. The
requirements below were the build's contract; they are kept because they still describe
what the adapter has to keep satisfying.

---

## Where the synopsis sits on a film page (read 2026-09-24)

Findings, one film page per tenant read as a visitor on 2026-09-24:

- **Kilta** (`/film/agentti-o-s-s-117-iskee/`): the header logo is an inline SVG drawn with
  `<path d='...'>`. `<p[^>]*>` matched `<path`, so the first "paragraph" ran from the
  logo through the whole site menu and both titles to the first `</p>`. Inside `article`
  the page has five real paragraphs: four of KAVI aluesarja notice (60, 135, 98 and 98
  characters) and the synopsis, 1465 characters.
- **Laika** (`/film/8-1-2/`): the first paragraph over 120 characters is a ticket notice
  ("Kino Iglu! Liput 10 EUR / 7 EUR ..."); the synopsis is the longer one after it.
- **Myyri**: a festival page and a film page; the longest paragraph is event or film text
  either way.
- **Sheryl** (`/film/chungking-express-2/`): the same `<path>` match read its menu
  ("ABOUT CONTACT BOOK A MOVIE ..."); `declare_syn` withheld it as no settled language.

Implementation status: `SYN_RE` requires `<p` followed by whitespace or `>`, and the
synopsis is the longest paragraph over 120 characters. Tests: `SynopsisParagraphTest` in
`tests/test_kinola.py`.

## Kilta's description sections (read 2026-09-24, all 40 listed films)

Findings, from each film page read once as a visitor:

- The description is the `<p>` run inside `article` between `div.page-title` and the info
  block `div.hide-for-l-up`; one page opens it with an `<h3>` heading.
- A paragraph of only `---` or `--` separates the Finnish section from a Swedish one (and
  on Dialogpolisen an English one); `***` separates Kinokopla's ticket notices from the
  synopsis.
- Notices: 55 paragraphs bold throughout, nearly all headings and strand lines (three are
  one-line taglines or a content sentence, which the rule also drops). Of 63 paragraphs
  that open bold without being bold throughout, most are synopsis text starting with the
  film's title; the notices among them quote a price, name Kino Kilta or carry a URL.
- Credits: "Lähde: ..." and "Källa: ...".
- Result with the section rule: 31 pages Finnish only, 3 Finnish and Swedish, 1 Finnish,
  Swedish and English, 5 withheld as no language settled (one is the RetkiKino programme).

Implementation status: `kilta_synopsis` in `kinola.py`; tests in `KiltaSynopsisTest`.

## Sheryl's runtime (read 2026-09-24, all 5 listed films)

Findings: every film page carries one `<hr>` followed by a title block, the title in bold,
the original title, the country, then an optional release date and the runtime
("2026-09-18, 94 min"), ending at the first blank line before "Director". The labelled
meta block above the synopsis has no runtime. `_head` reached the title block only where
the synopsis was not in `<p>` elements, so Chungking Express (102 min) and Happy Together
(96 min) published none while Resident Evil, Spider-Man and Verity had theirs by that
accident.

Implementation status: `sheryl_runtime` reads the title block and nothing else;
`SherylRuntimeTest` covers both shapes.

## Build requirements

Recorded 2026-09-15 with the policy, and **not implemented**. These are what the adapter
has to satisfy, not a description of anything that exists.

**The classifier**

- Validate the structured-metadata predicate against the four fixtures and against the
  pages as they stand at the time of writing, rather than against the 2026-09-14 sample
  alone. An age classification is not film evidence. No single field is assumed
  sufficient in advance.
- Explicit event-level evidence of a live act prevents automatic inclusion even where
  generic metadata is present. **Built 2026-09-15**: the exclusion is consulted before the
  labels, and the case is covered by a fixture of a billed live act whose page fills
  `Ohjaus` and `Lajityyppi`, which publishes without one. The three states are `film` and
  `unresolved`, both runtime verdicts, and `non-film`, which only an exclusion asserts.
- **Known limitation, and it is not going away by itself: precedence is not detection.** A
  recorded exclusion outranks director and genre metadata, but a *newly encountered* live
  act carrying that metadata and no entry publishes as a film, and nothing in the adapter
  notices. The fixture proves the precedence holds once an entry exists; it does not prove
  conflicting live-event evidence is found automatically, and no test claims it does. The
  remedy is one more scoped entry, never a title or synopsis keyword, which the policy
  forbids and which would misfile every concert film.
  **Corrected 2026-09-15:** this line said a new case is caught by a person reading the run
  log. It is not. The log names what was withheld and counts what published; it never names
  a published title, so a wrongly included act reads as an ordinary film in it. It is
  noticed on the site or in the data by someone who knows the programme. **Also corrected
  the same day:** keywords being the only remaining route is an assertion, not a finding.
  No other structural signal was looked for -- a ticket type, a venue field, a list the
  cinema publishes itself -- so nothing establishes that there is none.
- Never classify from a keyword in the title or the synopsis alone, in either direction.

**Overrides**

- Two directions: force-include a film the predicate leaves unresolved, force-exclude an
  event the predicate wrongly includes. The second is the reason the mechanism cannot be
  one-sided.
- **Applied before the default classifier**, so an override decides rather than argues
  with it.
- Scoped to a provider and a stable event or page identifier, or a verified canonical
  URL. Never a loose title keyword, which would reintroduce the classification rule this
  policy forbids.
- Each entry carries its action, its reason, its evidence source and the date that
  evidence was verified.
- Revalidated against available evidence. A redundant override is one that does not
  change the default decision; the guard identifies those. An event that has left the
  programme, or a page that cannot be read, does **not** by itself prove an override
  redundant, so neither may be treated as grounds to drop one.
  **Built 2026-09-15 as `kinola.override_state`**, scoring every entry on every run as
  `active`, `redundant` or `evidence-unavailable` and logging one line each. It replaced a
  first attempt that lived in the test file and could only prove decision semantics
  against a fixed fixture, not that an entry is still needed as its source page changes.
- **Necessity and validity are separate questions.** `redundant` says the entry changes no
  publication decision *today*. It does not say its evidence was wrong, and it is not
  grounds for deletion: an exclusion earns its keep precisely when a cinema that fills no
  field now fills a misleading one later, at which point the same entry turns `active`
  again and is the only thing withholding a gig. Nothing removes an entry automatically,
  and no test requires one removed in order to pass.
- *A Fox Under a Pink Moon* is a known candidate for an inclusion override if the
  validated predicate still leaves it unresolved. Its identity and its source page are
  verified before an entry is written, not assumed from this file.

**Measurement**

- Measure what the policy omits as **both** unique events and screening counts, split
  into explicit non-films and unresolved entries. The 2026-09-14 sample counted pages
  (37 Kilta, 23 Laika) and rows (56, 47) but never the screenings behind an unresolved
  page, so the cost of the policy is currently unknown.

**Rows and destinations**

- A sold-out film screening is preserved even though its checkout link is gone: Laika's
  sold-out rows carry none. The destination is the film page's own href **read from the
  source**, never constructed, with `soldOut: true` and whichever existing destination
  semantics that implies.

**Fixtures**

- Keep the four already listed. Add coverage during implementation for conflicting
  metadata, and for both override directions.

**What not to touch**

- `scripts/providers/orion.py` reads the third template and stays as it is. A change
  there would need its own justification, demonstrated by the implementation rather than
  assumed now.

## Ticket links: two answers on one platform (read 2026-09-26)

**Findings.** The committed `data/area-*.json`, read 2026-09-26:

| Site | Adapter | Link on a bookable row | Showtimes |
|---|---|---|---|
| Kino Kilta | `kinola.py` | the listing's `/checkout/{uuid}` | 49 checkout, 14 film page |
| Kino Laika | `kinola.py` | the listing's `/checkout/{uuid}` | 61 checkout |
| Cinema Orion | `orion.py` | the listing's `/checkout/{uuid}` | 33 checkout |
| Kino Myyri | `kinola.py` | the film page | 20 film page |
| Cinema Sheryl | `kinola.py` | the film page | 13 film page |

- Myyri and Sheryl withhold the link on purpose: `kinola.py`'s module docstring ("Myyri's
  ticket link is not published") and the docstring of the function the two share call
  `/checkout/{uuid}` "a booking endpoint, which 'Access and ethics' in CLAUDE.md keeps this
  repo out of". The Myyri and Sheryl entries in `docs/archive/2026-09-providers.md` say the
  same.
- Kilta, Laika and Orion publish the same shape, copied from the listing and never built
  (`kinola._destination`, `orion.py`); a sold-out row falls back to the film page there too.
- The rule cited is CLAUDE.md's "Booking, payment and administrative endpoints are never
  called and are not inventoried."
- Other platforms' ticket links are purchase pages already: Riviera and Biokaari link each
  screening's `websales/show/{id}`.
- The one recorded case of a booking link kept out, Kino Engel (`engel.py`, the comment
  above `DETAIL_RE`), is a link that exists only behind the Johku widget's key-protected
  read endpoints, so obtaining it would mean using a credential a visitor is not issued.

**Inference.** The two answers read the same sentence differently. Linking a reader to a
page they click through to is not this repository calling it, and none of the five adapters
requests a checkout URL; the difference between the two groups is only what the showtime
opens.

**Proposal.** A showtime links to a screening's purchase page when the cinema's public
listing itself carries that link for a visitor to click, whatever its path is called: the
adapter copies the href, never builds it, never requests it, and falls back to the film
page when the row carries none. What stays out is a link that could only be obtained by
calling a booking, payment or administrative endpoint or with a credential not issued to a
visitor (Engel's). The one-time check that a new link lands on the screening is made by
opening it in a browser, as a visitor would, and is never part of a run. Under this rule
Myyri and Sheryl would publish their listing's `/checkout/{uuid}` like the other three.

**Status.** Decided 2026-09-26 by the maintainer, later the same day: Myyri and Sheryl
publish the listing's exact checkout href, copied and resolved, never constructed and never
requested, including for a one-time check in a browser; the film page stays the fallback
for a sold-out row or one with no ticket anchor. The access rule in CLAUDE.md now says so.
Refreshed the same day: Myyri 20 and Sheryl 13 showtimes carry checkout links, every one
of them an href on that site's listing (Myyri's listing has 3 more, on rows the publication
policy omits). The record is in `docs/archive/2026-09-providers.md`.

## Language names (read 2026-10-03, every listed film of all four tenants)

Findings, from the film pages read once as a visitor through `fetch_site`:

- Sheryl labels the lines `Language` and `Subtitles` in English with English names
  ("English", "Finnish, Swedish", "Cantonese, Mandarin"); 7 films, one without a
  Subtitles line. The reader knew only `kieli` and `tekstitys`, so all 9 screenings
  published no language.
- Kilta, Laika and Myyri used 23 names Gilda's table lacks over 21 films, among them
  persia, tanska, heprea, hindi, "English", "Dubattu englanniksi", and Laika's and
  Myyri's machine-translated forms: "italialainen", "romanialainen", "kiillottaa" (Polish).
  Each was dropped alone, so "suomi, persia" published as Finnish only.
- Kilta writes "Ei teksitystä" once; read as no subtitle line, since `XX-S` stays Engel's.

Implementation status: `NAMES` in `kinola.py`; a line with an unknown name publishes
nothing for that part and the run log names the film. `LanguageNamesTest`.
