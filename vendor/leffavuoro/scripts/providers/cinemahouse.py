"""Cinemahouse: the WordPress `cinema-reservations` plugin. Stdlib only.

Three cinemas run it under a `cinemahouse-child` theme on GeneratePress: Kino
Piispanristi in Kaarina, Kino Lumo in Salo and Laitilan Kino in Laitila (the last on an
older build of the child theme, with the same plugin markup). Each is one venue, and the
whole programme is server-rendered on the front page, so the schedule is one request per
site.

The front page carries two panels of the same data. `cr-movie-tile` is the film grid,
with the poster, the age limit, the runtime, the genres and the film-page link;
`cr-screening-row` is the screening list, one row per screening with the date, time,
room, price, free seats and the reservation link. The rows carry no film id, so the two
are joined on the normalised title.

What shapes the parser:

  * **A row's date has no year.** "15.9. 13:00 · Sali 1" is the whole of it, and the
    programme reaches months out (Laitila publishes fortnightly to mid-December). The
    year comes from the nearest-year rule `orion._iso` uses, never from the current year.
  * **The film page's JSON-LD is not the time source.** Laitilan Kino's older theme
    stamps `startDate` with `+00:00` on a 13:00 Helsinki screening while the rendered
    clock is right, so the rendered wall clock is what is read and what a visitor sees.
    Read 2026-09-14; Piispanristi and Lumo write `+03:00`.
  * **`eventId` is the normalised title, not the film slug.** A strand gets its own
    WordPress post ("ENNAKKONÄYTÖS: Dyyni: Osa kolme" against the plain run), and
    `strands.apply` takes that prefix off the title in run.py afterwards, so a slug id
    would leave one film as two cards under one name. `synmerge.norm` of the title with
    the strand already off is the key `normTitle` and the synopsis cache use. Same
    reasoning as Kino Tapiola's per-run slugs.
  * **Screenings are deduplicated on the plugin's own screening id.** The three sites
    render each row once today (175 / 71 / 7 rows, as many distinct ids), but the id is
    what a repeated surface would repeat, and it is unique inside a site only, so it is
    never compared across sites. A row with no reservation link falls back to the film,
    start and room.
  * **Seat counts are read and not published**, the rule since 2026-08-30: "Vapaat
    paikat: 89 / 95" only decides `soldOut`.
  * **The audio language is in the title.** The cinemas publish a dubbed run and a
    subtitled run as separate films, marked by a trailing capitalised SUOMEKSI or
    ENGLANNIKSI. That is the cinema's own statement about the audio, so it becomes
    `lang`; the title itself is stored verbatim, because it is the merge key.

An empty programme is decided on the filter `<select>`, which the plugin renders from
its own screening dates and which nothing in the film parse reads: the template intact,
no `date:` option in it, no screening row and no film tile is a cinema with nothing on.
A page that still lists films, or still offers a day, and parses to zero rows is a
broken parse and fails the site.
"""
import datetime
import html as html_mod
import re
import sys
import time
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import synmerge
from common import EmptyProgramme, capped, fetch, get_text, resolve_year, served
from strands import split as split_strand

FI = ZoneInfo("Europe/Helsinki")

# `base` is the host read and the key run.py paces on; each site is its own host, so the
# three are read at the same time and each one request at a time. `notes` are the stems
# synmerge uses to drop a screening note from a synopsis, so a paragraph naming the
# cinema does not reach the slot every chain showing that film reads from.
SITES = [
    {"provider": "kinopiispanristi", "label": "Kino Piispanristi",
     "base": "https://www.kinopiispanristi.fi", "notes": ("Piispanristi",),
     "venues": [{"id": "piispanristi-kaarina", "provider": "kinopiispanristi",
                 "name": "Kino Piispanristi", "short": "Kino Piispanristi",
                 "city": "Kaarina"}]},
    {"provider": "kinolumo", "label": "Kino Lumo",
     "base": "https://www.kinolumo.fi", "notes": ("Kino Lumo",),
     "venues": [{"id": "lumo-salo", "provider": "kinolumo",
                 "name": "Kino Lumo", "short": "Kino Lumo", "city": "Salo"}]},
    {"provider": "laitilankino", "label": "Laitilan Kino",
     "base": "https://www.laitilankino.fi", "notes": ("Laitila",),
     "venues": [{"id": "laitilankino-laitila", "provider": "laitilankino",
                 "name": "Laitilan Kino", "short": "Laitilan Kino", "city": "Laitila"}]},
]


def _cls(tag, name):
    """An opening `<tag>` whose class list holds exactly `name`.

    The lookarounds refuse a longer class with the same prefix, so `cr-screening-row`
    does not match `cr-screening-row-compact` if the plugin ever ships one.
    """
    return (r"<" + tag + r"\b[^>]*\bclass=\"[^\"]*(?<![\w-])"
            + name + r"(?![\w-])[^\"]*\"[^>]*>")


# The one element that survives an empty programme: the filter is rendered even when
# nothing matches, while the tab bar and the screenings list are not. Its absence is a
# changed template, not an empty cinema.
FILTER_RE = re.compile(_cls("select", "cr-movies-filter-select"), re.I)
DAY_OPTION_RE = re.compile(r"<option\b[^>]*\bvalue=\"date:(\d{4}-\d{2}-\d{2})\"", re.I)

ROW_OPEN = _cls("div", "cr-screening-row")
DAY_HEADER = _cls("div", "cr-screening-day-header")
# A row ends where the next row or the next day heading begins. The last row's slice
# runs to the end of the document; every field below is scoped to a `cr-screening-*`
# class, none of which the page carries outside a row, so the trailing markup is inert.
ROW_RE = re.compile(ROW_OPEN + r"(.*?)(?=" + ROW_OPEN + r"|" + DAY_HEADER + r"|\Z)",
                    re.S | re.I)
ROW_TITLE_RE = re.compile(_cls("div", "cr-screening-title") + r"(.*?)</div>", re.S | re.I)
ROW_META_RE = re.compile(_cls("div", "cr-screening-meta") + r"(.*?)</div>", re.S | re.I)
ROW_PRICE_RE = re.compile(_cls("div", "cr-screening-price") + r"(.*?)</div>", re.S | re.I)
ROW_SEATS_RE = re.compile(_cls("div", "cr-screening-seats") + r"(.*?)</div>", re.S | re.I)
CTA_RE = re.compile(r"<a\b([^>]*(?<![\w-])cr-screening-cta(?![\w-])[^>]*)>", re.I)
SCREENING_ID_RE = re.compile(r"data-screening-id=\"(\d+)\"", re.I)
# `data-embed-url` carries the same screening id and must not answer for the link, so
# the attribute name is matched with its own boundary.
HREF_RE = re.compile(r"(?:^|\s)href\s*=\s*\"([^\"]+)\"", re.I)

TILE_RE = re.compile(_cls("article", "cr-movie-tile") + r"(.*?)</article>", re.S | re.I)
TILE_LINK_RE = re.compile(r"<a\b[^>]*(?<![\w-])cr-movie-tile__link(?![\w-])[^>]*>", re.I)
TILE_TITLE_RE = re.compile(_cls("h3", "cr-movie-tile__title") + r"(.*?)</h3>", re.S | re.I)
TILE_META_RE = re.compile(_cls("div", "cr-movie-tile__meta") + r"(.*?)</div>", re.S | re.I)
AGE_RE = re.compile(r"<span\b[^>]*(?<![\w-])cr-badge--age(?![\w-])[^>]*>(.*?)</span>",
                    re.S | re.I)
RUNTIME_RE = re.compile(r"<span\b[^>]*(?<![\w-])cr-badge--runtime(?![\w-])[^>]*>(.*?)</span>",
                        re.S | re.I)
IMG_SRC_RE = re.compile(r"<img\b[^>]*?(?:^|\s)src\s*=\s*\"([^\"]+)\"", re.I)

# "15.9. 13:00 · Sali 1": the date and clock a visitor reads, and the room after the
# separator. Both halves are the plugin's, so the separator is the split point rather
# than a guess about where a room name starts.
WHEN_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2})[:.](\d{2})")
# `resolve_year`'s (behind, ahead). The three sites' committed programmes reached +89
# days on 2026-09-19, Laitila publishing fortnightly to mid-December, so 180 is twice
# the widest span seen and half the 365 a year's slip would need.
WINDOW = (30, 180)
SEPARATOR = "\u00b7"
FREE_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
EUR_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\u20ac|eur\b)", re.I)
MIN_RE = re.compile(r"(\d+)\s*min\b", re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# The film page's synopsis. The `cr-prose` block holds paragraphs and no nested div.
PROSE_RE = re.compile(_cls("div", "cr-prose") + r"(.*?)</div>", re.S | re.I)

# A trailing capitalised language marker. The cinemas publish "Kojootti vs. ACME
# SUOMEKSI" and "Kojootti vs. ACME ENGLANNIKSI" as two films, which is a statement about
# the audio and not an inference from a word inside a title.
AUDIO_SUFFIX = {"SUOMEKSI": "FI-A", "ENGLANNIKSI": "EN-A"}


class _Empty:
    """Stands in for a regex match that is not there, so an optional cell reads the same
    way as a present one."""

    @staticmethod
    def group(_):
        return ""


_EMPTY = _Empty()


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _iso(day, month, hh, mm, today=None):
    """`15.9.` plus a clock -> an ISO start, or "" when the date cannot be placed.

    `common.resolve_year` picks the nearest occurrence and then bounds it. These rows
    print no weekday, so nearest is the whole rule: a January row read in December is
    next January because that is nearer than the one eleven months back.

    The private loop this replaced took the first candidate inside a -45..+320 window
    rather than the nearest one, and tried the current year first, so a row 46 or more
    days stale skipped to next year: `1.8.` read on 2026-09-19 published as 2027-08-01.
    """
    today = today or datetime.datetime.now(FI).date()
    year = resolve_year(day, month, today, None, WINDOW)
    if year is None:
        return ""
    return datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()


def _price(cell):
    """"12,00 €" -> "12€", eTiketti's format, which the app and the pages render as is.

    A trailing zero is only stripped from a decimal amount: "10" must not become "1".
    Text with no amount is passed through, so a free screening keeps its own words.
    """
    text = _txt(cell)
    m = EUR_RE.search(text)
    if not m:
        return text
    v = m.group(1).replace(",", ".")
    if "." in v:
        v = v.rstrip("0").rstrip(".")
    return f"{v}\u20ac"


def _sold_out(cell):
    """"Vapaat paikat: 89 / 95" -> False. The counts themselves are never published:
    the data is hours old by the time it is read, and a count carries the authority of
    a figure while a sold-out mark survives staleness."""
    m = FREE_RE.search(_txt(cell))
    return bool(m) and int(m.group(1)) == 0


def _rating(badge):
    """The age badge is a bare "12", "7" or "S". Anything else blanks.

    Whitelisted the way Finnkino's classification is: an unrecognised value rendered
    inside the age chip and failed every `rating ===` comparison in the client.
    """
    b = _txt(badge).upper()
    if b == "S":
        return "S"
    m = re.fullmatch(r"K?\s*-?\s*(\d{1,2})", b)
    return f"K-{m.group(1)}" if m else ""


def _minutes(badge):
    m = MIN_RE.search(_txt(badge))
    return m.group(1) if m else ""


def _audio(title):
    """-> "FI-A", "EN-A" or "". The marker has to be the title's last word."""
    parts = _txt(title).split()
    return AUDIO_SUFFIX.get(parts[-1], "") if parts else ""


def _ticket(base, href):
    """The row's reservation link, resolved against the site. -> absolute http(s) URL.

    A bare path stored here reaches the client as a bare path and the browser resolves
    it against leffavuoro.fi, which is the Cinema Orion incident of 2026-09-06. A row
    with no link falls back to the cinema's programme page.
    """
    home = base.rstrip("/") + "/"
    url = urljoin(home, html_mod.unescape(href)) if href else home
    parts = urlsplit(url)
    return url if parts.scheme in ("http", "https") and parts.netloc else home


# ---------------------------------------------------------------- parse

def parse_days(page):
    """The dates the filter offers. -> [YYYY-MM-DD].

    The plugin builds this list from its own screenings, and nothing in the film parse
    reads it, which is what makes an empty list evidence rather than a second reading of
    the same silence.
    """
    return DAY_OPTION_RE.findall(page)


def parse_films(page):
    """The film grid. -> {normalised title: {url, img, rating, len, genres}}.

    Keyed on `synmerge.norm` of the published title rather than on the exact string:
    the rows and the tiles are rendered from one record but not from one template, and
    a doubled space already differs between them.
    """
    out = {}
    for block in TILE_RE.findall(page):
        t = TILE_TITLE_RE.search(block)
        title = _txt(t.group(1)) if t else ""
        if not title:
            continue
        a = TILE_LINK_RE.search(block)
        href = HREF_RE.search(a.group(0)) if a else None
        img = IMG_SRC_RE.search(block)
        meta = TILE_META_RE.search(block)
        out.setdefault(synmerge.norm(title), {
            "url": html_mod.unescape(href.group(1)) if href else "",
            "img": html_mod.unescape(img.group(1)).split("?")[0] if img else "",
            "rating": _rating((AGE_RE.search(block) or _EMPTY).group(1)),
            "len": _minutes((RUNTIME_RE.search(block) or _EMPTY).group(1)),
            "genres": _txt(meta.group(1)) if meta else "",
        })
    return out


def parse_screenings(page):
    """The screening list. -> [{title, day, month, hh, mm, aud, price, soldOut, sid, href}].

    A row the clock cannot be read out of is returned with `hh` None, so the caller can
    tell one odd row from a template that moved.
    """
    rows = []
    for block in ROW_RE.findall(page):
        t = ROW_TITLE_RE.search(block)
        meta = ROW_META_RE.search(block)
        if not t or not meta:
            continue
        head, _, room = _txt(meta.group(1)).partition(SEPARATOR)
        when = WHEN_RE.search(head)
        cta = CTA_RE.search(block)
        attrs = cta.group(1) if cta else ""
        sid = SCREENING_ID_RE.search(attrs)
        href = HREF_RE.search(attrs)
        rows.append({
            "title": _txt(t.group(1)),
            "day": int(when.group(1)) if when else None,
            "month": int(when.group(2)) if when else None,
            "hh": int(when.group(3)) if when else None,
            "mm": int(when.group(4)) if when else None,
            "aud": room.strip(),
            "price": _price((ROW_PRICE_RE.search(block) or _EMPTY).group(1)),
            "soldOut": _sold_out((ROW_SEATS_RE.search(block) or _EMPTY).group(1)),
            "sid": sid.group(1) if sid else "",
            "href": html_mod.unescape(href.group(1)) if href else "",
        })
    return rows


def parse_film(page, notes=()):
    """A film page -> the cinema's own Finnish synopsis, or "".

    Screening notes are dropped at the paragraph boundary, the rule `synmerge` already
    applies to Gilda: a paragraph quoting a price or naming the cinema describes one
    cinema's screening and must not reach the slot every chain showing the film reads.
    """
    m = PROSE_RE.search(page)
    if not m:
        return ""
    text = synmerge.drop_notes_html(m.group(1), notes)
    return text if len(text) > 40 else ""


# ---------------------------------------------------------------- normalise

def normalise(rows, films, site, today=None):
    """Parsed rows plus the film grid -> [common.Show], sorted by start.

    Deduplicated on the plugin's screening id, which is unique inside a site and
    meaningless across sites, so the key never leaves this site. A row with no
    reservation link has no id either and falls back to the film, start and room.
    """
    venue = site["venues"][0]
    out, seen, skipped = [], set(), 0
    for r in rows:
        if not r["title"] or r["hh"] is None:
            skipped += 1
            continue
        start = _iso(r["day"], r["month"], r["hh"], r["mm"], today)
        if not start:
            skipped += 1
            continue
        film = films.get(synmerge.norm(r["title"])) or {}
        # The strand comes off before the id is taken, because run.py takes it off the
        # title afterwards: "ENNAKKONÄYTÖS: Dyyni: Osa kolme" and the plain run are one
        # film and have to share one card.
        eid = synmerge.norm(split_strand(r["title"])[0])
        key = ("sid", r["sid"]) if r["sid"] else ("row", eid, start, r["aud"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "eventId": eid,
            "title": r["title"],
            "original": "",
            "len": film.get("len", ""),
            "rating": film.get("rating", ""),
            "genres": film.get("genres", ""),
            "method": "",
            "theatre": venue["name"],
            "aud": r["aud"],
            "start": start,
            "url": _ticket(site["base"], r["href"]),
            "img": film.get("img", ""),
            "lang": _audio(r["title"]),
            "soldOut": r["soldOut"],
            "price": r["price"],
            "provider": site["provider"],
            "venue": venue["id"],
            "movieUrl": film.get("url", ""),
        })
    if skipped:
        print(f"[{site['provider']}] {skipped} screening row(s) with no readable date, "
              f"or none a candidate year places inside the window, skipped")
    out.sort(key=lambda s: s["start"])
    return out


def parse(page, site, today=None):
    """The front page -> [common.Show]. Raises on a changed template or a broken parse.

    `EmptyProgramme` only on the plugin's own evidence: the filter is there, it offers
    no day, and neither panel holds anything. A page that still lists a film or still
    offers a day and yields no screening is the broken case CLAUDE.md requires to keep
    failing, because it is what a markup change upstream looks like.
    """
    if not FILTER_RE.search(page):
        raise RuntimeError(
            f"no cr-movies-filter-select on the page ({served(page)}), so this is not the "
            f"programme this parser reads. Treating it as a fetch or template failure "
            f"rather than a cinema with nothing on")
    films = parse_films(page)
    rows = parse_screenings(page)
    if not rows:
        days = parse_days(page)
        if films or days:
            raise RuntimeError(
                f"no screening row parsed while the page offers {len(days)} day(s) and "
                f"{len(films)} film(s) ({served(page)}): a page that lists films and "
                f"yields no screening is the broken case, whatever produced it")
        raise EmptyProgramme(f"{site['label']}: the filter offers no day and the "
                             f"programme lists no film")
    shows = normalise(rows, films, site, today)
    if not shows:
        raise RuntimeError(f"{len(rows)} screening row(s) and none parsed "
                           f"({served(page)}): the rows are there and their shape is not")
    return shows


# ---------------------------------------------------------------- fetch

def get(url):
    """One page. `cache=True` is the correct way to ask and costs nothing here: measured
    2026-09-14, all three origins answer LiteSpeed with no ETag and no Last-Modified, so
    `common.fetch` writes no cache entry for them."""
    return get_text(url, fetcher=fetch)


def enrich(shows, site, get=get, sleep=1.0):
    """One film page per film, for the cinema's own Finnish synopsis.

    An enrichment loop, so `common.capped` trims it rather than raising: the schedule is
    already parsed and a film past the cap loses its synopsis for one run. Nothing else
    on the film page is read; the grid already carries the poster, the age limit, the
    runtime and the genres, so a failed page costs the synopsis alone.
    """
    by_url = {}
    for s in shows:
        if s.get("movieUrl"):
            by_url.setdefault(s["movieUrl"], []).append(s)
    ok = fail = 0
    for n, (url, rows) in enumerate(capped(sorted(by_url.items()), site["provider"])):
        if n:
            time.sleep(sleep)
        try:
            syn = parse_film(get(url), site.get("notes", ()))
        except Exception as e:
            fail += 1
            print(f"[{site['provider']}] film page {url.rstrip('/').rsplit('/', 1)[-1]} "
                  f"failed: {type(e).__name__}: {e}")
            continue
        if not syn:
            fail += 1
            continue
        ok += 1
        for s in rows:
            if not s.get("_syn"):
                s["_syn"] = syn
    print(f"[{site['provider']}] film pages: {ok} with a synopsis, {fail} without, "
          f"{len(by_url)} films")
    return shows


def fetch_site(site):
    """Runner contract: one front page per site, one venue, then the film pages."""
    shows = parse(get(site["base"].rstrip("/") + "/"), site)
    enrich(shows, site)
    return {site["venues"][0]["id"]: shows}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    site = next((s for s in SITES if s["provider"] == args[0]), SITES[0]) if args else SITES[0]
    src = args[1] if len(args) > 1 else ""
    if src:
        page = open(src, encoding="utf-8", errors="replace").read()
        data = parse(page, site)
    else:
        data = fetch_site(site)[site["venues"][0]["id"]]
    dates = sorted({s["start"][:10] for s in data})
    print(f"{site['label']}: {len(data)} showtimes, {len({s['eventId'] for s in data})} "
          f"films, {len(dates)} dates ({dates[0] if dates else '-'} .. "
          f"{dates[-1] if dates else '-'})")
    for s in data:
        print(f"  {s['start'][:16]}  {s['title'][:36]:38} {s['aud']:10} "
              f"{s['price']:8} {s['rating']:5} {s['len']:4} {s['lang']:6} "
              f"{s['url'].rsplit('=', 1)[-1]}")
