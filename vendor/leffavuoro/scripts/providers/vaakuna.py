"""Kino Vaakuna, Laurinkatu 48, Lohja. Stdlib only.

Probed 2026-09-15. Its own site, on none of the platforms this repo reads. The front page
is the whole programme: one `div.MovieCard` per film, each with the film-page link, the
poster, the ticket price, the runtime, an age limit and a table of screenings.

    <a href="https://www.kinovaakuna.fi/elokuvat/the-odyssey.html" class="MovieCard__PosterLink">
      <img class="MovieCard__Poster" src=".../media/cache/....png" alt="The Odyssey Juliste"></a>
    <h2 class="font-size-h5 mb-3">The Odyssey</h2>
    <li><strong>Liput: 15€ (lahja/sarjalippu +2€)</strong></li>
    <li>Kesto: 2 h 53 min</li>
    <li>Ikäraja: <img src=".../media/layout/img/icon/16.png"></li>
    <div>Näytösajat:</div>
    <table ...><tr><td>Ti 15.09.   klo 18:40</td></tr></table>

Three things that shape the parser:

- **No year is published, but a weekday is.** The rows read `Ti 15.09.   klo 18:40`, and
  that `Ti` **selects** the year: the same day and month falls on a different weekday in
  each of last year, this year and next, so exactly one candidate can match. That makes the
  choice unambiguous given the window; it does not prove the cinema meant that date, so
  `common.resolve_year` also refuses a candidate too far from today. A weekday matching
  none of the three, or one selecting a date roughly a year away, leaves the row skipped
  and counted rather than placed. The nearest-occurrence fallback in that function is for
  sources that print no weekday at all; this one always does.
- **The age limit is an image whose filename is the number**, `icon/16.png`, so it is read
  rather than inferred: `16` becomes `K-16`. A filename that is not a number yields no
  rating.
- **There is no online purchase.** "Varaa liput" links to the film's own page and the
  cinema takes reservations by phone and email, so the showtime links there and the
  registry entry is `book="reserve"`. No ticket host exists and none is invented, and no
  auditorium is invented either: the page names none.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import fetch, get_text, resolve_year, weekday_index

BASE = "https://www.kinovaakuna.fi"
LISTING = BASE + "/etusivu.html"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "vaakuna-lohja", "name": "Kino Vaakuna", "short": "Kino Vaakuna",
         "city": "Lohja"}

SITES = [{"provider": "vaakuna", "label": "Kino Vaakuna", "base": BASE, "venues": [VENUE]}]

# The horizon this source was measured at on 2026-09-15: 10 dates, +0 to +9 days. 30
# behind and 60 ahead is several times that and far short of the 365 a mistyped weekday
# would need. A screening this cinema ever publishes further out than 60 days is dropped
# and named in the log rather than placed on a date it may not mean.
WINDOW = (30, 60)

CONTAINER_RE = re.compile(r'class="MovieCard', re.I)
CARD_RE = re.compile(r'<div class="MovieCard\b(.*?)(?=<div class="MovieCard\b|</main>|\Z)',
                     re.S | re.I)
SLUG_RE = re.compile(r'href="[^"]*/elokuvat/([^"/]+)\.html"', re.I)
TITLE_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S | re.I)
PRICE_RE = re.compile(r'Liput:\s*([^<]{1,60})', re.I)
KESTO_RE = re.compile(r'Kesto:\s*(?:(\d+)\s*h)?\s*(\d+)\s*min', re.I)
AGE_RE = re.compile(r'Ik(?:&auml;|ä)raja:\s*<img[^>]*/icon/([^."/]+)\.png', re.I)
POSTER_RE = re.compile(r'<img[^>]*class="[^"]*MovieCard__Poster[^"]*"[^>]*src="([^"]+)"', re.I)
SHOW_RE = re.compile(r'<td[^>]*>\s*([A-Za-zÄÖäö]{2,12})?\s*(\d{1,2})\.(\d{1,2})\.\s*'
                     r'klo\s*(\d{1,2})[:.](\d{2})', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _rating(icon):
    """`icon/16.png` -> `K-16`; a name that is not a number yields nothing."""
    name = (icon or "").strip().upper()
    if name in ("S", "0"):
        return "S"
    return f"K-{int(name)}" if name.isdigit() else ""


def parse(page, today=None):
    """The front page -> [show]. `today` is the date the year is resolved against and
    defaults to today in Helsinki; it is a parameter so the tests can pin it.

    Raises when no film card is present, and when the cards yield no screening. No empty
    state is recorded for this site, so zero rows is never read as nothing on."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{LISTING}: no film card on the page, so this is not the programme this "
            f"parser reads. Treating it as a fetch or template failure rather than a "
            f"cinema with nothing on")
    today = today or datetime.datetime.now(FI).date()
    shows, seen, unplaced = [], set(), []
    for block in CARD_RE.findall(page):
        slug = SLUG_RE.search(block)
        t = TITLE_RE.search(block)
        if not (slug and t):
            continue
        title = _txt(t.group(1))
        if not title:
            continue
        m = PRICE_RE.search(block)
        price = _txt(m.group(1)) if m else ""
        m = KESTO_RE.search(block)
        length = str(int(m.group(1) or 0) * 60 + int(m.group(2))) if m else ""
        m = AGE_RE.search(block)
        rating = _rating(m.group(1)) if m else ""
        m = POSTER_RE.search(block)
        img = m.group(1) if m else ""
        for wd, day, month, hh, mm in SHOW_RE.findall(block):
            day, month = int(day), int(month)
            # The row prints a weekday ("Ti 15.09."). It picks out exactly one candidate
            # year, so it is used instead of the nearest-occurrence fallback, and a
            # weekday matching none of them leaves the row unresolved rather than placed.
            year = resolve_year(day, month, today, weekday_index(wd), WINDOW)
            if year is None:
                unplaced.append(f"{wd} {day:02d}.{month:02d}.")
                continue
            try:
                start = datetime.datetime(year, month, day, int(hh), int(mm), tzinfo=FI)
            except ValueError:
                continue
            key = (slug.group(1), start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            shows.append({
                "eventId": slug.group(1),
                "title": title,
                "original": "",
                "len": length,
                "rating": rating,
                "genres": "",
                "method": "",
                "theatre": VENUE["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": f"{BASE}/elokuvat/{slug.group(1)}.html",
                "img": img,
                "lang": "",
                "soldOut": False,
                "price": price,
                "provider": "vaakuna",
                "venue": VENUE["id"],
            })
    if unplaced:
        print(f"[vaakuna] {len(unplaced)} row(s) whose weekday matches no candidate year, "
              f"skipped: {', '.join(unplaced[:5])}")
    if not shows:
        raise RuntimeError(
            f"{LISTING}: film cards with no screening row this parser places "
            f"({len(unplaced)} unplaced). No empty state is recorded for this site, so "
            f"this is a template or format change rather than a cinema with nothing on")
    shows.sort(key=lambda s: s["start"])
    return shows


def get_listing():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(LISTING, fetcher=fetch)


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one venue."""
    shows = parse(get_listing())
    print(f"[vaakuna] {len(shows)} showtimes, {len({s['eventId'] for s in shows})} films, "
          f"{len({s['start'][:10] for s in shows})} dates")
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    for s in data:
        print(f"  {s['start'][:16]} {s['title'][:30]:32} {s['rating']:5} {s['len']:4} "
              f"{s['price'][:22]:24} {s['url'][-28:]}")
