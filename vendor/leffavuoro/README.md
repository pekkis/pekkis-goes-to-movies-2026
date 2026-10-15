# Leffavuoro

Leffavuoro collects Finnish cinema showtimes into one web app that you can install on a
phone or a computer: **https://leffavuoro.fi**

It has showtimes for 141 venues in 100 cities across 86 providers. The full list is in
[Cinemas](#cinemas).

## What it does

- Each showtime shows the film's poster, TMDB rating, age limit, runtime, genres and
  language. Ticket prices and sold-out marks are shown when the cinema publishes them.
- Tapping a showtime opens the cinema's own booking page. Cinemas that only take
  reservations open their programme page instead. Heureka's planetarium opens its ticket
  shop because the screening is included in a general admission ticket.
- Cities with more than one venue get a combined view that shows the same film from
  different chains as one card. The same goes for 15 regions, and the picker switches between
  its 100 cities and those regions. Pääkaupunkiseutu, for example, is one row in the picker
  instead of four cities. A region groups towns that are close enough for a cinema in one
  to replace a cinema in another.
- The picker search ignores diacritics. "jarvela" finds Järvelä and "capital region"
  finds Pääkaupunkiseutu.
- The app can be installed as a PWA and shows the last loaded schedule when offline.
- The home cinema, day, language, view, filters and theme are saved in `localStorage`. The
  venue on screen is not saved. When the app loads it opens the venue named in `?area=`,
  then the home cinema, and otherwise the chooser.
- Every venue and every city with several venues also has a static page in Finnish,
  Swedish and English. See [Generated pages](#generated-pages).

## How it works

The app never contacts the cinemas. A pipeline fetches the schedules in advance and
commits them as static JSON files, and GitHub Pages serves those files from the same
domain as the app. There is no CORS setup and there are no API keys in the browser. The
only third-party requests are for analytics, described under [Privacy](#privacy).

Some cinemas block requests from datacenter addresses and can only be read from an
ordinary internet connection. For that reason the pipeline runs in two halves. Each
provider in `scripts/providers/registry.py` is marked `where="local"` or `where="cloud"`.
A local machine reads the local half, normally four times a day. It pushes the results and
then starts the cloud workflow, which also runs on its own schedule.

The Finnkino token is taken from a browser session on every local run, and credentials are
not stored. GitHub's runners cannot get a token at all because Finnkino blocks datacenter
addresses with a Cloudflare 403.

After the fetch, `enrich_tmdb.py` adds TMDB ratings, trailers, synopses and posters where
the cinema does not provide them. It never overwrites the cinema's own text. Then
`mirror_posters.py` copies the posters to this site, `build_pages.py` builds the static
pages and the run commits everything.

Each fetcher writes its exit code to its own log in `logs/`. A failing cinema does not stop
the others. The committed logs are the authoritative record of each run.

[docs/architecture.md](docs/architecture.md) explains how the pieces fit together.
[IDEAS.md](IDEAS.md) lists open work. [docs/archive/](docs/archive/) holds dated decision
records, including approaches that were rejected. [docs/research/](docs/research/ticketing-platforms.md)
describes what each ticketing platform publishes.

## Running it

    python3 scripts/providers/run.py biorex                 # one module
    python3 scripts/providers/run.py --where cloud          # one half
    python3 scripts/providers/run_cloud.py --where cloud    # what the workflow runs
    python3 scripts/run_tests.py                            # unit tests, one process per file

The browser tests in `tests/browser/` run the app and the generated pages in Playwright. CI
runs them in Chromium and WebKit, two files at a time. To run them locally:

    python3 -m venv .venv && .venv/bin/pip install playwright==1.62.0
    .venv/bin/python -m playwright install chromium webkit
    .venv/bin/python scripts/run_tests.py --dir tests/browser --jobs 2
    KINO_BROWSER_ENGINE=webkit .venv/bin/python scripts/run_tests.py --dir tests/browser --jobs 2

## Adding a provider

1. Write `scripts/providers/{name}.py` with these two names:

       SITES             [{provider, label, venues:[{id, name, short, city}], base}]
       fetch_site(site)  -> {venue_id: [show, ...]}

2. Add an entry to `scripts/providers/registry.py` with the id, label, host, `accent` and
   `accentDark`, a `book` mode (`buy`, `reserve`, `door`, `list` or `admission`), the module
   and `where` it runs.
3. Run `python3 scripts/build_providers.py --sync-index`. It writes `data/providers.json`
   and the client's offline fallback list. The command edits `index.html`, which means
   `CACHE` in `sw.js` has to be bumped in the same commit.

First check whether the cinema uses a platform that is already supported. A cinema on Vista
with open XML, MyCloudCinema, Nexxo, eTiketti, Johku, Kinola, TMB, Cinemahouse or The Events
Calendar only needs a `SITES` entry in the existing adapter. `base` is the host a site is
read from, and sites with the same `base` are read one at a time. `reads` lists any other
host the adapter requests. The full checklist, including accents, link checks and the
access rules, is in [CLAUDE.md](CLAUDE.md) under "Adding a provider".

## Generated pages

The app itself is a single JavaScript-rendered URL. To give search engines something to
index, `build_pages.py` renders static pages from the same JSON at the end of every run. A
schedule and its pages always land in the same commit.

    /teatteri/{slug}/   one venue      /sv/teatteri/{slug}/   /en/theatre/{slug}/
    /kaupunki/{slug}/   a whole city   /sv/kaupunki/{slug}/   /en/city/{slug}/

Each language has 158 pages, one for each of the 141 venues and the seventeen cities with more than one venue.
Together with the front page the sitemap has 475 URLs. Regions do not get pages because
they would compete with the city and venue pages they are made of. A city with only one
venue does not get a page either. Its venue page has the city in its title and address.

Each page has the showtimes in plain HTML, `hreflang` links between the three languages and
`ScreeningEvent` and `MovieTheater` structured data. It has no `aggregateRating` because the
ratings come from TMDB. They are shown as credited text instead. Links into the app use
`/?area={venueId or city:Name}&lang={fi|sv|en}`. The reader lands on the same cinema or city
in the same language, and the app's saved home cinema does not change.

The pages use the app's design. The ticket's design values are in [DESIGN.md](DESIGN.md). A
page has two small inline scripts for the theme, its JSON-LD and `/pageview.js` (see
[Privacy](#privacy)). No script renders content. The pages contain nothing that changes
from run to run, and a page is rewritten only when its showtimes change.

## Data shape

Every provider writes the same files, and the client has no provider-specific code.

    data/providers.json            {providers: [{id, label, host, accent, accentDark, book, site?}]}
    data/area-{venueId}.json       {generated, dates[], horizon, shows[]}
    data/venues-{provider}.json    {generated, oldest, status, stale[], unverified[],
                                    pending[], provider, venues[{id, name, short, city}]}
    data/venuelists-{half}.json    {half, providers: {id: <venues file>}}, one per half
    data/films-extra.json          synopses, posters and trailers by title; synopses by
                                   language: fi, en, and sv where a cinema publishes one
    data/tmdb-genres.json          {fi, sv, en} genre id -> name, for rendering `gids`
    data/regions.json              {regions: [{name, sv, en, cities[]}]}, from the registry
    data/areas.json                Finnkino's venue list (legacy shape, numeric ids)
    data/films.json                Finnkino's film details, keyed by its film id
    data/tmdb.json                 TMDB cache for Finnkino films, keyed by its film id
    data/tmdb-titles.json          TMDB cache for every other provider, keyed by title
    data/prices-{provider}.json    prices read off ticket pages, keyed by screening
    data/film-lang-{provider}.json film languages read off a cinema's film pages

A showtime has `eventId, title, original, start (ISO, Europe/Helsinki), theatre, aud, url,
img, len, rating, genres, lang, method, soldOut`. Every provider except Finnkino also adds
`price, provider, venue`. The enrichment step adds `tmdbId, gids, tmdb, votes, tr, oyear`,
which are TMDB's id, genre ids, score, vote count, trailer and the film's first release
year. Optional fields are `age`, `year` (the release year as the cinema publishes it) and,
for Finnkino, `rd`, the premiere date while it is still in the future. The TMDB search uses
`original` and `year` when they exist and the title alone otherwise.

`rating` is the **film's** age classification. `age` is an extra limit set by the
**screening**. A licensed auditorium can be 18+ whatever the film's rating, and Heureka's
planetarium admits children from five. TMDB fields (`tmdbId`, `tmdb`, `votes`, `gids`,
`tr`, `oyear` and a TMDB poster in `img`) are only written for a trusted match, which means
an exact title or a hand-written alias id. A weak match could merge two different films into
one card. A TMDB poster is marked with `isrc: "tmdb"`, and a cinema's own poster has no
mark. When a cinema leaves `rating` blank, it can be borrowed from another chain showing the
same trusted match, and it is then marked `rsrc: "shared"`. In `films-extra.json` an entry
filled by TMDB records its `id`, and `ts` lists the synopsis languages that came from TMDB.
TMDB fields stay in the area files only while some venue shows the film, and
`tmdb-titles.json` keeps all of them.

In a provider file, `generated` is the time the file was written and `oldest` is the
timestamp of its oldest venue. The health line in the app uses `oldest`. A venue without
screenings is in one of three lists. `pending` means the cinema's listing was read and had
nothing in it, and the venue is published empty. `stale` means the venue came back empty or
missing and its previous file is kept because it still has a day ahead. `unverified` means
there was nothing worth keeping, and the venue is published empty. `status` is `partial`
when `stale` or `unverified` names a venue and `ok` otherwise.

## Files

    index.html, sw.js, manifest.webmanifest   the app, its service worker, the PWA manifest
    pageview.js                      the generated pages' one-event analytics loader
    fonts/                           self-hosted Archivo subsets and the OFL licence
    robots.txt, sitemap.xml          crawl rules and the generated sitemap
    teatteri/, kaupunki/, sv/, en/   generated pages, committed by every run
    status/, tietosuoja/             the status page and the privacy page, hand-written
    data/                            generated JSON and posters, committed by every run
    logs/                            the run logs, one per fetcher
    docs/                            architecture, decision records, research notes, counts

    scripts/fetch_data.py            Finnkino fetcher (Vista OCAPI)
    scripts/providers/registry.py    the one list of providers
    scripts/providers/{name}.py      one adapter per provider or platform
    scripts/providers/run.py         runs one adapter, or a list of them
    scripts/providers/run_cloud.py   one pool over every cloud module
    scripts/providers/common.py      shared fetch with retry and pacing, atomic writes
    scripts/providers/enrich_tmdb.py TMDB ratings, trailers, synopses and posters
    scripts/providers/mirror_posters.py  copies posters to this origin
    scripts/providers/prices.py      per-screening prices read off ticket pages, cached
    scripts/providers/refresh.py     when a cached TMDB entry is read again
    scripts/providers/strands.py     event strand prefixes split off a title
    scripts/providers/synmerge.py    merges provider synopses into films-extra.json
    scripts/providers/venuelists.py  the per-half venue lists
    scripts/build_providers.py       registry -> data/providers.json and the client's fallback
    scripts/build_regions.py         registry -> data/regions.json
    scripts/build_venuelists.py      venue files -> data/venuelists-{half}.json
    scripts/build_pages.py           the generated pages and the sitemap
    scripts/build_counts.py          the counts in docs/counts.md and this file
    scripts/make_cards.py            draws this project's own title cards
    scripts/accent_check.py          chain accent separation, colour-vision models included
    scripts/check_*.py               the checks CI and the local wrapper run
    scripts/ci_verified.py           lets main skip checks its branch already passed
    scripts/indexnow.py              tells IndexNow which pages a push changed
    scripts/poll_windows.py          when cinemas publish, from committed data
    scripts/run_tests.py             runs a test directory one process per file

    tests/                           the unit suite
    tests/browser/                   the Playwright suite
    .github/workflows/biorex.yml     the cloud providers, enrichment and pages
    .github/workflows/ci.yml         checks, unit suite, regeneration drift, browser suite
    .github/workflows/logs.yml       check_runs.py on any push that touches a log
    .github/workflows/indexnow.yml   indexnow.py on page changes

## Privacy

There are no accounts, cookies, ads or cross-site tracking. The app and the generated city
and venue pages send cookieless analytics, described below. The status page and the
privacy page load no analytics. Preferences stay in `localStorage`. Schedules are static
JSON files on this site, and no cinema learns who is browsing.

**Posters and the typeface are served from this origin**, from `data/posters/` and
`fonts/`. A poster that has not been mirrored yet is simply missing and is never loaded
from another host. Both the client and `build_pages.py` refuse images outside
`data/posters/`. Tapping a showtime or a trailer takes you to the cinema's booking page or to
YouTube. GitHub Pages hosts the site and logs requests like any host.

Analytics use **PostHog EU Cloud**. The browser makes two requests. One loads the bundle
from `eu-assets.i.posthog.com`, pinned to version 1.434.2 and its sha-384 hash with
`integrity`. The other sends events to `eu.i.posthog.com`. Cookieless does not mean
anonymous. PostHog receives the IP address and the request headers and derives an
identifier from them on its server. An IP address counts as personal data under the GDPR,
and this project does not claim otherwise. There are no cookies, browser storage
identifiers, person profiles or session recordings.

`analyticsScrub()` in `index.html` drops every event that is not in the table below and
every property that is not listed for that event. This includes the 43 properties the
library added when it was measured on 2026-09-20 (posthog-js 1.434.2, recorded in
[docs/archive/2026-09-app.md](docs/archive/2026-09-app.md)).

| Event | Properties |
|---|---|
| `$pageview` | `category`: home, venue, city or region in the app; `generated_city` or `generated_theatre` on a generated page |
| `area_opened` | `kind`, `area` |
| `cinema_opened` | `venue` |
| `date_changed` | `offset_days` |
| `language_changed` | `lang` |
| `search_used` | none; the query is not sent |
| `ticket_opened` | `provider` |

`$pageview` also sends `$current_url`. It is built as `https://leffavuoro.fi/app/{category}`
in the app and `https://leffavuoro.fi/pages/{category}` on a generated page, and the real URL
is never sent. Every event includes the project `token` and `distinct_id`, which in
cookieless mode is always `$posthog_cookieless`. Autocapture, heatmaps, surveys, feature
flags and remote configuration are turned off. Analytics only starts on
`https://leffavuoro.fi`. With Do Not Track or Global Privacy Control turned on, the bundle is
not loaded and nothing is sent.

The generated pages load `/pageview.js` (about 2.3 kB gzipped). It sends one `$pageview`
per page load with the page category and nothing else. It loads the PostHog bundle only
after the page has finished loading. It uses the same scrubber, origin check, DNT and GPC
check, pinned bundle and settings as the app, and `tests/test_analytics_privacy.py` fails if
the two differ.

Visitor numbers are estimates. PostHog builds its cookieless identifier from the IP address,
the user agent, the hostname and a salt that changes daily. One person on two devices
counts twice, people sharing an address and a browser count once, and a returning reader
counts again each day. Readers with DNT or GPC turned on, or with PostHog blocked, are not
counted.

The privacy page for readers is [/tietosuoja/](tietosuoja/), in Finnish, Swedish and
English. It also states the one-year retention period and the legal basis.

## Cinemas

Every provider and the platform or site its schedule is read from. The list comes from
`scripts/providers/registry.py`, and [docs/counts.md](docs/counts.md) has the generated
totals.

| Cinemas | Read from | Venues | Runs |
|---|---|---:|---|
| Finnkino | Vista OCAPI, short-lived token | 17 | local |
| BioRex | own site | 12 | cloud |
| Kinoset, Kino Aurora, Kino Hirvi, Bio Säde, Kino Marilyn, Kino Olympia, Järvelän Kino, Kino Metso | Nexxo | 17 | cloud |
| Kotkan Leffat, Savon Kinot, Bio Rex Kokkola, Kinopirtti, Leffabuumi, Studio 123 Järvenpää, Studio 123 Kouvola, Kino 123, Ihme Kompleksi, Kinotar 123, Kino Juha, Bio Grand, Bio Vuoksi, Kino Iiris, Joutsan Kino, K-Kino, Bio Grani, Cine, Elokuvateatteri Star, Cinema Niagara, Haapamäen Elokuvat | eTiketti | 31 | cloud; local: Savon Kinot, Joutsan Kino, Cine, Elokuvateatteri Star, Haapamäen Elokuvat |
| Riviera | own site | 2 | cloud |
| Gilda | MyCloudCinema | 2 | cloud |
| Cinema Orion | own site | 1 | cloud |
| Kino Engel | own site | 1 | local |
| Kino Akseli | own site | 1 | local |
| Heureka | own site | 1 | local |
| Korjaamo Kino | Vista public XML | 1 | cloud |
| Kino Tapiola | own site | 1 | cloud |
| Kino Regina | own site | 1 | local |
| Kino Piispanristi, Kino Lumo, Laitilan Kino | cinema-reservations | 3 | cloud |
| Iso-Hannu | own site | 1 | cloud |
| Kino-Toijala, Kino-Sampo, KinoMania, Elokuvateatteri Elo | TMB Cinema | 4 | cloud |
| Julia 1&2 | own site | 1 | cloud |
| Bio-Kaari | own site | 1 | cloud |
| Kino Vaakuna | own site | 1 | cloud |
| Kuvakukko | own site | 2 | cloud |
| Kino Kirkkonummi | own site | 1 | cloud |
| Bio Savoy | own site | 1 | cloud |
| Cine Mäntsälä | MyCloudCinema | 1 | cloud |
| Kino Kilta, Kino Laika, Kino Myyri, Cinema Sheryl, Kino Konepaja | Kinola | 5 | cloud; local: Cinema Sheryl |
| Bio Marilyn, Vihdin Kino, Bio Forum, Kinokulma, Kino Hannikainen, Kino Virta, Kino Kulttuurimylly | Johku storefront | 7 | cloud |
| Ritz Vaasa, Tähti Kino | The Events Calendar | 2 | cloud |
| Kino Hamina | own site | 1 | cloud |
| Kinotour | own site | 3 | cloud |
| Elokuvateatteri Marita | own site | 1 | cloud |
| Lieksan Kino | own site | 1 | cloud |
| Navettakino | own site | 1 | cloud |
| Pyhäsalmen VPK | My Calendar | 1 | cloud |
| Bio Pallas | own site | 1 | cloud |
| Elokuvateatteri Huvimylly | own site | 1 | local |
| Movie Company Alatalo | own site | 5 | cloud |
| Elävienkuvien teatteri | own site | 1 | local |
| Elokuvateatteri Matin-Tupa | own site | 1 | cloud |
| Kino Kuusamotalo | own site | 1 | cloud |
| Kino Akustiikka | Localhub | 1 | cloud |
| Kino-Huovi | own site | 1 | local |
| Kino K13 | own site | 1 | cloud |
| Kino Helios | Malmitalo's site | 1 | cloud |
| Kannusali | Espoo's event calendar | 1 | cloud |

## Data sources and access

Schedule data belongs to the cinemas, the 86 providers listed under [Cinemas](#cinemas).
Ratings, trailers and fallback synopses and posters come from TMDB. Every showtime links to
the cinema's own page, and the footer credits the source of the schedule on screen.

Not every image in `data/posters/` comes from a cinema or TMDB. Files named `card-*.jpg` are
this project's own **title cards**, an abstract background generated from a seed with the
film's title on top. They are used for films that have no poster this site may publish,
such as Heureka's planetarium films, and `scripts/make_cards.py` draws them. All other files
are mirrored copies. Finnkino's are named by its release id and the rest by the first 16 hex
digits of the sha1 of the source URL.

Every provider is read through the same public interface its own website uses, with an
honest User-Agent and **on a schedule that no visitor can influence**. Different cinemas are
read in parallel, but each cinema gets one request at a time, at the pace its adapter sets.
The app has no code that contacts a cinema.

Normally the local providers are read four times a day. The cloud providers are read after
each local run and on GitHub's schedule, which sometimes runs late or not at all. This is
the usual cadence and nothing enforces it. A manual run adds one more. Booking, payment and
admin endpoints are never called.

This is a personal, non-commercial project and is not affiliated with any cinema. A cinema
that does not want to be included can be removed by deleting one registry entry. See
[Contact](#contact).

## Licence

    Leffavuoro
    Copyright (C) 2026  Shady-Dev
    Licensed under the GNU Affero General Public License, version 3 or later.

The **code** is licensed under [AGPL-3.0](LICENSE). You can use it, change it and run it. If
you deploy a modified version that people use over a network, you must offer them its
source code (AGPL section 13).

**The licence covers only the code.** It does not cover:

    data/area-*.json     showtimes, which belong to the cinemas
    data/posters/*.jpg   poster art from the cinemas' own CDNs and TMDB, apart from
                         data/posters/card-*.jpg, this project's own title cards,
                         which the licence does cover
    fonts/archivo-*      Archivo, under the SIL Open Font Licence (fonts/OFL.txt)

Forking the code gives no rights to that material. If you read the providers yourself, use
your own name and User-Agent, and read "Access and ethics" in [CLAUDE.md](CLAUDE.md) first.

## Contact

**leffavuoro@gmail.com**

The pipeline identifies itself to every provider as
`Leffavuoro/1.0 (+https://leffavuoro.fi)`. The link leads here, where a cinema can see who
is reading its schedule and find the address above. If you run one of these cinemas and do
not want to be included, get in touch and the adapter will be removed. No reason is needed.
Questions about how a schedule is read, or reports of a wrong showtime, are welcome at the
same address.
