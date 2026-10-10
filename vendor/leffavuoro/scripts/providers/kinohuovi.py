"""Kino-Huovi, Harjavalta. Stdlib only.

One request, to the front page. The programme is a Duda blog list rendered server-side:
`<div class="postArticle">` per film, holding `.postTitle h3 a` and a `.postDescription`
whose plain text carries the dates, the weekdays, the time, the runtime and the price.
Checked for a structured source first and there is none: the site is Duda rather than
WordPress, it publishes no feed, and the card text is where the programme lives.

What shapes the parser, measured on the live page 2026-09-21:

- **The card's own link is not a film key.** The card titled `RAKKAUTTA JA VIRTAHEPOJA` is
  served at `/hetki ennen valoa`, the alias of the film that occupied the slot before it,
  so the alias is recycled and two different films share one. `eventId` is therefore a slug
  of the published title. The title itself stays verbatim, because it is what `normTitle()`,
  `films-extra.json` and `tmdb-aliases.json` key on.
- **A card states one compact date or a range, plus the weekdays.**
  `RAKKAUTTA JA VIRTAHEPOJA 25.-28.9. PE, LA, SU ja MA klo 18.00` is four screenings, and
  the four weekdays are what proves the four days. A range expands only when the listed
  weekdays and the expanded dates agree one for one; a card where they disagree is counted
  and left out rather than published on a guess.
- **No date carries a year.** `common.resolve_year` places each one from the weekday, so a
  page left up past its week selects a year the window then refuses.
- **One `klo` applies to every date on the card.** A card carrying as many times as dates
  pairs them in order; any other count settles nothing and the card is left out.
- **The price is published only when the ticket line is one bare amount.** `Liput 12€.` is
  that; anything further on the line states a condition this cannot settle.
- **The runtime is the card's own `Kestoaika`**, written `n.1t30min.` and `n. 1t 40min.`.
  The cinema qualifies it as approximate and that is the figure it publishes; nothing here
  computes one.
- **The poster is the card's `data-background-image`, and its shape cannot be checked from
  the URL.** Duda's CDN names the file `-1920w.jpg` and serves a resized variant, 224x320
  and 225x320 for the two live cards read on 2026-09-21, so both are portrait. This is the
  one field here whose shape the parser cannot verify, unlike `matintupa.py` where the
  resizer writes the dimensions into the filename.
- **No rating is printed on a card**, so `rating` stays empty and the shared KAVI pass may
  supply one.

**Zero cards fails the site.** The page publishes no sentence saying there is no
programme, so there is no evidence of an empty one to read a zero-card parse as, and
`common.EmptyProgramme` needs that evidence.

**`book="door"`.** The site states "osta liput teatterilta tai kysy lisää" and carries no
online sale: no ticket host appears anywhere in the page. The showtime links to the card's
own page on the cinema's site.
"""
import datetime
import html as html_mod
import re
import sys
from urllib.parse import quote
from zoneinfo import ZoneInfo

from common import check_shows, get_text, resolve_year, weekday_index

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kinohuovi", "label": "Kino-Huovi",
     "base": "https://www.kinohuovi.fi",
     "listing": "/",
     "venues": [{"id": "kinohuovi-harjavalta", "name": "Kino-Huovi",
                 "short": "Kino-Huovi", "city": "Harjavalta"}]},
]

# `resolve_year`'s (behind, ahead). The live page carried eight days and the cinema
# publishes a weekend at a time, so this is headroom rather than a fit.
WINDOW = (30, 120)

CARD_RE = re.compile(r'<div[^>]*\bclass="[^"]*\bpostArticle\b[^"]*"[^>]*>(.*?)'
                     r'(?=<div[^>]*\bclass="[^"]*\bpostArticle\b|\Z)', re.S | re.I)
TITLE_RE = re.compile(r'<div[^>]*\bclass="[^"]*\bpostTitle\b[^"]*"[^>]*>\s*<h3[^>]*>\s*'
                      r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
DESC_RE = re.compile(r'<div[^>]*\bclass="[^"]*\bpostDescription\b[^"]*"[^>]*>(.*?)</div>',
                     re.S | re.I)
IMG_RE = re.compile(r'data-background-image="([^"]+)"', re.I)
TIME_RE = re.compile(r'\bklo\s*(\d{1,2})[.:](\d{2})', re.I)
# `25.-28.9.` and `21.9.`, the two forms the cards use. The times are blanked before this
# runs, so `18.00` cannot be read as a day and a month.
DATE_RE = re.compile(r'\b(\d{1,2})\.(?:\s*[-–]\s*(\d{1,2})\.)?(\d{1,2})\.')
WEEKDAY_RE = re.compile(r'\b(ma|ti|ke|to|pe|la|su)\b', re.I)
KESTO_RE = re.compile(r'Kestoaika\s*n?\.?\s*(?:(\d{1,2})\s*(?:t|h)\s*)?(\d{1,3})\s*min',
                      re.I)
# One amount and nothing else after it. A comma or a dot separates the cents.
PRICE_RE = re.compile(r'\bLiput\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*\.?\s*$', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def text(fragment):
    """Markup -> one line of plain text."""
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", fragment or ""))).strip()


def slug_of(title):
    """The published title -> this row's film key.

    The card's own alias is recycled across films on this site, so it cannot be the key.
    """
    return re.sub(r"-{2,}", "-", re.sub(r"[^\w]+", "-", (title or "").lower(),
                                        flags=re.UNICODE)).strip("-")


def minutes_of(value):
    """`Kestoaika n. 1t 40min.` -> "100". `Kestoaika 95 min` -> "95". Anything else -> ""."""
    m = KESTO_RE.search(value or "")
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def price_of(value):
    """The card text -> a price string, or "" when the ticket line states a condition."""
    for line in re.split(r"(?<=\.)\s+", value or ""):
        m = PRICE_RE.search(line.strip())
        if m:
            return f"{m.group(1)}€".replace(".", ",")
    return ""


def absolute(href, base):
    """A card href -> an absolute URL. The live aliases carry spaces."""
    href = html_mod.unescape(href or "")
    if not href.startswith("http"):
        href = base.rstrip("/") + "/" + href.lstrip("/")
    return quote(href, safe=":/?#[]@!$&'()*+,;=~-._%")


def dates_of(body, today):
    """The card text -> ([date, ...], reason).

    `reason` is "" when the dates are settled, and names why nothing is published
    otherwise, so the caller can count the card rather than guess at it.
    """
    weekdays = [w.lower() for w in WEEKDAY_RE.findall(body)]
    m = DATE_RE.search(body)
    if not m:
        return [], "undated"
    first, last, month = int(m.group(1)), int(m.group(2) or m.group(1)), int(m.group(3))
    if not (1 <= month <= 12) or not (1 <= first <= 31) or last < first:
        return [], "unreadable"
    days = list(range(first, last + 1))
    if weekdays and len(weekdays) != len(days):
        return [], "mismatch"
    out = []
    for i, day in enumerate(days):
        wd = weekday_index(weekdays[i]) if weekdays else None
        year = resolve_year(day, month, today, wd, WINDOW)
        if year is None:
            return [], "mismatch" if weekdays else "undated"
        out.append(datetime.date(year, month, day))
    return out, ""


def rows(site, page, today=None):
    """-> (shows, report). One row per date of every programme card."""
    today = today or datetime.datetime.now(FI).date()
    venue, base = site["venues"][0], site["base"]
    out = []
    report = {"cards": 0, "undated": 0, "unreadable": 0, "mismatch": 0,
              "no_price": 0, "no_weekday": 0}
    for card in CARD_RE.findall(page):
        t = TITLE_RE.search(card)
        d = DESC_RE.search(card)
        if not t or not d:
            continue
        title = text(t.group(2))
        if not title:
            continue
        report["cards"] += 1
        body = text(d.group(1))
        times = [(int(h), int(mi)) for h, mi in TIME_RE.findall(body)]
        blanked = TIME_RE.sub(" ", body)
        days, reason = dates_of(blanked, today)
        if reason:
            report[reason] += 1
            continue
        if not WEEKDAY_RE.search(blanked):
            report["no_weekday"] += 1
        if len(times) == 1:
            times = times * len(days)
        elif len(times) != len(days):
            report["mismatch"] += 1
            continue
        price = price_of(body)
        if not price:
            report["no_price"] += 1
        img = html_mod.unescape(IMG_RE.search(card).group(1)) if IMG_RE.search(card) else ""
        url, length, key = absolute(t.group(1), base), minutes_of(body), slug_of(title)
        for day, (hour, minute) in zip(days, times):
            out.append({
                "eventId": key,
                "title": title,
                "original": "",
                "len": length,
                "rating": "",
                "genres": "",
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": datetime.datetime(day.year, day.month, day.day, hour, minute,
                                           tzinfo=FI).isoformat(),
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
    """Runner contract: one request for the front page."""
    pid, venue = site["provider"], site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    shows, report = rows(site, get_text(url), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no programme card with a screening. This site publishes no sentence "
            f"saying there are none, so there is no evidence of an empty programme to read "
            f"this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['cards']} card(s)")
    for key, note in (("undated", "card(s) with no programme date"),
                      ("unreadable", "card(s) whose date is out of range"),
                      ("mismatch", "card(s) whose dates, weekdays and times disagree"),
                      ("no_weekday", "card(s) stating no weekday to check the year against"),
                      ("no_price", "card(s) whose ticket line settles no single amount")):
        if report[key]:
            print(f"[{pid}] {report[key]} {note}")
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
        print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['price']:7} "
              f"{s['len']:4} {s['img'][-30:]}")
    sys.exit(0)
