"""Lieksan Kino, the town's cinema in the Brahe hall of its culture centre. Stdlib only.

One request. `lieksanelokuvat.net` is hand-written HTML with a section per part of the
page, and `section-b` is the programme, one `article` per film:

    <section id="section-b" class="main-section">
      <h2>Elokuvissa nyt</h2>
      <div class="upcoming-movie-container">
        <article class="entry">
          <div class="entry-top">
            <img class="entry-image" src="data/images/9c17debc-....jpg" alt="">
            <a class="entry-anchor" href="https://www.youtube.com/watch?v=...">
          <div class="entry-bottom">
            <h3>ORTOTOPOLOGIAN LOPUTTOMAT ALKEET</h3>
            <p class="entry-text">MARKKU PÖLÖSEN UUSIN ELOKUVA!<br />...</p>
            <side>
              <div class="side-row-cell"><h4>Liput:</h4>12&thinsp;€</div>
              <div class="side-row-cell"><h4>Kesto:</h4>75 min</div>
              <div class="side-row-cell"><img class="entry-rating-icon"
                   src="graphics/rating-icon-7.svg" alt="Sallittu yli 7-vuotiaille."></div>
              <div class="showtimes"><h4>Esitysajat:</h4>
                <ul><li><p>Su 20.09. 15.00</p><p></p><p></p></li>

What shapes the parser:

- **A line the parser cannot read fails the site.** The `showtimes` block is counted as
  well as parsed, so a row whose shape moves is a failure with the previous files kept
  rather than a schedule one screening short. The two empty `<p>` elements beside every
  line are the site's own and were empty on all seven rows read; nothing reads them.
- **The section is the boundary.** `section-c`, "Tulossa esitettäväksi", renders the same
  `article.entry` markup for five films with no `<side>` and no screening row. Reading the
  page flat would publish a coming-soon list as a programme the moment the site gives one
  of those a date.
- **A screening line prints no year**, so the weekday selects it through
  `common.resolve_year` and a line it cannot place raises rather than disappearing. The
  programme read on 2026-09-19 ran from the next day to eight days out, so the window is
  headroom rather than a fit.
- **The price is the film's own `Liput:` cell**, a single amount on all four films read
  (12, 11, 13 and 13 euro). Anything else settles nothing. The page's other two figures
  are different products and are not read: `OSTA ENNAKKOLIPPUJA 1 kpl 13 €, 5 kpl 60 €` is
  a voucher bought from the cinema by phone, and the PAM members' five euro is a discount
  that needs a card at the counter, the same shape as Iso-Hannu's concessions.
- **The rating is the icon's filename**, `rating-icon-7.svg` through `-18` and `-s`. The
  `alt` says the same thing in prose and is not read.
- **The poster is the article's own image**, portrait on the site's own host: 512x724 to
  512x768 on all nine films across both sections, measured 2026-09-19. **The dimensions
  are not in the markup**, so unlike `hamina.py` and `tribe.py` this adapter cannot check
  one per run, and a landscape image would publish. What it can do is refuse anything
  outside a film article, which is where the two landscape notices on the same page sit.
- **No ticket host exists and none is invented.** The page's own words: "Liput ovat
  ostettavissa Lieksan kulttuurikeskuksen aulasta noin 30 minuuttia ennen näytöksen
  alkua." So `book="door"` and a showtime opens this page, as Kino Hamina does.
- **Titles are published verbatim**, capitals included, because the raw title is the key
  for `normTitle()`, `films-extra.json` and `tmdb-aliases.json`, and every one of those
  reads it case-folded. Kino Regina recases its own because its film pages carry the
  film's spelling a second time; nothing here does.
- No language and no genre is published anywhere on the site, so both stay empty and the
  shared enrichment fills what it can.

**Zero rows fails the site.** The Wayback captures of this domain stop in 2021 on an older
design, so no emptied programme has ever been seen on this template and there is no
evidence of what one looks like: `common.EmptyProgramme` is for the case where that
evidence is in hand. A film in `section-b` with no screening row is a different thing, a
run that has ended, and it is counted and left out.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, fetch, get_text, resolve_year, served, weekday_index
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "lieksankino", "label": "Lieksan Kino",
     "base": "https://www.lieksanelokuvat.net",
     "listing": "/",
     "venues": [{"id": "lieksankino-lieksa", "name": "Lieksan Kino",
                 "short": "Lieksan Kino", "city": "Lieksa"}]},
]

# `resolve_year`'s (behind, ahead). The programme read on 2026-09-19 reached eight days
# out over two weekends, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

SECTION_RE = re.compile(r'<section id="section-b".*?(?=<section id="section-c"|\Z)', re.S)
ARTICLE_RE = re.compile(r'<article class="entry">.*?(?=<article class="entry">|</section>|\Z)',
                        re.S)
TITLE_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S | re.I)
TEXT_RE = re.compile(r'<p class="entry-text">(.*?)</p>', re.S | re.I)
PRICE_RE = re.compile(r"<h4>\s*Liput:\s*</h4>\s*(.*?)\s*</div>", re.S | re.I)
LEN_RE = re.compile(r"<h4>\s*Kesto:\s*</h4>\s*(.*?)\s*</div>", re.S | re.I)
RATING_RE = re.compile(r'class="entry-rating-icon"[^>]*rating-icon-([^."]+)\.svg', re.I)
IMG_RE = re.compile(r'<img class="entry-image" src="([^"]+)"', re.I)
SHOW_RE = re.compile(r"<li>\s*<p>\s*(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.\s*"
                     r"(\d{1,2})[.:](\d{2})\s*</p>", re.S | re.I)
ROW_RE = re.compile(r"<li>.*?</li>", re.S | re.I)
SHOWTIMES_RE = re.compile(r'<div class="showtimes">(.*?)</div>', re.S | re.I)
MIN_RE = re.compile(r"(\d{1,3})\s*min", re.I)
AMOUNT_RE = re.compile(r"^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$")
TAGS_RE = re.compile(r"<[^>]+>")


class ShowRowError(RuntimeError):
    """A screening line the page prints and this parser could not place.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = TAGS_RE.sub(" ", s)
    s = html_mod.unescape(s).replace("\xa0", " ").replace("\u2009", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")).strip()


def _one_line(s):
    return re.sub(r"\s+", " ", _txt(s))


def _minutes(text):
    m = MIN_RE.search(text or "")
    return m.group(1) if m else ""


def _rating(name):
    v = (name or "").strip().lower()
    if v.isdigit():
        return f"K-{int(v)}"
    return "S" if v == "s" else ""


def _price(value):
    """`12&thinsp;€` -> "12€". Anything that is not one amount settles nothing."""
    m = AMOUNT_RE.match(_one_line(value))
    return f"{m.group(1)}€" if m else ""


def _poster(article, base):
    m = IMG_RE.search(article)
    if not m:
        return ""
    src = html_mod.unescape(m.group(1))
    if src.startswith("http"):
        return src
    return f"{base.rstrip('/')}/{src.lstrip('/')}"


def programme(page):
    """The `section-b` block, or "" when the page does not render it."""
    m = SECTION_RE.search(page or "")
    return m.group(0) if m else ""


def rows(site, page, today=None):
    """-> ([show], report). One row per screening line the programme section prints."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    out, report = [], {"no_dates": [], "no_price": set()}
    for article in ARTICLE_RE.findall(programme(page)):
        m = TITLE_RE.search(article)
        title = _one_line(m.group(1)) if m else ""
        if not title:
            continue
        sm = SHOWTIMES_RE.search(article)
        block = sm.group(1) if sm else ""
        found = SHOW_RE.findall(block)
        # Counted before a film with no readable line is set aside as a finished run: a
        # film whose every line changed shape reads nothing either, and is the case the
        # count exists for.
        listed = len(ROW_RE.findall(block))
        if not found and not listed:
            report["no_dates"].append(title)
            continue
        if listed != len(found):
            raise ShowRowError(f"{site['provider']}: {title!r} lists {listed} screening "
                               f"line(s) and {len(found)} could be read")
        pm, lm, rm = PRICE_RE.search(article), LEN_RE.search(article), RATING_RE.search(article)
        price = _price(pm.group(1) if pm else "")
        if not price:
            report["no_price"].add(title)
        tm = TEXT_RE.search(article)
        syn = _one_line(tm.group(1)) if tm else ""
        for wd, day, month, hh, mm in found:
            year = resolve_year(int(day), int(month), today, weekday_index(wd), WINDOW)
            if year is None:
                raise ShowRowError(
                    f"{site['provider']}: {title!r} prints {wd} {day}.{month}. and no "
                    f"candidate year carries that weekday inside the window, so the "
                    f"screening cannot be placed")
            try:
                start = datetime.datetime(year, int(month), int(day), int(hh), int(mm),
                                          tzinfo=FI)
            except ValueError as e:
                raise ShowRowError(f"{site['provider']}: {title!r} prints the impossible "
                                   f"date {day}.{month}.{year}") from e
            row = {
                "eventId": norm(title),
                "title": title,
                "original": "",
                "len": _minutes(lm.group(1) if lm else ""),
                "rating": _rating(rm.group(1) if rm else ""),
                "genres": "",
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": url,
                "img": _poster(article, site["base"]),
                "lang": "",
                "soldOut": False,
                "price": price,
                "provider": site["provider"],
                "venue": venue["id"],
            }
            if syn:
                row["_syn"] = syn
            out.append(row)
    out.sort(key=lambda s: s["start"])
    return out, report


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, today=None):
    pid = site["provider"]
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    page = get(url)
    shows, report = rows(site, page, today)
    if not shows:
        raise RuntimeError(
            f"{url}: no screening line in the programme section ({served(page)}). No "
            f"emptied programme has been seen on this template, so there is no evidence "
            f"of one to read this as, and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len({s['eventId'] for s in shows})} film(s)")
    if report["no_dates"]:
        print(f"[{pid}] {len(report['no_dates'])} film(s) in the programme section with no "
              f"screening line, left out: {', '.join(report['no_dates'][:6])}")
    if report["no_price"]:
        print(f"[{pid}] {len(report['no_price'])} film(s) whose Liput cell settles no "
              f"amount: {', '.join(sorted(report['no_price'])[:6])}")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:32]:34} {s['rating']:5} "
                  f"{s['len']:4} {s['price']:6} img={'y' if s['img'] else '-'} "
                  f"syn={len(s.get('_syn', ''))}")
    sys.exit(0)
