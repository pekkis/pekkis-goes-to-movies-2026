"""Per-screening prices from the public ticket page a showtime already links to.

A listing rarely carries a price; the page a visitor lands on when tapping the showtime
usually does, as a table of ticket categories. This module is the shared side step:
after an adapter has built its rows, `enrich()` reads at most FETCH_MAX of those pages a
run, one GET each, sequential and `sleep` apart, and puts the price the adapter's parser
returns on every row that links to that page. Nothing here can fail a schedule: a page
that cannot be read leaves the price "" and the showtime is published without it.

The cache at data/prices-{provider}.json maps a screening key (the URL's last path
segment) to {"price", "at"}, plus "fields" for an adapter that reads more than the price
off the same page (Riviera's language, 2026-09-23). It is pruned to the keys on the listing, so it cannot grow
past the programme, and rewritten only when it changed. A key is read again after TTL_H,
so a price change reaches the site within that time and a screening is otherwise read
once for its life on the listing. Never-read keys go first, then the oldest. Three
consecutive failures end the pass for the run; a failed page is not cached, so it is
retried next run, while a page with no usable price is cached as "" and waits the TTL.

Parsers are the adapters' own (`riviera.ordinary_price`, `regina.ordinary_price`,
`vista.ordinary_price`): each names the ordinary ticket category explicitly, so a
wheelchair, concession or member ticket listed first never becomes the advertised price,
and no row or two rows with different amounts is "" -- unknown, never zero.
"""
import datetime
import json
import os
import pathlib
import time

from common import UA, fetch, write_json

TTL_H = float(os.environ.get("KINO_PRICE_TTL_H") or 48)
FETCH_MAX = int(os.environ.get("KINO_PRICE_MAX") or 40)
FAIL_STOP = 3
OUT = pathlib.Path("data")


def _out():
    """Where the caches live: run.py's OUT when the runner is loaded (tests point it at a
    temporary tree), else data/ under the working directory."""
    try:
        import run
        return pathlib.Path(run.OUT)
    except Exception:                              # noqa: BLE001 -- run.py is optional here
        return OUT


def fmt(amount):
    """"20,00" -> "20€", "12,50" -> "12.5€": eTiketti's shape, which the client's
    priceLabel() and the pages' price_label() already render. -> "" for zero or junk."""
    try:
        v = float(str(amount).replace(",", ".").strip())
    except ValueError:
        return ""
    if v <= 0:
        return ""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s + "€"


def one_amount(amounts):
    """The price when the ordinary rows agree -> fmt() of it, else ""."""
    norm = {str(a).replace(",", ".").strip() for a in amounts}
    return fmt(norm.pop()) if len(norm) == 1 else ""


def _age_h(entry, now):
    try:
        at = datetime.datetime.fromisoformat(entry["at"])
    except (KeyError, TypeError, ValueError):
        return float("inf")
    return (now - at).total_seconds() / 3600


def key_of(url, prefix):
    """The screening key of a ticket URL under `prefix` -> str, or "" when not one."""
    if not (prefix and url and url.startswith(prefix)):
        return ""
    tail = url[len(prefix):].split("?")[0].split("#")[0].strip("/")
    return tail.rsplit("/", 1)[-1] if tail else ""


def enrich(shows, *, provider, prefix, parse, referer="", path=None, now=None,
           sleep=1.0, limit=None, headers=None, fetch_fn=None, fields=None, label=None):
    """Put each screening's price on its rows. -> counts dict.

    `prefix` is the ticket-page URL prefix a row's `url` must carry to be asked;
    `parse(page_html)` -> "20€" or "". `headers` replaces the default GET headers.
    `fields(page_html)` -> {"lang": "EN-A, FI-S"} reads more facts off the same page, so
    a page already read for the price needs no second request. The answer is cached
    beside the price and put on
    rows that carry no value of their own. An entry cached before `fields` existed is due
    once more, never-read keys still first; until it is re-read it keeps its price. A
    `fields` that raises records nothing and leaves the price alone. `label` names the
    pages in the log for a caller reading something other than ticket pages ("film pages").
    `fetch_fn(url, headers)` -> bytes or str does the GET; an adapter passes one built on
    its own module-level getter, so a test that fakes that getter keeps the price pages
    offline too. The default is common.fetch with two tries and a 20 s timeout.
    """
    path = pathlib.Path(path or (_out() / f"prices-{provider}.json"))
    limit = FETCH_MAX if limit is None else limit
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    try:
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(old, dict):
            old = {}
    except (OSError, ValueError):
        old = {}

    by_key = {}
    for s in shows:
        k = key_of(s.get("url") or "", prefix)
        if k:
            by_key.setdefault(k, []).append(s)
    cache = {k: v for k, v in old.items() if k in by_key and isinstance(v, dict)}

    def lacks(k):
        return fields is not None and "fields" not in cache[k]

    due = [k for k in by_key
           if k not in cache or _age_h(cache[k], now) >= TTL_H or lacks(k)]
    due.sort(key=lambda k: (k in cache, k in cache and not lacks(k),
                            cache.get(k, {}).get("at", ""), k))
    todo, deferred = due[:limit], max(0, len(due) - limit)
    page_word = f"{label[:-1]}" if label else "price page"      # "film pages" -> "film page"
    if deferred:
        head = f"{label}: {len(due)}" if label else f"prices: {len(due)} ticket pages"
        print(f"[{provider}] {head} due, reading {limit}, {deferred} wait for the next run")

    hdrs = headers or {"user-agent": UA, "accept": "text/html"}
    if referer and "referer" not in hdrs:
        hdrs = dict(hdrs, referer=referer)
    fetched = failed = streak = 0
    for n, k in enumerate(todo):
        if streak >= FAIL_STOP:
            deferred += 1
            continue
        if n:
            time.sleep(sleep)
        url = by_key[k][0]["url"]
        try:
            page = (fetch_fn(url, hdrs) if fetch_fn
                    else fetch(url, headers=hdrs, tries=2, timeout=20))
            if isinstance(page, bytes):
                page = page.decode("utf-8", "replace")
        except Exception as e:                     # noqa: BLE001 -- the price is optional
            failed += 1
            streak += 1
            print(f"[{provider}] {page_word} {k}: {type(e).__name__}: {str(e)[:80]}")
            continue
        streak = 0
        fetched += 1
        entry = {"price": parse(page) or "", "at": now.isoformat()}
        if fields is not None:
            try:
                got = fields(page) or {}
            except Exception as e:                 # noqa: BLE001 -- the fields are optional
                got = {}
                print(f"[{provider}] page fields {k}: {type(e).__name__}: {str(e)[:80]}")
            entry["fields"] = {f: v for f, v in got.items() if isinstance(v, str) and v}
        cache[k] = entry

    for k, group in by_key.items():
        entry = cache.get(k) or {}
        price = entry.get("price") or ""
        extra = entry.get("fields") or {}
        for s in group:
            s["price"] = price
            for f, v in extra.items():
                if not s.get(f):
                    s[f] = v

    if cache != old:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, dict(sorted(cache.items())), indent=1)
    st = {"screenings": len(by_key),
          "priced": sum(1 for k in by_key if (cache.get(k) or {}).get("price")),
          "fetched": fetched, "reused": len(by_key) - len(due),
          "unknown": sum(1 for k in by_key if k in cache and not cache[k].get("price")),
          "failed": failed, "deferred": deferred}
    if fields is not None:
        st["with_fields"] = sum(1 for k in by_key if (cache.get(k) or {}).get("fields"))
    return st


def report(provider, st):
    """The one log line a run leaves about prices."""
    more = (f", {st['with_fields']} with page fields" if "with_fields" in st else "")
    print(f"[{provider}] prices: {st['screenings']} screenings, {st['priced']} priced, "
          f"{st['fetched']} pages read, {st['reused']} reused, {st['unknown']} without an "
          f"ordinary ticket, {st['failed']} failed, {st['deferred']} deferred{more}")


def run(shows, **kw):
    """enrich() that cannot raise: a failure logs and leaves the prices as they were."""
    provider = kw.get("provider", "?")
    try:
        report(provider, enrich(shows, **kw))
    except Exception as e:                         # noqa: BLE001 -- the price is optional
        print(f"[{provider}] prices skipped: {type(e).__name__}: {str(e)[:80]}")
