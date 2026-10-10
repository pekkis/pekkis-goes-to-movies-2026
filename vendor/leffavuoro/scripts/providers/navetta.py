"""Navettakino, a cinema in a cowshed in Pyhälahti, Konnevesi. Stdlib only.

One request. The front page is a WordPress block page, and the programme is prose in it:

    <p class="wp-block-paragraph"><strong>Tulevan viikolopun näytökset</strong></p>
    <p class="wp-block-paragraph">Hetki ennen valoa<br>su 20.9 klo 15:00</p>
    <p class="wp-block-paragraph">Presidentin kyyditys<br>su 20.9 klo 17:00</p>
    <p class="wp-block-paragraph"><br><br></p>
    <p class="wp-block-paragraph"><strong>Hetki ennen valoa</strong></p>
    <figure class="wp-block-image ..."><img width="719" height="1024" src="...juliste...">
    <p class="wp-block-paragraph">Klaus Härön uutuuselokuva kertoo ...</p>
    <p class="wp-block-paragraph">K7, 87 min, liput 10 €</p>

What shapes the parser:

- **The list is the schedule and the blocks below are a shelf.** On the day read the page
  carried three film blocks and two screenings, Ryhmä Hau having a block and no showing.
  So the blocks supply the poster, the synopsis, the rating, the runtime and the price,
  joined to a screening on the normalised title, and a screening whose title has no block
  publishes anyway with those fields empty. A film is not omitted for being thinly
  described.
- **A film title is the paragraph a figure follows.** Nothing else marks one: the heading
  is a `<strong>` the editor sometimes closes early, "Presidentin kyydity</strong>s" on the
  day read, so the paragraph's whole text is the title and the `<strong>` is not read.
- **The screening list ends at the first blank paragraph or the first film block.** Every
  paragraph between the heading and that point is a screening: a title line and one date
  line per showing. A line inside that block the parser cannot read raises, because the
  block is where the cinema states its whole weekend. Read 2026-10-10, the page put the
  first screening in the heading's own paragraph and left no blank before the film blocks,
  so lines after the heading count as the first screening.
- **The date prints no year** and no dot after the month, `su 20.9 klo 15:00`, so the
  weekday selects the year through `common.resolve_year`.
- **The metadata line is read by pattern, not by position.** The three films read gave
  `K7, 87 min, liput 10 €`, `Kesto 1 h 27 min, K12, liput 10 €` and `Kesto 1 h 29 min,
  K7, liput 10 €`. A `liput` figure that is not one amount settles nothing.
- **No ticket host exists and none is invented.** The contact page's own words:
  "Lippukassa avataan 30 minuuttia ennen ensimmäistä näytöstä." So `book="door"` and a
  showtime opens this page.
- The poster is the block's own figure, portrait with the dimensions in the tag,
  700x1000 to 719x1024 on the three films read, so a landscape image is left out.
- No language and no genre is published, so both stay empty.

**An empty weekend is the ordinary case here, and the page says so in its own words:**
"Meillä on näytöksiä pääsääntöisesti vain viikonloppuisin, mutta toiminta on hieman
epäsäännöllistä. Esitysajat ilmestyvät tälle sivulle aina alkuviikosta, mikäli
viikonlopulle on näytöksiä tulossa." So the evidence for an empty programme is that
sentence, the screening heading rendered with nothing listed under it, and no date or
clock printed anywhere in the content. The last is read without the listing parser: the
sentence says times appear only when there are screenings, so a time the listing did not
reach (a blank line under the heading, the weekend typed as a list block) fails the site.
`EMPTY_VENUES_CONFIRMED` then publishes a fresh empty file rather than ageing the last
weekend for a month. The Wayback captures of this domain stop in 2024 on an older
template and the two 2026 ones are the host's challenge page, so what the page looks like
with the heading removed is **not** known: that case raises, which keeps the previous
files and names it in the log.
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
    {"provider": "navettakino", "label": "Navettakino",
     "base": "https://www.navettakino.fi",
     "listing": "/",
     "venues": [{"id": "navettakino-konnevesi", "name": "Navettakino",
                 "short": "Navettakino", "city": "Konnevesi"}]},
]

# `resolve_year`'s (behind, ahead). The page publishes the coming weekend and nothing
# further, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

CONTENT_RE = re.compile(r'<div class="entry-content.*?(?=</article>|\Z)', re.S | re.I)
BLOCK_RE = re.compile(r"<(p|figure)\b[^>]*>(.*?)</\1>", re.S | re.I)
# The site's own spelling, "viikolopun", is a typo for viikonlopun. Matched loosely enough
# to survive its correction and tightly enough not to match the intro paragraph.
HEADING_RE = re.compile(r"tulevan\s+viiko\w*\s+näytökset", re.I)
# The intro sentence that says the times appear only when there are screenings. It is what
# proves an empty page is this page rather than an error page.
INTRO_RE = re.compile(r"esitysajat\s+ilmestyvät\s+tälle\s+sivulle", re.I)
# A weekday and a date, or a clock, anywhere in the content. Loose on purpose: it is
# checked only when the listing yielded nothing, and a hit there fails the site.
TIMES_RE = re.compile(r"\b(?:ma|ti|ke|to|pe|la|su)\s+\d{1,2}\.\d{1,2}\b"
                      r"|\bklo\s*\d{1,2}[:.]\d{2}", re.I)
SHOW_RE = re.compile(r"^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s*klo\s*"
                     r"(\d{1,2})[:.](\d{2})$", re.I)
IMG_RE = re.compile(r'<img[^>]*?width="(\d+)"[^>]*?height="(\d+)"[^>]*?src="([^"]+)"', re.I)
RATING_RE = re.compile(r"\bK[-\s]?(\d{1,2})\b")
S_RATING_RE = re.compile(r"(?:^|[\s,(])S(?=[\s,)]|$)")
MIN_RE = re.compile(r"(?:(\d{1,2})\s*h\s*)?(\d{1,3})\s*min", re.I)
PRICE_RE = re.compile(r"liput\s+([^,;]+?)\s*(?:$|,|;)", re.I)
AMOUNT_RE = re.compile(r"^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$")
TAGS_RE = re.compile(r"<[^>]+>")

POSTER_MIN_RATIO = 1.2
POSTER_MIN_WIDTH = 300

# Set on the evidence in the docstring: the intro sentence, the screening heading with
# nothing listed under it, and no date or clock anywhere in the content. A heading the page
# does not render never reaches this: it raises, because that is a template change and not
# a quiet weekend.
EMPTY_VENUES_CONFIRMED = True


class ListingError(RuntimeError):
    """The programme block is there and this parser could not read it.

    Skipping a line would publish a weekend one screening short with nothing in the log
    to say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = TAGS_RE.sub("", s)
    s = html_mod.unescape(s).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")).strip()


def content(page):
    """The page's `entry-content`, or "" when it does not render one."""
    m = CONTENT_RE.search(page or "")
    return m.group(0) if m else ""


def blocks(page):
    """[(kind, text or raw)] for the content's paragraphs and figures, in document order."""
    out = []
    for tag, inner in BLOCK_RE.findall(content(page)):
        out.append(("figure", inner) if tag.lower() == "figure" else ("p", _txt(inner)))
    return out


def _minutes(text):
    m = MIN_RE.search(text or "")
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def _rating(text):
    m = RATING_RE.search(text or "")
    if m:
        return f"K-{int(m.group(1))}"
    return "S" if S_RATING_RE.search(text or "") else ""


def _price(text):
    """`liput 10 €` -> "10€". A figure that is not one amount settles nothing."""
    m = PRICE_RE.search(text or "")
    if not m:
        return ""
    a = AMOUNT_RE.match(m.group(1).strip())
    return f"{a.group(1)}€" if a else ""


def _poster(figure):
    m = IMG_RE.search(figure or "")
    if not m:
        return ""
    w, h, url = int(m.group(1)), int(m.group(2)), html_mod.unescape(m.group(3))
    if w < POSTER_MIN_WIDTH or h < w * POSTER_MIN_RATIO:
        return ""
    return url


def _is_meta(text):
    """A short line stating a rating, a runtime or a ticket price rather than prose."""
    if len(text) > 120:
        return False
    return bool(PRICE_RE.search(text) or MIN_RE.search(text) or RATING_RE.search(text))


def films(page):
    """{norm(title): facts} for every block on the page. -> dict.

    A film block is a paragraph a figure follows. What comes after the figure and before
    the next such paragraph is that film's own prose: the longest of those paragraphs is
    the synopsis and the metadata line is whichever one states a rating, a runtime or a
    price.
    """
    bl = blocks(page)
    out = {}
    for i, (kind, value) in enumerate(bl):
        if kind != "p" or not value or i + 1 >= len(bl) or bl[i + 1][0] != "figure":
            continue
        facts = {"img": _poster(bl[i + 1][1]), "syn": "", "len": "", "rating": "",
                 "price": ""}
        for kind2, text in bl[i + 2:]:
            if kind2 == "figure":
                break
            if not text:
                continue
            if _is_meta(text):
                facts["len"] = facts["len"] or _minutes(text)
                facts["rating"] = facts["rating"] or _rating(text)
                facts["price"] = facts["price"] or _price(text)
            elif len(text) > len(facts["syn"]):
                facts["syn"] = text
        out.setdefault(norm(value), facts)
    return out


def listing(page):
    """The screening paragraphs under the heading. -> list or None.

    The list ends at the first blank paragraph or the first film block, a paragraph a
    figure follows. Lines after the heading inside its own paragraph are the first
    screening. None means the page did not render the heading at all, which is a template
    change rather than a quiet weekend.
    """
    bl = blocks(page)
    for i, (kind, text) in enumerate(bl):
        m = HEADING_RE.search(text or "") if kind == "p" else None
        if m:
            rest = text[m.end():].lstrip(" :").strip()
            out = [rest] if rest else []
            for j in range(i + 1, len(bl)):
                kind2, text2 = bl[j]
                if kind2 != "p" or not text2:
                    break
                if j + 1 < len(bl) and bl[j + 1][0] == "figure":
                    break
                out.append(text2)
            return out
    return None


def rows(site, page, today=None):
    """-> ([show], report). One row per screening line the weekend block prints."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    listed = listing(page)
    if listed is None:
        raise ListingError(f"{site['provider']}: the page renders no "
                           f"'Tulevan viikonlopun näytökset' heading")
    shelf = films(page)
    out, report = [], {"no_facts": set(), "no_price": set()}
    for para in listed:
        lines = [l for l in para.split("\n") if l.strip()]
        if len(lines) < 2:
            raise ListingError(f"{site['provider']}: the screening paragraph {para!r} "
                               f"carries no date line")
        title = lines[0].strip()
        facts = shelf.get(norm(title))
        if facts is None:
            report["no_facts"].add(title)
            facts = {"img": "", "syn": "", "len": "", "rating": "", "price": ""}
        if not facts["price"]:
            report["no_price"].add(title)
        for line in lines[1:]:
            m = SHOW_RE.match(line.strip())
            if not m:
                raise ListingError(f"{site['provider']}: {title!r} prints the line "
                                   f"{line!r}, which is no date and time this parser reads")
            wd, day, month, hh, mm = m.groups()
            year = resolve_year(int(day), int(month), today, weekday_index(wd), WINDOW)
            if year is None:
                raise ListingError(
                    f"{site['provider']}: {title!r} prints {wd} {day}.{month}. and no "
                    f"candidate year carries that weekday inside the window, so the "
                    f"screening cannot be placed")
            try:
                start = datetime.datetime(year, int(month), int(day), int(hh), int(mm),
                                          tzinfo=FI)
            except ValueError as e:
                raise ListingError(f"{site['provider']}: {title!r} prints the impossible "
                                   f"date {day}.{month}.{year}") from e
            row = {
                "eventId": norm(title),
                "title": title,
                "original": "",
                "len": facts["len"],
                "rating": facts["rating"],
                "genres": "",
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": url,
                "img": facts["img"],
                "lang": "",
                "soldOut": False,
                "price": facts["price"],
                "provider": site["provider"],
                "venue": venue["id"],
            }
            if facts["syn"]:
                row["_syn"] = facts["syn"]
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
        if TIMES_RE.search(TAGS_RE.sub(" ", content(page))):
            raise RuntimeError(
                f"{url}: the weekend block is empty and the page prints a date or time "
                f"elsewhere ({served(page)}). Treating it as screenings the listing missed "
                f"rather than a quiet weekend, so the previous files stand")
        if INTRO_RE.search(content(page)):
            print(f"[{pid}] {venue['name']}: the weekend block is empty and the page says "
                  f"the times appear only when there are screenings, so the venue is "
                  f"confirmed empty")
            return {venue["id"]: []}
        raise RuntimeError(
            f"{url}: the weekend block is empty and the page does not carry its own "
            f"sentence about when times appear ({served(page)}). Treating it as a fetch "
            f"or template failure rather than a quiet weekend, so the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len({s['eventId'] for s in shows})} film(s)")
    if report["no_facts"]:
        print(f"[{pid}] {len(report['no_facts'])} screening(s) whose film has no block on "
              f"the page, published without metadata: "
              f"{', '.join(sorted(report['no_facts'])[:6])}")
    if report["no_price"]:
        print(f"[{pid}] {len(report['no_price'])} film(s) whose block settles no price: "
              f"{', '.join(sorted(report['no_price'])[:6])}")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:30]:32} {s['rating']:5} "
                  f"{s['len']:4} {s['price']:6} img={'y' if s['img'] else '-'} "
                  f"syn={len(s.get('_syn', ''))}")
    sys.exit(0)
