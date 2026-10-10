"""Kino Engel (Sofiankatu 4, Helsinki): front-page scrape. Stdlib only.

kinoengel.fi answers HTTP 202 with an `SG-Captcha: challenge` header to a datacenter
address, so this runs on the local half. The challenge is on IP reputation, not on the
request shape.

The WordPress REST API (`wp/v2/elokuva`) is the archive, not the programme: `acf` is empty
on every film and it returns 899 posts. The schedule exists only in the rendered page.
REST may still serve the cinema's own synopsis and a full-size poster later; see the note
at the bottom.

Parser notes:

- Rows carry their own date ("La 29.08." next to "klo 17:30"), so the `<h2>` day headings
  and the date `<select>` are not read.
- A strand is a separate `elokuva` post: `autofiktio` (3303) and `kesakino-autofiktio`
  (3295) are one film, and 23 of the first 100 posts are `kesakino-`. The `eventId` is the
  slug with the strand prefix removed, so both land on one card.
- KesäKino is a room, not a strand: it is the outdoor screen and goes in `aud`. `kesäkino`
  stays in `EVENT_PREFIXES` because `enrich_tmdb.clean()` needs it off the search string;
  this adapter strips it first. `BARNSÖNDAGAR:` and `BARNFESTIVAL:` are real strands and
  are left for the central pass.
"""
import datetime
import html as html_mod
import http.client
import re
import sys
import time
import urllib.error
from zoneinfo import ZoneInfo

from common import capped, fetch, get_text, resolve_year, syn_language, weekday_index

BASE = "https://kinoengel.fi"
URL = BASE + "/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "engel-helsinki", "provider": "engel", "providerId": "1",
         "name": "Kino Engel", "short": "Kino Engel", "city": "Helsinki"}

# `base` names the host this site is read from, which is the runner's pacing key.
# Nothing in this module reads it: fetch_site reads URL above and nothing else, and
# the committed run log records one host attempted, kinoengel.fi. It was absent until
# 2026-09-19, when a sweep of every host the committed logs name found this site and
# Kino Akseli as the only two declaring none. Both are local-half, so the cloud pool's
# one shared group for base-less sites never reached them; CLAUDE.md asks for the host
# to be named either way.
SITES = [{"provider": "engel", "label": "Kino Engel", "base": BASE,
          "venues": [VENUE]}]

# The outdoor screen. Slug prefix is the reliable signal; the visible title carries
# "KESÄKINO:" too, but the slug is ascii-folded and cannot be affected by a typo.
# `resolve_year`'s (behind, ahead). The committed programme reached +9 to +15 days on
# 2026-09-19 and this cinema publishes a week or two at a time, so 120 is headroom.
WINDOW = (30, 120)

OUTDOOR_SLUG = "kesakino-"
OUTDOOR_AUD = "KesäKino"

# Attribute quoting is mixed on this page: WordPress emits double quotes, the Johku
# schedule widget emits single. Every attribute regex here has to accept both, which
# cost a live run to find: `<img src='...'>` matched nothing and every poster came back
# empty while the parse otherwise looked healthy.
Q = r'["\']'
ANCHOR_RE = re.compile(r'<a\b[^>]*href=["\'](?:https?://kinoengel\.fi)?(/elokuva/([^"\'/]+)/?)["\'][^>]*>'
                       r'(.*?)</a>', re.S | re.I)
DATE_RE = re.compile(r'(Ma|Ti|Ke|To|Pe|La|Su)\s*(\d{1,2})\.(\d{1,2})\.')
TIME_RE = re.compile(r'klo\s*(\d{1,2})[:.](\d{2})')
IMG_RE = re.compile(r'<img\b[^>]*>', re.I)
SRCSET_RE = re.compile(r'srcset=["\']([^"\']+)["\']')
SRC_RE = re.compile(r'\b(?:data-src|src)=["\']([^"\']+)["\']')
TAGS_RE = re.compile(r"<[^>]+>")
# A premiere card writes the weekday out in full and leaves the time span empty.
COMING_RE = re.compile(r'(?:Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai|Lauantai|'
                       r'Sunnuntai)\s*(\d{1,2})\.(\d{1,2})\.')
NOISE_RE = re.compile(r"Osta liput|Lue lisää[\s›»>]*|Varaa|Liput"
                      r"|klo\s*\d{1,2}[:.]\d{2}"
                      r"|(?:Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai|Lauantai"
                      r"|Sunnuntai|Ma|Ti|Ke|To|Pe|La|Su)\s*\d{1,2}\.\d{1,2}\.", re.I)
# Prefixes this adapter takes off the title itself. Kesäkino because it becomes `aud`;
# the rest stay for strands.apply in run.py.
SELF_PREFIX = ("kesäkino", "kesakino")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s))).strip()


def _biggest(srcset):
    best, bw = "", -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                continue
            if w > bw:
                best, bw = bits[0], w
    return best


def _poster(block):
    m = IMG_RE.search(block)
    if not m:
        return ""
    tag = m.group(0)
    ss = SRCSET_RE.search(tag)
    if ss:
        big = _biggest(ss.group(1))
        if big:
            return big
    src = SRC_RE.search(tag)
    url = src.group(1) if src else ""
    # Elementor ships a transparent placeholder in `src` when it lazy-loads.
    return "" if url.startswith("data:") else url


def _iso(day, month, hh, mm, today=None, weekday=None):
    """A row's `La 29.08.` plus its clock -> an ISO start, or "" when it cannot be placed.

    `common.resolve_year` selects the year and then bounds it. The private loop this
    replaced took the first candidate inside a window rather than the nearest one, so a
    row 46 or more days stale resolved to next year: `1.8.` read on 2026-09-19 published
    as 2027-08-01. The weekday the row prints selects the year outright.
    """
    today = today or datetime.datetime.now(FI).date()
    year = resolve_year(day, month, today, weekday, WINDOW)
    if year is None:
        return ""
    return datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()


def _title(block):
    """Everything in the row that is not the date, the time or the button."""
    return re.sub(r"\s+", " ", NOISE_RE.sub(" ", _txt(block))).strip(" -–·|")


def _strip_outdoor(title):
    low = title.lower()
    for pre in SELF_PREFIX:
        if low.startswith(pre + ":"):
            rest = title[len(pre) + 1:].strip(" -–:")
            if rest:
                return rest
    return title


def parse(page, today=None):
    shows = []
    coming = []
    unplaced = []
    for m in ANCHOR_RE.finditer(page):
        href, slug, block = m.group(1), m.group(2), m.group(3)
        d = DATE_RE.search(block)
        t = TIME_RE.search(block)
        if not (d and t):
            # The page renders the programme twice. The timed listing gives
            # "Pe 05.09." + "klo 21:30" + "Osta liput" and is what this parser wants.
            # A second listing repeats the same screenings with the weekday written out
            # ("Perjantai 02.10.") and an **empty time span**, so those rows cannot be
            # placed in a time-ordered day list and are skipped.
            #
            # Do not read the timeless rows as premieres: on the first live run 44 of
            # the 46 were films that carry a time in the other listing. Only the dates
            # that appear *nowhere* with a time are worth reporting, and on 2026-08-29
            # that was 11.09. and 02.10. Those two are in the date picker, so their
            # times are presumably fetched when the reader picks the date. Reported
            # rather than chased, because a wrong count here would be worse than a
            # missing one and nothing about it is verifiable from this page alone.
            cd = COMING_RE.search(block)
            if cd:
                coming.append((f"{int(cd.group(2)):02d}-{int(cd.group(1)):02d}",
                               _title(block)[:40]))
            continue
        start = _iso(int(d.group(2)), int(d.group(3)),
                     int(t.group(1)), int(t.group(2)), today,
                     weekday_index(d.group(1)))
        if not start:
            unplaced.append(f"{d.group(1)} {d.group(2)}.{d.group(3)}.")
            continue
        outdoor = slug.lower().startswith(OUTDOOR_SLUG)
        title = _title(block)
        if outdoor:
            title = _strip_outdoor(title)
        if not title:
            continue
        shows.append({
            # Never the raw slug: kesakino-autofiktio and autofiktio are one film.
            "eventId": slug[len(OUTDOOR_SLUG):] if outdoor else slug,
            "title": title,
            "original": "",
            "len": "",
            "rating": "",
            "genres": "",
            "method": "",
            "theatre": VENUE["name"],
            "aud": OUTDOOR_AUD if outdoor else "",
            "start": start,
            "url": BASE + href if href.startswith("/") else href,
            "img": _poster(block),
            "lang": "",
            "soldOut": False,
            "price": "",
            "provider": "engel",
            "venue": VENUE["id"],
        })
    # One anchor can appear twice on a page (a carousel and the day list), so drop
    # exact repeats of the same film at the same minute rather than double-counting.
    seen, out = set(), []
    for s in shows:
        k = (s["eventId"], s["start"], s["aud"])
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    out.sort(key=lambda s: s["start"])
    # Only the dates no timed row covers. Everything else is the second listing
    # repeating a screening this parse already has.
    if unplaced:
        print(f"[engel] {len(unplaced)} row(s) whose weekday matches no candidate year "
              f"inside the window, skipped: {', '.join(unplaced[:5])}")
    have = {s["start"][5:10] for s in out}
    orphan = sorted({(md, t) for md, t in coming if md not in have})
    if orphan:
        dates = sorted({md for md, _ in orphan})
        print(f"[engel] {len(dates)} date(s) listed with no time anywhere, skipped: "
              + ", ".join(dates) + " -- "
              + " | ".join(t for _, t in orphan))
    return out


# ---------------------------------------------------------------- film pages
#
# The listing carries title, date, time and poster and nothing else. The film page at
# /elokuva/{slug}/ carries the rating, runtime, genres, languages, original title and
# the cinema's own synopsis, so one request per showing film fills in almost
# everything the listing drops. 17 films on the first run, paced.
#
# What the film page does **not** have is the showtime table. The rows visible in a
# browser (date with year, auditorium, per-screening price, a real booking link) are
# injected by johku.com/widget.js and appear nowhere in the 81 kB of HTML. Its read
# endpoints answer 403 without the key the widget is issued, and lifting that key is
# out of bounds under "Access and ethics". So price, `aud` and a per-show booking URL
# stay empty here, and the two timeless dates stay missing.

DETAIL_RE = re.compile(r'<label>\s*([^<]+?)\s*</label>\s*'
                       r'(?:<span>(.*?)</span>|<div class=["\']contentratings["\']>(.*?)</div>)',
                       re.S | re.I)
GENRE_RE = re.compile(r'class=["\']cmd-desription[^"\']*["\'][^>]*>.*?<h5[^>]*>(.*?)</h5>', re.S | re.I)
SYN_RE = re.compile(r'class=["\']cmd-desription[^"\']*["\'][^>]*>.*?</h5>\s*<p>(.*?)</p>\s*</div>', re.S | re.I)
RATING_CLASS_RE = re.compile(r'class=["\']rating\s+([^"\']+)["\']', re.I)
KESTO_RE = re.compile(r'(?:(\d+)\s*h)?\s*(\d+)\s*min', re.I)

# Finnish language names as this site writes them -> the tag set the client's LN map
# keys on. Swedish is SV, the ISO 639-1 language code, not SE, which is Sweden.
LANGS = {"suomi": "FI", "ruotsi": "SV", "englanti": "EN", "saksa": "DE", "ranska": "FR",
         "espanja": "ES", "italia": "IT", "venäjä": "RU", "viro": "ET", "tanska": "DA",
         "norja": "NO", "islanti": "IS", "japani": "JA", "kiina": "ZH", "korea": "KO"}


# "Ei tekstitystä" is the page saying outright that there are no subtitles (Gråben vs
# Acme, read 2026-09-29): `XX-S`, which the app and the pages show in words. An empty or
# unknown field says nothing and stays blank.
NO_SUBS_RE = re.compile(r"^\s*ei\s+tekstityst\u00e4\s*\.?\s*$", re.I)


def _langs(spoken, subs):
    """"puhuttu kieli: englanti" + "Suomi-Ruotsi" -> "EN-A, FI-S, SE-S";
    "Ruotsi" + "Ei tekstitystä" -> "SV-A, XX-S"."""
    out = []
    for name in re.split(r"[,/;-]| ja ", (spoken or "").split(":")[-1]):
        code = LANGS.get(name.strip().lower())
        if code and f"{code}-A" not in out:
            out.append(f"{code}-A")
    for name in re.split(r"[,/;-]| ja ", subs or ""):
        code = LANGS.get(name.strip().lower())
        if code and f"{code}-S" not in out:
            out.append(f"{code}-S")
    if NO_SUBS_RE.match(subs or ""):
        out.append("XX-S")
    return ", ".join(out)


def details(page):
    """Film-page metadata. Returns {} for anything the page does not carry."""
    d = {}
    fields = {}
    for m in DETAIL_RE.finditer(page):
        label = _txt(m.group(1)).upper()
        if m.group(3) is not None:
            # IKÄRAJA. **The value is in the class, not in the text**: the markup is
            # <span class="rating K-12"><span>Ikäraja ei vielä tiedossa</span></span>,
            # so reading the text gives every film the same placeholder. The sibling
            # spans (seksi, paihteet, vakivalta, kauhu) are KAVI content descriptors,
            # which this app does not render, so only a K-nn or S token is kept.
            for cls in RATING_CLASS_RE.findall(m.group(3)):
                tok = cls.strip().split()[0]
                if re.fullmatch(r"K-\d+|S", tok):
                    d["rating"] = tok
                    break
        else:
            fields[label] = _txt(m.group(2) or "")

    if fields.get("ALKUPERÄINEN NIMI"):
        d["original"] = fields["ALKUPERÄINEN NIMI"]
    kesto = KESTO_RE.search(fields.get("KESTO", ""))
    minutes = int(kesto.group(1) or 0) * 60 + int(kesto.group(2)) if kesto else 0
    # "KESTO 0h 0 min" (Lilla spöket Laban busar vidare, read 2026-10-04) is a field the
    # cinema has not filled in. A card reading "0 min" states a fact that is not one.
    if minutes:
        d["len"] = str(minutes)
    lang = _langs(fields.get("LISÄTIEDOT", "") or fields.get("KIELI", ""),
                  fields.get("TEKSTITYS", ""))
    if lang:
        d["lang"] = lang
    g = GENRE_RE.search(page)
    if g:
        # Published in caps ("KOMEDIA,DRAAMA"). Only a fallback for films TMDB misses,
        # since genres are rendered from `gids`, but a shouting fallback is still worse
        # than a readable one.
        names = [n.strip().capitalize() for n in _txt(g.group(1)).split(",") if n.strip()]
        if names:
            d["genres"] = ", ".join(names)
    syn = SYN_RE.search(page)
    if syn:
        text = _txt(syn.group(1))
        # Placed per text: the `BARNSÖNDAGAR` pages carry a Swedish synopsis, the rest
        # Finnish, and no page declares which (read 2026-09-24). Unplaceable is withheld.
        lang = syn_language(text) if len(text) > 40 else ""
        if lang:
            # `_syn` is stripped by run.py after synmerge folds it into
            # films-extra.json; a synopsis repeated across every showtime would add
            # tens of kB to the venue file.
            d["_syn"] = {lang: text}
    return d


def enrich(shows, get=None):
    """One film page per distinct film, folded onto its showtimes."""
    # The film pages answered 500 with their metadata intact on the day the listing did,
    # and `details()` returning nothing is already the "no metadata" path below, so a body
    # that is an error page after all costs a row its rating and nothing more.
    get = get or tolerant_get
    by_url = {}
    for s in shows:
        by_url.setdefault(s["url"], []).append(s)
    ok = fail = 0
    for n, (url, rows) in enumerate(capped(sorted(by_url.items()), 'engel')):
        if n:
            time.sleep(0.5)
        try:
            d = details(get(url))
        except Exception as e:
            fail += 1
            print(f"[engel] detail {url.rsplit('/', 2)[-2]}: {type(e).__name__}: {e}")
            continue
        if not d:
            fail += 1
            print(f"[engel] detail {url.rsplit('/', 2)[-2]}: nothing parsed")
            continue
        ok += 1
        for s in rows:
            for k, v in d.items():
                if v and not s.get(k):
                    s[k] = v
    print(f"[engel] film pages: {ok} parsed, {fail} with nothing usable, "
          f"{sum(1 for s in shows if s.get('rating'))}/{len(shows)} showtimes rated")
    return shows


# The smallest body that has ever carried this programme. The live page is 126 kB and the
# challenge shell is 12 kB, so this separates them by an order of magnitude rather than a
# margin.
MIN_BYTES = 20000

# Two markers the parse does not use to find its rows, so a body that has them and still
# parses to nothing is a broken parse rather than an empty programme. `/elokuva/` is the
# film-link path every row is built on and `Osta liput` is the buy label beside each time.
MARKERS = ("/elokuva/", "Osta liput")


# The second way this host fails. Since 2026-09-21 it also accepts the connection and
# closes it without sending a response, which `http.client` raises as RemoteDisconnected
# and `urllib` sometimes hands on inside a URLError. `common.fetch` retries every
# exception, so the listing was already tried three times, 5 s and 10 s apart, and on
# 2026-09-22 02:15, 2026-09-23 02:15 and twice more all three attempts fell inside the
# same bad window and the run failed.
#
# Nothing can be rescued here the way a 500's body is rescued below: a closed connection
# carries no body to weigh. Waiting longer is the only lever. Probed 2026-09-23 from an
# ordinary connection, six requests 4 s apart: six 200s, 126,219 bytes each, 0.3-0.4 s. The
# host is healthy between the windows, so the windows are short and a slower second round
# is likely to clear them.
#
# Three more attempts 20 s and 40 s apart, so the listing is given about a minute before
# the site is called down, against the 15 s it had. It still fails closed: when the site is
# really gone this reports the same failure a minute later, and the previous file stands.
#
# The listing only. `enrich()` already counts a film-page failure and moves on, costing
# that row its metadata and nothing else, and a cinema showing 30 films would otherwise be
# made to wait a minute per page for metadata it can do without.
DROPPED = (http.client.RemoteDisconnected, ConnectionResetError)
PATIENT_TRIES = 3
PATIENT_BACKOFF = 20


def dropped(e):
    """Did the connection close without an answer, rather than the site answering? -> bool

    An HTTPError is an answer and is never this, which matters because it is a URLError
    too. A URLError's `reason` is where urllib puts the original socket error.
    """
    if isinstance(e, urllib.error.HTTPError):
        return False
    if isinstance(e, DROPPED):
        return True
    return isinstance(e, urllib.error.URLError) and isinstance(e.reason, DROPPED)


def patient_get(url, **kw):
    """`get_text`, with a slower second round when the connection was closed on us."""
    try:
        return get_text(url, fetcher=fetch, **kw)
    except Exception as e:
        if not dropped(e):
            raise
        print(f"[engel] {url}: the connection was closed without a response; "
              f"{PATIENT_TRIES} more attempt(s), {PATIENT_BACKOFF}s apart")
        kw = {**kw, "tries": PATIENT_TRIES, "backoff": PATIENT_BACKOFF}
        return get_text(url, fetcher=fetch, **kw)


def tolerant_get(url, tries=2, backoff=3, timeout=20):
    """This site's pages, read through a 500 when the 500 still carries them.

    `common.fetch` throws an error response's body away unread, which is the right
    default everywhere else. Only 500 is tolerated, only here, and only after `usable`
    has weighed the body; every other status still raises.
    """
    try:
        return get_text(url, fetcher=fetch, tries=tries, backoff=backoff, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code != 500:
            raise
        return get_text(url, fetcher=fetch, tries=1, timeout=timeout, keep_body_on=(500,))


def usable(page):
    """Is this body the programme? -> (bool, reason). Size, markers, then a real parse."""
    if len(page) < MIN_BYTES or "sgcaptcha" in page:
        return False, f"{len(page)} bytes, below the {MIN_BYTES}-byte floor or challenged"
    missing = [m for m in MARKERS if m not in page]
    if missing:
        return False, f"{len(page)} bytes without {', '.join(missing)}"
    return True, ""


def fetch_page():
    """One page, with one guarded retry when the site answers 500 but serves the schedule.

    Read 2026-09-21: `kinoengel.fi` began answering **HTTP 500 with the complete
    programme**, 126 kB that parses to 25 timed screenings over 5 dates, the same rows a
    reader sees. `common.fetch` throws an error response's body away unread, which is the
    right default and stays the default; this asks for the 500's body back and then has to
    earn it, because an error page and a programme are not told apart by the status alone.

    A closed connection is the site's other failure since 2026-09-21 and is handled
    before this, in `patient_get`: there is no body to weigh, so the only answer is to
    wait longer before giving up. See the note above `DROPPED`.

    Three checks, and the row count is deliberately the last: a body that is big enough
    and carries the markers the parse does not key on, and still yields no screening, is a
    broken parse rather than a cinema with nothing on, and it fails the site the way a
    refused fetch does. Only 500 is tolerated, only for this site, and the log says so on
    every run so this cannot quietly become normal.
    """
    try:
        page = patient_get(URL)
    except urllib.error.HTTPError as e:
        if e.code != 500:
            raise
        page = get_text(URL, fetcher=fetch, tries=1, keep_body_on=(500,))
        ok, why = usable(page)
        if not ok:
            raise RuntimeError(f"{URL}: HTTP 500 and the body is not the programme "
                               f"({why}); the previous file stands") from e
        shows = enrich(parse(page))
        if not shows:
            raise RuntimeError(f"{URL}: HTTP 500 with a body that looks like the "
                               f"programme ({len(page)} bytes, markers present) and no "
                               f"screening parsed out of it, which is a broken parse "
                               f"rather than an empty programme") from e
        print(f"[engel] the site answered 500 and served the programme anyway: "
              f"{len(page)} bytes, {len(shows)} showtimes. Published, because the body "
              f"passed the size, marker and row checks; see fetch_page()")
        return shows
    ok, why = usable(page)
    if not ok:
        raise RuntimeError(f"challenged (needs a residential IP): {why}")
    return enrich(parse(page))


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one venue."""
    return {VENUE["id"]: fetch_page()}


# Next pass, deliberately not in this one: wp/v2/elokuva?slug[]=... with
# _embed=wp:featuredmedia gives the cinema's own Finnish synopsis (`content.rendered`,
# which synmerge prefers over TMDB) and a full-size poster, for the ~40 films
# showing rather than all 899. One request, keyed by the slugs this parse already has.

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = parse(open(src, encoding="utf-8", errors="replace").read()) if src else fetch_page()
    films = {s["eventId"] for s in data}
    outdoor = [s for s in data if s["aud"] == OUTDOOR_AUD]
    dates = sorted({s["start"][:10] for s in data})
    print(f"{len(data)} showtimes, {len(films)} films, {len(dates)} dates "
          f"({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}), "
          f"{len(outdoor)} KesäKino, {sum(1 for s in data if s['img'])} with a poster")
    for s in data:
        print(f"  {s['start'][:16]}  {s['title'][:38]:40} {s['aud']:9} {s['eventId'][:28]}")
