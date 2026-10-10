"""Elokuvateatteri Huvimylly, in the Tapahtumatalo hall in Raahe. Stdlib only.

One request, to WordPress's own REST route:

    /wp-json/wp/v2/pages?slug=etusivu&_fields=id,modified_gmt,content

`[0].content.rendered` is byte-identical to the `entry-content` of the front page and
about a tenth of its transfer, 4 kB against 45 kB, and it carries `modified_gmt` as well.
The route was chosen after checking for a screenings API and finding none: `/wp-json/`
lists no plugin namespace holding events, `/wp/v2/types` has only the core types plus
`elementor_library`, and `/wp/v2/posts` is empty. The programme is typed by hand into one
page in the classic editor.

**The site names itself Elokuvateatteri Huvimylly**, eight times on the front page and in
its `<title>`. "Bio Huvimylly" is what the nytleffaan.fi directory calls it, and the
directory also lists the same street address a second time as "Raahesali", which is the
hall rather than the operator. The cinema's own name is the one published.

The programme is one flat `<ul>` of free-form typed lines, which is what shapes everything
below. Measured over the live page and eleven Wayback captures from 2023-05 to 2026-04:

- **A screening is a `Klo` line, and a date heading is a weekday plus a day and month.**
  Consecutive headings share the rows that follow them, which the site does: `Torstaina
  28.12` and `Perjantaina 29.12` head one list of times. No date carries a year on the
  live page, so `common.resolve_year` places it from the weekday. The weekday is spelled
  out, and it is misspelled often enough to matter (`Sunnuntainan`, `Sunnunaina`,
  `Lauanataina`); `common.weekday_index` reads the first two characters, so all of those
  land correctly and the tail is never parsed.
- **A title can run across two `<li>`, and the rating marker is what closes it.** The
  screening at 14.00 on the live page is `Klo 14.00   Saapasjalkakissa` on one line and
  `unohdettu  saari  -k7/4-` on the next. Nothing distinguishes that continuation from a
  free-text note by position alone, and the captures carry real notes in the same place
  (`elokuvan jälkeen ilmainen pullakahvitarjoilu`). So the rule is structural rather than
  positional: the row ends at its `-k7/4-` marker. A `Klo` line carrying one is complete;
  a `Klo` line without one takes the next `<li>` as its continuation **only if that line
  carries a marker**, and otherwise the row is left out and counted. Guessing would publish
  a note as part of a title, and the title is the key for `normTitle()`,
  `films-extra.json` and `tmdb-aliases.json`.
- **Every rating shape the captures show is read**, because the field is typed freehand:
  `-k7/4-`, `-k12/9-`, `-s-`, `k7/4-`, `-k 16/13`, `-k16/13`, `-12/9-`, `-7/4-`, `-k7/-9-`
  and `-k12/9` with an en dash. The second number is KAVI's accompanied-viewing floor and
  is not published; `rating` carries the first.
- **A line this parser cannot place is left out, counted and named in the log, and the
  site fails when more of them fail than succeed.** The captures hold `Klo?`, a dotless
  `Klo 1900`, a row whose title is the placeholder `elokuva avoin`, and a row with no title
  at all. Reading a time out of `Klo 1900` would mean guessing an hour, and publishing
  `elokuva avoin` would put a placeholder on the site as a film. Raising on each was the
  first design and was rejected on the measurement: one capture carries four placeholder
  rows at once, so an operator's ordinary Tuesday would fail the whole site and age every
  other row with it. What the count buys instead is the loud case: a template change breaks
  every row rather than a few, so `unplaceable` exceeding the number of distinct start
  times raises, the same shape `lieksa.py` gets from counting listed lines against read
  ones. Kinotour's undeclared towns are the precedent for counting and naming rather than
  dropping in silence.
- **One line can hold two times**, `Klo 14.00  ja 19.00  Myrskyluodon Maija -k12/9-`, and
  it is two screenings of one film. Both are published.
- **The price is the standing line, and it settles every row.** `Liput  vain 10-€` carries
  no weekday, hall, age or format condition and no row states a price of its own, so it is
  established for every screening rather than a tariff that turns on something unread. It
  is parsed from that line each run and not hardcoded; if the line stops yielding exactly
  one amount, `price` is empty everywhere. The gift tickets and the `Sarjalippu 5x
  elokuvakertaa 45€` on another page are separate products and are not read, the same call
  `lieksa.py` makes about its advance vouchers.
- **No poster is published from this site.** Four portrait JPEGs sit in their own `<li>`
  after the rows with no alt text, no link and no title, and their order is not the rows'
  order: the 2026-02-17 capture runs `vin`, `lm`, `humiseva-harju`, `kaija`, `otso`
  against rows Vinski 2, Kaija Koo, Luottomies, Humiseva Harju, Otso Karu. The filenames
  are hand-abbreviated and key back to nothing, the counts disagree with the row counts in
  both directions across the captures, and two captures use a landscape still as a poster.
  Pairing them by position would put a wrong poster on a row, so the TMDB pass supplies
  them instead.
- **The first `<li>` carries the operator's private email address.** It is read only for
  the price amount, and no line's text is ever carried out of the parse: the report counts
  the lines it could not use rather than keeping them, so there is no field a later change
  could print. `tests/test_contact_address.py` refuses any address in any tracked file,
  generated data included.

**Zero rows fails the site.** No sentence anywhere on it says there are no screenings, and
`/tulevat-elokuvat/` is an empty Elementor page rather than that marker, so there is no
evidence of an empty programme to read a zero-row parse as. The closest state in the
captures is 2024-04-16: the boilerplate renders, no `Klo` line does, and an announcement
stands where the rows were. `common.EmptyProgramme` needs positive evidence and this site
has published none.

**Local, on inherited evidence.** A non-residential address was served 403 with `Server:
Apache` and no `CF-Ray` on 2026-09-18, while an ordinary connection gets 200; re-read from
an ordinary connection on 2026-09-19, 200 again, which neither confirms nor contradicts
the 403. The runner itself has never tried. Routing local on a 403 is the safe direction,
per CLAUDE.md, and needs no runner evidence.
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
    {"provider": "huvimylly", "label": "Elokuvateatteri Huvimylly",
     "base": "https://www.huvimylly.com",
     "listing": "/wp-json/wp/v2/pages?slug=etusivu&_fields=id,modified_gmt,content",
     "page": "/",
     "venues": [{"id": "huvimylly-raahe", "name": "Elokuvateatteri Huvimylly",
                 "short": "Elokuvateatteri Huvimylly", "city": "Raahe"}]},
]

# `resolve_year`'s (behind, ahead). The live page carried one date 22 days out and the
# captures reach about five weeks, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# One `Weekday D.M` with an optional space-separated year, read only out of a line
# HEAD_LINE_RE has already accepted whole.
#
# **The anchoring on HEAD_LINE_RE is the guard, and it is load-bearing twice over.** It
# rejects the captures' `Sunnuntaina  7.12024-`, where a four-digit year is typed straight
# onto the month and no reading of it is safe: the digits left after `7.12` match nothing
# the pattern allows, so the line is not a heading and the screening under it raises
# rather than being placed in December. And it rejects an announcement that happens to
# carry a long word and a date, `Paddington seikkailee 24.1 alkaen`, which without the
# closing anchor would be read as a heading on the weekday "seikkailee" and would place a
# phantom screening. A lookahead on this pattern was tried and removed: it could not be
# made to fail on its own, because the anchoring already rejects every line it would
# catch.
# Six letters at least, written once and used by both patterns. Every Finnish weekday
# name in the essive is eight letters or more, and the floor is what keeps a bare
# `Klo 14.00` line from being read as the weekday "Klo" on 14 February.
WEEKDAY_WORD = r"[A-Za-zÅÄÖåäö]{6,}"
HEAD_ONE_RE = re.compile(rf"({WEEKDAY_WORD})\s+(\d{{1,2}})\.(\d{{1,2}})\.?(?:\s+(\d{{4}}))?")
HEAD_LINE_RE = re.compile(rf"^[-\s]*(?:{WEEKDAY_WORD}\s+\d{{1,2}}\.\d{{1,2}}\.?"
                          rf"(?:\s+\d{{4}})?[\s,ja]*)+$")
KLO_RE = re.compile(r"^klo\b", re.I)
TIME_RE = re.compile(r"(\d{1,2})[.:](\d{2})\b")
# The marker is anchored to the end of the line, which is where all twelve shapes in
# the captures sit, and it has to open with a dash or with a `k` against the number.
# Both requirements were put in by a failing case rather than by taste: an unanchored
# pattern read the final `s` of `Koiramies-k7/4-` as an S rating and published the
# title as "Koiramie". A trailing dash is optional, because `-k 16/13` has none, and
# the en dash is written as an escape because `-k12/9\u2013` is one of the shapes.
RATING_RE = re.compile(
    "\\s*[-\u2013]\\s*k?\\s*(\\d{1,2}|s)\\b\\s*(?:/\\s*[-\u2013]?\\s*\\d{1,2})?\\s*[-\u2013]?\\s*$"
    "|\\s*\\bk\\s*(\\d{1,2})\\b\\s*(?:/\\s*[-\u2013]?\\s*\\d{1,2})?\\s*[-\u2013]?\\s*$", re.I)
# The classes Finnish law has: S, 7, 12, 16 and 18 (kavi.fi/en/age-ratings, read
# 2026-09-25). A typed code outside them is a typo, not a rating: Alatalo's "-k6/13" for
# Lapin sota, which Elokuvateatteri Star lists as K-16, went out as K-6 and the shared
# rating pass lent it to four chains. It closes the title and publishes no rating.
KAVI_CODES = ("S", "7", "12", "16", "18")
# `-k?` closes a title and states no rating, which is not the same as stating none.
UNKNOWN_RATING_RE = re.compile("\\s*[-\u2013]\\s*k\\s*\\?\\s*[-\u2013]?\\s*$", re.I)
PRICE_RE = re.compile(r"liput\s+vain\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*-?\s*€", re.I)


class ShowRowError(RuntimeError):
    """A line inside the programme this parser could not place.

    The programme is typed freehand, so an unreadable line is as likely to be a real
    screening as a note. Publishing a guess would put a wrong time or a note-laden title
    on the site, so the site fails and the previous files stand.
    """


def _text(fragment):
    s = re.sub(r"<br\s*/?>", " ", fragment or "")
    s = TAGS_RE.sub(" ", s)
    s = html_mod.unescape(s).replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", s).strip()


def items(payload):
    """The programme's `<li>` texts, in order. -> [str].

    Raises when the route does not answer with the one page it is asked for, so a login
    wall or a moved slug fails rather than parsing to zero rows.
    """
    try:
        doc = json.loads(payload)
    except ValueError as e:
        raise RuntimeError(f"the page route did not answer JSON ({served(payload)})") from e
    if not isinstance(doc, list) or not doc:
        raise RuntimeError(f"the page route answered no page ({served(payload)})")
    body = ((doc[0].get("content") or {}).get("rendered")) or ""
    return [_text(x) for x in LI_RE.findall(body)]


def price_of(lines):
    """The standing `Liput vain 10-€` amount, or "". One amount or nothing."""
    for line in lines:
        found = PRICE_RE.findall(line)
        if len(found) == 1:
            return f"{found[0]}€"
    return ""


def _dates(line):
    """Every `Weekday D.M [YYYY]` a heading line names. -> [(weekday, day, month, year)]."""
    return [(m.group(1), int(m.group(2)), int(m.group(3)),
             int(m.group(4)) if m.group(4) else None)
            for m in HEAD_ONE_RE.finditer(line)]


STRIP = " -\u2013:,"


def _split_rating(text):
    """`Pirjo -s-` -> ("Pirjo", "S", True). -> (title, rating, marked).

    `marked` is whether the line closed its own title, which is the structural
    question here; `rating` can be "" on a line that closed it with the site's own
    `-k?`, which states that the rating is unknown rather than stating none.
    """
    text = text or ""
    m = UNKNOWN_RATING_RE.search(text)
    if m:
        return text[:m.start()].strip(STRIP), "", True
    m = RATING_RE.search(text)
    if not m:
        return text.strip(STRIP), "", False
    code = (m.group(1) or m.group(2)).upper().lstrip("0") or "0"
    if code not in KAVI_CODES:
        return text[:m.start()].strip(STRIP), "", True
    rating = "S" if code == "S" else f"K-{code}"
    return text[:m.start()].strip(STRIP), rating, True


def rows(site, lines, today=None):
    """-> ([show], report). One show per time on every `Klo` line."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["page"]
    price = price_of(lines)
    # `unread` is a count and never the lines: the page's first item carries the
    # operator's own email address, and a report field holding it is one print away from
    # publishing it.
    out, report = [], {"unread": 0, "no_price": 0, "unplaceable": 0}
    pending, fresh = [], True
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or set(line) <= set(".… "):
            continue
        if PRICE_RE.search(line):
            continue
        if HEAD_LINE_RE.match(line) and _dates(line):
            if not fresh:
                pending, fresh = [], True
            pending += _dates(line)
            continue
        if not KLO_RE.match(line):
            report["unread"] += 1
            continue
        if not pending:
            raise ShowRowError(f"{site['provider']}: {line[:60]!r} is a screening line "
                               f"with no date heading before it")
        fresh = False
        rest = line[3:].strip()
        times = []
        while True:
            m = TIME_RE.match(rest)
            if not m:
                break
            times.append((int(m.group(1)), int(m.group(2))))
            rest = rest[m.end():].lstrip(" ja")
        if not times:
            report["unplaceable"] += 1          # `Klo?`, and a dotless `Klo 1900`
            continue
        title, rating, marked = _split_rating(rest)
        if not marked:
            nxt = lines[i] if i < len(lines) else ""
            if nxt and not KLO_RE.match(nxt) and _split_rating(nxt)[2]:
                tail, rating, _ = _split_rating(nxt)
                title = f"{title} {tail}".strip()
                i += 1
            else:
                report["unplaceable"] += 1      # no marker closes the title
                continue
        if not title:
            report["unplaceable"] += 1          # `Klo 14.00 -k7/4-`, a row with no film
            continue
        for wd, day, month, year in pending:
            got = year or resolve_year(day, month, today, weekday_index(wd), WINDOW)
            if got is None:
                raise ShowRowError(
                    f"{site['provider']}: {title!r} is headed {wd} {day}.{month}. and no "
                    f"candidate year carries that weekday inside the window, so the "
                    f"screening cannot be placed")
            for hh, mm in times:
                try:
                    start = datetime.datetime(got, month, day, hh, mm, tzinfo=FI)
                except ValueError as e:
                    raise ShowRowError(f"{site['provider']}: {title!r} is headed the "
                                       f"impossible date {day}.{month}.{got} "
                                       f"{hh}.{mm:02d}") from e
                out.append({
                    "eventId": norm(title),
                    "title": title,
                    "original": "",
                    "len": "",
                    "rating": rating,
                    "genres": "",
                    "method": "",
                    "theatre": venue["name"],
                    "aud": "",
                    "start": start.isoformat(),
                    "url": url,
                    "img": "",
                    "lang": "",
                    "soldOut": False,
                    "price": price,
                    "provider": site["provider"],
                    "venue": venue["id"],
                })
    if not price:
        report["no_price"] = len(out)
    placed = len({s["start"] for s in out})
    if report["unplaceable"] > placed:
        raise ShowRowError(
            f"{site['provider']}: {report['unplaceable']} screening line(s) could not be "
            f"placed against {placed} that could, so the template has moved rather than "
            f"the cinema having typed a few odd rows")
    out.sort(key=lambda s: s["start"])
    return out, report


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, today=None):
    pid = site["provider"]
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    shows, report = rows(site, items(get(url)), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no screening line in the page's own content. This site publishes no "
            f"sentence saying there are none, so there is no evidence of an empty "
            f"programme to read this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len({s['eventId'] for s in shows})} film(s)"
          + (f", priced {shows[0]['price']}" if shows[0]["price"] else ""))
    if report["no_price"]:
        print(f"[{pid}] the standing price line yields no single amount, so "
              f"{report['no_price']} row(s) publish none")
    if report["unplaceable"]:
        print(f"[{pid}] {report['unplaceable']} screening line(s) whose time or title this "
              f"parser could not place, left out")
    if report["unread"]:
        print(f"[{pid}] {report['unread']} line(s) in the programme that are neither a "
              f"date heading nor a screening, left out")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:36]:38} {s['rating']:5} "
                  f"{s['price']:6}")
    sys.exit(0)
