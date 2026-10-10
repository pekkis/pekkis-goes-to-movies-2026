"""Elokuvateatteri Matin-Tupa, Ylistaro. Stdlib only.

One request, to the programme page:

    /ohjelmistossa/

The page is WordPress with a Toolset view, and the view is rendered server-side: the
films are in the HTML, one `<div class="col-sm-6">` per film, two to a `<div class="row">`.
Checked for a structured source first and there is none. `/wp-json/` lists 340 routes and
no namespace holding screenings; `/wp/v2/types` has the core types plus Kadence and
Toolset furniture and no film type; `/wp/v2/posts` is the news feed, whose newest entry is
from August. The `kategoria` taxonomy has `ohjelmistossa` at count 0. So the rendered view
is the only place the programme exists.

What shapes the parser, measured on the live page 2026-09-20:

- **A film block is `<h2><a href="/elokuvat/{slug}/">Title</a></h2>` and the fields under
  it are `<b>`-labelled**: `Esitysajat:`, `Liput:`, `Kesto:`, `Genre:`. The block ends at
  the `>> Lue lisää` link back to the same film page. The slug is the row's `eventId`,
  because it is the cinema's own stable key for the film and the title is not: the title
  is what `normTitle()`, `films-extra.json` and `tmdb-aliases.json` key on and it is
  published verbatim.
- **No date carries a year.** `Esitysajat:` holds one `<br>`-separated line per screening,
  `la 19.9. klo 17.15`, with the weekday abbreviated to two letters. `common.resolve_year`
  places it and `common.weekday_index` gives it the weekday to select on, so a stale page
  cannot quietly become a future screening.
- **The price is published only when the `Liput:` value is one bare amount.** The live page
  has `14 €` and `13 €` on three films and `14,00 €. Kts. lisätiedot` on the fourth, a
  Neulekino evening whose ticket is sold with a 3,80 € serving and a members' discount that
  the row does not state. An amount followed by anything else settles nothing for that
  screening, so `price` stays empty there and carries on the rows that state one figure and
  no condition.
- **The poster is the cinema's own `alignleft` image and it is portrait.** WordPress
  renders it through Toolset's `-wpcf_WxH` resizer, 235x336 and 236x336 on the live page,
  so the dimensions are in the filename and are checked rather than assumed: a landscape
  file is not published and the TMDB pass supplies a poster instead.
- **The rating is the KAVI icon's filename**, `ikaraja_12-wpcf_30x30.png` beside a content
  symbol. The number is read from the filename because the page prints no rating text;
  `ikaraja_s` is the S marker. An icon this parser does not recognise leaves `rating`
  empty rather than guessing.

**Zero blocks fails the site.** The page publishes no sentence saying there is no
programme, so there is no evidence of an empty one to read a zero-block parse as, and
`common.EmptyProgramme` needs that evidence.

**`book="door"`.** `/palvelut/lipunmyynti-ja-tuolikartta/` states the box office opens 30
minutes before the day's first screening and that reservations are taken by telephone and
email. There is no online sale anywhere on the site: the only off-site link on that page
is the web developer's. The showtime links to the film's own page on the cinema's site.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, get_text, resolve_year, weekday_index

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "matintupa", "label": "Elokuvateatteri Matin-Tupa",
     "base": "https://www.matin-tupa.fi",
     "listing": "/ohjelmistossa/",
     "venues": [{"id": "matintupa-ylistaro", "name": "Elokuvateatteri Matin-Tupa",
                 "short": "Elokuvateatteri Matin-Tupa", "city": "Ylistaro"}]},
]

# `resolve_year`'s (behind, ahead). The live page carried four days and the cinema
# publishes a week at a time, so this is headroom rather than a fit.
WINDOW = (30, 120)

BLOCK_RE = re.compile(r'<div class="col-sm-\d+">(.*?)</div>', re.S | re.I)
TITLE_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]*/elokuvat/([^"/]+)/?)"[^>]*>(.*?)</a>',
                      re.S | re.I)
# Everything between the two labels. `Liput:` always follows `Esitysajat:` on the live
# page; a block missing it takes the rest of the block, which the time pattern then filters.
TIMES_RE = re.compile(r'<b>\s*Esitysajat:\s*</b>(.*?)(?:<b>|$)', re.S | re.I)
SHOW_RE = re.compile(r'\b([A-Za-zÅÄÖåäö]{2})\s+(\d{1,2})\.(\d{1,2})\.?\s*klo\s*'
                     r'(\d{1,2})[.:](\d{2})', re.I)
FIELD_RE = re.compile(r'<b>\s*(Liput|Kesto|Genre):\s*</b>(.*?)(?:<b>|<p|<br|$)', re.S | re.I)
# One amount and nothing else. A comma or a dot separates the cents, and the euro sign may
# sit either side; anything after it means the row states a condition this cannot settle.
PRICE_RE = re.compile(r'^(?:€\s*)?(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|eur)?$', re.I)
LEN_RE = re.compile(r'(?:(\d{1,2})\s*(?:t|h)\s*)?(\d{1,3})\s*min', re.I)
# Toolset's resizer writes the served dimensions into the filename.
POSTER_RE = re.compile(r'<img[^>]+src="([^"]+?-wpcf_(\d{2,4})x(\d{2,4})\.(?:jpe?g|png|webp))"'
                       r'[^>]*class="[^"]*\balignleft\b', re.S | re.I)
RATING_RE = re.compile(r'ikaraja_(\d{1,2}|s)\b', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def text(fragment):
    """Markup -> one line of plain text."""
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", fragment or ""))).strip()


def fields(block):
    """-> {label: value} for the `<b>`-labelled fields of one film block."""
    return {m.group(1).lower(): text(m.group(2)) for m in FIELD_RE.finditer(block)}


def price_of(value):
    """The `Liput:` value -> a price string, or "" when it states more than one amount.

    A figure with a note beside it settles nothing for the screening: the live page's
    `14,00 €. Kts. lisätiedot` is a Neulekino evening sold with a serving and a members'
    discount the row does not state.
    """
    m = PRICE_RE.match((value or "").strip())
    return f"{m.group(1)}€".replace(".", ",") if m else ""


def minutes_of(value):
    """`1 t 27 min` -> "87". `95 min` -> "95". Anything else -> ""."""
    m = LEN_RE.search(value or "")
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def poster_of(block, base):
    """The block's own portrait poster -> an absolute URL, or "".

    The dimensions are in the filename, so the shape is read rather than assumed. A
    landscape file is left to the TMDB pass.
    """
    m = POSTER_RE.search(block)
    if not m or int(m.group(3)) <= int(m.group(2)):
        return ""
    src = html_mod.unescape(m.group(1))
    return src if src.startswith("http") else base.rstrip("/") + "/" + src.lstrip("/")


def rating_of(block):
    """`ikaraja_12-wpcf_30x30.png` -> "K-12", `ikaraja_s` -> "S", anything else -> ""."""
    m = RATING_RE.search(block)
    if not m:
        return ""
    return "S" if m.group(1).lower() == "s" else f"K-{int(m.group(1))}"


def rows(site, page, today=None):
    """-> (shows, report). One row per `Esitysajat:` line of every film block."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    base = site["base"]
    out, report = [], {"blocks": 0, "untitled": 0, "undated": 0, "no_price": 0}
    for block in BLOCK_RE.findall(page):
        t = TITLE_RE.search(block)
        if not t:
            continue
        report["blocks"] += 1
        title = text(t.group(3))
        if not title:
            report["untitled"] += 1
            continue
        url = html_mod.unescape(t.group(1))
        url = url if url.startswith("http") else base.rstrip("/") + "/" + url.lstrip("/")
        slug = t.group(2)
        f = fields(block)
        price = price_of(f.get("liput", ""))
        if not price:
            report["no_price"] += 1
        length, genres = minutes_of(f.get("kesto", "")), f.get("genre", "")
        img, rating = poster_of(block, base), rating_of(block)
        window = TIMES_RE.search(block)
        for m in SHOW_RE.finditer(text(window.group(1)) if window else ""):
            day, month = int(m.group(2)), int(m.group(3))
            year = resolve_year(day, month, today, weekday_index(m.group(1)), WINDOW)
            if year is None:
                report["undated"] += 1
                continue
            start = datetime.datetime(year, month, day, int(m.group(4)), int(m.group(5)),
                                      tzinfo=FI)
            out.append({
                "eventId": slug,
                "title": title,
                "original": "",
                "len": length,
                "rating": rating,
                "genres": genres,
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": url,
                "img": img,
                "lang": "",
                "soldOut": False,
                "price": price,
                "provider": site["provider"],
                "venue": venue["id"],
            })
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def fetch_site(site, today=None):
    """Runner contract: one request for the programme page."""
    pid = site["provider"]
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    shows, report = rows(site, get_text(url), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no film block with a screening line. This site publishes no sentence "
            f"saying there are none, so there is no evidence of an empty programme to read "
            f"this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['blocks']} film(s)")
    if report["no_price"]:
        print(f"[{pid}] {report['no_price']} film(s) state a ticket line this parser "
              f"cannot settle to one amount, so their rows publish no price")
    if report["undated"]:
        print(f"[{pid}] {report['undated']} screening line(s) whose date no candidate year "
              f"holds inside the window, left out")
    if report["untitled"]:
        print(f"[{pid}] {report['untitled']} film block(s) with no title, left out")
    return per_venue


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src:
        with open(src, encoding="utf-8", errors="replace") as fh:
            shows, report = rows(SITES[0], fh.read())
        print(report)
    else:
        shows = fetch_site(SITES[0])[SITES[0]["venues"][0]["id"]]
    for s in shows:
        print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} "
              f"{s['price']:7} {s['len']:4} {s['img'][-28:]}")
    sys.exit(0)
