"""Elokuvateatteri Marita, Outokumpu. Stdlib only.

One request. The front page renders the whole programme in its `show-times` module, one
`movie-info` block per screening:

    <div id="show-times" class="page-module show-times">
      <div class="module-title ..."><H2>Lähipäivien näytökset</H2></div>
      <div class="show-times-movies">
        <div class="movie-info width-content-narrow grid-x ...">
          <div class="movie-info-image ...">
            <a href="https://elokuvateatterimarita.fi/elokuva/hetki-ennen-valoa/">
              <img width="421" height="600" src=".../Hetki-ennen-valoa-juliste-421x600.jpg">
          <div class="movie-info-text ...">
            <h3><a href=".../elokuva/hetki-ennen-valoa/">Hetki ennen valoa</a></h3>
            <div class="movie-info-price">Hinta: 10 €</div>
            <div class="movie-info-language">Kieli: Suomi</div>
            <div class="movie-content-labels">
              <img class="age-img" src=".../labels/7.png"><img class="label-img" src=".../labels/a.png">
          <div class="movie-info-times ...">
            <div class="movie-info-times-date">19.09.2026</div>
            <div class="movie-info-times-time">klo 17.00</div>

What shapes the parser:

- **`Kieli` is the spoken language, and that was established rather than assumed.** Ten
  captures of this page between 2025-05 and 2026-05 carry `Englanti` on *Five Nights At
  Freddy's 2*, *Sydäntalvi* and *Michael*, `saksa` on one festival screening, and `Suomi`
  on Finnish films and on the dubbed prints of *Zootropolis 2* and *The Super Mario Galaxy
  Movie*. The site publishes no subtitle field anywhere, so the value is the print being
  shown and it is published in the audio role. A value naming more than one language, or
  none this repo has a code for, publishes nothing.
- **The rating is the `age-img` filename and only that.** The block prints a second and
  third image from the same directory, `a.png`, `v.png`, `p.png`, `x.png`, which are KAVI
  content descriptors rather than classifications, the distinction `engel.py` already
  makes. `s.png` is the S rating and the numbers are K-limits.
- **A price belongs to its screening.** `Hinta: 10 €` is that screening's ticket. The
  festival rows of 2025-09-13 printed `Hinta: 10/8 €` and one row of 2026-05-16 printed no
  price element at all; neither settles an amount, so both publish none.
- **The date carries its year**, so nothing is inferred and `common.resolve_year` is not
  used.
- **The film page carries what the row does not**: `Kesto`, `Lajityyppi` and the cinema's
  own Finnish synopsis under `Kuvaus`. One request per distinct film, paced and capped, so
  a page that will not answer costs that film its metadata and never the programme. The
  page's `Ikäraja` reads `K-7 (4)`, where the 4 is the flexibility years; the row's image
  is read instead and the two agree.
- **No ticket host exists and none is invented.** The site carries no `liput`, `varaa`,
  `osta` or `lipunmyynti` anywhere, on the programme or on the contact page, so the
  provider is registered `book="door"` and a showtime opens the film's own page, which the
  row already links. The href is read from the markup, never built from the title.
- The poster is portrait on the site's own host, 421x600 on the rows read 2026-09-19 with
  the dimensions in the tag, so a landscape image would be left out the way `tribe.py`
  leaves one out.

**An empty programme is evidence, not an empty parse.** Three of ten captures over eleven
months render the module with no `show-times-movies` container and the words `Ei tulevia
näytösaikoja` in its place: 2025-10-12, 2026-02-09 and 2026-04-14, a small-town cinema
between programmes. `empty_programme_evidence` requires all three conditions, the shape
`kinola.py` uses, so a markup change underneath the row parser fails the site instead.

On that evidence the venue is returned empty and `EMPTY_VENUES_CONFIRMED` publishes a
fresh empty file. `common.EmptyProgramme` wrote nothing until 2026-09-24. The gaps here
run for weeks, and keeping the last programme through one would age the health line into
a warning about a cinema that is working exactly as it says. That is the case
"Confirmed empty beats kept data" settled for Kino Metso's Muurame on 2026-09-05.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import capped, check_shows, fetch, get_text, served
from etiketti import lang_codes
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "marita", "label": "Elokuvateatteri Marita",
     "base": "https://elokuvateatterimarita.fi",
     "listing": "/",
     "venues": [{"id": "marita-outokumpu", "name": "Elokuvateatteri Marita",
                 "short": "Elokuvateatteri Marita", "city": "Outokumpu"}]},
]

MODULE_RE = re.compile(r'<div id="show-times".*?(?=<div class="page-module|</section>|\Z)', re.S)
CONTAINER_RE = re.compile(r'<div class="show-times-movies"', re.I)
NO_SHOWS_RE = re.compile(r"Ei\s+tulevia\s+näytösaikoja", re.I)
MODULE_TITLE_RE = re.compile(r"Lähipäivien\s+näytökset", re.I)
ROW_RE = re.compile(r'<div class="movie-info width-content-narrow.*?'
                    r'(?=<div class="movie-info width-content-narrow|\Z)', re.S)
LINK_RE = re.compile(r'<h3>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
PRICE_RE = re.compile(r'movie-info-price">(.*?)</div>', re.S | re.I)
LANG_RE = re.compile(r'movie-info-language">(.*?)</div>', re.S | re.I)
DATE_RE = re.compile(r'movie-info-times-date">\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', re.I)
TIME_RE = re.compile(r'movie-info-times-time">\s*klo\s*(\d{1,2})[.:](\d{2})', re.I)
AGE_RE = re.compile(r'<img[^>]*class="age-img"[^>]*labels/([^"/]+)\.png', re.I)
IMG_RE = re.compile(r'<img[^>]*?width="(\d+)"[^>]*?height="(\d+)"[^>]*?src="([^"]+)"', re.I)
AMOUNT_RE = re.compile(r"^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$")
FACT_RE = re.compile(r'movies-info-title">\s*(.*?)\s*</div>\s*'
                     r'<div[^>]*movies-info-text">\s*(.*?)\s*</div>', re.S | re.I)
SYN_RE = re.compile(r"<h2>\s*Kuvaus\s*</h2>(.*?)<div", re.S | re.I)
MIN_RE = re.compile(r"(?:(\d{1,2})\s*h\s*)?(\d{1,3})\s*min", re.I)
TAGS_RE = re.compile(r"<[^>]+>")

POSTER_MIN_RATIO = 1.2
POSTER_MIN_WIDTH = 300
# Between film pages, the pace every adapter reading one keeps.
SLEEP = 1.2

# Set on the evidence above: the module states an empty programme in the site's own words,
# so `fetch_site` returns the venue empty and run.py publishes a fresh empty file marked
# pending. Zero rows without that sentence never reaches this: it raises.
EMPTY_VENUES_CONFIRMED = True


class RowError(RuntimeError):
    """A screening block this parser could not read.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = TAGS_RE.sub(" ", s)
    return re.sub(r"\s+", " ", html_mod.unescape(s).replace("\xa0", " ")).strip()


def module(page):
    """The `show-times` block, or "" when the page does not render it."""
    m = MODULE_RE.search(page or "")
    return m.group(0) if m else ""


def empty_programme_evidence(page):
    """True only where the site says it has nothing on. -> bool.

    All three: the module rendered with its own heading, no `show-times-movies` container,
    and `Ei tulevia näytösaikoja` inside the module. Zero rows on its own is what a broken
    parser produces, which `common.EmptyProgramme` forbids reading as an empty programme.
    """
    block = module(page)
    return bool(block and MODULE_TITLE_RE.search(block)
                and not CONTAINER_RE.search(block) and NO_SHOWS_RE.search(block))


def _minutes(text):
    """`1 h 27 min` -> "87", `95 min` -> "95". -> str, "" when neither shape is there."""
    m = MIN_RE.search(text or "")
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def _rating(name):
    """The age image's filename -> `K-12`, `S`, or "" for a content descriptor."""
    v = (name or "").strip().lower()
    if v.isdigit():
        return f"K-{int(v)}"
    return "S" if v == "s" else ""


def _price(value):
    """`Hinta: 10 €` -> "10€". Two amounts or no element settle nothing and give ""."""
    v = re.sub(r"^\s*hinta\s*:\s*", "", _txt(value), flags=re.I)
    m = AMOUNT_RE.match(v)
    return f"{m.group(1)}€" if m else ""


def _lang(value):
    """`Kieli: Suomi` -> "FI-A". "" unless exactly one known language is named."""
    v = re.sub(r"^\s*kieli\s*:\s*", "", _txt(value), flags=re.I)
    codes = lang_codes(v)
    return f"{codes[0]}-A" if len(codes) == 1 else ""


def _poster(block):
    m = IMG_RE.search(block)
    if not m:
        return ""
    w, h, url = int(m.group(1)), int(m.group(2)), html_mod.unescape(m.group(3))
    if w < POSTER_MIN_WIDTH or h < w * POSTER_MIN_RATIO:
        return ""
    return url


def _genres(value):
    parts = [p.strip() for p in (value or "").split(",")]
    return ", ".join(p[:1].upper() + p[1:] for p in parts if p)


def film_facts(page):
    """A film page -> {len, genres, syn}. A field the page omits comes back empty."""
    facts = {k.strip().lower(): _txt(v) for k, v in FACT_RE.findall(page or "")}
    m = SYN_RE.search(page or "")
    return {"len": _minutes(facts.get("kesto", "")),
            "genres": _genres(facts.get("lajityyppi", "")),
            "syn": _txt(m.group(1)) if m else ""}


def rows(site, page):
    """-> ([show], report). One row per screening block the module prints."""
    venue = site["venues"][0]
    block = module(page)
    out, report = [], {"no_price": set(), "no_lang": set()}
    for n, row in enumerate(ROW_RE.findall(block)):
        link = LINK_RE.search(row)
        if not link:
            raise RowError(f"{site['provider']}: block {n + 1} carries no film link")
        title = _txt(link.group(2))
        d, t = DATE_RE.search(row), TIME_RE.search(row)
        if not title or not d or not t:
            raise RowError(f"{site['provider']}: block {n + 1} for {title!r} has no "
                           f"readable title, date or time")
        day, month, year = int(d.group(1)), int(d.group(2)), int(d.group(3))
        try:
            start = datetime.datetime(year, month, day, int(t.group(1)), int(t.group(2)),
                                      tzinfo=FI)
        except ValueError as e:
            raise RowError(f"{site['provider']}: block {n + 1} for {title!r} prints the "
                           f"impossible date {day}.{month}.{year}") from e
        price_cell = PRICE_RE.search(row)
        price = _price(price_cell.group(1) if price_cell else "")
        if not price:
            report["no_price"].add(title)
        lang_cell = LANG_RE.search(row)
        lang = _lang(lang_cell.group(1) if lang_cell else "")
        if not lang:
            report["no_lang"].add(title)
        age = AGE_RE.search(row)
        out.append({
            "eventId": norm(title),
            "title": title,
            "original": "",
            "len": "",
            "rating": _rating(age.group(1) if age else ""),
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": start.isoformat(),
            "url": html_mod.unescape(link.group(1)),
            "img": _poster(row),
            "lang": lang,
            "soldOut": False,
            "price": price,
            "provider": site["provider"],
            "venue": venue["id"],
        })
    out.sort(key=lambda s: s["start"])
    return out, report


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def enrich(shows, sleep=None, fetch_page=None):
    """Fill `len`, `genres` and `_syn` from one film page per distinct film. -> int, pages read.

    `capped`, not `budget_or_raise`: these pages carry no screening, so a film past the cap
    keeps its showtimes and loses only its metadata. A page that will not answer costs the
    same and is reported.
    """
    fetch_page = fetch_page or get
    sleep = SLEEP if sleep is None else sleep
    pages = {}
    for n, url in enumerate(capped(sorted({s["url"] for s in shows}), "marita")):
        if n:
            time.sleep(sleep)
        try:
            pages[url] = film_facts(fetch_page(url))
        except Exception as e:
            print(f"[marita] film page {url}: {type(e).__name__}: {e}", file=sys.stderr)
    for s in shows:
        facts = pages.get(s["url"])
        if not facts:
            continue
        s["len"], s["genres"] = facts["len"], facts["genres"]
        if facts["syn"]:
            s["_syn"] = facts["syn"]
    return len(pages)


def fetch_site(site):
    pid = site["provider"]
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    page = get(url)
    shows, report = rows(site, page)
    if not shows:
        if empty_programme_evidence(page):
            print(f"[{pid}] {venue['name']}: the programme module says 'Ei tulevia "
                  f"näytösaikoja', so the venue is confirmed empty")
            return {venue["id"]: []}
        raise RuntimeError(
            f"{url}: no screening block, and the page does not say it has nothing on "
            f"({served(page)}). Treating it as a fetch or template failure rather than a "
            f"cinema between programmes, so the previous files stand")
    read = enrich(shows)
    check_shows({venue["id"]: shows}, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    films = {s["eventId"] for s in shows}
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len(films)} film(s), {read} film page(s) read")
    if report["no_price"]:
        print(f"[{pid}] {len(report['no_price'])} film(s) whose row settles no price: "
              f"{', '.join(sorted(report['no_price'])[:6])}")
    if report["no_lang"]:
        print(f"[{pid}] {len(report['no_lang'])} film(s) whose row names no single known "
              f"language: {', '.join(sorted(report['no_lang'])[:6])}")
    return {venue["id"]: shows}


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:30]:32} {s['rating']:5} "
                  f"{s['len']:4} {s['price']:6} {s['lang']:6} "
                  f"img={'y' if s['img'] else '-'} syn={len(s.get('_syn', ''))}")
    sys.exit(0)
