"""Fetch Finnkino schedule via digital-api (Vista OCAPI) and write JSON into data/."""
import datetime, gzip, json, os, re, sys, time, pathlib
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "providers"))
import common    # noqa: E402  shared atomic writers, see providers/common.py
from common import has_future_shows  # noqa: E402  shared with run.py
import strands   # noqa: E402  shared strand list, see providers/strands.py
import synmerge  # noqa: E402  shared synopsis helpers, see providers/synmerge.py
import refresh   # noqa: E402  shared rating-refresh schedule, see providers/refresh.py
import enrich_tmdb  # noqa: E402  the title key, so this file keeps no fourth copy

DIGITAL_API = "https://digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1"
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"
PAGE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip",
}
ATTR_RE = re.compile(r"^\dD$|^(IMAX|4DX|Dolby|ScreenX|D-BOX|LUXE|iSense|HFR|Laser|PLF)", re.I)
# A rating below this many votes is noise, not a verdict. Keep in step with
# enrich_tmdb.MIN_VOTES so the two passes cannot disagree about the same film.
TMDB_MIN_VOTES = 25


def _tmdb_complete(c):
    """What a fully-formed entry in data/tmdb.json looks like. -> bool.

    Handed to refresh.due(). Narrower than the title cache's predicate on purpose: this
    one carries no synopsis and no poster, because Finnkino publishes both itself, so
    requiring them here would mark every entry incomplete for ever.
    """
    return isinstance(c, dict) and "n" in c and "x" in c and "g" in c
# Event attributes worth keeping, and what they mean. The rest of what OCAPI ships here
# is marketing and region codes (Maxim, Pkseutu, SEVERAL, TKU & R, Tampere, Varaus20),
# which say nothing to a visitor. A licensed bar auditorium is 18+ whatever the film is
# rated -- Finnkino spells that out in "Annisk_K18" -- so the limit belongs on the
# screening, exactly as it does for BioRex. See the `age` convention in
# docs/archive/2026-09-providers.md.
EVENT_ATTRS = {"anniskelu": ("Anniskelu", ""),
               "annisk_k18": ("Anniskelu", "K-18"),
               "eventcine": ("Event cinema", "")}
# The same hand-written escape hatch enrich_tmdb.py uses, keyed by the normalised
# published title. Until now only the cloud pass could read it, so a Finnkino film TMDB
# cannot be searched by title had no fix at all: "Maailman rikkain nainen" already had
# an alias, which corrected Gilda's row and left Finnkino's blank.
ALIAS_FILE = pathlib.Path(__file__).resolve().parent / "providers" / "tmdb-aliases.json"


def load_aliases():
    try:
        return {k: v for k, v in json.loads(ALIAS_FILE.read_text()).items()
                if not k.startswith("_")}
    except Exception as e:
        print(f"[tmdb] no aliases ({e})")
        return {}


# The title key, imported rather than restated. This file kept a fourth copy that said
# it "must behave like enrich_tmdb.norm()" and did not: it left `_` in, because Python's
# \w counts the underscore as a word character while the client's \p{L}\p{N} does not.
# `Dyyni: Osa_kolme` keyed as `dyyni osa_kolme` here and `dyyni osa kolme` everywhere
# else, so an alias or a cache entry written by one pass was unreachable from the other.
# Three implementations have to agree (enrich_tmdb.norm, synmerge.norm, normTitle in
# index.html); a fourth that only claims to is worse than none.
_tnorm = enrich_tmdb.norm


def _alias(aliases, meta):
    """A Finnkino film's alias: the Finnish title's key, the query's, then the Finnish
    title's cleaned search string, as `enrich_tmdb.alias_of` reads it. OCAPI's `y` is the
    release date, a reissue's included, so only a year printed in the title stops the
    cleaned lookup."""
    fi = meta.get("fi") or ""
    year = enrich_tmdb.published_year({"title": fi})
    return (enrich_tmdb.alias_of(aliases, _tnorm(fi), _tnorm(enrich_tmdb.clean(fi)), year)
            or aliases.get(_tnorm(meta["q"])))


def alias_overrides(tmdb_cache, films_meta, aliases):
    """The cached films an alias replaces. -> [fid].

    A non-exact entry with an alias, and since 2026-09-25 an exact entry whose id an alias
    id disagrees with, the rule `enrich_tmdb.alias_supersedes` states for the cloud pass:
    Finnkino's "Avengers: Endgame Encore" kept a one-vote record on 96 rows with an alias
    for 299534 in the file.
    """
    return [fid for fid, v in tmdb_cache.items() if fid in films_meta
            and enrich_tmdb.alias_supersedes(_alias(aliases, films_meta[fid]), v)
            and not (enrich_tmdb.is_weak(v)
                     and v.get("al") == str(_alias(aliases, films_meta[fid])))]


def _queries(q):
    """Search candidates, best first. Mirrors enrich_tmdb.queries().

    OCAPI's originalTitle is empty for some releases and the Finnish title is used
    instead, so the query can arrive as "Autot (uudelleenjulkaisu)", which matches
    nothing, or "Mutiny - Lavastettu syylliseksi", whose distributor subtitle stops the
    exact-title rule from firing on a hit that is in fact the right film.

    The search string is `enrich_tmdb.clean()`'s. This file kept its own bracket list,
    which lacked `englanniksi`, `på svenska`, `puhumme suomea` and the rest, so the two
    passes could search one film differently (prior review #33).
    """
    out = []

    def add(x):
        x = (x or "").strip(" -–:,")
        if len(x) > 2 and x.lower() not in [o.lower() for o in out]:
            out.append(x)

    c = enrich_tmdb.clean(q)
    add(c)
    add(q)
    # Dash only, never a colon. A Finnish distributor subtitle is appended with a dash
    # ("Mutiny - Lavastettu syylliseksi"), while a colon usually carries the franchise:
    # splitting "Mission: Impossible - Dead Reckoning" would search "Mission", and an
    # exact hit on that now earns a tmdbId and would merge two different films.
    head = re.split(r"\s+[-–]\s+", c, maxsplit=1)[0]
    add(head)
    return out


def _get_json(url, headers):
    return json.loads(http_get(url, headers))


def _judge(hits, cand, meta, th, year=""):
    """`enrich_tmdb.pick()` for this pass. -> (hit, exact).

    With a year, an exact title is held to it and a second film of that title and year is
    a tie, as in the cloud pass. Without one, the published runtime decides between films
    sharing the title, rivals only English offers included (`with_rivals`).
    """
    if not hits:
        return None, False
    minutes, rts = meta.get("m") or [], None
    if not year and minutes:
        hits, rts = enrich_tmdb.with_rivals(hits, cand, th, fetch=_get_json)
    return enrich_tmdb.pick(hits, cand, year or None, meta["q"], minutes, rts)
THEATER_SLUGS = {
    "Cine Atlas Tampere": "finnkino-cine-atlas",
    "Fantasia Jyväskylä": "finnkino-fantasia",
    "Flamingo Vantaa": "finnkino-flamingo",
    "Itis Helsinki": "finnkino-itis",
    "Kinopalatsi Helsinki": "finnkino-kinopalatsi-helsinki",
    "Kinopalatsi Turku": "finnkino-kinopalatsi-turku",
    "Kuvapalatsi Lahti": "finnkino-kuvapalatsi",
    "LUXE Mylly Raisio": "finnkino-luxe-mylly",
    "Maxim Helsinki": "finnkino-maxim",
    "Omena Espoo": "finnkino-omena",
    "Plaza Oulu": "finnkino-plaza",
    "Plevna Tampere": "finnkino-plevna",
    "Promenadi Pori": "finnkino-promenadi",
    "Scala Kuopio": "finnkino-scala",
    "Sello Espoo": "finnkino-sello",
    "Strand Lappeenranta": "finnkino-strand",
    "Tennispalatsi Helsinki": "finnkino-tennispalatsi",
}

def http_get(url, headers, timeout=25, tries=3, backoff=5):
    """Every request this script makes, through the shared fetcher. -> bytes.

    It used to be a bare `urlopen().read()`: no retry, no body cap, no `Retry-After`,
    and none of the refusal diagnostics the rest of the pipeline prints. That covered
    the Finnkino API, the poster downloads and the TMDB calls alike, so a transient 502
    on one business date failed the whole seven-day fetch and a TMDB 429 was answered
    immediately with two more requests.

    `common.fetch` supplies all four, and `tries`/`backoff` pass straight through to it
    so a caller can tune the wait without reaching around this function.

    Two things stay here. The gunzip is this script's:
    `common.fetch` returns the body as served, and Finnkino has been seen answering
    gzip. And `cache` stays off, because none of these endpoints sends a validator and a
    POST-like token page is not addressed by its URL alone.
    """
    raw = common.fetch(url, headers=headers, timeout=timeout,
                       tries=tries, backoff=backoff)
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw

def get_token():
    """The local wrapper hands the token in through FINNKINO_TOKEN; it was taken from a
    real browser session moments earlier and is used within seconds.

    The direct fetch below only works from an ordinary connection: www.finnkino.fi
    answers Cloudflare 403 to datacenter IPs, which is why this half of the pipeline
    runs at home and has no cloud fallback. The Cloudflare Worker path that used to sit
    between these two was removed on 2026-08-27 — never deployed, and it existed to
    solve the same problem the local run already solves.
    """
    tok = os.environ.get("FINNKINO_TOKEN", "").strip()
    if tok:
        print("[token] using FINNKINO_TOKEN from the environment")
        return tok
    print("[token] no FINNKINO_TOKEN, trying a direct fetch (needs a residential IP)")
    for i, u in enumerate(["https://www.finnkino.fi/",
                           "https://www.finnkino.fi/teatterit/finnkino-tennispalatsi/"], 1):
        try:
            html = http_get(u, PAGE_HEADERS).decode("utf-8", "replace")
            m = JWT_RE.search(html)
            if m:
                print(f"[token] direct from {u}")
                return m.group(0)
        except Exception as e:
            print(f"[token] {u}: {e}")
        time.sleep(1 + i)
    raise RuntimeError("no token: set FINNKINO_TOKEN, or run from an ordinary connection")

def api(path, token):
    return json.loads(http_get(DIGITAL_API + path, {
        "authorization": f"Bearer {token}",
        "accept": "application/json",
        "user-agent": UA,
        "referer": "https://www.finnkino.fi/",
    }))

# Finnkino's language vocabulary where it departs from ISO 639-1. SE is ISO 3166 for
# Sweden, the country; TU and MA are Finnkino's own for Turkish and Malayalam, measured
# on 2026-09-02 as "Keltaiset kirjeet" (62 rows, tagged TR-A by every other chain that
# screens it) and "I'm Game" (3 rows). LI is its own for Lithuanian, measured on
# 2026-09-22 as "Sve\u010dias \u2013 The Visitor" at Kinopalatsi Helsinki (2 rows, spoken,
# with FI and EN subtitles). Everything downstream is keyed by the ISO code:
# the other adapters publish it and the client's name table knows only it.
FINNKINO_LANG = {"SE": "SV", "TU": "TR", "MA": "ML", "LI": "LT"}


def lang_tag(lbl):
    """OCAPI language attribute -> this app's tag. '.FI-S' -> 'FI-S', '.FI-SE-A' ->
    'FI-SV-A', '.TU-A' -> 'TR-A'.

    Only the language components are mapped: the trailing A or S is the role, and a
    compound label carries two languages before it.
    """
    parts = lbl.lstrip(".").split("-")
    return "-".join([FINNKINO_LANG.get(c, c) for c in parts[:-1]] + [parts[-1]])


def loc(obj):
    """Vista text object -> {'fi': ..., 'en': ...}"""
    if not isinstance(obj, dict):
        return {"fi": "", "en": ""}
    fi = obj.get("text") or ""
    en = ""
    for tr in obj.get("translations") or []:
        if str(tr.get("languageTag", "")).lower().startswith("en"):
            en = tr.get("text") or ""
            break
    return {"fi": fi, "en": en}


def place_syn(syn):
    """loc()'s synopses, each in the slot common.syn_language gives it. Finnkino's slots
    are not always what they claim (2026-09-27: "fi" held English for NT LIVE: All My
    Sons, "en" the bare title for Pressure). Three words or fewer is dropped, a text no
    language settles stays put, and one already in its own slot wins."""
    out = {"fi": "", "en": ""}
    placed = [(common.syn_language(syn[k]) or k, k, syn[k])
              for k in ("fi", "en") if len((syn.get(k) or "").split()) > 3]
    for lang, k, text in sorted(placed, key=lambda p: p[0] != p[1]):
        if not out.get(lang):
            out[lang] = text
    return out

# A site id is upstream text, and it is the one filename component in this pipeline that
# a third party writes: `area-{sid}.json` below. It also goes into a query string. Every
# other provider's venue ids come from registry.py, and common.check_shows refuses a show
# filed under a venue its site does not list; this path has neither guard, so the shape is
# checked here instead.
SITE_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")


def usable_sites(raw_sites):
    """The sites with a name and an id this pipeline will write. -> (sites, dropped)."""
    sites, dropped = [], []
    for s in raw_sites:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        sid, name = str(s["id"]), t(s, "name", "text")
        if not name:
            continue
        (sites if SITE_ID.fullmatch(sid) else dropped).append(
            {"id": sid, "name": name})
    return sites, dropped


def site_query(sites):
    """The siteIds query for /showtimes. -> str.

    quote() cannot fire while SITE_ID holds, and is here so the two do not have to be
    read together to know the query is safe."""
    return "&".join("siteIds=" + urllib.parse.quote(s["id"], safe="") for s in sites)


def t(obj, *keys):
    for k in keys:
        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
    return obj if isinstance(obj, str) else ""

POSTER_DIR = pathlib.Path("data/posters")
_poster_cache = {}
# The moviexchange release id, which names the file and goes into the CDN path. Upstream
# text like the site id above, and checked for the same reason: `../../escape` wrote two
# levels above data/posters. All 84 committed Finnkino posters are named by one on
# 2026-09-25, so the shape is measured rather than assumed.
RELEASE_ID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")


def poster_decodes(raw: bytes) -> bool:
    """Whether a poster body is a whole image. -> bool.

    `common.fetch` returns a body cut short of its Content-Length without raising, so the
    length alone proves nothing. Pillow decodes it where it is installed (the runner, the
    worktree venv). Without it, a JPEG has to open with SOI and close with EOI, which is
    what a truncated body loses; every committed Finnkino poster does both.
    """
    try:
        from PIL import Image
    except ImportError:
        return raw[:2] == b"\xff\xd8" and raw.rstrip(b"\x00")[-2:] == b"\xff\xd9"
    import io
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
        return True
    except Exception:
        return False


def download_poster(rid: str) -> str:
    """Download poster once per release id; return relative path or ''.

    A file already on disk is used only if it decodes; a broken one is fetched again. The
    new body is decoded before it is kept and lands through a temp file and a rename, so a
    run stopped mid-write leaves no half poster under the final name."""
    if rid in _poster_cache:
        return _poster_cache[rid]
    if not RELEASE_ID.fullmatch(rid or ""):
        print(f"[poster] {rid!r}: not a release id, not fetched")
        _poster_cache[rid] = ""
        return ""
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    rel = f"data/posters/{rid}.jpg"
    p = pathlib.Path(rel)
    if not (p.exists() and poster_decodes(p.read_bytes())):
        url = f"https://film-cdn.moviexchange.com/api/cdn/release/{rid}/media/Poster?width=200"
        try:
            raw = http_get(url, {"user-agent": UA, "referer": "https://www.finnkino.fi/",
                                 "accept": "image/*"})
            if len(raw) <= 500:
                raise RuntimeError("too small")
            if not poster_decodes(raw):
                raise RuntimeError(f"{len(raw)} bytes that do not decode as an image")
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_bytes(raw)
            tmp.replace(p)
        except Exception as e:
            print(f"[poster] {rid}: {e}")
            _poster_cache[rid] = ""
            return ""
    _poster_cache[rid] = rel
    return rel

def enrich_cached_ratings(films_meta, tmdb_cache, aliases, th, today):
    """Read what TMDB knows about every due film into `tmdb_cache`, in place.

    -> {looked, rechecked, weak, thin, scheduled, settled, deferred}, which is everything
    the caller prints about the pass.

    Lifted out of main() so it can be driven from a test. This file cannot run on a
    runner -- Finnkino answers a datacenter address with a Cloudflare 403 -- so the only
    way to exercise the schedule and the failure paths without a live token is to call
    the pass directly with TMDB stubbed.
    """
    looked = rechecked = 0
    tmdb_weak, tmdb_thin = [], []
    # Entries taken out for a fresh judgment. An alias replacing an exact entry removes a
    # judgement known wrong, so that one is not put back if the search fails. A weak
    # entry publishes nothing and goes back with today's attempt date, as in enrich_tmdb.
    retried = {}
    overridden = alias_overrides(tmdb_cache, films_meta, aliases)
    for fid in overridden:
        if enrich_tmdb.is_weak(tmdb_cache[fid]):
            retried[fid] = tmdb_cache[fid]
        del tmdb_cache[fid]
    # A weak entry is complete to refresh.due(), which would park it a day or a week and
    # then re-read the wrong id without searching. So it leaves the cache for a search
    # when its daily retry is due or the query or year it was judged on has changed (no
    # record reads as changed), and is skipped outright until then.
    for fid, m in films_meta.items():
        c = tmdb_cache.get(fid)
        if m["q"] and enrich_tmdb.is_weak(c) and (
                enrich_tmdb.weak_due(c, today)
                or (c.get("q"), c.get("y")) != (_tnorm(m["q"]), m["y"] or "")):
            retried[fid] = tmdb_cache.pop(fid)
    kept = {fid for fid, m in films_meta.items()
            if m["q"] and enrich_tmdb.is_weak(tmdb_cache.get(fid))}
    # Which entries are due, and which of those only because their rating is old.
    # Finding a trailer used to end an entry's life here as well: the skip was
    # `v or c == today`, so 46 of the 59 cached films were frozen, 45 of them last
    # read on 2026-08-28. The schedule is providers/refresh.py, shared with the cloud
    # pass so the two cannot drift apart again.
    todo, refreshes, deferred = refresh.due(
        [fid for fid, m in films_meta.items() if m["q"] and fid not in kept],
        tmdb_cache, today, _tmdb_complete)
    settled = set()          # scheduled refreshes that came back with vote data
    for fid, meta in films_meta.items():
        if fid not in todo:
            continue
        cached = tmdb_cache.get(fid)
        cached = cached if isinstance(cached, dict) else None
        replaced = False
        try:
            mid = cached.get("i") if cached else None
            va = (cached.get("r") or 0) if cached else 0
            votes = (cached.get("n") or 0) if cached else 0
            exact_id = bool(cached.get("x")) if cached else False
            gids = (cached.get("g") or []) if cached else []
            # An alias is either a bare TMDB id, which skips the search, or a
            # replacement search string. Keyed on the Finnish title first, since
            # that is what the cinema publishes and what the file is keyed by.
            alias = _alias(aliases, meta)
            named = ""              # a weak candidate's title, for the kept-list log
            if not mid and alias and str(alias).isdigit():
                mid = int(alias)
                exact_id = True     # a hand-written id is as good as exact
                va = votes = 0      # rating comes from the detail call below
            if not mid:
                # Every candidate is tried until one matches the title exactly; the
                # first hit of any kind is the fallback. Stopping at the first
                # candidate that returns anything is what sent "Die Hard 2 - Die
                # Harder" to Die Hard in the cloud pass.
                fallback = None
                cands = _queries(meta["q"])
                if alias and not str(alias).isdigit():
                    cands.insert(0, str(alias))
                for cand in cands:
                    q = urllib.parse.quote(cand)
                    u = f"https://api.themoviedb.org/3/search/movie?language=fi-FI&query={q}"
                    year = meta["y"] and cand != str(alias or "")
                    res = json.loads(http_get(
                        u + (f"&primary_release_year={meta['y']}" if year else ""), th))
                    results = res.get("results") or []
                    hit, exact = _judge(results, cand, meta, th, meta["y"] if year else "")
                    # A reissue carries the *reissue* year, so the filter hides the
                    # film: "Autot (uudelleenjulkaisu)" is a 2026 release of a 2006
                    # title, and searching the alias "Cars" with year=2026 returned
                    # "The Boy Who Counted Cars". Retry unfiltered when the year found no
                    # film of that exact title, and judge the answer as a title with no
                    # year: OCAPI's is the Finnish release, so it narrows the search and
                    # never refuses a hit. A tie of that year stays a tie.
                    if year and not enrich_tmdb.exact_hits(results, cand):
                        alt = json.loads(http_get(u, th)).get("results") or []
                        if alt:
                            a_hit, a_exact = _judge(alt, cand, meta, th)
                            if a_exact or not hit:
                                hit, exact, results = a_hit, a_exact, alt
                    if hit and exact:
                        mid = hit.get("id")
                        va = hit.get("vote_average") or 0
                        votes = hit.get("vote_count") or 0
                        exact_id = True
                        break
                    if hit and fallback is None:
                        fallback = hit
                    time.sleep(0.2)
                else:
                    if fallback is not None:
                        mid = fallback.get("id")
                        va = fallback.get("vote_average") or 0
                        votes = fallback.get("vote_count") or 0
                        exact_id = False
                        named = fallback.get("title") or ""
                        tmdb_weak.append(f"{meta['q']} -> {fallback.get('title')}")
            # An id that did not come from a search carries no vote data with it
            # (an alias id, or one restored from cache before "n" existed), and this
            # pass otherwise never fetches the movie detail. One request, only in
            # that case, keeps the rating and the vote floor working.
            # One detail call covers both gaps: vote data for an id that did not come
            # from a search, and the genre ids, which this pass never had. Skipped
            # once the cache carries both, so it costs one pass per film, not one
            # per run. Genre names are localized client-side from
            # data/tmdb-genres.json, written by the cloud pass.
            # ...and once more when the entry is being refreshed, which is the only
            # way a rating this pass already holds can ever be re-read. Without that
            # clause an age-based refresh would fetch nothing and stamp the entry as
            # current, which is worse than not refreshing at all.
            detail_ok = False
            if mid and (not votes or not gids or fid in refreshes):
                try:
                    d = json.loads(http_get(
                        f"https://api.themoviedb.org/3/movie/{mid}", th))
                    # Both halves of the pair or neither. `or va` used to let a
                    # response carrying one of them write a zero over a real rating.
                    fresh_r = refresh.numeric(d.get("vote_average"))
                    fresh_n = refresh.numeric(d.get("vote_count"))
                    if fresh_r is not None and fresh_n is not None:
                        va, votes = fresh_r, fresh_n
                        detail_ok = True
                    if d.get("genres"):
                        gids = [g["id"] for g in d["genres"] if g.get("id")]
                except Exception as e:
                    print(f"[tmdb-detail] {meta['q']}: {e}")
            # Seeded from the cache. A video request that fails must not empty a
            # trailer this entry already had; one that answers and finds none does
            # clear it, which is the rule the detail read follows too.
            yt = (cached.get("v") or "") if cached else ""
            if mid:
                try:
                    vids = json.loads(http_get(
                        f"https://api.themoviedb.org/3/movie/{mid}/videos", th)).get("results") or []
                    yt = ""
                    for pref in (lambda v: v.get("type") == "Trailer" and v.get("official"),
                                 lambda v: v.get("type") == "Trailer",
                                 lambda v: v.get("type") == "Teaser"):
                        hit = next((v for v in vids if v.get("site") == "YouTube" and pref(v)), None)
                        if hit:
                            yt = hit.get("key") or ""
                            break
                except Exception as e:
                    print(f"[tmdb-videos] {meta['q']}: {e}")
            # A rating needs votes: a premiere with three of them shows a clean
            # 10.0, which reads as a verdict. Same floor as enrich_tmdb.
            shown = round(va, 1) if va and votes >= TMDB_MIN_VOTES else 0
            if va and not shown:
                tmdb_thin.append(f"{meta['q']} ({round(va, 1)} / {votes} votes)")
            # `c` is what parks an entry, so a *refresh* may only move it once a
            # detail response carried the vote pair. The daily half is different and
            # deliberately so: it is a trailer hunt that makes no detail request by
            # design, and requiring one to advance the date would turn a once-a-day
            # check into a once-a-run one at somebody else's expense.
            stamp = (today if (detail_ok or fid not in refreshes)
                     else (cached.get("c") or "") if cached else "")
            # `a` is every attempt, `c` only the ones that answered. Keeping them
            # apart is what stops an id that can never be read from holding the head
            # of the queue for ever -- see providers/refresh.py.
            attempt = today if mid else ((cached.get("a") or "") if cached else "")
            tmdb_cache[fid] = {"r": shown, "n": votes, "v": yt,
                               "x": bool(mid) and exact_id, "g": gids,
                               "i": mid or "", "c": stamp, "a": attempt}
            # A weak entry records what it was judged on, so new evidence re-judges it,
            # and the candidate's title for the log; with a string alias, which one.
            if mid and not exact_id:
                tmdb_cache[fid].update({"q": _tnorm(meta["q"]), "y": meta["y"] or "",
                                        "t": named})
                if alias:
                    tmdb_cache[fid]["al"] = str(alias)
            replaced = True
            if detail_ok and fid in refreshes:
                settled.add(fid)
            if cached:
                rechecked += 1
            else:
                looked += 1
            time.sleep(0.25)
        except Exception as e:
            print(f"[tmdb] {meta['q']}: {e}")
            # A scheduled refresh that got as far as being attempted has to record
            # that even when nothing else can be written, or it reads as never
            # attempted and returns to the head of the queue on every later run.
            # Only the marker moves; everything else stays as cached, so the entry
            # keeps what it had and stays due. Guarded so an exception after the
            # write cannot put the old entry back over a refresh that worked.
            if fid in refreshes and cached and not replaced:
                tmdb_cache[fid] = {**cached, "a": today}
            if fid in retried and not replaced:
                tmdb_cache[fid] = {**retried[fid], "a": today}

    kept_log = sorted(f"{films_meta[fid]['q']} -> "
                      f"{tmdb_cache[fid].get('t') or 'TMDB ' + str(tmdb_cache[fid]['i'])}"
                      for fid in kept)
    # Every kept entry has an attempt date: one without is due, so it was searched.
    kept_until = (datetime.date.fromordinal(
        min(datetime.date.fromisoformat(tmdb_cache[fid]["a"]).toordinal() for fid in kept)
        + enrich_tmdb.WEAK_RETRY_DAYS).isoformat() if kept else "")
    return {"looked": looked, "rechecked": rechecked, "weak": tmdb_weak,
            "thin": tmdb_thin, "scheduled": len(refreshes),
            "settled": len(settled), "deferred": deferred,
            "overridden": len(overridden), "kept": kept_log, "kept_until": kept_until}


def main() -> int:
    out = pathlib.Path("data"); out.mkdir(exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    token = get_token()

    raw_sites = api("/sites", token)
    raw_sites = raw_sites.get("sites", raw_sites) if isinstance(raw_sites, dict) else raw_sites
    sites, dropped = usable_sites(raw_sites)
    if dropped:
        print("[sites] dropped, id is not [A-Za-z0-9_-]{1,32} "
              f"({len(dropped)}): " + " | ".join(f"{d['id']!r} ({d['name']})"
                                                 for d in sorted(dropped, key=lambda d: d["name"])))
    if not sites:
        print("ERROR: no sites", file=sys.stderr); return 1
    sites.sort(key=lambda s: s["name"])
    print(f"[sites] {len(sites)} cinemas")
    # areas.json is written after the schedule files, not here. It is the file whose
    # age answers "when did Finnkino last refresh", so stamping it on a run that then
    # publishes no schedule would say the data is current while it is not.

    qs = site_query(sites)
    per_site = {s["id"]: [] for s in sites}
    unknown_attrs = set()
    films_meta = {}
    films_full = {}
    today = datetime.date.today()
    failed_dates = []
    for d in range(7):
        date = (today + datetime.timedelta(days=d)).isoformat()
        try:
            data = api(f"/showtimes/by-business-date/{date}?{qs}", token)
        except Exception as e:
            print(f"[schedule] {date} failed: {e}", file=sys.stderr)
            failed_dates.append(date)
            continue
        rd = data.get("relatedData", {})
        films = {str(f["id"]): f for f in rd.get("films", [])}
        genmap = {str(g["id"]): t(g, "name", "text") for g in rd.get("genres", [])}
        scr = {str(s["id"]): s for s in rd.get("screens", [])}
        rat = {str(r["id"]): r for r in rd.get("censorRatings", [])}
        att = {str(a["id"]): a for a in rd.get("attributes", [])}
        n = untitled = 0
        for s in data.get("showtimes", []):
            film = films.get(str(s.get("filmId", "")), {})
            site_id = str(s.get("siteId", ""))
            if site_id not in per_site:
                continue
            if not t(film, "title", "text"):
                # A renamed title field would publish every row as "?". Dropped and
                # counted per date below.
                untitled += 1
                continue
            fmt_list, lang_list = [], []
            show_age = ""      # a limit this screening adds on top of the film's rating
            for aid in (s.get("attributeIds") or []):
                a = att.get(str(aid), {})
                lbl = t(a, "shortName", "text") or t(a, "name", "text")
                if not lbl:
                    continue
                if ATTR_RE.match(lbl):
                    fmt_list.append(lbl)
                elif re.match(r"^\.?[A-Z]{2}(?:-[A-Z]{2})?-(?:A|S)$", lbl):
                    lang_list.append(lang_tag(lbl))
                elif lbl.lower() in EVENT_ATTRS:
                    tag, lim = EVENT_ATTRS[lbl.lower()]
                    if tag not in fmt_list:
                        fmt_list.append(tag)
                    if lim:
                        show_age = lim
                else:
                    # Anything else is dropped: marketing and region codes. Logged once
                    # per run so a new attribute cannot go missing silently the way
                    # Anniskelu did.
                    unknown_attrs.add(lbl)
            attr_names = " · ".join(fmt_list)
            lang_attr = ", ".join(lang_list)
            rating_raw = t(rat.get(str(film.get("censorRatingId", "")), {}), "classification", "text")
            m = re.match(r"^\d+", rating_raw)
            # Only S and K-n are ratings. OCAPI also ships "Tulossa" and "-" here, and a
            # raw pass-through rendered them in the age-limit chip and silently fell out
            # of every rating === test (the kids filter, the planned K-18 filter). If
            # "coming soon" is ever worth showing, it belongs next to the premiere chip.
            rating = f"K-{m.group(0)}" if m else ("S" if rating_raw == "S" else "")
            site_name = next((x["name"] for x in sites if x["id"] == site_id), "")
            slug = THEATER_SLUGS.get(site_name, "")
            fid = str(s.get("filmId", ""))
            if fid and fid not in films_meta:
                rt = str(film.get("runtimeInMinutes") or film.get("runTime") or "")
                films_meta[fid] = {"q": t(film, "originalTitle", "text") or t(film, "title", "text"),
                                   "fi": t(film, "title", "text"),
                                   "y": (film.get("releaseDate") or "")[:4],
                                   "m": [int(rt)] if rt.isdigit() and int(rt) else []}
                trs = film.get("trailers") or []
                tr_uri = ""
                if trs and isinstance(trs[0], dict):
                    tr_uri = trs[0].get("uri") or trs[0].get("url") or ""
                syn = film.get("synopsis") or film.get("shortSynopsis") or {}
                films_full[fid] = {
                    "t": loc(film.get("title")),
                    "o": t(film, "originalTitle", "text"),
                    "s": place_syn(loc(syn)),
                    "tr": tr_uri,
                    "y": films_meta[fid]["y"],
                    # Full premiere date, not just the year. Tickets for a premiere go on
                    # sale days ahead, so a film can be bookable before it opens and the
                    # date is the thing a visitor wants to see. Only Finnkino publishes
                    # it; the other providers show no badge rather than a guessed one.
                    "rd": (film.get("releaseDate") or "")[:10],
                }
            runtime = film.get("runtimeInMinutes") or film.get("runTime") or ""
            rid = (film.get("externalIds") or {}).get("moviexchangeReleaseId") or ""
            img = download_poster(rid) if rid else ""
            genres = ", ".join(filter(None, (genmap.get(str(gid), "")
                               for gid in (film.get("genreIds") or []))))
            per_site[site_id].append({
                "eventId": str(s.get("filmId", "")),
                "title": t(film, "title", "text"),
                "original": t(film, "originalTitle", "text"),
                "len": str(runtime) if runtime else "",
                "rating": rating,
                "age": show_age,
                "genres": genres,
                "method": attr_names,
                "theatre": site_name,
                "aud": t(scr.get(str(s.get("screenId", "")), {}), "name", "text"),
                "start": t(s.get("schedule", {}) if isinstance(s.get("schedule"), dict) else {}, "startsAt")
                         or (s.get("schedule", {}) or {}).get("startsAt", ""),
                "url": (f"https://www.finnkino.fi/liput/valitse-paikat/?showtimeId={s.get('id')}"
                        if s.get("id") else
                        (f"https://www.finnkino.fi/teatterit/{slug}/" if slug else "https://www.finnkino.fi/")),
                "img": img,
                "lang": lang_attr,
                "soldOut": bool(s.get("isSoldOut")),
            })
            # On the show too, while it is ahead: the badge must not wait on films.json,
            # which the client reads only in English or for a sheet.
            release = (film.get("releaseDate") or "")[:10]
            if release >= today.isoformat():
                per_site[site_id][-1]["rd"] = release
            # Same rule every other provider gets in run.py: a strand prefix goes to
            # `method` so the film does not fragment away from its plain-titled twin.
            strands.apply(per_site[site_id][-1])
            n += 1
        print(f"[schedule] {date}: {n} showtimes")
        if untitled:
            print(f"[schedule] {date}: {untitled} row(s) with no title, dropped")
        time.sleep(0.4)

    # The seven requests are independent, and a day that fails is a day missing from
    # every Finnkino venue at once. Written out, that day is absent from `dates`, which
    # the client reads as "schedule not published yet" rather than "no shows" -- so the
    # snapshot is not smaller than the truth, it disagrees with it, and it carries a
    # fresh timestamp saying so. Nothing surfaced it either: the run exited 0, the age
    # was current, and the health line stayed green.
    #
    # So publish seven days or none. The alternative on a failure is the previous file,
    # which is hours older and *says* it is hours older -- the age and the health line
    # both move, and a run exiting non-zero is what check_runs.py turns red on the next
    # push. Same rule the rest of the pipeline already follows: a provider that parses
    # nothing fails its run rather than blanking its venues.
    #
    # Poster downloads and the token fetch have already happened by here. Neither is a
    # snapshot -- posters accumulate under a release id and are re-used by the next run.
    if failed_dates:
        print(f"ERROR: {len(failed_dates)} of 7 dates failed "
              f"({', '.join(failed_dates)}); publishing nothing, "
              f"all {len(sites)} venues keep the schedule they have", file=sys.stderr)
        return 1
    # Seven dates answered and not one listed a screening. Seventeen venues over a week is
    # never empty, so this is the response changing under the parser (a renamed
    # `showtimes` reads as a quiet week), and CLAUDE.md's rule applies: a provider that
    # parses zero showtimes fails the run. Checked before anything is written, so the
    # venues keep their files and `areas.json` keeps its age. Finnkino has no
    # `EmptyProgramme` case: no empty listing has ever been seen from OCAPI.
    if not any(per_site.values()):
        print(f"ERROR: 7 dates answered and no showtime parsed for any of {len(sites)} "
              f"venues; publishing nothing, every venue keeps the schedule it has",
              file=sys.stderr)
        return 1

    tmdb_token = os.environ.get("TMDB_TOKEN", "").strip()
    if tmdb_token:
        cache_p = out / "tmdb.json"
        try:
            tmdb_cache = json.loads(cache_p.read_text())
        except Exception:
            tmdb_cache = {}
        th = {"Authorization": f"Bearer {tmdb_token}", "accept": "application/json",
              "user-agent": UA}
        # An entry with no "x" was matched before the exact-title rule existed and its
        # id cannot be re-judged after the fact, so drop it and search again. One-off.
        # Weak entries were swept here too, on every load, until 2026-09-25; they are
        # now kept and retried daily inside enrich_cached_ratings.
        stale = [k for k, v in tmdb_cache.items() if not (isinstance(v, dict) and "x" in v)]
        for k in stale:
            del tmdb_cache[k]
        if stale:
            print(f"[tmdb] dropped {len(stale)} entries matched by the old picker")
        aliases = load_aliases()
        today = datetime.date.today().isoformat()
        # Same rule as enrich_tmdb: an alias exists to replace a bad match, so an entry
        # it supersedes is searched again. Done inside the pass (`alias_overrides`).
        stats = enrich_cached_ratings(films_meta, tmdb_cache, aliases, th, today)
        if stats["overridden"]:
            print(f"[tmdb] dropped {stats['overridden']} entries an alias replaces")
        looked, rechecked = stats["looked"], stats["rechecked"]
        tmdb_weak, tmdb_thin = stats["weak"], stats["thin"]
        common.write_json(cache_p, tmdb_cache)
        # A film that matched *nothing* was invisible here: the weak list only names the
        # ones that found something wrong. "Ryhmä Hau: Dinoelokuva" sat with an empty id
        # for a day because of it, showing no rating and no genres while the log looked
        # clean. enrich_tmdb has always printed this; now so does the Finnkino pass.
        missing = sorted(m["q"] for fid, m in films_meta.items()
                         if m.get("q") and not (tmdb_cache.get(fid) or {}).get("i"))
        if missing:
            print(f"[tmdb] no TMDB match ({len(missing)}): " + " | ".join(missing))
        if tmdb_weak:
            print(f"[tmdb] weak match, no exact title ({len(tmdb_weak)}): "
                  + " | ".join(sorted(tmdb_weak)))
        if stats["kept"]:
            print(f"[tmdb] weak candidate kept, not searched until {stats['kept_until']} "
                  f"({len(stats['kept'])}): " + " | ".join(stats["kept"]))
        if tmdb_thin:
            print(f"[tmdb] rating held back, under {TMDB_MIN_VOTES} votes "
                  f"({len(tmdb_thin)}): " + " | ".join(sorted(tmdb_thin)))
        mergeable = sum(1 for c in tmdb_cache.values()
                        if isinstance(c, dict) and c.get("x") and c.get("i"))
        line = refresh.report(stats["scheduled"], stats["settled"],
                              stats["deferred"])
        if line:
            print(f"[tmdb] {line}")
        print(f"[tmdb] {looked} new lookups, {rechecked} re-checks, "
              f"cache {len(tmdb_cache)}, {mergeable} mergeable by id")
        # Only a trusted entry publishes: an exact title match or an alias id. The
        # `tmdbId` gate always said so, because a weak id would merge two different
        # films into one row; the rating, the votes, the genre ids and the trailer were
        # written from a weak candidate all the same, and were the wrong film's. Same
        # rule as enrich_tmdb.trusted(). The Finnkino trailer stands where TMDB's is not
        # trusted. Every venue file this run publishes, and films.json, are rebuilt from
        # this run's response, so a weak candidate's fields from an earlier run do not
        # survive the first run after this rule.
        def _trusted(c):
            return isinstance(c, dict) and bool(c.get("x")) and bool(c.get("i"))
        for shows in per_site.values():
            for sh in shows:
                c = tmdb_cache.get(sh["eventId"])
                if not _trusted(c):
                    continue
                if c.get("r"):
                    sh["tmdb"] = c["r"]
                    if c.get("n"):
                        sh["votes"] = c["n"]
                # Cross-chain film identity for the combined city view.
                sh["tmdbId"] = c["i"]
                if c.get("g"):
                    sh["gids"] = c["g"]
        # `i` lets the app sheet reach this text from another chain's title variant.
        for fid, entry in films_full.items():
            c = tmdb_cache.get(fid)
            if not _trusted(c):
                continue
            entry["i"] = c["i"]
            if c.get("v"):
                entry["tr"] = "https://www.youtube.com/watch?v=" + c["v"]

    # Finnkino drops the odd character to "?" ("Catherine Laga?aia"). Other chains run
    # the same distributor blurb intact, so where films-extra.json holds a copy that
    # differs only at those positions, take its characters. Nothing is guessed; see
    # synmerge.repair_from_twin.
    try:
        extra = (json.loads((out / "films-extra.json").read_text())).get("films") or {}
    except Exception:
        extra = {}
    repaired = synmerge.repair_from_twin(films_full, extra)
    if repaired:
        print(f"[films] {repaired} character(s) restored from another chain's copy")

    common.write_json(out / "films.json",
                      {"generated": now, "films": films_full})
    print(f"[films] {len(films_full)} film entries")
    if unknown_attrs:
        print(f"[attrs] dropped, neither format nor language ({len(unknown_attrs)}): "
              + " | ".join(sorted(unknown_attrs)))

    written = kept = 0
    today_iso = datetime.date.today().isoformat()
    for sid, shows in per_site.items():
        path = out / f"area-{sid}.json"
        # A partial OCAPI response must not blank 17 venues, so an empty result keeps
        # whatever is already committed (same rule as run.py for every other provider).
        # A venue with no file yet still gets one: areas.json lists every site
        # regardless of shows, so the picker would otherwise link to a 404.
        #
        # Only while the kept file still describes a day that has not passed. A file whose
        # last day is behind us protects nothing: every screening in it has been and gone,
        # and keeping it freezes `generated` for as long as the venue stays out of the
        # feed. The client ages a combined city view on its oldest part, so one frozen
        # venue puts a stale banner on every reader of that city and the hours in it climb
        # without bound. Maxim Helsinki, site 1103, did this on 2026-09-18: a normal
        # six-screening day on the 17th, absent from all seven business dates the next
        # run asked for, and the file stuck at 07:08:33Z while the other sixteen moved on.
        if not shows and path.exists() and has_future_shows(path, today_iso):
            print(f"[schedule] {sid}: no shows, keeping previous file", file=sys.stderr)
            kept += 1
            continue
        if not shows and path.exists():
            print(f"[schedule] {sid}: no shows and nothing left ahead in the kept file, "
                  f"publishing it empty", file=sys.stderr)
        # Dates present, so the UI can tell "no shows" apart from
        # "schedule not published yet" instead of showing one message for both.
        day_list = sorted({s["start"][:10] for s in shows if s.get("start")})
        common.write_json(path,
                          {"generated": now, "dates": day_list,
                           "horizon": day_list[-1] if day_list else "",
                           "shows": shows})
        written += 1
    print(f"[schedule] {written} venue files written, {kept} kept as-is")

    # `generated` is this publish, which check_staleness.py reads as "a run happened".
    # `oldest` is the weakest venue file on disk, run.py's rule for every other provider:
    # a venue kept from an earlier run stamped areas.json fresh, and the status page
    # called Finnkino as current as its newest venue (prior review #17).
    stamps = []
    for s in sites:
        path = out / f"area-{s['id']}.json"
        if path.exists():
            try:
                stamps.append(json.loads(path.read_text()).get("generated") or now)
            except (OSError, ValueError, AttributeError):
                stamps.append(now)
    common.write_json(out / "areas.json",
                      {"generated": now, "oldest": min(stamps) if stamps else now,
                       "areas": sites})
    print("done")
    return 0

if __name__ == "__main__":
    sys.exit(main())
