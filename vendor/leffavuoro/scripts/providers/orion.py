"""Cinema Orion (Helsinki, Eerikinkatu 15, run by ELKE ry): front page table. Stdlib only.

Everything is server-rendered on one page: a `<table class="kinola-day">` per day, one
`<tr>` per screening with date, time, title, price and the ticket link. One request.

  * Ticket URLs come from the markup, never built, but they are resolved against the
    site before they are stored. The site published absolute orion.kinola.ee links until
    2026-09-06 and now publishes site-relative ones (`/checkout/{uuid}`); a bare path
    reaches the client as a bare path, and the browser resolves it against leffavuoro.fi,
    which answers 404. urljoin leaves an absolute link alone, so festival screenings
    keep pointing at the festival's own box office (Espoo Ciné ->
    boxoffice.espoocine.fi). A row with no link (free admission) falls back to the
    programme page.
  * The price cell's `title` attribute carries the ticket-type breakdown, so a screening
    with cheaper types reads "alkaen 8.5€".

The title cell has two shapes:

    <td class='title'> Espoo Ciné: Four Minus Three </td>
    <td class='title'><a href='/elokuvat/{slug}/' title ="Film"> Film
      <span class="descrption">Finnish blurb<span> </a></td>

In the linked shape the title is read from the anchor's `title` attribute, not the cell
text, which would glue the blurb onto the title and split one film into one "film" per
blurb. `descrption` is the site's spelling and its inner `<span>` is never closed. The
blurb is an event note ("Klubialennus, viimeinen näytös."), not a description, so it is
never `_syn`: the film page's own description is (see `page_synopsis`).

`eventId` is the film page slug where there is one; festival rows fall back to a slug of
the title. A known event prefix ("Espoo Ciné:", "Pieni elokuvakerho:") is split off into
`method` from the shared list in `strands.py`, matched exactly, never as a colon pattern.
Third-party events (festivals, HopeaCine, Orion Club) are real screenings here and stay
in the data with the title stored exactly as published, so norm() keys agree with the
client.

Single screen, so `aud` stays blank. No age limits, runtimes or seat counts in the table;
the TMDB pass fills what it can.

Language (2026-09-23): each film page the table links to states `Kieli:` and
`Tekstitys:` for the film, so `film_language` reads those pages after the table, one per
film, at most FILM_MAX a run and paced, through `prices.enrich`'s cache and cap into
data/film-lang-orion.json. The value is the film's, put on each of its screenings, so a
film whose screenings differ in title or whose note names a version settles nothing.
Probe: docs/research/screening-language-sources.md.
"""
import datetime, html as html_mod, os, re, sys, unicodedata
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import prices
from common import fetch, get_text, resolve_year, syn_language, weekday_index
from etiketti import strict_codes
from huvimylly import KAVI_CODES
from strands import split as split_strand

URL = "https://cinemaorion.fi/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "or-helsinki", "provider": "orion", "name": "Cinema Orion",
         "short": "Cinema Orion", "city": "Helsinki"}

# Single screen, so one site with one venue. See run.py for the contract.
#
# `base` names the host this site is read from, which is the runner's pacing key. Nothing
# here reads it -- fetch_site reads URL above and nothing else -- and it was absent until
# 2026-09-15, when `run_cloud.py` started grouping hosts across modules and every base-less
# site landed in one shared group. One request, to cinemaorion.fi, verified before this was
# written.
SITES = [{"provider": "orion", "label": "Cinema Orion", "base": URL,
          "venues": [VENUE]}]

# `resolve_year`'s (behind, ahead). The committed programme reached -1 to +29 days on
# 2026-09-19 and this cinema publishes about eleven dates at a time, so 120 is headroom.
WINDOW = (30, 120)

# <h3><span>Torstai</span> 27.08.</h3> then <table class="kinola-day">...
BLOCK_RE = re.compile(r'<h3\b[^>]*>(?P<head>.*?)</h3>'
                      r'|<table\b[^>]*class=["\'][^"\']*kinola-day[^"\']*["\'][^>]*>'
                      r'(?P<table>.*?)</table>', re.S | re.I)
ROW_RE = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.S | re.I)
CELL_RE = re.compile(r'<td\b([^>]*)>(.*?)</td>', re.S | re.I)
CLASS_RE = re.compile(r'class=["\']([^"\']*)["\']', re.I)
ANCHOR_RE = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S | re.I)
# To the quote that opened it: titles carry apostrophes (`title ="Don't Look Back"`).
TITLE_ATTR_RE = re.compile(r'title\s*=\s*(["\'])(.*?)\1', re.I | re.S)
HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)
SLUG_URL_RE = re.compile(r'/elokuv[au]t?/([^/?#"\']+)', re.I)
# The site spells it "descrption", and the span inside it is never closed, so stop at
# whatever tag comes next rather than at a </span> that may not exist.
DESCR_RE = re.compile(r'<span[^>]*class=["\'][^"\']*descrption[^"\']*["\'][^>]*>'
                      r'(.*?)(?:</span>|<span\b[^>]*>|</a>|$)', re.S | re.I)
# The live date cell reads `Torstai 27.08.`; the day heading above the table carries
# the same shape. The weekday is optional because the cell has been seen without one.
DATE_RE = re.compile(r'(?:([A-Za-zÄÖÅäöå]{2,})\s+)?(\d{1,2})\.(\d{1,2})\.')
TIME_RE = re.compile(r'(\d{1,2})[:.](\d{2})')
EUR_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:€|eur\b)', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _slug(title):
    """Fallback id for a row with no film page. NFKD rather than a hand-written accent
    table: festival programmes bring accents no fixed table anticipates."""
    s = unicodedata.normalize("NFKD", _txt(title).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "naytos"


def _ticket(href):
    """The row's ticket link, resolved against the site. See the module docstring: the
    site moved to site-relative paths, and a bare path stored here becomes a leffavuoro.fi
    link in the client, because safeUrl passes a scheme-less URL through. An absolute
    href, including a festival's own box office, comes back unchanged."""
    return urljoin(URL, href) if href else URL


def _num(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _price(cell_text, breakdown):
    """Display price. Several ticket types -> "alkaen {cheapest}€"."""
    amounts = sorted({float(a.replace(",", "."))
                      for a in EUR_RE.findall(f"{cell_text} {breakdown}")})
    if len(amounts) > 1:
        return f"alkaen {_num(amounts[0])}\u20ac"
    if amounts:
        return f"{_num(amounts[0])}\u20ac"
    return _txt(cell_text)          # "Vapaa pääsy" and anything else non-numeric


def _film(cell_html):
    """Title cell -> (title, blurb, slug, film page URL). Two shapes, see the module
    docstring."""
    a = ANCHOR_RE.search(cell_html)
    if not a:
        return _txt(cell_html), "", "", ""
    attrs, inner = a.group(1), a.group(2)
    d = DESCR_RE.search(inner)
    blurb = _txt(d.group(1)) if d else ""
    ta = TITLE_ATTR_RE.search(attrs)
    # The attribute is the film title on its own. Without it, cut the anchor text at
    # the blurb span rather than flattening the whole cell.
    title = html_mod.unescape(ta.group(2)).strip() if ta else _txt(inner.split("<span")[0])
    href = HREF_RE.search(attrs)
    sm = SLUG_URL_RE.search(href.group(1)) if href else None
    page = urljoin(URL, html_mod.unescape(href.group(1))) if sm else ""
    return title, blurb, (sm.group(1) if sm else ""), page


def _iso(day, month, hh, mm, today=None, weekday=None):
    """The table carries no year -> an ISO start, or "" when the date cannot be placed.

    `common.resolve_year` selects the year and then bounds it. The private loop this
    replaced took the first candidate inside a window rather than the nearest one, so a
    row 46 or more days stale resolved to next year: `1.8.` read on 2026-09-19 published
    as 2027-08-01. Where the cell or the heading prints a weekday it selects the year.
    """
    today = today or datetime.datetime.now(FI).date()
    year = resolve_year(day, month, today, weekday, WINDOW)
    if year is None:
        return ""
    return datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()


def _cells(row):
    """{class: (attrs, inner_html)} for one <tr>. Cell order is not assumed."""
    out = {}
    for attrs, inner in CELL_RE.findall(row):
        cls = CLASS_RE.search(attrs)
        for name in (cls.group(1).split() if cls else []):
            out.setdefault(name, (attrs, inner))
    return out


def parse(page, today=None):
    shows, heading, unplaced = [], "", []
    for m in BLOCK_RE.finditer(page):
        if m.group("head") is not None:
            heading = _txt(m.group("head"))
            continue
        for row in ROW_RE.findall(m.group("table")):
            cells = _cells(row)
            title, blurb, slug, film_page = _film(cells.get("title", ("", ""))[1])
            title, strand = split_strand(title)
            tm = TIME_RE.search(_txt(cells.get("time", ("", ""))[1]))
            # The row's own date cell first; the day heading above the table is the
            # fallback in case that cell is ever dropped from the markup.
            dm = DATE_RE.search(_txt(cells.get("date", ("", ""))[1])) or DATE_RE.search(heading)
            if not title or not tm or not dm:
                continue
            # The weekday comes from whichever text supplied the date, never from the
            # other one: the heading and a cell could disagree if the markup moved.
            start = _iso(int(dm.group(2)), int(dm.group(3)),
                         int(tm.group(1)), int(tm.group(2)), today,
                         weekday_index(dm.group(1)) if dm.group(1) else None)
            if not start:
                unplaced.append(f"{dm.group(0).strip()} {title[:28]}")
                continue
            price_attrs, price_html = cells.get("price", ("", ""))
            bd = TITLE_ATTR_RE.search(price_attrs)
            href = HREF_RE.search(cells.get("link", ("", ""))[1])
            shows.append({
                "eventId": slug or _slug(title),
                "title": title,
                "original": "",
                "len": "",
                "rating": "",
                "genres": "",
                "method": strand,
                "theatre": VENUE["name"],
                "aud": "",
                "start": start,
                "url": _ticket(html_mod.unescape(href.group(1)) if href else ""),
                "img": "",
                "lang": "",
                "soldOut": False,
                "price": _price(_txt(price_html), html_mod.unescape(bd.group(2)) if bd else ""),
                "provider": "orion",
                "venue": VENUE["id"],
                # Helpers: the note for the version check, dropped in fetch_site; the
                # page, dropped with `_syn` before the venue is written.
                "_note": blurb,
                "movieUrl": film_page,
            })
    if unplaced:
        print(f"[orion] {len(unplaced)} row(s) whose date no candidate year places inside "
              f"the window, skipped: {', '.join(unplaced[:5])}")
    shows.sort(key=lambda s: s["start"])
    return shows


def fetch_page():
    page = get_text(URL, fetcher=fetch)
    if "kinola-day" not in page:
        raise RuntimeError("no kinola-day table on the page (markup changed?)")
    return parse(page)


# ---------------------------------------------------------------- language

# The film page's definition table, 2026-09-23 (18 of 18 pages carried both rows):
#   <td id='field_…' class='dt'>Kieli:</td> <td class='dd'>englanti, portugali</td>
FIELD_RE = re.compile(r"class=['\"]dt['\"]>\s*(Kieli|Tekstitys)\s*:\s*</td>\s*"
                      r"<td class=['\"]dd['\"]>(.*?)</td>", re.S | re.I)
# A note or title naming a version means the film's one value may not be this screening's.
VERSION_RE = re.compile(r"dub|puhu(?:ttu|mme)|tekstit|versio|orig|alkuper", re.I)
FILM_MAX = int(os.environ.get("KINO_FILM_PAGE_MAX") or 12)
FILM_CACHE = "film-lang-orion.json"


def page_language(page_html):
    """A film page's `Kieli:` and `Tekstitys:` rows -> "ES-A, FI-S, SV-S", or "" for what
    the page does not state clearly (see etiketti.strict_codes)."""
    got = {k.lower(): _txt(v) for k, v in FIELD_RE.findall(page_html or "")}
    parts = [f"{c}-A" for c in strict_codes(got.get("kieli"))]
    parts += [f"{c}-S" for c in strict_codes(got.get("tekstitys"))]
    return ", ".join(parts)


# The table's other rows, 2026-10-04 (Syystarina: "Kesto: 112 min", "Ikäraja: S",
# "Alkuperäinen nimi: Conte d'automne", "Valmistumisvuosi: 1998"). Each only in the shape
# seen: "Ikäraja: Ei vielä tiedossa" and "Valmistumisvuosi: 1931-1973" publish nothing.
FACT_RE = re.compile(r"class=['\"]dt['\"]>\s*(Kesto|Ikäraja|Alkuperäinen nimi|Valmistumisvuosi)"
                     r"\s*:\s*</td>\s*<td class=['\"]dd['\"]>(.*?)</td>", re.S | re.I)
FACTS = ("len", "rating", "original", "year")


def page_facts(page_html):
    """A film page's runtime, rating, original title and year -> {field: str}, each left
    out where the page does not state it plainly."""
    got = {k.lower(): _txt(v) for k, v in FACT_RE.findall(page_html or "")}
    out = {}
    m = re.fullmatch(r"(\d{2,3})\s*min", got.get("kesto", ""), re.I)
    if m:
        out["len"] = m.group(1)
    rating = got.get("ikäraja", "").upper()
    if rating in KAVI_CODES:
        out["rating"] = "S" if rating == "S" else f"K-{rating}"
    if got.get("alkuperäinen nimi"):
        out["original"] = got["alkuperäinen nimi"]
    if re.fullmatch(r"(?:19|20)\d{2}", got.get("valmistumisvuosi", "")):
        out["year"] = got["valmistumisvuosi"]
    return out


# The page's own text, 2026-09-27: <div class='entry' id="longdesc"> ... <aside
# class='naytokset ohjelmisto'>. Its JSON-LD carries the same text with the paragraph
# breaks lost ("Valkoinen.Kolme väriä"), so that is not read.
ENTRY_RE = re.compile(r"""id=["']longdesc["'][^>]*>(.*?)<aside[^>]*naytokset""", re.S | re.I)
PARA_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
# A film in one of the cinema's series names it under its heading, <h2><a
# href=".../erikoisnaytokset/aanen-alkemistit/">ÄÄNEN ALKEMISTIT</a></h2>. Read 2026-09-29,
# 2 of 21 pages open their description with a paragraph about that series, its name in
# <em> first; the film's own text starts in the next paragraph.
SERIES_RE = re.compile(r"""<h2>\s*<a[^>]*href=["'][^"']*/erikoisnaytokset/[^"']+["'][^>]*>"""
                       r"(.*?)</a>\s*</h2>", re.S | re.I)
EM_LEAD_RE = re.compile(r"\s*<em>(.*?)</em>", re.S | re.I)


# A sentence announcing one screening: a date, a clock time and "näytös" together, as in
# Urpo ja Turpo's "Elokuvasta järjestetään 21.11. klo 10:30 ilmaisnäytös lapsen oikeuksien
# viikon kunniaksi." (read 2026-10-04). Sentences part where a stop meets a capital, so
# "21.11. klo" stays one sentence.
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c5\u00c4\u00d6\"\u201c\u201d])")
NOTE_DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.")
CLOCK_RE = re.compile(r"\bklo\s*\d{1,2}[.:]\d{2}\b", re.I)
SHOWING_RE = re.compile(r"n\u00e4yt\u00f6", re.I)


def _drop_screening_sentences(text):
    return " ".join(x for x in SENTENCE_RE.split(text)
                    if not (NOTE_DATE_RE.search(x) and CLOCK_RE.search(x)
                            and SHOWING_RE.search(x)))


def page_synopsis(page_html):
    """The film page's description -> {lang: text}: the paragraphs of its `longdesc`
    block, Finnish and often English after `***`. Each part goes where `syn_language`
    places it, or nowhere. The listing's note is not on the page, and a first paragraph
    that opens with the name of the series the page is filed under is left out."""
    m = ENTRY_RE.search(page_html or "")
    if not m:
        return {}
    paras = PARA_RE.findall(m.group(1))
    series = SERIES_RE.search(page_html)
    lead = EM_LEAD_RE.match(paras[0]) if paras else None
    if series and lead and _txt(lead.group(1)).casefold() == _txt(series.group(1)).casefold():
        paras = paras[1:]
    out = {}
    for part in " ".join(_txt(p) for p in paras).split("***"):
        # An inline tag became a space: "<em>Valkoinen</em>." read "Valkoinen .".
        part = re.sub(r"\(\s+", "(", re.sub(r"\s+([.,;:!?)])", r"\1", part)).strip()
        part = _drop_screening_sentences(part)
        if part:
            out.setdefault(syn_language(part), part)
    return {k: v for k, v in out.items() if k}


def film_language(shows, *, path=None, now=None, sleep=1.5, limit=None, fetch_fn=None):
    """Put each film's language, and its page's synopsis as `_syn`, on its screenings.
    -> counts dict. Never raises: a page that cannot be read leaves its screenings as
    they were."""
    films, unclear = {}, 0
    for s in shows:
        if s.get("movieUrl"):
            films.setdefault(s["movieUrl"], []).append(s)
    asks = []
    for url, rows in films.items():
        if (len({r["title"] for r in rows}) > 1
                or any(VERSION_RE.search(f"{r['title']} {r.get('_note') or ''}") for r in rows)):
            unclear += 1
            continue
        asks.append({"url": url, "price": ""})
    path = path or (prices._out() / FILM_CACHE)
    try:
        st = prices.enrich(asks, provider="orion", prefix=URL, parse=lambda page: "",
                           fields=lambda page: {"lang": page_language(page),
                                                **page_facts(page), **{
                               f"syn_{k}": v for k, v in page_synopsis(page).items()}},
                           path=path,
                           now=now, sleep=sleep, limit=FILM_MAX if limit is None else limit,
                           fetch_fn=fetch_fn or (lambda u, h: fetch(u, headers=h, tries=2,
                                                                    timeout=20)),
                           label="film pages")
    except Exception as e:                         # noqa: BLE001 -- the language is optional
        print(f"[orion] film languages skipped: {type(e).__name__}: {str(e)[:80]}")
        return {}
    by_url = {a["url"]: a.get("lang", "") for a in asks}
    facts = {a["url"]: {f: a[f] for f in FACTS if a.get(f)} for a in asks}
    syn = {a["url"]: {k[4:]: v for k, v in a.items() if k.startswith("syn_")} for a in asks}
    for url, rows in films.items():
        for r in rows:
            if by_url.get(url) and not r.get("lang"):
                r["lang"] = by_url[url]
            for f, v in facts.get(url, {}).items():
                if not r.get(f):
                    r[f] = v
            if syn.get(url):
                r["_syn"] = syn[url]
    print(f"[orion] film languages: {len(films)} films, "
          f"{sum(1 for v in by_url.values() if v)} with a language, {st['fetched']} pages "
          f"read, {st['failed']} failed, {st['deferred']} deferred, {unclear} left out as "
          f"possibly more than one version")
    return dict(st, films=len(films), unclear=unclear)


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one screen, keyed by the venue id."""
    shows = fetch_page()
    film_language(shows)
    for s in shows:
        s.pop("_note", None)
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = parse(open(src, encoding="utf-8", errors="replace").read()) if src else fetch_page()
    print(f"{len(data)} showtimes, {len({s['eventId'] for s in data})} films")
    for s in data:
        host = re.sub(r"^https?://([^/]+).*", r"\1", s["url"])
        print(f"  {s['start'][:16]}  {s['title'][:38]:40} {s['price']:12} {host}")
