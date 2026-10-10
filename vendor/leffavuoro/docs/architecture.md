# Architecture

How Leffavuoro is put together, and which constraints shaped it. Extracted from
[README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) rather than invented; where the two
disagree with this file, they are the authority and this one is stale.

**No counts here on purpose.** Provider, venue, city, page and poster figures move with
every run and have been wrong five times from being carried between documents. They live in
one place, `IDEAS.md` under "Documentation state". This file describes shape, not size.

## The constraints everything else follows from

1. **No build step.** `index.html` is the whole client, served as authored. A syntax error
   in its inline script ships, so `scripts/check_inline_js.py` and CI stand in for a
   compiler.
2. **No dependencies beyond the standard library** in the pipeline, except Pillow for
   poster downscaling. No framework in the client.
3. **Static hosting.** GitHub Pages serves a branch. There is no server, so anything
   dynamic has to have happened before the push.
4. **Some cinemas refuse datacenter addresses.** That single fact splits the pipeline in
   two and is the reason for most of what follows.

## Two halves, one branch

No cinema is called at page load. A pipeline reads every provider ahead of time and commits
static JSON, which Pages serves from the same origin: no CORS, no key in the client, and
no request to a cinema from a visitor's browser. The one third party the app and the
generated city and theatre pages call is PostHog's EU analytics. The status page and the
privacy page call nothing. README's Privacy section lists what is sent.

It runs in two places because it has to:

- **Cloud half**, `.github/workflows/biorex.yml` on GitHub Actions, for providers a runner
  can read.
- **Local half**, a wrapper on an ordinary connection, for providers that answer a
  datacenter address with a Cloudflare 403 or a SiteGround challenge. It also takes a fresh
  Finnkino token from a real browser session each run, so no credential is stored.

`scripts/providers/registry.py` marks each provider `where="local"` or `where="cloud"` and
**is** the list. Routing is per site, not per adapter, which is how some eTiketti cinemas
run locally while the rest run on Actions. Both halves push to `main`, so both need the
pull-rebase retry, and generated data files cannot content-merge.

The local wrapper itself is **not in this repo**: its schedule, paths and credential
handling are machine-specific and live in private notes. The consequence to keep in mind is
that a repository change does not reach it. A change to what the local half writes or
stages has to be made there by hand.

## One adapter contract

A provider is a registry entry plus an adapter exposing two things:

    SITES             [{provider, label, venues:[{id, name, short, city}], base?}]
    fetch_site(site)  -> {venue_id: [show, ...]}

`scripts/providers/run.py` is the generic runner for all of them. It reads unrelated hosts
concurrently and serialises the sites that share one, so an adapter's own pacing still
describes what a single server experiences. The rule that makes that work, and the traps in
it, are in [CLAUDE.md](../CLAUDE.md) under "Adding a provider"; they are not repeated here.
One adapter serves many providers, because most small cinemas run one of a few ticketing
platforms.

`scripts/providers/run_cloud.py` is what the cloud workflow runs: the same host-keyed pool,
once, over every cloud module's sites rather than once per module. Workers fetch; the
coordinator publishes on one thread in module order and then site order, because
`films-extra.json` is one file for the whole run and the site that wins a synopsis has to be
the earlier one rather than whichever host answered first. It writes the same
`logs/run-{module}.log` per module. The local half keeps calling `run.py --where local`, and
so does anyone exercising one adapter by hand.

Every adapter is held to one show shape at the boundary: `common.Show` names the keys and
`common.check_shows` is the runtime rule `run_site` applies to what `fetch_site` returned
*before any write*, so a missing key or a show filed under the wrong venue fails that site
like a parse error and the previous files stand.

## What the data looks like

Every provider writes the same thing, so the client carries no per-provider code. The field
list is in [README.md](../README.md) under "Data shape"; the structural points are:

- `data/area-{venueId}.json` is one venue's schedule, `data/venues-{provider}.json` its
  venue list plus freshness. `data/venuelists-local.json` and `data/venuelists-cloud.json`
  carry every provider file of one half verbatim; each half rewrites its own after its run
  (`scripts/providers/venuelists.py`), so neither can conflict on or lag the other. The
  client reads those two and fetches a provider's own file only when neither carries it. Synopses and fallback artwork sit once in
  `data/films-extra.json`, keyed by normalised title, rather than repeated on every show. A
  synopsis is keyed by language inside that: `fi` and `en`, plus `sv` where a cinema
  publishes a native Swedish one. An adapter declares the language on its `_syn`; a bare
  string means Finnish, which is what every adapter published before 2026-09-16. TMDB's
  fields there are a projection of `data/tmdb-titles.json` for films some area file shows;
  an entry for a film none shows keeps only its text (E10, 2026-09-26).
- `data/providers.json` and the client's offline fallback list are **generated** from the
  registry by `scripts/build_providers.py --sync-index`. The client derives every label,
  host, accent and footer verb from it, so there is no second copy to go stale.
- Three implementations of the title normalisation must agree: `enrich_tmdb.norm()`,
  `synmerge.norm()` and `normTitle()` in the client. A mismatch fails silently.

## The order of a run

    fetch (per site, paced per host; on the cloud half one pool across every module)
      -> one show shape, checked at the boundary
      -> enrich_tmdb.py      ratings, trailers, synopses, posters a provider lacks
      -> mirror_posters.py   every remote poster copied under data/posters/
      -> build_pages.py      the indexable pages and sitemap.xml
      -> commit

Enrichment never overwrites a cinema's own text, and only a trusted match (an exact title
or a hand-written alias) publishes TMDB metadata: a weak id folds two films into one card.

`mirror_posters.py` sweeps the whole of `data/`, so whichever half runs first mirrors any
provider's posters. Two independent guards cover the window before it does: the client
refuses a poster outside `data/posters/` and `build_pages.py` leaves such a reference out of
the markup. An unmirrored poster is a missing picture, never a request to another host.

## The client

One file, no framework, no router. It reads static JSON from this origin and has no code
that calls a cinema. `sw.js` serves data JSON stale and revalidates behind, and its `CACHE`
version must be bumped in every commit that touches `index.html`.

After every data-file answer the worker posts `{checked, ok}` to the page, failures
included, and adds `fresh` when it had handed the page a cached copy and newer bytes are
now in Cache Storage. The page answers a message from Cache Storage only, never with a
fetch. A refresh that lands before the page has filled the slot it feeds is replayed once
the slot exists (`onFresh.filled`). The stale banner waits on those checks: late data on
screen shows a neutral "checking" state until every file behind the selection has been
answered or `FETCH_MS` has passed (`updateState`), so a copy about to be replaced is not
announced as late.

Two rules the client's correctness rests on: provider text is escaped at every `innerHTML`
interpolation and every provider URL goes through `safeUrl()`; and anything the language
toggle can reach must be redrawn by `applyLang()`. Behaviour that can be decided away from
the DOM is extracted as a pure function between comment markers and tested in node.

## The generated pages

The app is one JS-rendered URL, so `scripts/build_pages.py` renders static pages per venue
and per multi-venue city from the same committed JSON, at the end of every run on both
halves. They share the client's design and carry real HTML showtimes plus structured data.

Two properties hold them together: the output is **deterministic**, so nothing volatile may
go into a page or `write_if_changed` stops converging; and the pages depend on the day they
were built for, so `--date recorded` rebuilds for the day the committed sitemap carries.
CI's drift check regenerates and requires a clean tree.

## How failure is meant to surface

- Each fetcher writes its exit code to its **own** committed log rather than aborting, so
  one dead provider never blocks the rest. The committed logs under `logs/` are the
  authoritative record; the Actions logs are not, and are not read.
- A provider that parses zero showtimes fails the run, which catches an empty parse that
  would otherwise leave old data ageing with no signal. The one exception is an adapter
  raising `common.EmptyProgramme` after positive evidence of an empty listing. That site's
  venues are published empty and `pending`, so screenings the cinema withdrew leave the page.
- A failed venue writes no file, keeping the previous data, and is named `stale` in its
  provider file, while that file still has a day ahead. One whose every day has passed is
  published empty and named `unverified`, so a spent file cannot freeze a stamp. `oldest` is the provider's weakest venue, which is what the app's health
  line ages on, so a provider is only as fresh as its worst cinema.
- `scripts/check_runs.py` answers "did anything fail" by reading every committed log.
  `scripts/check_staleness.py` answers the different question "did a run happen at all",
  which the first cannot: a log reading `exit=0` four days ago passes it.

## Where the seams are

| Concern | Lives in |
|---|---|
| Which providers exist, and where each runs | `scripts/providers/registry.py` |
| How one provider is read | `scripts/providers/{module}.py` |
| Pacing, retry, body caps, atomic writes | `scripts/providers/common.py` |
| Everything the client renders | `index.html` |
| The visual decisions that are not defaults | [DESIGN.md](../DESIGN.md) |
| Schedule, credentials, machine paths | private notes outside this repo |
