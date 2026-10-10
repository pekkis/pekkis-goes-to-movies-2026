# Kino: open work and decision index

This file is the index of open work. It holds proposals, priorities, statuses and the
dated decision records that are still live. It stopped holding history on 2026-09-15,
when 4,790 lines of closed records and investigation evidence moved to
[docs/archive/](docs/archive/) and [docs/research/](docs/research/). The map is at the
bottom, under "Where the rest went".

## How to read this file

- **Active work** is open and has a next action. The next action is written down.
- **Blocked** is open and cannot proceed without something outside this repo: a
  maintainer decision, a third party, or an endpoint that does not exist.
- **Deferred** is decided against for now, with the reason. A deferred line is not a
  backlog item; it is a record so the same idea is not re-proposed from scratch.
- Anything closed is in `docs/archive/`, with the entry as it was written. The heading
  text is unchanged, so a reference that names a heading still resolves.
- Accepted working rules are not here. They are in [CLAUDE.md](CLAUDE.md), and the visual
  contract is in [DESIGN.md](DESIGN.md). A finding does not become a rule by being
  written down: promoting one into `CLAUDE.md` needs an entry here like any other change.

One role nothing else can take: `scripts/check_design_push.py` requires an `IDEAS.md`
change in the same commit as a `DESIGN.md` or `tests/test_design_contract.py` change. A
contract change is explained here, never in `docs/research/`.

## Active work

### Provider coverage, and what is next

83 providers, 134 venues, 96 cities, declared and committed alike, measured 2026-09-21.
Check for an existing platform first. Every candidate assessed, with its evidence, is in
[docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md).

- **Sun Kino:** `allproducts.json` closed (403, session required); another source untested.
  **Eventio:** closed 2026-09-19. Its one known tenant is Kino Regina, already built.
- **Complete:** eTiketti (twenty-one), Nexxo (eight), Kinola (four), Johku (six),
  Cinemahouse (three), TMB (four), MyCloudCinema's two, Vista's one, the parser-shaped.
- **Next action:** none from these.

### Heureka's own posters still wait for written permission

The initials tiles are gone. Three planetarium films draw Leffavuoro's own title cards as
of 2026-09-20: abstract art this repository generates, plus the published title, never a
poster and never derived from anyone's artwork. **That supersedes the decline of generated
artwork**; a weak TMDB match and a cropped 16:9 still stay declined. Heureka's *own*
artwork is unchanged, licensed to nobody, and public availability is not permission.
The decision, its safeguards and what was measured are in
[docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md).
**Next action:** written permission from Heureka's media contact, if its artwork is ever
wanted. Nothing is blocked on it now.

### Credential hygiene and rotation

Tracked in private notes outside this repo. The Finnkino token is fetched fresh at run
time and used within seconds, so there is no stored credential and nothing to rotate;
this item covers the rest.

### The PostHog bundle is pinned by its hash

`sc.integrity` in `index.html` and `pageview.js` holds the sha-384 of the 1.434.2 bundle,
measured 2026-09-22. If that path is rebuilt the hash stops matching and analytics stops.
Record: [docs/archive/2026-09-app.md](docs/archive/2026-09-app.md).
**Next action:** re-measure it in both files with any `PH_VERSION` bump; the tests compare them.

### Swedish copy: a native reader over the settled vocabulary

The vocabulary was settled and applied on 2026-09-23 ("visning", "visningstider",
"Textning:", "på plats", "Din startvy"); record in
[docs/archive/2026-09-app.md](docs/archive/2026-09-app.md).
The maintainer settled the four remaining terms the same day. The review covers the strings
added since: the checking state "Kontrollerar visningstiderna…", the rating label and the
footer credit. The contact line matters most. Unrelated work does not wait on it.
**Next action:** a native Finland-Swedish reader over the result.

### Two providers are read over plain HTTP

Neither host serves TLS, probed 2026-09-22 and 2026-10-04. [CLAUDE.md](CLAUDE.md) bounds a cleartext
`base` to that case; probe in [docs/research/adapter-http.md](docs/research/adapter-http.md).
**Next action:** re-probe when either host is next touched.

### Thirteen sites go red when genuinely empty

None has a recorded empty state, so zero rows fails the run instead of clearing data.
List, reads and gaps: [docs/research/empty-states.md](docs/research/empty-states.md).
**Next action:** when one fails with its own page showing nothing on, record that state.

## Blocked

### A way to read a generated page's full synopsis

The pages print 200 characters, three lines on a phone, and nothing opens the rest; the
app's film sheet has it. Proposal: a "Koko kuvaus" link under the text to the app's deep
link `/?area=<venue>&lang=<l>#m=<film id>`, which opened that sheet for 8 films in Chromium
and WebKit on 2026-10-04; on a phone a tap leaves the page and Back returns. A `<details>`
with the full text would repeat it on every page. **Unblocks when:** the maintainer picks.

### A runtime to break a same-year TMDB tie

Both passes keep a tie of title and year weak. Measured 2026-09-27, 3 of 55 Finnkino
films would tie that way against shorts, each settled by its runtime
([docs/archive/2026-09-pipeline.md](docs/archive/2026-09-pipeline.md)).
**Unblocks when:** the maintainer decides whether `by_runtime` decides such a tie.

### The cloud cron fires about half its slots

23 of 42 slots ran 09-15 to 09-25; since 09-20 only 06:30 and 14:30 UTC, a median 80 min
late (audit, 2026-09-25). External, cause unknown. **Unblocks when:** GitHub runs them.

### Julia 1&2 Hyvinkää prints two prices on one screening

All 21 Julia showtimes carry `14€ / 12€` (2026-09-24); the app and pages label it
"alkaen 14 €" and JSON-LD says 14. The maintainer holds taking the minimum: 12 € may be a
conditional discount. **Unblocks when:** Julia's own page says what each amount is for.

### Kino Konepaja has no programme to read

A real Kinola tenant publishing no screening, so it gets a `SITES` entry the day it lists
one. Re-read 2026-09-20: `/naytokset/` now redirects to the front page, whose event list
still says "Ei tulevia tapahtumia." above a coming-soon grid, and the site states the
cinema is shut and reopening soon. Evidence in
[docs/research/kinola.md](docs/research/kinola.md); the classifier and the
three tenants that do publish are in
[docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md).
**Next action:** re-read the listing, at the front page now.

### Staleness monitor: the ping

The repo half is done, `scripts/check_staleness.py`: a pure function of a file and a
clock, answering "did a run happen", which `check_runs.py` cannot. Its threshold is
`STALE_H` from `index.html` and a test fails if the two drift apart.
**Next action:** the external ping that calls it. The schedule, the file location and the
recipient are machine-specific and live in the wrapper outside this repo, so this item
cannot close here.

### Kuva-Tähti's two cinemas need the Johku widget flow

Kauttuan Kuva (Eura) and Kuvala (Uusikaupunki), one merchant on Johku's **client-rendered**
storefront, which `johku.py` cannot read: read 2026-09-21, five surfaces render no film, date
or time. The rows arrive through `/api/auth/widget-session` and an `X-ApiKey`, the flow
declined for Kino Engel on 2026-09-20; no key was copied or recorded. Evidence:
[docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md).
**Next action:** re-read for a server-rendered template or a feed, each a `SITES` entry.

### Rekolan Kino and Juvan Kino wait for a programme

Both read 2026-09-21. **Rekolan Kino** (Vantaa) held only past rows on its Squarespace
page, the latest 20.9., and a parser with zero rows while the page lists films must fail; it
sells through Kino Myyri's Kinola storefront, which never names it, so it needs its own
parser. **Juvan Kino** publishes through `juvantapahtumat.fi`, whose cinema category states 0
events. Evidence: [docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md).
**Next action:** re-read both listings later.

### Kino Kaustinen has no screening to verify against

A real eTiketti tenant publishing none, so no ticket destination can be checked, which is
the rule six dead Nexxo links bought. Re-read 2026-09-20: "Ei ohjelmistoa saatavilla."
Blocked on the cinema's own programme, not on work here; it is one `SITES` entry the day
it lists a film. Evidence:
[docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md).
**Next action:** re-read on a later Monday.

### Search Console re-read

The five-day baseline is too thin to change anything on, and the queued "ohjelmisto"
experiment waits on it. Blocked twice over: the 2026-09-18 to 2026-10-02 window has not
closed, and no Search Console access exists from here.
**Next action:** read the same tables after 2026-10-02, once access exists. Evidence:
[docs/research/seo-and-search.md](docs/research/seo-and-search.md).

### Finnkino prices

Blocked by the access rule rather than by difficulty. The programme response the adapter
already reads carries no price field anywhere, scanning it for any key containing price,
amount, cost, ticket, fee, tariff or currency returns zero matches, and the obvious
ticket-type paths answer 404. The only route left is the seat-selection flow, which this
repo does not call or inventory.
The one route left open, a visitor-facing price *page*, is **deferred** by the maintainer
on 2026-09-16 for Finnkino and BioRex alike: neither is easily done. Nothing is probed and
nothing is scheduled. Evidence: [docs/research/prices.md](docs/research/prices.md).

### Iobio, Inkoo: readable only through two exceptions

The third host on The Events Calendar, and the one `tribe.py` does not read. Its films
carry no category of their own and are marked by an "IoBio:" title prefix, with each
screening duplicated across a Finnish and a Swedish calendar. Both exceptions are ones this
repo has written against: a word in a title is not a classifier, and a bilingual dedup has
to pick a canonical row, which double-publishes in one direction and drops a screening in
the other with nothing in a count to show it.
**What would change it:** Iobio publishing a film category of its own, or one calendar
rather than two. Then it is an ordinary `SITES` entry. Evidence:
[docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md).

## Deferred

Each of these was looked at and set down, with the reason. None is scheduled.

**App and client**

- A Swedish synopsis from TMDB. `enrich_tmdb` fetches `fi-FI` and `en-US` overviews and
  breaks out of the loop once Finnish answers, so adding `sv-SE` would be a third request
  per film per run and a restructure of that loop. Out of scope on 2026-09-16 by the
  maintainer's instruction; the slot exists and Bio Savoy fills it, so this would only
  widen the coverage.
- Precaching the app shell on install. **Declined 2026-09-20 by the maintainer**, and the
  recorded cache-deletion design is preserved: `sw.js` carries `/data/` across a version
  bump and deliberately does not carry `index.html`, so an old shell cannot come back as
  the offline fallback. The cost accepted with it is that a reader who updates and closes
  the tab has no page to launch offline until one online load. Record:
  [docs/archive/2026-09-app.md](docs/archive/2026-09-app.md).
- A "choose a cinema" shortcut at the top of a city page, and a general-feedback link
  beside the screening report. Both came out of the 2026-09-22 flow review and both add or
  move something a reader sees; the maintainer asked in the same session for no change to
  the page's design, so they stay proposals. The cinema list is already on the page, at the
  bottom; the report route is already there and stays separate from any feedback link.

- The screening's language on the Ajat ticket. **Declined 2026-09-23 by the maintainer:**
  it would widen the 120 px ticket to about 250 and leave a 320 px phone about 20 px of
  title. Record: [docs/archive/2026-09-app.md](docs/archive/2026-09-app.md).
- Sparse-date dimming in the date picker: `<input type="date">` cannot disable individual
  days without a custom picker.
- A timer for a tab left visible all day, which never fires `visibilitychange`. The
  resume and rollover refreshes cover everything else.
- `aria-busy` on the picker trigger until the venue lists arrive. It is the honest ready
  signal and a two-line client change. The `index.html` freeze that first held it was
  lifted on 2026-09-25 ([docs/archive/2026-09-app.md](docs/archive/2026-09-app.md)), but
  CLAUDE.md still asks for the maintainer's word before a ready marker is added, so it
  stays a proposal. The browser tests click until the picker opens instead.
- `safeUrl` still accepts a scheme-less URL, so the next provider publishing a bare path
  repeats Cinema Orion's 2026-09-06 fault. Whether the client should reject one or resolve
  it against the provider host is a separate change.
- Keyed DOM reuse in the render path: at this list size it buys nothing over
  `content-visibility:auto` and costs a rewrite.
- Seat counts on screen. They are parsed and deliberately not published: data is hours old
  and "12 vapaata" can be zero, while sold-out survives staleness. Do not restore them
  without solving the staleness.
- A floating theme button or a duplicate in the pinned strip. Theme and language are set
  about once a month and reintroducing them costs the 58 px v70 recovered.
- The tools row wrapping to two lines at 320 px. Forcing five controls onto one line costs
  tap targets, abbreviations or squeezed Finnish and Swedish labels.

**Pipeline**

- Counting how many consecutive runs Kino Engel's 500 fallback has been the only way in.
  **Decided 2026-09-21 by the maintainer:** the fallback stays indefinitely, and no
  persistent state is added to watch an incorrect upstream status code. It is narrowly
  scoped, validated and fails closed when the body stops carrying the programme, and the
  per-run log line is enough. Revisit only if Engel still answers 500 after a week, or if
  the tolerated response starts losing metadata. The host's second failure, a connection
  closed with no response, is a longer retry rather than a fallback and is separate:
  [docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md).
- Routing `enrich_tmdb.py` through `common.fetch`. It uses a bare `urlopen` with no retry,
  so a TMDB 429 skips that title.
- Bio Savoy's `accept-language: sv-AX,sv;q=0.9` and eTiketti's extra `accept` header. Both
  were left in place on 2026-09-19 when the twelve accidental page getters were folded
  into `common.get_text`: each has an obvious story and neither has a probe showing the
  host's response varies on it, and settling that is a read per host rather than a
  refactor. Measured per adapter in
  [docs/research/adapter-http.md](docs/research/adapter-http.md).
- `api()` in `fetch_data.py` has no retry, unlike `common.fetch`.
- Refactoring `enrich_tmdb.main()` (complexity 205, 481 lines): after the 09-25 rules settle.
- A dataclass for the fetch result. `run.py` already models it.
- A single shared TMDB pass. The two stay separate and agree on the rules, so the same
  film can briefly carry two ratings.
- Finnkino's editorial children's-film list as the authority for the Lapsille filter. It
  would work cross-chain by title and is another scrape on the local-only half. Watch the
  genre rule first.
- Pruning a poster once its film stops screening. A few MB a year.
- Closing the window where SITES and the venue files disagree: comparing them directly
  fails every provider addition until the pipeline has run.
- A cross-host redirect escapes the host claim. `common._claim` claims the request's host
  before sending and `urlopen` follows redirects, so the target is read unpaced and
  outside `hosts_attempted`. Swept 2026-09-19 over all 31 committed provider logs: every
  hostname they name is its module's own `base` or `reads`, and none carries a `refused
  to` line. The claim is taken before the request, so a redirect's target would not show
  up there either way, which makes this no evidence rather than a proof. Two sites name
  no `base` at all, Kino Engel and Kino Akseli; both are local-half, where the cloud
  pool's base-less group does not apply.

**Ops and pages**

- A distance figure on the region rows. `km` was deleted on 2026-09-18 rather than
  re-measured: nothing read it, it was never published, and the one figure that was
  measured fitted neither metric the others fitted. A radius, if one is ever wanted, gets
  measured once on one stated metric with its source. The record is in
  [docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md).
- Rewriting the history to drop the `Co-Authored-By` lines an earlier tooling default
  added. Measured and declined 2026-09-18: the practice already stopped, the line is
  cosmetic attribution rather than a name or a secret, and a rewrite would falsify every
  commit SHA the decision records cite. The figures are in
  [docs/archive/2026-09-ops.md](docs/archive/2026-09-ops.md).
- A README workflow badge. Measured and declined 2026-09-20: `ci.yml` runs only on code
  pushes, so a badge would show the verdict from the last code change rather than the
  repository's state. Record: [docs/archive/2026-09-ops.md](docs/archive/2026-09-ops.md).
- Moving the local fetch off the laptop. **Decided 2026-09-20 by the maintainer:** local
  fetching stays on the laptop, and replacing the infrastructure is outside this
  repository. The constraint is unchanged and is why the item existed: nine providers
  block or challenge datacenter addresses (Finnkino, Kino Akseli, Kino Engel, Joutsan
  Kino, Savon Kinot, Kino Regina, Cine, Elokuvateatteri Star, Elokuvateatteri Huvimylly)
  and three more run there until a runner is shown to read them, so 34 of 134 venues ride
  on one machine (docs/counts.md, 2026-09-24), and no cloud VM keeps that coverage.
- A Pages artifact deploy, to stop the committed pages growing the repo: 1.2 to 2.3 MiB a
  day packed, about 33 MiB a week for the whole repo (audit, 2026-09-25). It would move the
  traffic path behind Actions scheduling.
- A data branch: decided against 2026-09-01. Branching does not shrink history and every
  way off `main` is worse.
- `og:image` as a 1200x630 card rather than `icon-512.png`. It would preview better.
- A venue or city count in the meta description. It would be a third copy of a number that
  goes stale.
- The SEO experiment: "ohjelmisto" in Finnish theatre-page titles and descriptions on a
  subset against an unchanged control. Waits on the Search Console re-read.
- A Tuesday ~15:00 Helsinki local slot for Finnkino's weekly drop. Not built on a sample
  of one. Evidence:
  [docs/research/publication-rhythm.md](docs/research/publication-rhythm.md).
- Making showtime pages indexable. It would turn a personal app into a directory
  competing with the cinemas' own listings.
- Hidden text, `<noscript>` content that differs from what a visitor sees, or any other
  cloaking. Spam by every engine's definition.

## Documentation state

The counts are generated: [docs/counts.md](docs/counts.md), by `scripts/build_counts.py`,
which syncs README's four figures too. Hand-kept here, five of twenty-two passes shipped a
wrong number; earlier passes are in [docs/archive/2026-09-ops.md](docs/archive/2026-09-ops.md).
Where each document's content belongs is in [CLAUDE.md](CLAUDE.md), "Where it goes".

## Contact

**leffavuoro@gmail.com**

The address is written once as static markup in `status/index.html`. It is repeated here
and in `README.md` on purpose: `tests/test_contact_address.py` discovers it from the page
and requires both documents to carry the same one, so a half-finished rotation fails the
suite instead of shipping. The test also refuses any other address in any tracked file,
which is the leak guard. Do not remove this section without changing `SOURCES` in that
test, and do not add an address anywhere else.

The pipeline reads every provider as `Leffavuoro/1.0 (+https://leffavuoro.fi)`, and that
URL resolves to a page carrying this address, so a cinema can identify who is reading
them. If a cinema would rather not be included, the adapter comes out: one entry in
`scripts/providers/registry.py`, and no reason has to be given. The access rules are in
[CLAUDE.md](CLAUDE.md) under "Access and ethics".

## Where the rest went

Moved 2026-09-15: 4,790 lines of closed records and evidence, nothing deleted, headings kept.

**Closed decision records**, one archive file per area:

| File | What is in it |
|---|---|
| [docs/archive/2026-09-app.md](docs/archive/2026-09-app.md) | `index.html`, `sw.js`, the generated landing pages, `/status/`, accessibility, Finnish copy, the ticket's shape, and the `Done` checklist |
| [docs/archive/2026-09-pipeline.md](docs/archive/2026-09-pipeline.md) | `run.py`, `common.py`, the TMDB passes, the shared price and poster steps, the show contract, the rules every adapter is held to |
| [docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md) | one section per provider or sweep: what was probed, what the adapter decided, the accent, and the run that settled `where` |
| [docs/archive/2026-09-ops.md](docs/archive/2026-09-ops.md) | workflows, the checks that gate a push, hosting and DNS, the licence, IndexNow, crawler and snippet work, monitoring |
| [docs/archive/2026-09-gotchas.md](docs/archive/2026-09-gotchas.md) | the "Notes / gotchas" list: traps that cost a debugging session and did not become rules |

**Investigation evidence**, one topic file each:

| File | What is in it |
|---|---|
| [docs/architecture.md](docs/architecture.md) | how the pieces fit and the constraints behind them; a standing document, not an archive |
| [docs/research/ticketing-platforms.md](docs/research/ticketing-platforms.md) | BioRex, Nexxo, eTiketti, Vista, Johku, and the directory and domain sweeps |
| [docs/research/kinola.md](docs/research/kinola.md) | the three templates, films against other events, the four required fixtures |
| [docs/research/tooling-evaluation.md](docs/research/tooling-evaluation.md) | the seven tools measured on 2026-09-14 |
| [docs/research/prices.md](docs/research/prices.md) | where a ticket price can be read and where it cannot, per provider |
| [docs/research/accent-colour.md](docs/research/accent-colour.md) | how a chain accent is measured, the corrected ΔE figures, what binds a new one |
| [docs/research/languages.md](docs/research/languages.md) | which providers publish which languages, and the language-code measurement |
| [docs/research/seo-and-search.md](docs/research/seo-and-search.md) | the Search Console baseline and what the pages rank for |
| [docs/research/publication-rhythm.md](docs/research/publication-rhythm.md) | when cinemas publish, measured and as Finnkino states it |
| [docs/research/runner-challenges.md](docs/research/runner-challenges.md) | why a cloud run can fail on many unrelated cinemas at once, and what it costs |

**Accepted rules** were not moved into either: they were already in [CLAUDE.md](CLAUDE.md)
and [DESIGN.md](DESIGN.md). "Access and ethics" lived here; it is in `CLAUDE.md`, with how
each rule was arrived at in `docs/archive/2026-09-ops.md`.

"Seven backlog items closed without building them" and "The landing pages belong to the
product" now resolve in [docs/archive/2026-09-app.md](docs/archive/2026-09-app.md), with
what it records about the `index.html` freeze.
