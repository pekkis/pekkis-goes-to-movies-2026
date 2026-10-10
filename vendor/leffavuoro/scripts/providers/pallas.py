"""Bio Pallas, the funkis cinema in Karjaa, Raasepori. Stdlib only.

One request. `biopallas.com` is a Wix site and the programme **is** the front page:
`<title>Ohjelmisto/Program</title>`, and `pages-sitemap.xml` lists three URLs in all, the
root and two standing pages. There is no film page, no second request and no synopsis.

**It is server-rendered, and that was checked rather than assumed.** Wix often keeps the
content in a JSON payload, so all 60 `<script>` blocks were grepped for the titles the
page shows on 2026-09-19 and none carries one. The only `/_api/` strings on the page are
Wix platform infrastructure. The titles exist in the markup and nowhere else.

What shapes the parser:

- **The document order is the structure, and the component ids are not.** Wix renders each
  screening as a repeater item whose elements share an `__item-<id>` suffix, but the
  `comp-` prefix changes on every page edit (`comp-mu29rvaw__item-mtioxnm3` today against
  `comp-mdyjq4k43__item-mdms6esh` on a 2025-08-08 capture, for the same slot) and the item
  ids repeat across days. So nothing is keyed on either. What is stable is the order of
  the rich-text elements and the images:

      TEXT ['LÖRDAG/LAUANTAI 19.9']            <- day heading, ignored
      IMG  61d9eb_ae44...~mv2.jpg 1080x1920    <- poster
      TEXT ['Myrskyn ikkuna', '1h 40min -K12-']
      TEXT ['La/Lö 19.9', 'Klo 18.00']
      TEXT ['13€']

  A row is the date-and-time block. Its title is the block before it, its price the block
  after, its poster the last image before its title. The day headings are redundant, since
  every row repeats its own date, and they are read only to report a day the cinema has
  closed.
- **A row is a date and a time in one block, which is what excludes the coming-soon
  list.** The trailing "Seuraavana ohjelmistossa | Nästa i program" block renders the same
  markup for five entries carrying a title and a bare date, but the date stands alone in
  its own block with no `Klo` beside it. Those are release dates, not screenings. Both
  halves are required, and neither is the block's heading, so renaming the heading cannot
  let them through and a date block that stops carrying a readable time is dropped rather
  than published at midnight.
- **No date carries a year**, on the heading or on the row, on all six readings, so the
  weekday selects it through `common.resolve_year` and a line it cannot place raises. The
  weekday is bilingual and abbreviated, Finnish first: `La/Lö`, `Su/Sö`, `Ma/Må`, `Ti`,
  `Ke/Ons`, `To`. `common.weekday_index` reads the first two characters, so the Finnish
  half is what it sees and the Swedish half is never parsed.
- **The price is the row's own block, and one amount settles it.** Ten of thirteen rows
  read `13€`; the two matinees read `12€ med kaffeserv./kahvitarjoilulla`, one amount with
  a description of what it includes; the concert reads `22/25€`, two amounts with nothing
  on the row to choose between them, so that row publishes no price. The site states no
  house tariff at all, which is why this is a per-row field rather than a constant.
- **A row is not always a film.** 23.9 is a touring orchestra, sold through a third party's
  shop by an organiser who is not the cinema. It is published as a screening anyway,
  because the only thing separating it from a film row is the absence of the
  `1h 40min -K12-` line, and dropping rows on a missing optional field loses real films the
  day the cinema forgets one. Its ticket link is not read and not published: `book="door"`
  puts every row on the programme page, and this repo does not call a booking endpoint.
- **The poster lives in an attribute, not in a `src`.** The `<img>` carries no `src` at
  all; `<wow-image data-image-info="...">` holds escaped JSON whose `imageData.uri` names
  the file on `static.wixstatic.com`, with its own width and height beside it. Those
  dimensions are what the portrait filter reads, so unlike `lieksa.py` this adapter can
  check the shape of every poster it publishes. Measured across six readings, every poster
  is portrait and the page's one landscape image is its hero, outside every row.
  `mirror_posters.py` downscales the original, so the CDN's own resize is not used.
- **A language marker is published only when it names an audio language outright**, as
  `FI-A` or `SV-A`. The optional middle paragraph of the title block has carried
  `SUOMEKSI`, `PÅ SVENSKA`,
  `ORIGINAL version with subtitles FI/SV` and `Huom! Ilman suomenkielistä tekstitystä`
  across captures. The first two name the audio; the others describe subtitles or name two
  languages at once and settle nothing, so they publish nothing.
- **Titles are published verbatim**, because the raw title is the key for `normTitle()`,
  `films-extra.json` and `tmdb-aliases.json`. The one thing removed is a zero-width space:
  the site's editor leaves a trailing U+200B on many titles, which no reader sees and
  which would key those rows apart from the same film everywhere else.

**Zero rows fails the site.** Six readings over fourteen months, the live page plus five
Wayback captures, every one rendered a programme. What the site does have is a per-day
closure block, written as that day's only content in place of its rows, and its wording is
not standardised: `STÄNGT/KIINNI`, `Kiinni/stängd`, a bare `Kiinni`, `OLEMME LOMALLA/VI ÄR
PÅ SEMESTER`. That is evidence about a day, never about the programme, so it cannot carry
the `common.EmptyProgramme` gate the way Marita's single sentence does. A closed day is
counted and named in the log; an empty parse is the broken case and raises.
"""
import datetime
import html as html_mod
import json
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, fetch, get_text, resolve_year, served, weekday_index
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "biopallas", "label": "Bio Pallas",
     "base": "https://www.biopallas.com",
     "listing": "/",
     "venues": [{"id": "pallas-karjaa", "name": "Bio Pallas",
                 "short": "Bio Pallas", "city": "Karjaa"}]},
]

# `resolve_year`'s (behind, ahead). The page published Saturday to Thursday on the day it
# was read, and its own standing note says schedules go up every Monday, so a week is the
# horizon and 120 days is headroom rather than a fit.
WINDOW = (30, 120)

SCRIPT_RE = re.compile(r"<script.*?</script>", re.S | re.I)
RICH_RE = re.compile(r'data-testid="richTextElement"[^>]*>(.*?)</div>', re.S | re.I)
IMG_INFO_RE = re.compile(r'data-image-info="([^"]*)"')
PARA_RE = re.compile(r"</p>", re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# `La/Lö 19.9` and `Ti 22.9` alike: the Finnish abbreviation, then an optional Swedish one
# after a slash, then the day and month. Anchored, so a sentence mentioning a date is not
# a row.
DATE_RE = re.compile(r"^([A-Za-zÅÄÖåäö]{2,3})(?:\s*/\s*[A-Za-zÅÄÖåäö]{2,4})?\s*"
                     r"(\d{1,2})\.(\d{1,2})\.?$")
TIME_RE = re.compile(r"^klo\s*(\d{1,2})[.:](\d{2})$", re.I)
# The day heading, which carries the weekday spelled out in both languages.
HEADING_RE = re.compile(r"^[A-Za-zÅÄÖåäö]{3,}\s*/\s*[A-Za-zÅÄÖåäö]{3,}\s+(\d{1,2})\.(\d{1,2})\.?$")
META_RE = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*min)?\s*-\s*[Kk]?\s*([0-9]{1,2}|[Ss])\s*-")
# A figure that is part of a price: one against a euro sign, or one joined to another by
# a slash or a dash. Counting these is the whole rule, because what settles a row is
# whether the block names one amount or several. `22/25€` names two and `12€ med
# kaffeserv./kahvitarjoilulla` names one with a description of what it includes.
PRICE_PART = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)(?=\s*(?:[/\u2013-]\s*\d|€))")
# Only a marker that names the audio language outright. A subtitle note names no audio and
# `original ... FI/SV` names two, so neither is here. The value is the show contract's
# `FI-A` form: a bare `fi` matched nothing the client or the pages read (2026-10-04).
LANGS = {"suomeksi": "FI-A", "på svenska": "SV-A", "pa svenska": "SV-A"}

MEDIA = "https://static.wixstatic.com/media/"
POSTER_MIN_W = 300
POSTER_MIN_RATIO = 1.2


class ShowRowError(RuntimeError):
    """A screening the page prints and this parser could not place.

    Skipping one would publish a schedule a screening short with nothing in the log to say
    so, so it fails the site and the previous files stand.
    """


def _text(fragment):
    s = TAGS_RE.sub(" ", fragment or "")
    s = html_mod.unescape(s).replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", s).strip()


def _paragraphs(body):
    """A rich-text element's non-empty paragraphs, in order. -> [str]."""
    return [p for p in (_text(x) for x in PARA_RE.split(body or "")) if p]


def events(page):
    """Every rich-text block and poster on the page, in document order.
    -> [("text", [paragraph, ...]) | ("img", {"uri", "w", "h"})].

    Scripts are removed first: Wix inlines its own component definitions, which carry both
    shapes as string literals.
    """
    body = SCRIPT_RE.sub(" ", page or "")
    out = []
    for m in RICH_RE.finditer(body):
        paras = _paragraphs(m.group(1))
        if paras:
            out.append((m.start(), "text", paras))
    for m in IMG_INFO_RE.finditer(body):
        try:
            data = json.loads(html_mod.unescape(m.group(1))).get("imageData") or {}
        except (ValueError, AttributeError):
            continue
        uri = (data.get("uri") or "").strip()
        if uri:
            out.append((m.start(), "img",
                        {"uri": uri, "w": data.get("width"), "h": data.get("height")}))
    out.sort(key=lambda e: e[0])
    return [(kind, value) for _, kind, value in out]


def _poster(img):
    """A portrait poster on the cinema's own CDN, or "".

    The dimensions travel with the reference, so the shape is checked per run rather than
    trusted: the page's hero image is landscape and sits outside every row, and a template
    change that put it inside one would otherwise publish it.
    """
    if not img:
        return ""
    w, h = img.get("w"), img.get("h")
    if not isinstance(w, int) or not isinstance(h, int) or w < POSTER_MIN_W:
        return ""
    if h < w * POSTER_MIN_RATIO:
        return ""
    return MEDIA + img["uri"]


def _meta(paragraphs):
    """The optional `1h 40min -K12-` line. -> (minutes, rating), either possibly ""."""
    for p in paragraphs:
        m = META_RE.search(p)
        if not m:
            continue
        hours, mins, rating = m.groups()
        total = (int(hours) * 60 if hours else 0) + (int(mins) if mins else 0)
        code = rating.upper()
        return (str(total) if total else ""), ("S" if code == "S" else f"K-{int(code)}")
    return "", ""


def _lang(paragraphs):
    """An audio language the row names outright, or ""."""
    for p in paragraphs:
        got = LANGS.get(p.strip().lower().rstrip("!"))
        if got:
            return got
    return ""


# A paragraph naming a membership: `7€ F-Keks jäsenille` beside `10€` (2026-09-27).
MEMBER_RE = re.compile(r"j[äa]sen|medlem", re.I)


def _price(paragraphs):
    """One amount settles the row; anything else settles nothing.

    `12€ med kaffeserv./kahvitarjoilulla` is one amount with a description of what it
    includes and publishes 12€. `22/25€` offers two with nothing on the row to choose
    between them and publishes nothing. A members' amount in its own paragraph is not the
    public price and does not compete with it: `10€` / `7€ F-Keks jäsenille` publishes 10€,
    and a members' amount alone publishes nothing.
    """
    public = [a for p in paragraphs if not MEMBER_RE.search(p) for a in PRICE_PART.findall(p)]
    return f"{public[0]}€" if len(public) == 1 else ""


def rows(site, page, today=None):
    """-> ([show], report). One show per `Klo` line the programme prints."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    stream = events(page)
    out, report = [], {"closed": [], "no_price": [], "no_poster": []}
    headings, dated = [], set()
    last_img = None
    for i, (kind, value) in enumerate(stream):
        if kind == "img":
            last_img = value
            continue
        if HEADING_RE.match(value[0]) and len(value) == 1:
            headings.append(value[0])
            last_img = None
            continue
        if len(value) < 2:
            continue
        dm, tm = DATE_RE.match(value[0]), TIME_RE.match(value[1])
        if not dm or not tm:
            continue
        title_block = stream[i - 1][1] if i and stream[i - 1][0] == "text" else None
        if not title_block or not title_block[0]:
            raise ShowRowError(f"{site['provider']}: the screening at {value[0]} "
                               f"{value[1]} has no title block before it")
        price_block = stream[i + 1][1] if i + 1 < len(stream) and stream[i + 1][0] == "text" else []
        title = title_block[0]
        wd, day, month = dm.group(1), int(dm.group(2)), int(dm.group(3))
        year = resolve_year(day, month, today, weekday_index(wd), WINDOW)
        if year is None:
            raise ShowRowError(
                f"{site['provider']}: {title!r} prints {wd} {day}.{month}. and no "
                f"candidate year carries that weekday inside the window, so the "
                f"screening cannot be placed")
        try:
            start = datetime.datetime(year, month, day, int(tm.group(1)), int(tm.group(2)),
                                      tzinfo=FI)
        except ValueError as e:
            raise ShowRowError(f"{site['provider']}: {title!r} prints the impossible "
                               f"date {day}.{month}.{year} {tm.group(0)}") from e
        length, rating = _meta(title_block[1:])
        price = _price(price_block)
        img = _poster(last_img)
        if not price:
            report["no_price"].append(title)
        if not img:
            report["no_poster"].append(title)
        dated.add(f"{day}.{month}")
        out.append({
            "eventId": norm(title),
            "title": title,
            "original": "",
            "len": length,
            "rating": rating,
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": start.isoformat(),
            "url": url,
            "img": img,
            "lang": _lang(title_block[1:]),
            "soldOut": False,
            "price": price,
            "provider": site["provider"],
            "venue": venue["id"],
        })
        last_img = None
    for h in headings:
        m = HEADING_RE.match(h)
        if f"{int(m.group(1))}.{int(m.group(2))}" not in dated:
            report["closed"].append(h)
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
            f"{url}: no screening line on the programme page ({served(page)}). This site "
            f"has never been seen with an empty programme, only with a single day closed, "
            f"so there is no evidence of one to read this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len({s['eventId'] for s in shows})} film(s)")
    if report["closed"]:
        print(f"[{pid}] {len(report['closed'])} day(s) the page heads but does not fill, "
              f"read as closed: {', '.join(report['closed'][:6])}")
    if report["no_price"]:
        print(f"[{pid}] {len(report['no_price'])} row(s) whose price block settles no one "
              f"amount: {', '.join(sorted(set(report['no_price']))[:6])}")
    if report["no_poster"]:
        print(f"[{pid}] {len(report['no_poster'])} row(s) with no portrait poster: "
              f"{', '.join(sorted(set(report['no_poster']))[:6])}")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} "
                  f"{s['len']:4} {s['price']:7} {s['lang']:3} "
                  f"img={'y' if s['img'] else '-'}")
    sys.exit(0)
