# Working on this repo

Leffavuoro (leffavuoro.fi): Finnish cinema showtimes from the providers listed in
`scripts/providers/registry.py`, in one app. A single-file vanilla JS PWA served from
GitHub Pages, backed by a Python pipeline that commits static JSON. No build step, no
framework, no dependencies beyond the standard library in the pipeline.

## Read IDEAS.md first

It is the index of open work: active items with their next action, what is blocked and on
what, and what was deferred with the reason. Read it before proposing anything, because
several obvious improvements are recorded there as dead ends.

The reasoning behind what already exists is not in it. Closed decision records moved to
`docs/archive/` on 2026-09-15, one file per area, and `IDEAS.md` maps them at the bottom
under "Where the rest went". A long list of approaches tried and rejected is in there;
read the archive file for the area you are touching before reversing anything. If you
disagree with a recorded decision, argue with it in writing. Do not silently reverse it.
Update `IDEAS.md` in the same commit as the change it explains, and add the dated record
to the archive file for its area once the work is closed.

Write down why a change was made. The diff already records what changed.

## Where it goes

| What you have | Where it belongs |
|---|---|
| A rule every session must follow | `CLAUDE.md`, here |
| How the pieces fit, and why | `docs/architecture.md` |
| A visual value that is a decision | `DESIGN.md`, and only on written instruction |
| What the product is, and how to run it | `README.md` |
| A proposal, a priority, a status, an open item's next action | `IDEAS.md` |
| The dated record of a decision, once the work is closed | `docs/archive/<date>-<area>.md` |
| What you observed probing a site or evaluating a tool | `docs/research/<topic>.md` |

A research file separates findings, each with its source and the date it was read, from
inferences, open questions, and implementation status with the concrete next step. A
decision record links to its research file instead of repeating it. A
finding does not become a rule by being written down: promoting one into `CLAUDE.md` is a
decision, and it needs its `IDEAS.md` entry like any other.

`tests/test_ideas_index.py` enforces the `IDEAS.md` row rather than trusting it: a
whole-file ceiling, a 15-line ceiling per open item, and no measurement table inside one.
The rule above was prose for two days and was broken three times in that window, always
the same way, by writing a finished piece of work up in the file where the open work
lives. If an entry will not fit, that is the signal it is a record for `docs/archive/` or
evidence for `docs/research/`, not a reason to raise a cap.

`IDEAS.md` keeps one role nothing else can take: `scripts/check_design_push.py` requires
an entry there in the same commit as a `DESIGN.md` or `tests/test_design_contract.py`
change, so a contract change is explained in `IDEAS.md` and never in `docs/research/`.

## AGENTS.md is not this project's file

`CLAUDE.md` is the authoritative working-rules document and the only tracked one. An
`AGENTS.md` also appears in each worktree, untracked: `.gitignore` has excluded it since
commit `3996e21a`, whose note gives the reason as a file the agent tooling writes, which
untracked would show up as a pending change in every worktree and be offered as a pull
request, and tracked would be a public file this project does not author and cannot keep
accurate.

**What was checked here, 2026-09-14.** No generator for it exists in this repository: a
search of the tracked `.py`, `.yml`, `.sh`, `.json` and `.toml` files finds no reference
to `AGENTS.md`, and the only tracked file naming it is this one. Across the twelve
worktrees on one machine there were twelve different `AGENTS.md` files, 135 to 220 lines.
Four were read: the 135-line ones carry no design contract, no placement rule and no
mention of the browser suite, and the largest at 220 lines has the design contract but
neither of the other two.

**So those copies are stale, and nothing in this repository updates them.** A session
that reads one instead of this file is following superseded rules, and the gap is not
cosmetic.

What that evidence does **not** establish, and what this file therefore does not claim:
what writes those copies, when, or whether anything ever refreshes them. Twelve files
differing in length shows they disagree with each other, not how they came to. Read
`CLAUDE.md`. If your convention is to read `AGENTS.md`, read this file instead. Whatever
maintains those copies is not in this repository, so changing it is not attempted from
inside it.

## How to work

- **One commit per item.** Do not batch unrelated changes.
- **Ask when a fact cannot be checked.** If an endpoint is unreachable or a claim cannot
  be verified against the data, say so plainly and leave it unstated.
- **Measure counts against the data before writing them down.** Numbers carried over from
  an older document have been wrong five times: the city count, the poster count, the page
  rewrite frequency, and the venue and provider counts.
- **Verify a claim before documenting it.** The README asserted "no third-party requests"
  while the page loaded a webfont from Google and hot-linked posters from seven hosts.

## Commit messages

Conventional subject, `<area>: <what changed>`, stating the edit rather than arguing a
point. Body at most 120 words: why the change was made, the constraints that bound it, and
how it was verified, with break-verification on one line. Do not narrate the changed files
or repeat the diff. Longer reasoning and measurements belong in `IDEAS.md` or
`docs/archive/`; point at the entry instead of restating it. Commit as `Shady-Dev`, no
`Co-Authored-By`.

## Agent execution

- Before starting, briefly state what you will verify or change. During long work,
  give short evidence-based updates. The final report must stand on its own.
- Complete all reversible, in-scope work authorized by the request. Do not end a
  turn after merely announcing the next step or ask permission for work already
  requested.
- Stop for destructive actions, unauthorized external side effects, or a product
  decision whose alternatives would materially change the result.
- An explicit approval gate overrides autonomy. If the user says "design first"
  or asks to review a plan before implementation, stop at that gate.
- The request or approved plan defines the scope. Do not silently add nearby
  fixes, refactors, optimizations, documentation, or speculative tests. Report
  unrelated findings as follow-ups.
- Prefer surgical edits over whole-file rewrites when they produce the same
  result and preserve surrounding work.
- Batch independent reads and checks. Run dependent operations only after their
  prerequisites are known.
- Bound every background poll. If one misses a completion it should have seen,
  inspect the state it returned and switch to a direct status query rather than
  leaving it sleeping: a silent poll and a running job look identical.
- Re-measure repository and external state before relying on remembered counts,
  commits, workflow results, schedules, or generated data.
- Scratch checks do not need to become permanent tests. Commit focused tests at
  the same granularity as neighboring tests and only for requested behavior.
- Write directly and literally. Avoid mannered prose, decorative metaphors, and
  claims stronger than the evidence. Use headings and lists when they improve
  clarity.
- In handovers or compacted summaries, preserve exact user decisions,
  constraints, rejected approaches and reasons, paths, counts, dates, commit
  IDs, current state, and remaining work.

## Design contract

`DESIGN.md` lists the visual elements that are decisions: the ticket's anatomy and its
perforation first. `tests/test_design_contract.py` checks the client and the generator
against it, and CI refuses a push that touches `DESIGN.md` or that test without an
`IDEAS.md` change in the same push. A task spec that contradicts a value there is a
conflict to raise before building, never a change to make: on 2026-09-13 the perforation
left unpriced tickets under a spec, with the pinning tests rewritten in the same commit,
and came back the same evening. Change a contract value only on the maintainer's explicit
written instruction that names `DESIGN.md`, in one commit with the dated IDEAS entry.

## Client changes (`index.html`, `sw.js`)

- Bump the `CACHE` version in `sw.js` in **every** commit that touches `index.html`.
- `python3 scripts/check_inline_js.py` before pushing. It extracts the inline
  script block, `node --check`s it and `sw.js`, and parses any JSON-LD. The
  Checks workflow runs the same command, so a local pass is the same pass.
- A hard refresh verifies. No workflow dispatch is involved.
- Anything the language toggle can reach must be redrawn by `applyLang()`.
- Escape provider text at every `innerHTML` interpolation (`esc()`), and run every
  provider URL through `safeUrl()`. Adapters publish verbatim text, because the raw title
  is the key for `normTitle()`, `films-extra.json` and `tmdb-aliases.json`.
- `esc()` protects HTML contexts only. Provider text inside a `<script>` element needs
  `\uXXXX` escaping, because a literal `</script>` ends the element regardless of its
  type attribute. `ld_json()` in `build_pages.py` is the pattern; the escapes are
  equivalent JSON.
- Client behaviour that can be decided away from the DOM is tested by extracting a pure
  function verbatim between comment markers (`healthState`, `venueRows`). Keep the
  decision pure and the DOM plumbing thin, or it stops being extractable. Focus, inert and
  key handling stay verified live against the served page.
- **No `localStorage` assumptions beyond the existing keys.** Renaming `kino-prefs` or
  `kino-theme` wipes every user's saved venue, theme and starred cinema.

## Pipeline changes (`scripts/**`)

- After the commit, dispatch the cloud workflow, then verify against the **committed**
  `logs/run-*.log` files. Do not read the Actions logs. The cloud half runs
  `scripts/providers/run_cloud.py --where cloud`, one process and one pool over every cloud
  module; it writes the same per-module log plus `logs/run-cloud.log` for the run itself.
  The local half still calls `run.py --where local`, and so does exercising one adapter.
- Page changes show up in `logs/run-pages.log`, poster mirroring in
  `logs/run-posters.log`.
- **Both halves write into `logs/`.** The cloud half does because `biorex.yml` says so;
  the local half does because the wrapper outside this repo was changed to. A writer that
  still publishes to the repo root is caught by `check_runs.py`, which fails on a stray
  rather than reading the moved copies and calling them green.
- The pages depend on the day they are built for. `build_pages.py` alone builds for
  today in Helsinki (publishing); `--date recorded` rebuilds for the day the committed
  `sitemap.xml` carries (CI's reproducibility check, and a local regeneration on a later
  day). A diff after a plain rebuild on another day is the date moving, not drift.
- `scripts/fetch_data.py` and the local-only adapters cannot run on a runner. Compile
  check them, and **say clearly when a change needs a run from an ordinary connection**.
- `scripts/check_staleness.py` answers "did a run happen", which `check_runs.py` does
  not: a committed log reading `exit=0` four days ago passes that one. This repo holds
  only the verdict; the schedule, the file location and the recipient live in the
  out-of-repo wrapper. Its threshold is `STALE_H` from `index.html`, and a test fails if
  the two drift apart.
- A provider that parses zero showtimes fails the run, which catches an empty parse that
  would otherwise leave old data ageing with no signal. The one exception is an adapter
  raising `common.EmptyProgramme`, allowed **only** after fetching and parsing a listing
  that contained no films at all. A listing that lists films while the parse yields
  nothing is the broken case and must keep failing. Never add a per-site "allow empty"
  flag: it would switch the check off permanently for the site most likely to need it.

## Adding a provider

A registry entry plus an adapter. No hand-written `index.html` edit, but one generated
one: `python3 scripts/build_providers.py --sync-index` rewrites the `PROV_FALLBACK`
block from the registry, so bump `CACHE` in `sw.js` in the same commit. That block is
the list the client falls back to when `data/providers.json` cannot be read, and
`fetchVenueLists` looks up the venues of each provider in whichever list is in force, so a
provider missing from it loses its venues, not just its label.

- `scripts/providers/registry.py` is the single source of truth. `data/providers.json`
  is generated from it, and the client derives every label, host, accent and footer verb.
- An adapter exposes `SITES` and `fetch_site(site) -> {venue_id: [shows]}`.
- **A cleartext `base` only where the host serves no TLS.** Bio Savoy and Alatalo are read
  over `http://` because both refuse TCP/443 and answer 200 on port 80, probed 2026-09-22.
  That is the whole of the exception: an `http://` base needs the probe written up in
  `docs/research/adapter-http.md` with its date, and it comes out the day the host serves
  HTTPS. Never downgrade a host that has TLS, and never follow a `https:` -> `http:`
  redirect into one.
- **A site's `base` is the pacing key.** `run.py` reads hosts concurrently and
  serialises the sites that share one, keyed on `urlsplit(site["base"]).netloc`, so the
  sleep inside `fetch_site` still describes what a host sees. Two entries against one
  server must both name it in `base`: Bio Säde's data comes from kinohirvi.fi and only its
  ticket links go to biosade.fi, which is what `site` is for. On the cloud half that
  grouping is global -- `run_cloud.py` pools every module's sites at once -- so a site with
  no `base` shares one conservative group with every other base-less site **in the half**,
  not just in its module. Always name the host the site is read from. If a new cloud site
  lands on a registrable domain another module already reads,
  `tests/test_cloud_pool.py` fails: decide whether it is one upstream, and record the answer
  in `run_cloud.SHARED_UPSTREAMS` rather than widening the test.
- **`reads` names every *other* host the adapter requests**, ticket pages on their own
  host being the case that exists (Riviera's `tickets.rivieracinemas.fi`, Bio-Kaari's
  `bio-kaari.azurewebsites.net`). Grouping is
  over `base` plus `reads`, as connected components, so two sites touching one server are
  read one after the other whichever field named it. A differing `base` is not evidence of
  an independent upstream; check where the requests actually go. A URL read out of a page
  cannot be declared, and `common.reading` claims whatever host a request reaches for the
  life of that site's fetch: one site at a time, and a site that cannot get the claim
  within `KINO_HOST_CLAIM_WAIT` **fails before sending anything** rather than reading a
  host another site is still reading. A `refused to ...` line in a log is a `reads` entry
  waiting to be written: it says a request was withheld, never that two went out.
- **Check for an existing platform first.** A cinema running Vista, MyCloudCinema, Nexxo,
  eTiketti or Johku is a `SITES` entry against an existing adapter. Write a parser only if
  it runs on none of them.
- **Fetch the URL a showtime will link to and check it answers** before writing it into
  `SITES`. The API endpoint is the platform's and identical across its sites; the
  visitor-facing page is each site's own WordPress, named whatever its owner chose. Six
  Nexxo sites shipped dead ticket links because one site's path was copied onto all of
  them. No offline test can hold this. A checkout link copied from the listing is the
  exception: it is never requested, so a fixture holds that the exact href is copied, and
  the fallback page, the film page, is the one fetched and checked.
- **Measure a new accent against the whole set** with `python3 scripts/accent_check.py`.
  `--search {id}` proposes one, `--candidate HEX --city A,B` tests one, `--selftest`
  checks its own CIEDE2000 against published reference data. Do not quote an accent number
  that no script produced: the figures first recorded for these were CIE76 mislabelled as
  ΔE, and `docs/research/accent-colour.md` carries the corrected ones. Two views list
  chains together, a combined city and a region row from `REGIONS`, and both are measured:
  13 cities and 12 of the 14 regions as of 2026-09-21, so a site alone in its town is still
  constrained by its region. Combined-city pairs hold a strict 14.4 ΔE00 minimum across
  all three models, the worst being 14.409 of 66 pairs. Region pairs are measured on the
  same scale, but twenty established ones sit below it, of 166. Score on the weakest of
  the three models: Kino Engel and Cinema Sheryl are 19.2 apart to a deuteranope and 16.6
  to everyone else. Clear 14.4 in every view a new accent enters, and never lower an
  existing regional minimum without recording why in `IDEAS.md`. Colour stays
  supplementary: both views also print venue names and a chain legend.
- **A full city is re-solved, not excused.** When a city holds so many chains that no
  colour clears 14.4 against the ones already there, optimise that city's whole palette
  jointly instead of lowering the floor, widening the L* band or writing an exception into
  `tests/test_accent_check.py`. Helsinki reached ten chains on 2026-09-21: held at its
  eight existing accents the best candidate reached 12.12, and moving four of them lifted
  the city to 14.409 with every other city view still clearing 14.4 and no region minimum
  lowered. The solve is deterministic and recorded in `docs/archive/2026-09-providers.md`.
  A chain whose accent moves keeps every guarantee it had elsewhere, which is what makes
  moving it cheaper than an exception.
- **A price is published only where it is established for that screening.** A tariff that
  turns on something the adapter cannot read -- 2D against 3D with no marker on the row, an
  *arkipyhä* with no calendar to check -- settles no amount, and `price` stays empty for the
  screenings it does not settle. Publish the part it does settle and leave the rest blank:
  Iso-Hannu's `Pe-su ja arkipyhä 14,50 €` fixes Friday to Sunday outright and leaves Monday
  to Thursday open. Documenting that a figure is sometimes 0.50 out is not a substitute; the
  reader does not read the docstring. A labelled house tariff instead of a per-screening
  amount is a different field and needs the maintainer's decision.
- **A synopsis declares its language.** `_syn` as a bare string means Finnish and always
  has; an adapter publishing anything else writes `{"sv": ...}` and `synmerge` files it in
  that slot. The slot is keyed by normalised title and read by every chain showing the film,
  so an undeclared Swedish blurb is served as Finnish everywhere. Only `fi`, `sv` and `en`
  are accepted, because those are what the client offers.
- Check field-presence assumptions in the client as well as in the parser. Every frontend
  bug on the day multi-provider landed came from a field only Finnkino populated.
- **Check the published result against the cinema's own page before calling it done.** Not
  the parse and not the run log: the committed `data/area-*.json` and what the client draws
  from it, beside the cinema's own programme. Same films, same dates and times, a poster on
  every card, and the ticket link landing on that screening. This is the adapter author's
  job, not the maintainer's: on 2026-09-19 four new cinemas shipped 19 showtimes drawn as
  initials tiles, and it was found by the maintainer looking at the site. An initials tile
  is the TMDB pass failing to match a title, which is a marker the adapter published --
  `(Puhumme suomea!)`, `-elokuvanäytös` -- and it is fixed in `enrich_tmdb.clean`, on the
  search string, because the published title is a key. A provider commit that has not been
  looked at is not finished, and saying "the run exited 0" is not the same claim.

## Hard rules

- **Never use `raw.githubusercontent.com` to read this repo.** Its CDN served a
  two-commit-stale `index.html` minutes after a push and silently reverted a fix. Use the
  Contents API with `Accept: application/vnd.github.raw`, or a tarball of `main`.
- **Never commit a raw probe dump.** A third party's page carries whatever they ship to
  visitors, and one such dump put someone else's API key in this repo and tripped secret
  scanning. Probe, read the answer, write the *finding* in `docs/research/`, commit
  nothing raw.
  `.gitignore` blocks `probe/` and `probe-*`.
- **Nothing machine-specific in this repo.** It is public. No paths, no hostnames, no
  schedules, no credentials, no token retrieval, no third-party endpoint inventories
  beyond the read endpoints an adapter uses. Operational detail lives in private
  notes outside the repo.
- **No real name and no personal address, in a file or in a commit.** Commit as
  `Shady-Dev <19388620+Shady-Dev@users.noreply.github.com>`. If you see an author line
  that is not that or a `kino-bot`/`kino-local` identity, stop and say so. A real name
  reached 18 commits once and cost a history rewrite.
  `tests/test_contact_address.py` fails if any address other than the contact alias
  appears in a tracked file, generated pages included.
- **Never inflect Finnish city names in generated text.** Helsinki -> Helsing**i**ssä and
  Tampere -> Tampereella: the stem changes, and cities do not all take the same case.
  Gluing a case ending onto the nominative gives Helsin**ki**ssä, which is wrong. Always
  use the nominative with a separator.
- **Keep anything volatile out of generated pages**, or `write_if_changed` stops working:
  no build timestamp, no sold-out state in markup.
- **Do not read a site from a datacenter IP and conclude it is unreachable.** Several
  providers challenge datacenter addresses and answer an ordinary connection fine, and the
  block is often on a single endpoint while the rest of the host serves normally.

## Access and ethics

Every provider is read through the same public interface its own site uses, on a schedule
no visitor can influence, and every showtime links back to the cinema's own page. The
client reads static JSON from this origin and never calls a cinema. The cadence is not
enforced anywhere: normally the local providers run four times a day and the cloud half
gets a four-times-daily cron plus one run after each local run, so usually up to eight,
but `workflow_dispatch` stays callable by hand and scheduled execution is best-effort.
Describe it as a normal cadence, never as a bound, and do not write a fixed number back in.

Reading a site as an ordinary visitor is fine. Residential proxies, fingerprint spoofing,
solving a captcha, and using credentials that were never issued to a visitor are not.
Booking, payment and administrative endpoints are never called and are not inventoried.
Publishing a ticket link the cinema's own public listing carries is not calling it: the
adapter copies and resolves that exact href and never constructs one. As a rule it never
requests it either, not in a run and not once in a browser to check it. One narrow
exception, decided by the maintainer on 2026-10-09: Riviera and Bio-Kaari make cached,
paced, read-only GETs of each screening's public detail page on their MyCloudCinema ticket
host (`websales/show/{id}`), through `prices.py`, for the price and the language it states.
Nothing past that page is requested: checkout, seat reservation, payment and administrative
actions stay off limits for every provider. A link that could only be obtained by calling
such an endpoint, or with a credential a visitor is not issued, is not published.
If a cinema would rather not be included, removing it is one registry entry.

## Testing

    python3 scripts/run_tests.py

Stdlib `unittest`, no dependencies, no runner config. `run_tests.py` runs each
`tests/test_*.py` in its own process, one per CPU, and prints unittest's own verdict lines;
`python3 -m unittest discover -s tests` is the same suite in one process, about three times
slower. CI runs `run_tests.py --fail-on-skip`. Run it before pushing anything under
`scripts/`.

**Iterate with targeted files** (`-p "test_x.py"`), which cost seconds. Run the whole
suite **exactly once**, immediately before the final push, after every commit in the batch
is ready; where they apply, run the generators and the drift check first so generated
output goes in the same push. A failure is fixed with targeted runs and then one more full
suite. One commit per item still holds: several finished commits are pushed together after
that single run. Thirteen full runs in one two-hour block on 2026-09-20 cost 21 minutes,
19% of it, against six commits.

`tests/browser/` is a second suite, not discovered by the line above: the Playwright tests
in `test_client_browser.py` that drive the venue picker and the ticket links in a real
engine against fixture data and a pinned clock, plus those in `test_pages_layout.py`
below, which the same discovery picks up. `test_update_check.py` is the one file that runs
the service worker, against the stale banner, on the real clock, and
`test_ticket_separators.py` serves its own data to drive the square separators between a
ticket's facts, hover and focus. CI runs the directory as
the `browser` job in **Chromium and WebKit** since 2026-09-19, and `KINO_BROWSER_ENGINE`
picks the engine locally in every file, default chromium. Locally:

    python3 -m venv .venv && .venv/bin/pip install playwright==1.62.0
    .venv/bin/python -m playwright install chromium webkit   # or KINO_BROWSER_CHANNEL=chrome
    .venv/bin/python -m unittest discover -s tests/browser
    KINO_BROWSER_ENGINE=webkit .venv/bin/python -m unittest discover -s tests/browser

Run it for a change to the picker, the stubs or boot. A failure leaves a PNG and a trace
zip in `tests/browser/out/` (`playwright show-trace`). The page exposes no DOM signal for
"venue lists loaded", so the tests click the trigger until the picker opens; do not add a
sleep, and do not change `index.html` to add a marker without the maintainer's word.

`tests/browser/test_pages_layout.py` covers the generated pages instead of the app: where
a film's poster, header and ticket list are drawn, at eight widths, over four fixture films
including one with no poster and one that is a title and nothing else. CI runs it inside
the `browser` job in **Chromium and WebKit**, reported in its own summary section, and
either engine failing turns the Checks run red.

Red is a verdict, not a gate: `main` carries no branch protection and no ruleset, and
required status checks gate a pull request merge, which this repository does not use. The
push routine is what enforces it, so read the branch's Checks before the fast-forward.
On a push to `main` the suite, the drift check and the browser jobs are skipped when that
exact SHA already passed them on a branch push (`scripts/ci_verified.py`); the JavaScript
check and the design and CACHE gates always run over the push's own range. A direct push
to `main` gets the full run.

**Name the engines whenever you claim browser verification.** One engine is not a check. On
2026-09-18 the phone layout of the landing pages shipped correct in Chromium and broken in
WebKit -- `grid-row:1/-2` counts back from the explicit grid and the rule declared no
explicit rows -- and every landing page served an iPhone its metadata and synopsis below
the poster. The unit suite reads markup, the design contract reads numbers out of the CSS,
and the browser check written that day drove Chromium alone, so three layers were green.
It was found by a reader looking at their phone. "Verified in a browser" names nothing a
reviewer can check; write which engines, and at which widths.

`.github/workflows/ci.yml` runs the suite, `check_inline_js.py` and a regeneration-drift
check on every push that touches `index.html`, `sw.js`, `scripts/**`, `tests/**` or a
document the suite reads (`CLAUDE.md`, `IDEAS.md`, `README.md`, `docs/**`,
`tietosuoja/**`). It fails on a **skipped** test as well as a failing one: every dependency
is installed on the runner, so a skip means one went missing. Locally five poster tests skip because Pillow is
not on the system interpreter.

A fixture has to exercise the loop as well as the body. A one-item fixture once passed
while the pacing branch it never entered was missing an import, and `py_compile` does not
resolve names. Use two items minimum wherever there is pacing or an index.

**Verify every test by breaking the code it covers.** Write it, break that code, watch the
test go red, then restore. Every cap, fallback and error path has to be checked by
tripping it: one looked correct and silently published a half-empty schedule until it was
triggered.

Where the behaviour under test is partly urllib's (which exception a 429 raises, what
`e.headers` holds), tests talk to a real local HTTP server. A mock would encode the
assumption it is supposed to check.
