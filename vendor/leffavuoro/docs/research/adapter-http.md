# How each adapter asks for a page

Measured 2026-09-19 at `b4c8b0bb4`, by walking every `scripts/providers/*.py` with `ast`
and attributing each call to `fetch`, `common.fetch`, `urlopen` and `get_text` to the
function that makes it. Nothing here is a rule; the decisions it fed are in
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md) and the one item still
open is in [IDEAS.md](../../IDEAS.md).

## The shared way

`common.get_text(url, fetcher=None, **kw)` at `common.py:737`: `cache=True`, the
`TEXT_HEADERS` pair of an honest User-Agent and `accept-language: fi-FI,fi;q=0.9`, a 30 s
timeout, and a UTF-8 decode with replacement so one bad byte costs a character rather than
the page. `fetcher` is the seam the adapter tests rely on: each stubs its own module-level
`fetch`, so a wrapper reaching `common.fetch` directly would turn every one of those stubs
into a no-op.

## Findings

**The "twelve" in `4ce7e25e1` was right about the twelve it looked at and silently untrue
of twelve more.** That commit folded seven byte-identical wrappers and its message says
"No other wrapper was touched: twelve differ in a header, a timeout, an accept, an opener
or a JSON parse, and each difference is deliberate for that host." Re-measured: 34 small
HTTP wrappers exist, and grouping them on their normalised bodies rather than on their
source text gives four groups the earlier pass could not see.

| group | adapters | difference from `get_text` | verdict |
|---|---|---|---|
| no-arg page getter | julia, kirkkonummi, tapiola, vaakuna | none | accidental |
| no-arg front page | biokaari, isohannu | none | accidental |
| one-arg getter | kuvakukko, tmb | none | accidental |
| one-arg, kwargs reordered | cinemahouse | none | accidental |
| fetch, guard, parse | engel, kinoakseli, orion | none in the fetch | accidental |
| `enrich()` default getter | biokaari, engel, isohannu, regina, tapiola | `tries=2, backoff=3, timeout=20` | accidental, expressible |

The earlier pass grouped on source text, and all seven it folded carried a
`(url, tries=3, timeout=30)` parameter list these do not, which is why nine
byte-identical ones were never counted.

**The deliberate twelve, each with the evidence that settles it.**

| adapter | difference | evidence |
|---|---|---|
| biorex `_post`, `fetch_venue` | POST, cookie opener, referer | its own docstring; the site's selection flow |
| regina `get_schedule` | POST, `cache=False`, 40 s | the endpoint takes a form body |
| riviera | POST written inline in `fetch_site` | its own docstring |
| johku | `opener=OPENER` | [2026-09-providers.md](../archive/2026-09-providers.md); the hosts answer 103 Early Hints before the 200 |
| heureka | `cache=False`, 40 s, own headers | the page answers `If-None-Match` with a full 200 every time |
| gilda | 45 s, `accept: application/json`, JSON parse | named in [2026-09-pipeline.md](../archive/2026-09-pipeline.md) |
| vista | 40 s, `accept: application/xml, text/xml, */*` | the service is XML |
| nexxo | `accept: application/json`, referer per location | the API refuses without the referer |
| cinemantsala | `accept: application/json`, JSON parse | its own docstring |
| tribe | `accept: application/json` | the REST route is JSON |
| enrich_tmdb | bare `urlopen`, no retry | already a Deferred line in IDEAS.md |

**Two are unsettled rather than deliberate, and are left alone.**

- `biosavoy.get` sends `accept-language: sv-AX,sv;q=0.9`. Written in
  `aec9ff4d0`, "providers: add Bio Savoy, Mariehamn". Mariehamn is Swedish-speaking and
  the site is in Swedish, so the header has an obvious story, but no probe recorded here
  shows the host's response varying on it.
- `etiketti.get` sends an extra `accept: text/html,application/xhtml+xml`. Written in
  `f30978b06` and preserved through the `common.fetch` migration, whose own docstring says
  the migration kept the loop's behaviour unchanged. So the header was carried over rather
  than chosen, and no probe shows the twenty eTiketti hosts varying on it.

**Two providers are read over plain HTTP, because neither host serves TLS.** Probed
2026-09-22 from an ordinary connection:

| host | TCP/443 | plain HTTP | adapter |
|---|---|---|---|
| `www.biosavoy.ax` | refused, `curl: (7) ... port 443` | 200, 33850 bytes, no redirect | `biosavoy.py:99` |
| `www.moviecompanyalatalo.fi` | refused, same | 200, 11683 bytes, no redirect | `alatalo.py:63` |

Port 80 answers on both and port 443 does not, so there is no HTTPS endpoint to switch to
and no redirect to follow. Both are `where='cloud'`, 6 venues between them (Bio Savoy 1,
Alatalo 5), and they account for every `http://` ticket destination in the committed data:
28 showtimes, 15 Savoy and 13 Alatalo, measured 2026-09-22. Both are `book='door'`, so no
reader is sent to a payment form over cleartext.

Re-probed 2026-10-04: TCP/443 refused on `biosavoy.ax`, `www.biosavoy.ax` and
`www.moviecompanyalatalo.fi` (`curl` exit 7), and `moviecompanyalatalo.fi` has no A record
(exit 6), while `http://www.` answered 200 on both. So the status page's and the stale
notice's link, `https://{host}/`, could not connect for either; the registry's `site`
field sends those two links to the `http://www.` origin the adapter reads.

What that exposes: an on-path attacker controls what gets committed for those venues. What
it does not: `esc()` and `safeUrl()` stop injected text becoming script, and `safeAssetUrl`
stops it becoming an off-origin request. The rule this fed is in
[CLAUDE.md](../../CLAUDE.md) under "Adding a provider".

## Inferences, marked as such

- Folding the accidental twelve cannot be break-verified by re-inserting the old wrapper:
  that is an equivalent mutation and scores VOID by construction. What the fold is *for*
  is testable, and `tests/test_get_text_contract.py` asserts it: every page getter reaches
  its module's own `fetch` with the shared headers, `cache=True` and the 30 s timeout.
  Before that file, nothing in the repository asserted a request header at all.
- Settling the two unsettled ones needs a live read from an ordinary connection comparing
  the response with and without the header, per host. That is a probe, not a refactor.

## Status and next step

Folded 2026-09-19: the nine identical wrappers, the three guard wrappers' fetch line, and
the five `enrich()` default getters, which express exactly as
`get_text(u, fetcher=fetch, tries=2, backoff=3, timeout=20)`. Nineteen now-unused `UA`
constants came out with them. No adapter test changed and the suite stayed green, which is
what "accidental" means here.

**Next step: none scheduled.** The two unsettled headers are already deferred, and the
record is the Deferred entry in [IDEAS.md](../../IDEAS.md): each has an obvious story,
neither has a probe showing the host's response varies on it, and settling that is a read
per host rather than a refactor. Left as an open "next step" here it reads as work waiting
to be picked up, which is how a triage pass re-opens a decision that was already made.
