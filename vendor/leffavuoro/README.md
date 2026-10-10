# Leffavuoro

Finnish cinema showtimes as a fast, installable web page.

**Live at https://leffavuoro.fi**

## What it does

Showtimes for 134 venues in 96 cities across 83 providers: Finnkino, BioRex,
Kinoset, Kotkan Leffat, Riviera, Savon Kinot, Gilda, Cinema Orion, Kino Engel,
Bio Rex Kokkola, Kino Akseli, Kinopirtti, Leffabuumi, Studio 123 Järvenpää,
Studio 123 Kouvola, Kino 123, Ihme Kompleksi, Kinotar 123, Kino Juha, Bio Grand,
Bio Vuoksi, Kino Iiris, K-Kino, Joutsan Kino, Bio Grani, Kino Aurora, Kino
Hirvi, Bio Säde, Kino Marilyn, Kino Olympia, Järvelän Kino, Kino Metso,
Cinema Niagara, Heureka, Korjaamo Kino, Kino Tapiola, Kino Regina, Cine,
Elokuvateatteri Star, Kino Piispanristi, Kino Lumo, Laitilan Kino, Iso-Hannu,
Kino-Toijala, Kino-Sampo, KinoMania, Elokuvateatteri Elo, Julia 1&2, Bio-Kaari,
Kino Vaakuna, Kuvakukko, Kino Kirkkonummi, Bio Savoy, Cine Mäntsälä, Kino Kilta,
Kino Laika, Kino Myyri, Bio Marilyn, Vihdin Kino, Bio Forum, Kinokulma, Ritz Vaasa,
Tähti Kino, Kino Hamina, Kinotour, Elokuvateatteri Marita, Lieksan Kino,
Navettakino, Pyhäsalmen VPK, Bio Pallas, Elokuvateatteri Huvimylly, Movie Company
Alatalo, Cinema Sheryl, Haapamäen Elokuvat, Elävienkuvien teatteri, Kino
Hannikainen, Kino Virta, Elokuvateatteri
Matin-Tupa, Kino Kuusamotalo, Kino Akustiikka, Kino-Huovi, Kino K13 and Kino
Helios. Films with
posters, TMDB ratings, age limits, runtimes, genres,
languages, plus ticket prices and sold-out marks where the cinema publishes
them. Tapping a showtime opens that cinema's own booking page, its programme
page where the cinema takes seat reservations rather than payment, or the ticket
shop where the screening is included in a general admission ticket (Heureka's
planetarium).

Cities with more than one venue get a combined view that merges the same film
across chains into one card, and so do 15 regions: the picker switches between
its 96 cities and those regions, so Pääkaupunkiseutu is one row rather than four
cities. A region groups towns close enough that a cinema in one can replace one
in another. The theatre picker is searchable, and "jarvela" finds Järvelä,
"capital region" finds Pääkaupunkiseutu. Installs as a PWA and serves the last
loaded schedule offline. Home theatre, day, language, view, filters and theme
live in `localStorage`. The venue on screen is not stored: a load opens the one
named in `?area=`, else the home theatre, else the chooser.

## How it works

No cinema API is called at load time. A pipeline fetches ahead of time and
commits static JSON, which GitHub Pages serves from the same origin: no CORS, no
keys in the client, no third-party services beyond analytics. Some providers block or challenge
datacenter addresses and can only be read from an ordinary connection, so the
pipeline runs in two places; `scripts/providers/registry.py` marks each provider
`where="local"` or `where="cloud"` and is the list, so this page does not carry a
second copy of it to go stale. One adapter can serve many providers, because most
small cinemas run one of a few ticketing platforms:

| Adapter | Providers | Venues | Auth | Runs |
|---|---|---|---|---|
| Finnkino (Vista OCAPI) | 1 | 17 | short-lived token | Local |
| eTiketti | 21 | 31 | none | GitHub Actions; 5 of 21 local, see registry |
| BioRex | 1 | 12 | none | GitHub Actions |
| Nexxo | 8 | 13 | none | GitHub Actions |
| Riviera | 1 | 2 | none | GitHub Actions |
| Gilda (MyCloudCinema) | 1 | 2 | none | GitHub Actions |
| Cinema Orion | 1 | 1 | none | GitHub Actions |
| Kino Engel | 1 | 1 | none | Local |
| Kino Akseli | 1 | 1 | none | Local |
| Heureka | 1 | 1 | none | Local |
| Vista (public XML) | 1 | 1 | none | GitHub Actions |
| Kino Tapiola | 1 | 1 | none | GitHub Actions |
| Kino Regina | 1 | 1 | none | Local |
| Bio Pallas | 1 | 1 | none | GitHub Actions |
| Elokuvateatteri Huvimylly | 1 | 1 | none | Local |
| Movie Company Alatalo | 1 | 5 | none | GitHub Actions |
| Cinemahouse (cinema-reservations) | 3 | 3 | none | GitHub Actions |
| Iso-Hannu | 1 | 1 | none | GitHub Actions |
| TMB Cinema | 4 | 4 | none | GitHub Actions |
| Julia 1&2 | 1 | 1 | none | GitHub Actions |
| Bio-Kaari | 1 | 1 | none | GitHub Actions |
| Kino Vaakuna | 1 | 1 | none | GitHub Actions |
| Kuvakukko | 1 | 2 | none | GitHub Actions |
| Kino Kirkkonummi | 1 | 1 | none | GitHub Actions |
| Bio Savoy | 1 | 1 | none | GitHub Actions |
| Cine Mäntsälä (MyCloudCinema) | 1 | 1 | none | GitHub Actions |
| Kinola (Kilta, Laika, Myyri, Sheryl) | 4 | 4 | none | GitHub Actions; Sheryl local |
| Johku (6 storefronts) | 6 | 6 | none | GitHub Actions |
| The Events Calendar | 2 | 2 | none | GitHub Actions |
| Kino Hamina | 1 | 1 | none | GitHub Actions |
| Kinotour | 1 | 3 | none | GitHub Actions |
| Elokuvateatteri Marita | 1 | 1 | none | GitHub Actions |
| Lieksan Kino | 1 | 1 | none | GitHub Actions |
| Navettakino | 1 | 1 | none | GitHub Actions |
| Pyhäsalmen VPK (My Calendar) | 1 | 1 | none | GitHub Actions |
| Elävienkuvien teatteri | 1 | 1 | none | Local |
| Elokuvateatteri Matin-Tupa | 1 | 1 | none | GitHub Actions |
| Kino Kuusamotalo | 1 | 1 | none | GitHub Actions |
| Localhub (Ylivieska) | 1 | 1 | none | GitHub Actions |
| Kino-Huovi | 1 | 1 | none | Local |
| Kino K13 | 1 | 1 | none | GitHub Actions |
| Kino Helios (Malmitalo) | 1 | 1 | none | GitHub Actions |

A local machine runs the local half, normally four times a day, pushes, then
triggers the cloud workflow. It takes a fresh Finnkino token from a real browser session each
run, so there is no stored credential and nothing to rotate. There is no cloud
fallback: a runner cannot obtain a token at all, since the site answers
Cloudflare 403 to datacenter IPs. Routing is per site, not per adapter, which is
how five eTiketti cinemas can be local while the other sixteen run on Actions.

Each fetcher writes its exit code to its own committed log rather than aborting,
so one failing provider never blocks the rest. **The committed `logs/run.log` and
`logs/run-{module}.log` are the authoritative record; the Actions logs are not.**
After the fetch, `enrich_tmdb.py` fills in ratings, trailers, synopses and
posters a provider does not supply, without overwriting the cinema's own text;
`mirror_posters.py` and `build_pages.py` run after it.

How the pieces fit together is in [docs/architecture.md](docs/architecture.md), and open
work in [IDEAS.md](IDEAS.md). Why any of it is shaped this way, with the approaches tried
and rejected, is in the dated records under [docs/archive/](docs/archive/). The investigations those decisions rest on, what each
ticketing platform publishes and how it was read, are under
[docs/research/](docs/research/ticketing-platforms.md).

## Files

    index.html                       the whole app
    sw.js                            service worker
    manifest.webmanifest             PWA manifest
    fonts/                           self-hosted Archivo subsets + OFL licence
    robots.txt, sitemap.xml          crawl rules; the sitemap is generated
    docs/architecture.md             how the pieces fit, and the constraints behind them
    docs/research/                   per-topic investigation notes behind the decisions
    docs/archive/                    dated decision records, closed
    logs/                            committed run logs, one per fetcher (the record)
    teatteri/, kaupunki/, sv/, en/   generated pages (committed by every run, cloud and local)
    status/, tietosuoja/             the status page and the privacy page, hand-written
    data/                            generated JSON and posters (committed by every run)

    scripts/fetch_data.py            Finnkino fetcher (Vista OCAPI)
    scripts/providers/registry.py    single source of truth for every provider
    scripts/providers/run.py         generic runner for one adapter, or a list of them
    scripts/providers/run_cloud.py   one pool over every cloud module; what the workflow runs
    scripts/providers/{name}.py      one adapter per provider or platform
    scripts/providers/common.py      shared fetch with retry, atomic writes
    scripts/providers/prices.py      per-screening prices read off the ticket page, cached
    scripts/providers/strands.py     event strand prefixes split off a published title
    scripts/providers/synmerge.py    merges provider synopses into films-extra.json
    scripts/providers/enrich_tmdb.py TMDB ratings, trailers, synopses, posters
    scripts/providers/refresh.py     when a cached TMDB entry is due to be read again
    scripts/providers/mirror_posters.py  mirrors hot-linked posters same-origin
    scripts/make_cards.py            draws this project's own title cards (by hand)
    scripts/build_providers.py       registry -> data/providers.json + the client's fallback
    scripts/build_regions.py         registry -> data/regions.json
    scripts/build_pages.py           renders the indexable pages
    scripts/build_counts.py          measures the counts into docs/counts.md and README
    scripts/accent_check.py          chain accent separation, incl. deuteranope
    scripts/check_inline_js.py       node --check on the pages' inline scripts and sw.js
    scripts/check_cache_bump.py      fails when an index.html commit leaves CACHE unbumped
    scripts/check_design_push.py     fails when a design contract push has no IDEAS.md change
    scripts/check_runs.py            fails when any committed run log did not end exit=0
    scripts/check_staleness.py       fails when data/areas.json is older than 8 h
    scripts/indexnow.py              tells IndexNow which generated pages a push changed
    scripts/poll_windows.py          when the cinemas publish, from committed data, no network

    tests/                           python3 scripts/run_tests.py (one process per file)
    tests/browser/                   Playwright suite, run on its own (below)
    .github/workflows/biorex.yml     all cloud providers + enrichment
    .github/workflows/logs.yml       runs check_runs.py on any push that touches a log
    .github/workflows/indexnow.yml   runs indexnow.py on page changes
    .github/workflows/ci.yml         on code pushes: suite, JS check, design-push and
                                     CACHE-bump checks, regeneration drift; the browser
                                     job in Chromium and WebKit

## Data shape

Every provider writes the same thing, so the client has no per-provider code.

    data/providers.json          {providers: [{id, label, host, accent, book}]}
    data/area-{venueId}.json     {generated, dates[], horizon, shows[]}
    data/venues-{provider}.json  {generated, oldest, status, stale[], unverified[],
                                  pending[], provider, venues[{id,name,short,city}]}
    data/venuelists-{half}.json  {half, providers: {id: <venues file>}}, one per half
    data/films-extra.json        title-keyed synopses, posters, trailers
                                 a synopsis is keyed by language: fi, en, and sv
                                 where a cinema publishes one (Bio Savoy, Åland)
    data/tmdb-genres.json        {fi,sv,en} genre id -> name, for rendering `gids`
    data/regions.json            {regions: [{name, sv, en, cities[]}]}, from the registry
    data/areas.json              Finnkino venue list (legacy shape, numeric ids)
    data/films.json              Finnkino film details, keyed by its film id
    data/tmdb.json               TMDB cache for Finnkino films, keyed by its film id
    data/tmdb-titles.json        TMDB cache for every other provider, keyed by title
    data/prices-{provider}.json  prices read off ticket pages, keyed by screening
    data/film-lang-orion.json    Cinema Orion's film languages, read off its film pages

A showtime carries `eventId, title, original, start (ISO, Europe/Helsinki),
theatre, aud, url, img, len, rating, genres, lang, method, soldOut`, and on every
provider except Finnkino also `price, provider, venue`. The enrichment step adds
`tmdbId, gids, tmdb, votes, tr, oyear`: TMDB's id, genre ids, score, vote count,
trailer, and the film's first release year. `age` and `year` are optional.
Finnkino adds `rd`, the premiere date, while it is still ahead.
`year` is the film's release year as the cinema publishes it, a four-digit
string, absent when it publishes none. The TMDB search uses `original` and
`year` when present and runs on the title alone when they are absent, so older
files without either field stay valid.

Two fields are easy to confuse. `rating` is the **film's** age classification;
`age` is a limit the **screening** adds on top: a licensed auditorium can be 18+
whatever the film is rated, and Heureka's planetarium admits from five. Every
TMDB field (`tmdbId`, `tmdb`, `votes`, `gids`, `tr`, `oyear`, a TMDB poster in
`img`) is written only for a trusted match, an exact title or a hand-written
alias id: a weak id folds two different films into one card, and its poster,
rating and synopsis are the wrong film's. A TMDB poster carries `isrc: "tmdb"`,
so the pass can replace or drop it later; a cinema's own poster carries no mark.
A `rating` the cinema left blank can be borrowed from another chain showing the
same trusted match, and then carries `rsrc: "shared"`. In `films-extra.json` an
entry TMDB filled records the TMDB `id`, and `ts` lists the synopsis languages
TMDB's text fills, so a changed match replaces only those. TMDB's fields are there only
while some area file shows the film; `tmdb-titles.json` keeps them all.

On a provider file, `generated` is when it was written and `oldest` is its
weakest venue's timestamp; the health line ages on `oldest`. A venue with no
screenings is in one of three lists. `pending`: the adapter read the cinema's
listing and it holds nothing, so the venue is published empty. `stale`: the
venue came back empty or missing and its previous file, with a day still ahead,
is kept. `unverified`: nothing worth keeping, either no data ever or a kept
file whose every day has passed, which is published empty. `status` is
`partial` when `stale` or `unverified` names a venue, else `ok`.

## Adding a provider

1. Write `scripts/providers/{name}.py` exposing two things:

       SITES             [{provider, label, venues:[{id, name, short, city}],
                          base (optional, see below)}]
       fetch_site(site)  -> {venue_id: [show, ...]}

2. Add an entry to `scripts/providers/registry.py`: id, label, host, accent,
   `book` mode (`buy`, `reserve`, `door`, `list` or `admission`), module, and
   `where` it runs (`cloud` or `local`).

Then `python3 scripts/build_providers.py --sync-index`, which writes
`data/providers.json` and the client's offline fallback list from the same registry;
bump `CACHE` in `sw.js` with it, since that touches `index.html`. The rest of the
checklist, `build_counts.py` and `run_cloud.SHARED_UPSTREAMS` among it, is in
[CLAUDE.md](CLAUDE.md) under "Adding a provider". The workflow runs
`run_cloud.py --where cloud`, whose module list comes from the registry, and the
client reads `data/providers.json`. One module can serve several providers,
which is why the provider id sits on the site: `etiketti` serves twenty-one
providers today and `nexxo` eight.

`base` names the host a site is read from and is the pacing key; `reads` names
any other host the adapter requests. Sites that share a host are read one after
the other. The rules for both fields, and what `common.reading` does with a host
read out of a page, are in [CLAUDE.md](CLAUDE.md) under "Adding a provider".

**Check for an existing platform first.** A cinema running Vista with its public
XML services open, MyCloudCinema, Nexxo, eTiketti or Johku needs a `SITES` entry
against the existing adapter, as does one on a platform another adapter here
already reads for several cinemas: Kinola, TMB, Cinemahouse, The Events Calendar.
`vista.py` reads Korjaamo Kino that way. Adding a
venue to an existing provider is one line. Pick the accent with
`accent_check.py`, not by eye. Fetch the page a showtime will link to and check
it answers before writing it down: six Nexxo sites once shipped dead ticket
links because one site's path was copied onto all of them.

    python3 scripts/providers/run.py biorex
    python3 scripts/providers/run.py --where cloud
    python3 scripts/providers/run_cloud.py --where cloud   # what the workflow runs
    python3 scripts/run_tests.py

The browser suite in `tests/browser/` drives the app and the generated pages in
Playwright, and CI runs it in Chromium and WebKit. Locally:

    python3 -m venv .venv && .venv/bin/pip install playwright==1.62.0
    .venv/bin/python -m playwright install chromium webkit
    .venv/bin/python -m unittest discover -s tests/browser
    KINO_BROWSER_ENGINE=webkit .venv/bin/python -m unittest discover -s tests/browser

## Indexable pages

The app is one JS-rendered URL, so `build_pages.py` renders static pages from
the same committed JSON at the end of every run, on the runner and on the
local machine alike, so a schedule and the pages built from it land in one commit:

    /teatteri/{slug}/     one venue        /sv/teatteri/{slug}/   /en/theatre/{slug}/
    /kaupunki/{slug}/     a whole city     /sv/kaupunki/{slug}/   /en/city/{slug}/

151 per language, 454 sitemap URLs: 134 venues plus the seventeen cities with more
than one venue, and the front page. The 15 regions get no page of their own: a region
page would compete with the city and venue pages it is made of, and a region
exists only inside the picker. A one-venue city would
duplicate its venue page and compete with it, so those get the city into the
venue page's title and address instead.

Each page carries real HTML showtimes, an `hreflang` for each of the three
languages, and `ScreeningEvent`/`MovieTheater` structured data. No `aggregateRating`: the
ratings are TMDB's, and presenting another party's ratings as the page's own is
against Google's guidelines, so it appears as credited text. Every page links
into the app as `/?area={venueId or city:Name}&lang={fi|sv|en}`, so a reader lands on the
cinema or city they were reading about, in the language they were reading it
in, and the app's saved favourite is left alone. The wordmark carries the
language too.

The pages share the app's design, fonts, light and dark tokens and ticket-shaped
showtimes; the ticket's values are in [DESIGN.md](DESIGN.md). All three
languages carry the same page for the same cinema or city, so the selector
changes the language and nothing else. The theme toggle reads and writes the
same `kino-theme` key as the app. A page carries two inline scripts, both for
the theme, its JSON-LD, and one async `/pageview.js`, which sends a single
cookieless page view (see Privacy); no script renders content. Nothing volatile,
so a page is rewritten only when its showtimes change.

## Privacy

No accounts, cookies, advertising or cross-site tracking. The app and the
generated city and theatre pages send cookieless analytics, described below; the
status page and the privacy page load none. Preferences stay in `localStorage`. Schedule data is
static JSON from this origin, so browsing tells no cinema anything.

**Posters and the typeface are served from this origin**, from `data/posters/`
and `fonts/`. The app's card poster carries `referrerpolicy="no-referrer"`; the
film sheet's poster and the generated pages' images do not, and being
same-origin they send no referrer to another host.

**Analytics: PostHog EU Cloud.** Two requests: the bundle from
`eu-assets.i.posthog.com`, pinned to version 1.434.2 and to its sha-384 through
`integrity`, and the events to `eu.i.posthog.com`. This is **cookieless, which is
not anonymous**: PostHog receives the network IP address and the headers the
browser sends, and derives an identifier from them server-side to count visitors
without storing anything in the browser. An IP address is personal data under
the GDPR, so it is not claimed that none is processed. There are no cookies,
browser-storage identifiers, person profiles or session recordings.

`analyticsScrub()` in `index.html` is posthog-js's `before_send`. It drops any
event not listed here and any property not listed for it, including the 43 the
library attached when measured on the wire on 2026-09-20 (posthog-js 1.434.2; record in
[docs/archive/2026-09-app.md](docs/archive/2026-09-app.md)):

| Event | Properties |
|---|---|
| `$pageview` | `category`: home, venue, city or region in the app; `generated_city` or `generated_theatre` on a generated page |
| `area_opened` | `kind`, `area` |
| `cinema_opened` | `venue` |
| `date_changed` | `offset_days` |
| `language_changed` | `lang` |
| `search_used` | none; the query is not sent |
| `ticket_opened` | `provider` |

`$pageview` also carries `$current_url`, built as
`https://leffavuoro.fi/app/{category}` in the app and
`https://leffavuoro.fi/pages/{category}` on a generated page, and never the real
URL, which holds the search query or the cinema. Every event carries the project
`token` and `distinct_id`, which in
cookieless mode is the constant `$posthog_cookieless`; posthog-js builds no
request without them. Autocapture, heatmaps, surveys, feature flags and remote
configuration are off. Analytics initialises only on `https://leffavuoro.fi`,
and under Do Not Track or Global Privacy Control the bundle is not fetched and
nothing is sent. The reader-facing version is [/tietosuoja/](tietosuoja/), in
Finnish, Swedish and English, with the one-year retention and the legal basis.

**The generated pages** load `/pageview.js` (about 2.3 kB gzipped), which sends one
`$pageview` per load with its category and nothing else: not the path, city,
cinema, film, query, title or referrer. It carries the app's scrubber, origin
guard, DNT and GPC check, pinned bundle, integrity hash and init options, and
`tests/test_analytics_privacy.py` fails if the two files drift apart. It asks for
the bundle only after the page's load event, so a slow or blocked PostHog cannot
delay the page. The legacy redirect pages, `/status/` and `/tietosuoja/` load none
of it.

**The visitor figure is an estimate.** PostHog derives its cookieless identifier
from the IP address, the user agent, the hostname and a salt that changes daily,
so one person on two devices or networks counts twice, people sharing one IP
address and the same browser count once, and a returning reader counts again each
day. Readers with
DNT or GPC set, or with PostHog blocked, are not counted, and posthog-js drops
events from automated browsers and known bot user agents before sending them.

A poster not yet mirrored is a missing picture, never a request to another
host: the client and `build_pages.py` both refuse one outside `data/posters/`.
How mirroring and the two guards work is in
[docs/architecture.md](docs/architecture.md) under "The order of a run".
`python3 scripts/build_counts.py --posters` prints how many references exist and
how many files back them; neither figure is committed, since both move with
every run.

**Not every picture in `data/posters/` came from a cinema or from TMDB.** The
files named `card-*.jpg` are Leffavuoro's own **title cards**: an abstract
background this repository generates from a seed, with the film's published title
set over it in Archivo. They are editorial illustrations, never posters, and they
are not derived from anyone's artwork. They exist for films that have no poster
this site may publish -- Heureka's planetarium films, whose promotional artwork is
licensed to nobody -- where the alternative is a two-letter initials tile.
`scripts/make_cards.py` draws them and `--check` verifies the committed files
against what it draws. Everything else in that directory is a cinema's or TMDB's,
mirrored: Finnkino's named by Finnkino's release id, the rest by the first 16 hex
digits of the sha1 of the source URL.

Besides the analytics above, tapping a showtime or a trailer hands you to the
cinema's booking page or to YouTube. GitHub Pages serves the site and logs
requests, as any host would.

## Data sources

Schedule data belongs to the respective cinemas, the 83 providers listed at the
top of this page. Ratings, trailers and fallback synopses and posters come from
TMDB. Every showtime links to the cinema's own booking page, and the footer
credits the source being displayed.

Every provider is read through the same public interface its own site uses, under
an honest User-Agent, **on a schedule that no visitor can influence**. Unrelated
cinemas are read at the same time; any one cinema is read one request at a time,
at the pace its own adapter sets. The app loads static JSON from this origin, so
browsing it, reloading it or leaving it open reaches no cinema: the client has no
code that calls a cinema.

Data is refreshed by a scheduled job and by a refresh triggered after each local
collection run. Under the normal configured cadence the local providers, counted
in [docs/counts.md](docs/counts.md), are read four times a day, and the cloud providers usually up to eight, since runs
are queued rather than merged. **Those figures describe the typical cadence and
the configuration does not enforce them.** Scheduled execution is best-effort
and may be delayed or missed, and a manual refresh adds runs.

Booking, payment and administrative endpoints are never called. If a cinema would
rather not be included, removing it is one registry entry; see Contact below.

This is a personal, non-commercial project with no affiliation to any of them.

## Licence

    Leffavuoro
    Copyright (C) 2026  Shady-Dev
    Licensed under the GNU Affero General Public License, version 3 or later.

The **code** is [AGPL-3.0](LICENSE). Use it, change it, run it. Deploy a
modified version that people reach over a network and you must offer them its
source (AGPL section 13). GPL-3.0's copyleft triggers on distribution, which
hosting a fork never performs.

**The licence covers the code and nothing else here.** Not mine to relicense:

    data/area-*.json     showtimes, belonging to the cinemas listed above
    data/posters/*.jpg   poster art from the cinemas' own CDNs and TMDB,
                         except data/posters/card-*.jpg, which are this
                         project's own title cards and are covered by the licence
    fonts/archivo-*      Archivo, under the SIL Open Font Licence (fonts/OFL.txt)

Forking the code carries no right to that material. Read the providers yourself,
under your own name and User-Agent, and see Access and ethics in
[CLAUDE.md](CLAUDE.md) first.

## Contact

**leffavuoro@gmail.com**

The pipeline reads every provider as `Leffavuoro/1.0 (+https://leffavuoro.fi)`.
That URL resolves to this page so a cinema can identify who is reading them and
reach the address above.

If you run one of the cinemas above and would rather not be included, say so and
the adapter comes out. It is one entry in `scripts/providers/registry.py`, and
no reason has to be given. Questions about how a schedule is read, or a wrong
showtime, are welcome at the same address.
