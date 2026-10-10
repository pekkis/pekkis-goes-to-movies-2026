# Tools evaluated against this pipeline

Moved out of `IDEAS.md` on 2026-09-14. The constraint every verdict is measured against is
the one in `README.md` and `CLAUDE.md`: no build step, no framework, and no dependency
beyond the standard library in the pipeline. A tool has to beat that, not merely work.

Seven were looked at on 2026-09-14. One adopted, one taken into CI, one deferred, the rest
declined.

---

## Adopted: stdlib typing

**Findings**: `typing.TypedDict` is standard library, so it costs no dependency.

**Status**: `common.Show` names the seventeen keys every adapter publishes and
`common.check_shows` is the runtime rule `run_site` applies before any write. See "Every
adapter is held to one show contract, at the boundary" in
`docs/archive/2026-09-pipeline.md`. Done.

---

## In CI: Playwright

**Findings**: `tests/browser/`, six tests driving the venue picker and the ticket links in
a real engine, on Playwright's own pinned Chromium (build 151 for 1.62.0), against fixture
data copied from the committed 2026-09-14 files and a pinned clock. `expect` waits only; a
PNG and a trace are written per failure. `KINO_BROWSER_CHANNEL=chrome` runs it on the
installed Chrome locally.

**Inferences and open questions**: a click issued before the venue lists arrived failed 1
run in 7. The page exposes no DOM signal for "venues usable": `openVenueSheet` returns
while `allVenues` is empty, the day chips are built before `await loadAreas()`, and
`fillAreaSelect` touches no DOM of its own. The honest fix would be an `aria-busy` on the
trigger, which is a two-line client change; `index.html` is frozen by the maintainer's
instruction of 2026-09-14, so the test retries the click instead. See "The picker has no
ready signal, so the test clicks until it opens" in `docs/archive/2026-09-ops.md`.

**Status**: **Correction:** the original note called this a trial. It is in CI as the
`browser` job in `.github/workflows/ci.yml`, which installs the pin and caches the
download, and it is listed in `CLAUDE.md` under Testing. Seven tests as of 2026-09-14. No
next step.

---

## Deferred: Scrapy 2.19

**Findings**: measured defaults against a scripted local server, not read off the docs:

- a 500 and a 429 both finish as `finished` with zero items;
- three tries, 0.0 s apart;
- `Retry-After` is unread: `retry.py` carries no such code;
- a `start_requests`-only spider sends nothing, because `start()` has been the entry point
  since 2.13. That last one was an obsolete example on our side, not a defect in Scrapy.

**Inferences and open questions**: telling a failure from a genuinely empty answer would
need an errback flag or a stats check the spider writes itself. That is exactly what
`run.py` already does, together with `common.EmptyProgramme`, and those two carry this
repo's hardest-won rule: a listing that still lists films while the parse yields nothing
must keep failing.

**Status**: deferred. Adopting it would trade a working failure model for a framework.

---

## Reference only: Beautiful Soup

**Findings**: the Orion regexes match a bs4 rewrite on 5 of 6 malformed variants. The one
that differs is a nested table, and no Kinola page has one. bs4 is about 4× slower here.

**Inferences and open questions**: bs4 re-serialises attributes with single quotes, so a
regex must never be written against its rendering of a page. That trap is recorded under
`docs/archive/2026-09-gotchas.md` and is the reason the two approaches cannot be mixed
casually.

**Status**: not adopted, and `bs4` appears nowhere in the repository. **Correction,
checked 2026-09-14:** the BioRex research note used to claim its HTML-in-JSON response is
parsed "with BeautifulSoup". `biorex.py` has always parsed with stdlib `re`. Fixed in
`ticketing-platforms.md`.

---

## Declined: Awesome Python, Awesome Go, Superpowers

**Findings**: the first two are catalogues, not tools. Superpowers begins at
brainstorming, which `CLAUDE.md` and the `kino-*` skills already settle.

**Status**: declined. No next step.
