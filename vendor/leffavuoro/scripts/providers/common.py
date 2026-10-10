"""Shared HTTP fetch with retry for provider adapters.

Named common, not http: run.py and fetch_data.py put this directory first on sys.path,
and a local http.py would shadow the stdlib package urllib.request imports.

tries=3 with backoff*n sleeps: one transient 502 or connection reset no longer counts as
a site failure, and the worst case is 3*backoff seconds of extra wait per request.
"""
import contextlib
import datetime
import html as html_mod
import email.utils
import hashlib
import json
import os
import pathlib
import re
import threading
import time
import typing
import urllib.error
import urllib.parse
import urllib.request

# Identifies the reader. Every adapter used to send a Chrome string, which is an
# automated pipeline claiming to be a person at a keyboard -- the one thing in here a
# cinema had no way to check for itself. Probed against all eleven providers on
# 2026-08-30 before changing it: every one answers this byte-for-byte identically to the
# Chrome string, so honesty costs nothing. If a provider ever refuses it, record the
# reading in docs/research/ticketing-platforms.md and keep the browser string for that one
# host deliberately, rather than quietly re-disguising the whole pipeline.
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

# Validator cache for conditional GETs. Deliberately outside the repo tree and
# gitignored: it holds verbatim copies of third parties' pages, and committing those
# is the rule that probe/ already exists to enforce -- one such dump put someone
# else's API key in this repo. On Actions the directory is restored by actions/cache
# between runs; locally it simply survives, since the wrapper's `git reset --hard`
# does not touch untracked files.
CACHE_DIR = pathlib.Path(os.environ.get("KINO_HTTP_CACHE")
                         or pathlib.Path(__file__).resolve().parents[2] / ".http-cache")
_stats = {"hit": 0, "miss": 0, "stored": 0, "nostore": 0}

# run.py fetches independent hosts in parallel, so every counter in this module is now
# read-modify-written from several threads, and these counters are what the committed
# run-*.log offers as evidence for how the pipeline fetched. A wrong number there is
# worse than a slow run, so the arithmetic is made correct by construction rather than
# left to the interpreter.
#
# Measured rather than assumed: on CPython 3.14 with the GIL the lock changes nothing
# observable. `_stats["miss"] += 1` compiles to a subscript, an
# add and a store, and the eval loop does not offer to switch threads inside that stretch
# -- eight threads and 1.6 million increments lose exactly zero. The same is true of the
# Retry-After decision, whose read of `waited` and charge against it are separated by no
# call and no jump. So this is not a fix for an observed miscount.
#
# It is here because that behaviour is an implementation accident, not a language
# guarantee, and it is not true of a free-threaded build -- which 3.14 ships and which
# nothing in this repo pins against. The lock also lets the Retry-After ceiling be a
# decision rather than three separate reads: see fetch(). `_diag_seen` shares it so that
# its check-then-add cannot print one host's refusal twice.
_lock = threading.Lock()


# Per-module accounting, for a process that reads several modules at once.
#
# Until `run_cloud.py` the cloud half ran one process per module, so both of these were per
# module by construction: `run-{module}.log` reported only that module's requests, and the
# Retry-After budget below bounded that module alone. Putting every cloud module in one
# process would combine them silently -- a module's committed log would carry requests
# another module made, and one host throttling biorex would spend the patience etiketti has
# left. Neither is a change anyone decided on, so a fetch runs inside a *scope* and is
# charged to it as well as to the process.
#
# Thread-local, because a worker fetches one site at a time and each pool thread carries its
# own. No scope is the single-module path, where the process totals already are the module's
# and nothing here changes.
_scopes = threading.local()
_scope_stats = {}
_scope_throttle = {}
# Every host a scope issued a request to. The grouping in run.py serialises the hosts a site
# *declares*; this is what it turned out to aim at, and a module's committed log carries it,
# so a shared upstream shows up in the record instead of being assumed away. Aimed at rather
# than reached: the entry is made before the response, so it says nothing about the server
# having answered.
_scope_hosts = {}
_hosts_all = set()


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

# Three response headers `served()` reports beside the size and the title, recorded per
# thread by `fetch` as each response arrives. Names only, and these three: `Server` says
# which stack answered, `CF-Ray` says a particular front door did, and `Retry-After` says
# the refusal is timed rather than permanent. That is the evidence
# docs/research/runner-challenges.md had to infer from a byte count and a title, where
# three of the fourteen failing hosts were evidenced by a 403 with a `Server` header and
# two by nothing at all. No body is kept, here or anywhere: a third party's page is not
# committed to this repository.
_REPORTED_HEADERS = ("Server", "CF-Ray", "Retry-After")
_seen = threading.local()


def _note_headers(headers):
    """Remember the reported headers of the response this thread just had."""
    got = {}
    for name in _REPORTED_HEADERS:
        v = headers.get(name) if headers is not None else None
        if v:
            got[name] = " ".join(str(v).split())[:60]
    _seen.headers = got


def _header_note():
    """-> ", Server: x, CF-Ray: y" for what the last response carried, or ""."""
    got = getattr(_seen, "headers", None) or {}
    return "".join(f", {k}: {v}" for k, v in got.items())


def served(page, limit=70):
    """What the reader was actually handed, for a guard that could not parse it. -> str.

    **A missing marker says the marker is missing and nothing else.** A guard that reports
    "the template changed" has named one of at least three causes: the site changed its
    markup, or the reader was handed a challenge, an error page or a holding page instead
    of the programme. On 2026-09-16 four modules over seven independent domains failed
    within one run and every one of those sites served its real page, marker included, to
    an ordinary connection minutes later -- so the reading side was the cause and not one
    log said so, because none of them recorded what arrived.

    Two facts separate the cases and neither is a raw dump, which this repo never keeps: the
    size of what came back and what the document calls itself. A cinema's programme is tens
    of kilobytes and titled after the cinema; a challenge is a couple of kilobytes and
    titled "Just a moment...". The title is a third party's text, so it is unescaped,
    collapsed to one line and cut to `limit` before it goes anywhere near a committed log.

    **And three response headers, from 2026-09-19**: `Server`, `CF-Ray` and `Retry-After`,
    whichever of them the last response to this thread carried. They are the difference
    between "something refused us" and a named refusal: `Server` says which stack answered,
    `CF-Ray` says a particular front door did, and `Retry-After` says the refusal is timed
    rather than permanent. The nine-host challenge in docs/research/runner-challenges.md
    had to infer all of that from a byte count and a title, and two of its fourteen hosts
    were evidenced by nothing at all. Values are printed as served, truncated, and no body
    is kept.
    """
    page = page or ""
    note = _header_note()
    m = _TITLE_RE.search(page)
    if not m:
        return f"{len(page)} B served, no <title>{note}"
    title = html_mod.unescape(m.group(1))
    title = " ".join(title.split())[:limit]
    return (f'{len(page)} B served, titled "{title}"{note}' if title
            else f"{len(page)} B served{note}")


def _scope():
    return getattr(_scopes, "name", None)


def _box(counter):
    """The current scope's copy of `counter`, or None outside a scope.

    Identified by object, not by name: `_stats` and `_throttle` are module singletons that
    nothing rebinds, and the alternative is a second argument at every call site.
    """
    return (_scope_stats if counter is _stats else _scope_throttle).get(_scope())


@contextlib.contextmanager
def accounting(name):
    """Charge this thread's requests to `name` as well as to the process. -> context.

    Nests: a scope is restored, not cleared, so a caller inside another caller's scope
    leaves it as it found it.
    """
    with _lock:
        _scope_stats.setdefault(name, {"hit": 0, "miss": 0, "stored": 0, "nostore": 0})
        _scope_throttle.setdefault(name, {"asked": 0, "waited": 0.0, "refused": 0})
        _scope_hosts.setdefault(name, set())
    prev = _scope()
    _scopes.name = name
    try:
        yield
    finally:
        _scopes.name = prev


def reset_accounting():
    """Forget every scope. For a caller that runs more than one run in one process."""
    with _lock:
        _scope_stats.clear()
        _scope_throttle.clear()
        _scope_hosts.clear()
        _hosts_all.clear()
        _host_refused.clear()
        _diag_seen.clear()
    with _host_cv:
        _host_owner.clear()
        _host_cv.notify_all()


def hosts_attempted(scope=None):
    """Every host a request was issued to, by this scope or by the process. -> {netloc}.

    Attempted and not reached: a host lands here once its claim is held and the request is
    about to go out, so it counts a DNS failure, a refused connection and a 403 alike. What
    it is evidence of is which hosts a module's fetches were aimed at, which is what the
    declarations in `base` and `reads` are checked against.
    """
    with _lock:
        return set(_hosts_all if scope is None else (_scope_hosts.get(scope) or ()))


# One site at a time per host, whatever URL led there.
#
# `run.host_groups` serialises the hosts a site **declares** -- its `base` and any `reads`.
# It cannot cover a URL read out of a page, and four adapters fetch one: BioRex's film pages
# come from an href in an ajax fragment, Cinemahouse's from a tile link, Tapiola's and
# Kinola's from their listings, and none of the four is checked against a host anywhere.
# Read as a visitor on 2026-09-15 they all name the site's own host -- 197, 21/18/13, 27 and
# 57/47 hrefs, every one of them -- but that is a third party's markup answering today, not
# a property of this code. It mattered less while each module was its own process, because
# only sites of one module could overlap; the coordinator overlaps every module.
#
# So a fetch claims the host it is about to read, for as long as that site keeps reading it,
# and a second site waits. Past HOST_CLAIM_WAIT it **fails, before the request is sent**.
#
# Going ahead anyway was the first answer here and it was wrong: it dropped the guarantee at
# exactly the moment it was needed, when the other site is slow, and a log line does not
# make two concurrent requests at one cinema's server acceptable. Failing is also what the
# rest of this pipeline does with a site it cannot read properly -- `run.py` keeps the
# previous files, the health line ages, the log names the site, and everything else in the
# run still publishes -- so there is nothing new to reason about.
#
# It does not deadlock. Two adapters holding each other's hosts wait at most one ceiling:
# whichever gives up first releases what it held on the way out, which usually lets the
# other claim what it was waiting for and finish. So one site fails, not necessarily both,
# and both fail only if they time out together. Bounded either way, unlike waiting forever,
# and visible, unlike going ahead.
HOST_CLAIM_WAIT = float(os.environ.get("KINO_HOST_CLAIM_WAIT") or 60)
_host_cv = threading.Condition()
_host_owner = {}
_host_refused = {}          # label -> the message of the claim it gave up on


class HostBusy(RuntimeError):
    """Another site was still reading this host when the claim gave up.

    Raised before the request, so nothing is sent. The site fails, keeps its previous data
    and says which two sites collided; the remedy is to name the host in one of their
    `reads`, which moves the serialisation into the grouping where it costs nothing.
    """


@contextlib.contextmanager
def reading(label):
    """Claim hosts for one site's fetch, and release them all when it ends. -> context.

    `label` is the site's provider id, which is unique. Anything fetched outside one of
    these -- `enrich_tmdb`, `mirror_posters`, an adapter run by hand -- claims nothing and
    waits for nothing, so this changes only a run that reads sites concurrently.
    """
    prev = getattr(_scopes, "owner", None)
    _scopes.owner = label
    with _lock:
        _host_refused.pop(label, None)

    def release():
        _scopes.owner = prev
        with _host_cv:
            for h in [h for h, o in _host_owner.items() if o == label]:
                del _host_owner[h]
            _host_cv.notify_all()
        with _lock:
            return _host_refused.pop(label, None)
    # An adapter that catches broadly around its own fetches would otherwise turn a refused
    # claim into a partial publish: some pages read, one skipped, no error. The refusal is
    # recorded when it is raised and re-raised here if the body swallowed it, so the site
    # fails whatever the adapter did with the exception. That includes raising another one
    # afterwards: an EmptyProgramme from a listing the refusal left unread would otherwise
    # publish every venue empty (2026-09-25). An interrupt or an exit still goes through.
    try:
        yield
    except Exception as e:
        refused = release()
        if refused and not isinstance(e, HostBusy):
            raise HostBusy(refused) from e
        raise
    except BaseException:
        release()
        raise
    refused = release()
    if refused:
        raise HostBusy(refused)


def _claim(url):
    """Hold `url`'s host for this site until its fetch ends. -> the host, or "".

    Raises HostBusy, before anything is sent, when another site still holds it after
    HOST_CLAIM_WAIT. The host is recorded only once the claim is held, so a host a site was
    refused never appears in the log as one it read from.
    """
    host = urllib.parse.urlsplit(url).netloc
    owner = getattr(_scopes, "owner", None)
    if host and owner is not None:
        with _host_cv:
            held = _host_owner.get(host)
            if held is not None and held != owner:
                if not _host_cv.wait_for(
                        lambda: _host_owner.get(host, owner) == owner, HOST_CLAIM_WAIT):
                    # Says what happened, which is that nothing was sent: the two sites
                    # wanted this host at the same time and this one was refused it. An
                    # earlier draft read "is read by X and Y at once", which described the
                    # overlap the refusal exists to prevent.
                    why = (f"{host} refused to {owner}: {held} was still reading it after "
                           f"{HOST_CLAIM_WAIT:.0f}s, so no request was sent. Name it in "
                           f"one of their `reads` so the two sites are read one after the "
                           f"other instead of racing for it")
                    with _lock:
                        _host_refused[owner] = why
                    raise HostBusy(why)
            _host_owner[host] = owner
    if host:
        with _lock:
            _hosts_all.add(host)
            box = _scope_hosts.get(_scope())
            if box is not None:
                box.add(host)
    return host


def _bump(counter, key, by=1):
    with _lock:
        counter[key] += by
        box = _box(counter)
        if box is not None:
            box[key] += by


# A 429 or 503 with Retry-After is the only case where an upstream states its own
# terms, and the retry loop below used to ignore them: a provider asking for 60
# seconds got three more requests inside 15, on our schedule rather than its own.
# Kinoset has answered 403 under load before, so this is not hypothetical.
#
# Both ceilings exist because "sleep for as long as you are told" hands a stranger
# the ability to stall the pipeline. RETRY_AFTER_MAX bounds one wait,
# RETRY_AFTER_BUDGET bounds the whole process, so a host that 429s every request
# cannot turn one run into an all-day one. Past either, the request fails instead of
# waiting: the next run is four hours away, run.py keeps the previous file, and the
# health line ages honestly -- which is a better answer than more requests at a host
# that just said no.
RETRY_AFTER_MAX = int(os.environ.get("KINO_RETRY_AFTER_MAX") or 120)
RETRY_AFTER_BUDGET = int(os.environ.get("KINO_RETRY_AFTER_BUDGET") or 300)
_throttle = {"asked": 0, "waited": 0.0, "refused": 0}

# Every response body is read in bounded chunks, never with a bare read(): these are
# third parties, and a broken or compromised origin answering with gigabytes would
# otherwise sit in memory in full before any parser or Pillow ever saw it. Not a
# measured figure the way PAGE_BUDGET is -- the sizes that would need measuring are the
# upstreams' to change -- but the largest body this pipeline legitimately reads is a
# poster source image at a few MB, so 20 MB is generous headroom, not a boundary any
# real response has approached. A Content-Length past the cap is refused before the
# body is read; the chunked loop below enforces the cap whether or not the header was
# sent, since the header is only the origin's claim.
MAX_BODY = int(os.environ.get("KINO_MAX_BODY") or 20_000_000)


class Show(typing.TypedDict):
    """One screening as every adapter publishes it and as run.py, synmerge and the client
    read it. Plain dicts stay the runtime shape; this is the written contract, and
    `SHOW_KEYS` is what tests/test_show_contract.py holds each adapter to.

    Every key is required and a value the adapter cannot fill is "" (or False). Measured
    2026-09-14 across the twelve adapters: eleven emitted all seventeen and BioRex emitted
    no `price`, which the client tolerated only because priceLabel reads `r.price || ''`.
    Every frontend bug on the day multi-provider landed came from a field only Finnkino
    populated, so a key present with an empty value is the rule and a missing key is not.
    An adapter may add keys of its own (`_syn`, `age`, `movieUrl`); a TypedDict does not
    validate at runtime, so the test is the check, not this class.
    """
    eventId: str        # the provider's film id, scoped to its site; the film key in films.json
    title: str          # verbatim, the key for normTitle(), films-extra.json, tmdb-aliases.json
    original: str
    len: str
    rating: str
    genres: str
    method: str         # strand, format or language tag shown on the stub
    theatre: str
    aud: str            # room, verbatim: it is what the ticket prints
    start: str          # ISO 8601 with offset, Europe/Helsinki
    url: str            # absolute http(s); the client runs it through safeUrl()
    img: str
    lang: str
    soldOut: bool
    # A price is published only where its applicability to *this screening* is
    # established. A tariff that depends on something the adapter cannot read -- 2D against
    # 3D with no marker on the row, a weekday public holiday with no calendar to check --
    # settles no amount for that screening, and the field stays empty. A note in a docstring
    # saying the figure is sometimes 0.50 or 2.50 out does not make the figure right, and it
    # is not the reader who reads the docstring. Stated by the maintainer 2026-09-16, after
    # TMB and Iso-Hannu shipped amounts that were nearly right; the record is in
    # docs/archive/2026-09-providers.md.
    price: str          # "8€", "alkaen 10€", "Vapaa pääsy", or ""
    provider: str       # registry id
    venue: str          # a venue id the site's registry entry lists


SHOW_KEYS = tuple(Show.__annotations__)


def has_future_shows(path, today_iso):
    """Does the committed area file still describe a day that has not passed?

    Shared by fetch_data.py (Finnkino) and run.py (every other provider): a kept file
    whose last day is behind us protects nothing and freezes its venue's `generated`.

    The question is whether keeping it protects anything. `dates` lists the days the file
    holds screenings for, so the last of them is the file's own horizon; `horizon` carries
    the same value and is read as a fallback for a file written before `dates` existed.
    Today counts as ahead, because a day is not over while it is running.

    An unreadable file answers True. It cannot be shown to be spent, and replacing what
    could not be read would turn a disk fault into deleted schedule data.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(doc, dict):
        return True
    dates = doc.get("dates")
    if isinstance(dates, list) and dates:
        return max(str(d) for d in dates) >= today_iso
    horizon = doc.get("horizon")
    if isinstance(horizon, str) and horizon:
        return horizon >= today_iso
    return False


def check_shows(per_venue, label, venue_ids=()):
    """Refuse an adapter's result that does not meet `Show`. -> None, or raises RuntimeError.

    run.py calls this on what fetch_site returned, before anything is written, so a show
    missing a key or carrying the wrong type fails its site the way a parse error does:
    the previous files stay, the health line ages, and the log names the venue and the
    key. A TypedDict checks nothing at runtime; this is the check. Keys beyond the
    contract are allowed: adapters carry `_syn` for synmerge and `age`, `movieUrl` and
    `year` as documented extras, and the enrichment pass adds its own later.

    `venue_ids` is the site's venue list when the caller has one: a show filed under a
    venue the site does not list would be written to a file the picker never links.
    """
    for vid, shows in per_venue.items():
        if venue_ids and vid not in venue_ids:
            raise RuntimeError(f"{label}: shows for venue {vid!r}, which the site does not list")
        for s in shows:
            for k, t in Show.__annotations__.items():
                if k not in s:
                    raise RuntimeError(f"{label}: venue {vid}: a show has no {k!r} "
                                       f"(title {s.get('title')!r})")
                if not isinstance(s[k], t):
                    raise RuntimeError(f"{label}: venue {vid}: {k!r} is "
                                       f"{type(s[k]).__name__}, not {t.__name__} "
                                       f"(title {s.get('title')!r})")
            if not s["start"] or not s["venue"] or s["venue"] != vid:
                raise RuntimeError(f"{label}: venue {vid}: a show with start {s['start']!r} "
                                   f"filed under venue {s['venue']!r} (title {s['title']!r})")
            # The two values the contract states a form for. A start with no offset is read
            # in the viewer's zone by the client, and a url that is not http(s) is one
            # safeUrl() has to catch downstream (audit C6). "" stays allowed for url: it
            # is the contract's empty value.
            try:
                offset = datetime.datetime.fromisoformat(s["start"]).utcoffset()
            except ValueError:
                offset = None
            if offset is None:
                raise RuntimeError(f"{label}: venue {vid}: start {s['start']!r} is not ISO "
                                   f"8601 with an offset (title {s['title']!r})")
            if s["url"]:
                u = urllib.parse.urlsplit(s["url"])
                if u.scheme not in ("http", "https") or not u.netloc:
                    raise RuntimeError(f"{label}: venue {vid}: url {s['url']!r} is not an "
                                       f"absolute http(s) URL (title {s['title']!r})")


class EmptyProgramme(Exception):
    """An adapter reached a site, read its listing, and there were no films on it.

    A whole site parsing zero showtimes fails the run, and that has to stay true: it is
    the only thing that catches a parse which broke silently and would otherwise leave
    old data ageing with no signal. But some cinemas genuinely publish nothing for a
    week. Eight sites here are a single small venue -- K-Kino runs 3 showtimes, Kino
    Saimaa 2 -- so "empty" stopped being hypothetical the day the eTiketti sweep landed.

    The distinction an adapter can make, and run.py cannot, is *what the listing said*.
    Raise this only on **positive evidence that the upstream said it has nothing on** --
    an empty-state element the template renders in place of its films, a payload that
    answered in the expected schema with an empty collection. A listing that still lists
    films while the parse yields no showtimes is the broken case and must keep failing,
    and an unreachable listing raises its own error long before this.

    **"My parser found nothing" is not that evidence**, and reading it as such is the
    trap this class creates. Zero matches proves only that one regex or one key lookup
    came back empty, which is exactly what a markup or schema change upstream produces --
    while the page is still full of films. Inferring emptiness from it converts a parser
    regression into a soft ageing signal: exit 0, stale data preserved, nothing red, and
    the first symptom hours later on the health line. Every adapter raising this must
    therefore check something it did *not* use to find the films.

    Nothing is muted by configuration on purpose: a per-site "allow empty" flag would
    switch the check off permanently for the one site most likely to need it, which is
    the hole this is meant to avoid rather than open.
    """


def cache_stats(scope=None):
    """-> (304s, full bodies, entries written). Reset per run by the caller.

    With `scope`, only what was fetched inside `accounting(scope)` -- which is what a
    module's committed log has to report when one process read several modules.
    """
    with _lock:
        return dict(_scope_stats.get(scope) or {"hit": 0, "miss": 0, "stored": 0,
                                                "nostore": 0}
                    if scope is not None else _stats)


def throttle_stats(scope=None):
    """-> how often an upstream asked us to slow down, and what that cost.

    `asked` counts Retry-After responses, `waited` the seconds sat out,
    `refused` the ones whose ask was past a ceiling and so were not retried at all.
    All zero on a normal run, which is why run.py prints the line only when it is not.

    With `scope`, that module's share. The budget below is charged against the same figure,
    so a module's log reports the budget it actually spent.
    """
    with _lock:
        return dict(_scope_throttle.get(scope) or {"asked": 0, "waited": 0.0,
                                                   "refused": 0}
                    if scope is not None else _throttle)


def _retry_after(value):
    """Seconds to wait, from a Retry-After header. -> float, or None if unusable.

    RFC 9110 allows delta-seconds or an HTTP-date and both appear in the wild. A date
    already in the past means "now", not a negative sleep. None means the header was
    absent or unparseable, which leaves the caller on its own fixed backoff -- a
    malformed header is not a reason to give a provider three fast retries.
    """
    if not value:
        return None
    v = value.strip()
    if v.isdigit():
        return float(v)
    try:
        when = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (when - datetime.datetime.now(datetime.timezone.utc)).total_seconds())


# Which layer refused, on the way out of a request that is being given up on. A 403 in
# a committed log read `HTTP Error 403: Forbidden` and nothing else, which is the same
# line whether an edge blocked the address or the origin was throttling -- and those two
# want opposite responses. The block is gone by the time anyone reads the log: Kinoset
# refused all three venues at 08:31 UTC on 2026-08-30 and served them again at 09:14, so
# the run is the only witness there will ever be.
#
# `Server: cloudflare` with a CF-Ray is a decision at the edge. That does not clear by
# waiting, and the answer is to move the endpoint to the local half the way Finnkino
# already is. An origin server with neither is the application rate-limiting, which is
# what Kinoset has done before and which clears on its own -- leave it to the next cron.
#
# **Headers only, never the body.** `run-*.log` is committed to a public repo and a third
# party's error page carries whatever they ship to visitors; that is the raw-dump rule,
# and one such dump already put someone else's API key in here. These three are short,
# fixed, and about the refusal rather than about their stack.
DIAG_HEADERS = ("Server", "CF-Ray", "Retry-After")
_diag_seen = set()


def _server_hint(e):
    """-> 'Server: cloudflare; CF-Ray: ...', or '' if the response said none of them."""
    hh = getattr(e, "headers", None)
    if hh is None:
        return ""
    return "; ".join(f"{k}: {(hh.get(k) or '').strip()[:80]}"
                     for k in DIAG_HEADERS if (hh.get(k) or "").strip())


def _log_refusal(e, url, attempts):
    """Name the refusing layer once, the first time this host refuses this way.

    Deduplicated because `mirror_posters` calls fetch once per poster and has had 185
    failures against one host in a single run; a line each would bury the run's own
    summary, which is the thing that made that run unreadable in the first place. The
    ray id is unique per request by design, so it cannot be part of the key -- presence
    is what identifies the layer, and the line carries the first value seen.
    """
    hint = _server_hint(e)
    if not hint:
        return
    host = urllib.parse.urlsplit(url).netloc
    # Scoped, so one host refusing two modules names itself in both their logs. Without
    # it the second module's log is silent about a refusal it suffered, because the line
    # was printed into the first module's.
    key = (_scope(), host, e.code, (e.headers.get("Server") or "").strip(),
           bool((e.headers.get("CF-Ray") or "").strip()))
    with _lock:
        if key in _diag_seen:
            return
        _diag_seen.add(key)
    print(f"[http] {e.code} from {host}, gave up after {attempts} attempt(s) -- {hint}")


def _slot(url):
    return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".bin")


def _read_slot(path):
    try:
        raw = path.read_bytes()
        head, body = raw.split(b"\n\n", 1)
        return json.loads(head.decode()), body
    except Exception:
        return None, None


class BodyTooLarge(Exception):
    """A response body passed the max_bytes cap. Deterministic, so never retried:
    asking again downloads the same oversize answer at both ends' expense."""


class SiteDeadline(RuntimeError):
    """One site's fetch ran past its wall-clock deadline. Raised by `fetch` before a request
    or a retry sleep that would start past it, and between the chunks of a body that is
    still arriving, so a host that stops answering or drips its response ends one site
    rather than the run. Re-raised when the site's fetch ends if the adapter caught it."""


@contextlib.contextmanager
def site_deadline(seconds):
    """Bound one site's fetch to `seconds` of wall clock. -> context. None or 0: no bound.

    `timeout` bounds each socket operation only, and an adapter's page loop catches and
    goes on, so a host that stalls after its listing cost one site 105 s per film page and
    could hold a cloud run past the job's 30-minute cap, where the commit step never ran
    (audit C1, 2026-09-25). Inside this, every request's socket timeout is also capped at
    what is left. Per thread, like `reading`.
    """
    prev = (getattr(_scopes, "deadline", None), getattr(_scopes, "deadline_hit", None))
    _scopes.deadline = time.monotonic() + seconds if seconds else None
    _scopes.deadline_hit = None
    try:
        yield
    except Exception as e:
        hit = _scopes.deadline_hit
        _scopes.deadline, _scopes.deadline_hit = prev
        if hit and not isinstance(e, SiteDeadline):
            raise SiteDeadline(hit) from e
        raise
    except BaseException:
        _scopes.deadline, _scopes.deadline_hit = prev
        raise
    hit = _scopes.deadline_hit
    _scopes.deadline, _scopes.deadline_hit = prev
    if hit:
        raise SiteDeadline(hit)


def _deadline_left():
    """Seconds left on this thread's site deadline, or None when there is none."""
    d = getattr(_scopes, "deadline", None)
    return None if d is None else d - time.monotonic()


def _pause(secs, url):
    """A retry's backoff, unless it would end past the site's deadline: then the site
    stops here rather than sleeping into a request it may not send."""
    left = _deadline_left()
    if left is not None and secs >= left:
        _deadline_passed(url, "retry")
    time.sleep(secs)


def _deadline_passed(url, doing):
    """Record and raise that the deadline is past. -> never returns."""
    msg = (f"{url}: the site's {doing} would run past its fetch deadline; nothing more is "
           f"read and the site keeps its previous files")
    if getattr(_scopes, "deadline_hit", None) is None:
        _scopes.deadline_hit = msg
    raise SiteDeadline(msg)


class DowngradeRefused(RuntimeError):
    """A redirect from https to http, refused before it is followed. Never retried: the
    same request gets the same redirect. CLAUDE.md: never follow an `https:` -> `http:`
    redirect; a cleartext `base` is only for a host that serves no TLS at all."""


class NoDowngradeRedirect(urllib.request.HTTPRedirectHandler):
    """urllib's redirect handling, less the downgrade. Everything else is followed as
    before, an upgrade and a plain-HTTP host's own redirects included."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (req.full_url.lower().startswith("https:")
                and newurl.lower().startswith("http:")):
            fp.close()
            raise DowngradeRefused(f"{req.full_url}: refused a {code} redirect from https "
                                   f"to http ({newurl}); the programme is not read over "
                                   f"cleartext")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener(*handlers):
    """An opener that refuses the downgrade, with `handlers` added: what an adapter with
    its own session (BioRex's cookie jar) builds instead of `urllib.request.build_opener`."""
    return urllib.request.build_opener(NoDowngradeRedirect, *handlers)


# What `fetch` opens with when the caller passes no opener of its own.
_OPENER = make_opener()


def _read_capped(r, url, limit):
    """Read a response body, refusing past `limit` bytes. -> bytes."""
    cl = (r.headers.get("Content-Length") or "").strip()
    if cl.isdigit() and int(cl) > limit:
        raise BodyTooLarge(f"{url}: Content-Length {cl} is past the {limit}-byte cap")
    chunks, total = [], 0
    # read1 returns what has arrived, so a body that drips is still checked against the
    # site deadline between chunks; read(n) would block until n bytes or the end.
    read = getattr(r, "read1", None) or r.read
    while True:
        chunk = read(65536)
        if not chunk:
            return b"".join(chunks)
        left = _deadline_left()
        if left is not None and left <= 0:
            _deadline_passed(url, "response body")
        total += len(chunk)
        if total > limit:
            raise BodyTooLarge(f"{url}: body passed the {limit}-byte cap "
                               f"({total}+ bytes read)")
        chunks.append(chunk)


def _write_slot(path, meta, body):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # The temp name carries the writing thread, because the slot name is a hash of
        # the URL and two threads asking the same URL at once would otherwise write the
        # same `<hash>.tmp` -- one truncating the other's bytes and both then renaming
        # the result over the slot. Unlikely across different sites and not worth
        # leaving to luck, since the loser is a corrupt cache entry that is served as a
        # cached body on the next run.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(json.dumps(meta).encode() + b"\n\n" + body)
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)     # a unique name would otherwise accumulate
            raise
        _bump(_stats, "stored")
    except Exception:
        pass          # a cache that cannot be written must never fail a run


def fetch(url, headers=None, data=None, tries=3, backoff=5, timeout=30, opener=None,
          cache=False, max_bytes=None, keep_body_on=()):
    """GET (or POST when `data` is given) with retry. -> bytes.

    `max_bytes` caps the response body, MAX_BODY by default. Past it the read stops
    and BodyTooLarge is raised without a retry.

    `opener` lets a cookie-session adapter (BioRex) retry a single request
    without redoing the whole session dance. Retries every exception on
    backoff*n the way the per-adapter get() loops already do, with one
    exception: a 429 or 503 carrying Retry-After is retried on the interval the
    upstream named, and is not retried at all when that interval is past
    RETRY_AFTER_MAX or would take the run past RETRY_AFTER_BUDGET.

    `keep_body_on` is a tuple of status codes whose body is returned instead of raised,
    and it is empty for every caller but one. An error response's body is normally thrown
    away unread, which is right: a 500 means the server says it failed, and reading on is
    how a pipeline publishes an error page as a programme. Kino Engel is the exception
    that earned it -- on 2026-09-21 its WordPress began answering 500 while serving the
    complete programme, 126 kB that parses to 25 screenings -- and `engel.py` asks for
    the body only to validate it against its size, its markers and a non-empty parse
    before using it. Nothing here relaxes the default, and a body kept this way is never
    written to the cache slot.

    `cache=True` makes it a conditional GET: a stored ETag or Last-Modified goes back
    as If-None-Match / If-Modified-Since, and a 304 returns the stored body without
    the server sending it again. A response marked no-store or no-cache is never
    written to disk, and one with no validator is not either -- there would be
    nothing to revalidate it with.

    Measured 2026-08-30, across every endpoint this pipeline reads: only Cinema
    Orion sends a validator at all, so today this saves about one request per run
    rather than the bulk of them. It is here because it is the correct way to ask,
    it costs nothing when the origin offers nothing, and a provider that starts
    sending ETags is picked up without another change.

    Never enable it on a POST -- the response is not addressed by the URL alone,
    so a slot would collide across different request bodies.

    When a request is given up on, one `[http]` line names the refusing layer from a
    fixed set of response headers -- see DIAG_HEADERS. Never the body.
    """
    if data is not None:
        cache = False
    limit = MAX_BODY if max_bytes is None else max_bytes
    # Before the first attempt and not per attempt: every retry goes to the same host, and
    # the claim is held until this site stops reading it either way.
    _claim(url)
    slot = _slot(url) if cache else None
    meta, cached_body = _read_slot(slot) if cache else (None, None)

    hdrs = dict(headers or {"user-agent": UA})
    if meta and cached_body is not None:
        if meta.get("etag"):
            hdrs["if-none-match"] = meta["etag"]
        if meta.get("last_modified"):
            hdrs["if-modified-since"] = meta["last_modified"]

    last = None
    for n in range(tries):
        left = _deadline_left()
        if left is not None and left <= 0:
            _deadline_passed(url, "next request")
        # Each socket operation is bounded by what is left of the site's deadline too.
        t = timeout if left is None else max(0.05, min(timeout, left))
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            op = opener.open if opener is not None else _OPENER.open
            with op(req, timeout=t) as r:
                _note_headers(r.headers)
                body = _read_capped(r, url, limit)
                if cache:
                    _bump(_stats, "miss")
                    cc = (r.headers.get("Cache-Control") or "").lower()
                    et = r.headers.get("ETag")
                    lm = r.headers.get("Last-Modified")
                    # Storing a body the origin marked no-store is the thing this whole
                    # change exists to avoid. eTiketti and Nexxo both send it; measured
                    # 2026-08-30. Without a validator there is nothing to revalidate
                    # with either, so the slot would only ever grow.
                    if ("no-store" in cc or "no-cache" in cc):
                        _bump(_stats, "nostore")
                    elif et or lm:
                        _write_slot(slot, {"etag": et, "last_modified": lm}, body)
                return body
        except urllib.error.HTTPError as e:
            # An HTTPError *is* the response, and it holds its socket until the garbage
            # collector gets to it -- 24 ResourceWarnings in a suite run, and on a long
            # run against a host that is refusing everything, that many sockets waiting
            # on a collection nobody scheduled. Closed here because nothing ever wants
            # the body: `code`, `reason` and `headers` all survive the close, the retry
            # logic below reads only those, and `raise last` hands the caller an
            # exception rather than a stream. close() is idempotent, so the paths that
            # re-raise this same object cost nothing.
            # Asked for by the caller, and only ever by one. Read before the close,
            # returned before the retry logic, and deliberately not cached: an error
            # response is not a representation to revalidate later.
            if e.code in keep_body_on:
                try:
                    body = _read_capped(e, url, max_bytes or MAX_BODY)
                finally:
                    e.close()
                _note_headers(getattr(e, "headers", None))
                return body
            e.close()
            if e.code == 304 and cached_body is not None:
                _bump(_stats, "hit")
                return cached_body
            last = e
            # 429 and 503 are the two codes RFC 9110 lets carry Retry-After, and both
            # mean "not now" rather than "never". Wait the stated time instead of ours.
            hh = getattr(e, "headers", None)
            _note_headers(hh)
            wait = (_retry_after(hh.get("Retry-After"))
                    if e.code in (429, 503) and hh is not None else None)
            if wait is not None:
                # Counted, checked against the budget and charged to it in one step. The
                # budget bounds the whole process, so with hosts running in parallel a
                # check that read `waited` and charged it later would let several threads
                # each pass the same remaining budget and then all sleep against it. The
                # seconds are reserved before the sleep rather than after, and only when
                # there is a retry left to sleep for -- which is what the sequential code
                # did too, since the last attempt never slept.
                sleeping = n + 1 < tries
                with _lock:
                    # Charged to the scope as well, and the ceiling is read from whichever
                    # of the two is in force: RETRY_AFTER_BUDGET bounds one module's run,
                    # which is what it bounded when each module was its own process. A
                    # coordinator reading twenty modules must not let the first one to be
                    # throttled spend the budget the other nineteen have not touched.
                    box = _scope_throttle.get(_scope())
                    _throttle["asked"] += 1
                    if box is not None:
                        box["asked"] += 1
                    spent = _throttle["waited"] if box is None else box["waited"]
                    over = wait > RETRY_AFTER_MAX or spent + wait > RETRY_AFTER_BUDGET
                    if over:
                        _throttle["refused"] += 1
                        if box is not None:
                            box["refused"] += 1
                    elif sleeping:
                        _throttle["waited"] += wait
                        if box is not None:
                            box["waited"] += wait
                if over:
                    _log_refusal(e, url, n + 1)
                    raise
            if n + 1 < tries:
                _pause(backoff * (n + 1) if wait is None else wait, url)
        except (BodyTooLarge, DowngradeRefused, SiteDeadline):
            raise
        except Exception as e:
            last = e
            if n + 1 < tries:
                _pause(backoff * (n + 1), url)
    if isinstance(last, urllib.error.HTTPError):
        _log_refusal(last, url, tries)
    raise last


# Per-site ceiling on secondary page fetches -- the film pages an adapter reads after
# the listing tells it what is showing. Those loops iterate whatever the listing
# contains, so the request count is bounded in practice by how many films a cinema is
# showing (15-31 today) and unbounded in principle: a listing that ever returned
# thousands would be fetched in full, politely paced and still thousands of requests at
# someone else's expense.
#
# 120 is roughly four times the largest real figure. Truncating costs metadata, never
# showtimes -- those come from the listing, which is one request -- so a film past the
# cap simply shows without runtime, genres or synopsis until the next run. That is the
# right way round, and it is logged loudly because a cap that trims silently would read
# as complete data.
# What a server-rendered Finnish page is asked for. Seven adapters had written this out
# identically -- hamina, kinola, kinotour, lieksa, marita, navetta and vpk -- and the copies
# were byte for byte the same, which is the only kind worth folding together. Twelve other
# wrappers differ in a header, a timeout or an accept, and each difference is deliberate for
# that host, so none of them was harmonised into this.
TEXT_HEADERS = {"user-agent": UA, "accept-language": "fi-FI,fi;q=0.9"}


def get_text(url, fetcher=None, **kw):
    """One server-rendered page, decoded. -> str.

    `cache=True`, the Finnish page headers and a 30 s timeout, all overridable through
    `kw`, and the body decoded as UTF-8 with replacement so one bad byte costs a character
    rather than the page.

    `fetcher` is the seam the adapters' tests already use. Each of them stubs its own
    module-level `fetch` to serve a fixture, so a wrapper that let this function reach
    `common.fetch` directly would turn every one of those stubs into a no-op and the tests
    would quietly start talking to the internet. The wrapper passes its own `fetch` in.
    """
    kw.setdefault("cache", True)
    kw.setdefault("headers", dict(TEXT_HEADERS))
    kw.setdefault("timeout", 30)
    return (fetcher or fetch)(url, **kw).decode("utf-8", "replace")


PAGE_BUDGET = int(os.environ.get("KINO_PAGE_BUDGET") or 120)


def capped(items, label, limit=None):
    """Trim an *enrichment* loop to the budget. -> list, logged once if it trims.

    Only for pages that add metadata to showtimes already parsed from a listing --
    BioRex's and Engel's film pages. A film past the cap shows without runtime,
    genres or synopsis until the next run, which is a fair trade for a bounded
    request count.

    Not for a loop that produces the showtimes themselves; use budget_or_raise.
    """
    items = list(items)
    limit = PAGE_BUDGET if limit is None else limit
    if len(items) > limit:
        print(f"[{label}] page budget: {len(items)} film pages wanted, fetching {limit}, "
              f"{len(items) - limit} skipped this run -- those films lose metadata only")
        return items[:limit]
    return items


def budget_or_raise(items, label, limit=None):
    """Same ceiling, for a loop whose pages carry the schedule itself. -> list.

    eTiketti puts the screenings on the film pages, so trimming that loop does not
    cost metadata, it drops showtimes -- and a venue that publishes half its day is
    worse than one that publishes nothing, because run.py keeps the previous file
    when a site fails and the health line then ages honestly. Caught by testing the
    cap rather than by reading it: with the budget forced to 2, Kinopalatsi Kotka
    went to zero showtimes and Trio 123 to 6 of 34, and both would have shipped.
    """
    items = list(items)
    limit = PAGE_BUDGET if limit is None else limit
    if len(items) > limit:
        raise RuntimeError(
            f"{label}: {len(items)} film pages to fetch, over the {limit} budget. "
            "These pages carry the showtimes, so a partial fetch would publish a "
            "partial schedule; failing instead keeps the last good data.")
    return items


def write_text_atomic(path, text):
    """Write via a sibling .tmp then os.replace, atomic on the same filesystem.

    On Actions a torn write is harmless (ephemeral runner), but the local
    wrapper writes into a checked-out repo, so a run killed mid-write -- closed
    laptop, cancel-in-progress -- would leave truncated JSON that the next
    run's `git add data` commits. .tmp is gitignored for the same reason.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path, obj, **dumps_kw):
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, **dumps_kw))


# `write_text_atomic` makes one file atomic. A site owns several -- one per venue plus its
# provider file -- and publishing them one at a time means a failure partway leaves some
# venues on the new fetch and the rest on the previous one, under a provider file that
# describes neither. Staging splits the two halves of that write: everything that can fail
# on content or on space happens while only `.tmp` siblings exist, and the live files move
# in a burst of renames afterwards. `.tmp` is already gitignored, for the reason above.
def stage_json(path, obj, **dumps_kw):
    """Write `path`'s .tmp sibling and nothing else. -> (tmp, path) for commit_staged."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, **dumps_kw), encoding="utf-8")
    return tmp, path


def commit_staged(staged):
    """Rename every staged .tmp over its target. -> the number of files published."""
    for tmp, path in staged:
        os.replace(tmp, path)
    return len(staged)


def discard_staged(staged):
    """Remove staged .tmp files after a failure, so none is left for the next run."""
    for tmp, _ in staged:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


# data/films-extra.json is one file for the whole run, written by three passes and
# rewritten by both halves within the few minutes that separate their commits. Emitted as
# one line it cannot content-merge: a local push landing mid-run fails `pull --rebase` on
# it, fails the same way all three attempts, and the cloud run's whole commit is lost. One
# key per line lets git rebase unrelated keys cleanly, and `sort_keys` makes the order a
# function of the content rather than of whichever pass wrote it last, so two halves that
# added different films produce a diff git can reconcile instead of two whole-file
# rewrites. Measured 2026-09-19: 346 kB on one line becomes 362 kB over 4370 lines, 4.4%.
#
# The trailing newline is for the same reader: without it every append rewrites the last
# line and git reports "\ No newline at end of file" on both sides of it.
FILMS_EXTRA_FORMAT = {"indent": 1, "sort_keys": True}


def write_films_extra(path, doc):
    """The one emitter for data/films-extra.json, used by all three of its writers.

    A shared function rather than three call sites passing the same keywords: the point of
    the format is that the three agree byte for byte, and three copies of a keyword pair
    is exactly the shape that drifts. `tests/test_films_extra_format.py` asserts the
    agreement rather than trusting it.
    """
    write_text_atomic(path, json.dumps(doc, ensure_ascii=False,
                                       **FILMS_EXTRA_FORMAT) + "\n")

# The publication horizon a source is allowed to reach, as (days behind, days ahead).
# There is no universal right answer, so each caller passes its own and records what it
# measured. This default is the one the three sources using this helper were measured at on
# 2026-09-15: Kino Vaakuna +0..+9, Kino Kuvakukko +0..+9, Kino Manttu -4..-2, Kino
# Kirkkonummi -1..+9. Every one of them publishes about a week either side, so 30 back and
# 60 ahead is several times their observed span and still nowhere near the 365 a weekday
# slip needs.
#
# What this cannot do is tell a genuine far-future screening from a mistaken one. A cinema
# announcing a Christmas gala in October would fall outside and be dropped, named in the
# adapter's log rather than published on a date it might not mean. That is the trade this
# makes, and it is the reason the window is a caller's argument and not a constant here.
DEFAULT_WINDOW = (30, 60)

# Finnish weekday names as the cinema sites write them, full and abbreviated, keyed on the
# first two letters because that is unambiguous across all seven.
FI_WEEKDAYS = {"ma": 0, "ti": 1, "ke": 2, "to": 3, "pe": 4, "la": 5, "su": 6}


def weekday_index(name):
    """`Tiistai`, `ti`, `TI` -> 1 (Monday is 0). -> int, or None for anything else."""
    key = (name or "").strip().lower()[:2]
    return FI_WEEKDAYS.get(key)


def resolve_year(day, month, today, weekday=None, window=DEFAULT_WINDOW):
    """A `DD.MM.` with no year -> the year it means. -> int, or None.

    **Select first, then bound.** The intended candidate is chosen under one rule, and only
    then accepted or refused. It is never swapped for a different year because the first
    choice fell outside the window. That was a real bug on 2026-09-15: `18.3.` read on 15
    September resolved to *next* March, 184 days ahead, because the nearer occurrence 181
    days back had already been filtered out before the choice was made. The nearest
    occurrence is the answer or there is no answer.

    **With a weekday**, exactly one of the three candidate years can carry it: the same day
    and month falls on a different weekday in each, checked over 2000-2100 across 4,800
    windows with none where two coincide. That makes the selection unambiguous *given the
    window*; it does not establish the intended date. A page left up for years, or one with
    a mistyped weekday, still selects one of the three and nothing on the page says so.

    **Without one**, the nearest occurrence wins, ties going to the future. "Next
    occurrence" is the rule that suggests itself and is wrong where it matters: on 2 January
    a page still showing `28.12.` means five days ago, not in eleven months.

    **Then the window decides.** `window` is `(days behind, days ahead)` and the selected
    date must fall inside it or this returns None and the caller skips the row. This is what
    stops a stale listing with a wrong weekday becoming a far-future screening: `Ti 1.6.`
    read on 2026-09-15 selects 2027, because 1 June 2027 is the Tuesday, 259 days ahead,
    and 259 is far outside the horizon any of these cinemas publishes at. A stale row placed
    in the past is harmless, since the client hides past screenings; a phantom row in the
    future is shown to readers.

    Returns None when no candidate year holds that day and month at all, which is 29.02. in
    a three-year window with no leap year in it.
    """
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append((year, datetime.date(year, month, day)))
        except ValueError:
            continue
    if not candidates:
        return None
    if weekday is not None:
        matching = [c for c in candidates if c[1].weekday() == weekday]
        if not matching:
            return None          # the page contradicts itself: a slip or a template change
        year, when = matching[0]
    else:
        # Ties go to the future: a date equally far either way is the coming one.
        year, when = min(candidates,
                         key=lambda c: (abs((c[1] - today).days),
                                        0 if c[1] >= today else 1))
    if window is not None:
        behind, ahead = window
        if not -behind <= (when - today).days <= ahead:
            return None          # selected, then refused; never replaced by another year
    return year


# The languages a synopsis slot may be written for; `synmerge.LANGS` is the same list.
SYN_LANGS = ("fi", "sv", "en")

# Function words that occur in one of the three and not in the others, matched as whole
# words. Content words are useless: a Finnish blurb about an English film quotes English
# titles and names. The lists are disjoint, so "on" (fi and en) is in neither.
SYN_MARKERS = {
    "fi": ("ja", "ei", "että", "sekä", "kun", "joka", "jonka", "jossa", "jotka",
           "jolloin", "koska", "mutta", "myös", "hän", "hänen", "heidän", "ovat", "kuin",
           "vaan", "vai", "niin", "sen", "tai", "ennen", "vielä", "sitä", "siitä"),
    "sv": ("och", "att", "som", "den", "det", "är", "för", "med", "han", "hon", "inte",
           "sig", "sina", "från", "efter", "av", "till", "om", "har", "eller", "också",
           "sedan", "sin", "sitt"),
    "en": ("the", "and", "of", "to", "in", "is", "with", "his", "her", "from", "that",
           "their", "who", "when", "into", "but", "they", "which", "was", "are"),
}

# Case endings that no ordinary English or Swedish word of this length carries. Used only
# when neither of those two scored a single function word, because a short Finnish sentence
# can avoid every word in the list above: "Kilpa-auto Salama McQueen on matkalla
# Kaliforniaan ottamaan osaa suureen Piston Cup -kisaan" scores zero markers in all three
# languages and is plainly Finnish.
FI_ENDINGS = ("ssa", "ssä", "sta", "stä", "lla", "llä", "lle", "ksi", "aan", "ään",
              "jen", "ista", "istä", "ille", "oita", "öitä", "tta", "ttä")
# Long enough that the English and Swedish words sharing these endings (umbrella, vanilla,
# vista, unseen) do not reach the count.
FI_ENDING_MIN = 8

# Frozen once: the scoring loop asked for a set per word per language before this.
_SYN_SETS = {lang: frozenset(marks) for lang, marks in SYN_MARKERS.items()}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def syn_language(text, least=3, margin=2):
    """Which of SYN_LANGS a synopsis is in. -> "fi", "sv", "en", or "".

    The slot in films-extra.json is keyed by normalised title and read by every chain
    showing the film, so a text filed under the wrong language is served that way
    everywhere. CLAUDE.md states the rule under "Adding a provider"; this is how an adapter
    reading a mixed site obeys it.

    "" means too short or too even to place, and the caller publishes no synopsis. The
    winner needs `least` markers and `margin` times the runner-up. Finnish has a second
    route, `FI_ENDINGS`, and it opens only when Swedish and English both score nothing.
    """
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    counts = {lang: sum(1 for w in words if w in marks)
              for lang, marks in _SYN_SETS.items()}
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    (best, top), (_, second) = ranked[0], ranked[1]
    if top >= least and top >= margin * second:
        return best
    if counts["sv"] or counts["en"]:
        return ""
    endings = sum(1 for w in words
                  if len(w) >= FI_ENDING_MIN and w.endswith(FI_ENDINGS))
    return "fi" if endings >= least else ""
