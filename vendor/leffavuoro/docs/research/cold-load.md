# Cold load: what the app fetches before anything is chosen

The `IDEAS.md` entry "Every cold load reads all 82 venue lists" asked for a measurement of
what the chooser needs before a lazy load is proposed. This is that measurement.

## Findings

- **Requests per cold load**, the 2026-09-25 audit (Chromium, Playwright 1.62.0, a clone of
  the repository served locally, the worker blocked): chooser 88 requests, a venue 89, the
  Helsinki city view 115 (16 area files and 10 posters on top). All three fetch every
  provider's `venues-{id}.json` and `areas.json`.
- **Size of the venue lists**, the committed `data/`, read 2026-09-26: 82
  `venues-*.json` files holding 117 venues, 25 KiB together and 15 KiB gzipped each on its
  own; the median file is 275 B. `areas.json` (Finnkino) is under 1 KiB. Every file carries
  `generated`, `oldest`, `pending`, `provider`, `stale`, `status`, `unverified` and
  `venues`.
- **Who asks for them**, `index.html` read the same day: boot prefetches every
  `venues-{id}.json` named in `PROV_FALLBACK` before anything else, then `loadAreas()`
  awaits all of them through `fetchVenueLists()` and fills the picker. Each answer from
  the service worker starts a background revalidation (`cache: 'no-cache'`), so a warm
  load also sends 82 conditional requests.
- **What the plain chooser draws from them**: nothing until the picker opens. The city
  links are static markup, the day chips are built before the lists arrive, and the
  language control does not wait for them. A `?area=` link or a stored favourite does
  need them: `knownArea()` validates the location against the venues and the city and
  region groups built from them.

## Inferences

- The cost is the request count and the revalidations, not bytes: 15 KiB gzipped is less
  than one poster.
- Deferring the fetch until the picker opens saves the requests only for a reader who never
  opens it, and delays the first open for everyone else; with a link or a favourite the
  lists are needed at boot anyway.
- One file holding all 82 as committed would turn 82 requests into one on every load, cold
  or warm, without changing what the client knows.

## What was built (2026-09-26)

The single cloud-written file proposed here was changed by the maintainer on 2026-09-26: it
would have left the local half's venues and `pending` a cloud run behind. Built instead:

- `data/venuelists-local.json` and `data/venuelists-cloud.json`, each
  `{"half", "providers": {id: <that provider's file, verbatim>}}`, built by
  `scripts/providers/venuelists.py` from the per-provider files on disk. `run.py` rewrites
  the file of the half it fetched for after each run (the local wrapper runs it once per
  module, so the last process leaves the local file matching every local provider file);
  `run_cloud.py` rewrites the cloud file at the end of its run, an aborted run included.
  One writer per file, so neither half can conflict on or lag the other's.
- The client asks for both and fetches a provider's own `venues-{id}.json` only when
  neither carries it: a combined file that is missing, is not JSON or has the wrong shape
  costs its own providers a request each. The per-provider files stay written.
- The drift check: `scripts/build_venuelists.py` in the Checks regeneration step, and
  `tests/test_venuelists.py` comparing the committed combined files with the committed
  provider files.
- The app's health and freshness are unchanged: it reads only `venues` and `pending` from
  these files, and both arrive verbatim. The status page followed in a separate change the
  same day, on the maintainer's instruction: its load reads the two combined files with
  the same per-half fallback, and a worker message for a combined file updates each of its
  providers through the page's existing ordering rules.

## Measured after (2026-09-26)

Same method as the audit's (the tree served locally, one fresh context per view, every
request that reached the server counted, the worker's revalidations included; warm is a
reload once the worker controls the page). Before is 3f4456623, measured the same day; it
reads one request above the audit's figures for the chooser and the venue.

| View | Chromium cold | Chromium warm | WebKit cold | WebKit warm |
|---|---|---|---|---|
| chooser `/` | 89 -> 9 | 87 -> 7 | 90 -> 10 | 90 -> 10 |
| venue `?area=or-helsinki` | 90 -> 10 | 88 -> 8 | 91 -> 11 | 91 -> 11 |
| city `?area=city:Helsinki` | 115 -> 35 | 103 -> 23 | 109 -> 29 | 109 -> 29 |

Every view drops the 82 per-provider requests for the 2 combined files. The status page,
measured the same way with warm meaning a worker the app installed: Chromium 86 -> 6 cold
and 86 -> 6 warm, WebKit 86 -> 6 cold and 87 -> 7 warm. The combined files
are 3.8 KiB and 23.3 KiB, 0.8 KiB and 3.1 KiB gzipped, against 15 KiB for the 82 files
gzipped one by one.

## Status

Built for the app and the status page; the records are in `docs/archive/2026-09-app.md`.
The per-provider files remain the fallback both pages read when a combined file fails.
