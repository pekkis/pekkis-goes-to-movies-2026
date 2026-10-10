"""Movie Company Alatalo, a touring operator in northern Finland. Stdlib only.

One request to `http://www.moviecompanyalatalo.fi/`. Whole programme typed freehand into
the front page; no API, and /fi/Elokuvaesitykset.html is marketing prose with no screening.

- **http, not https.** 443 refused the connection 2026-09-19 and the apex has no A record.
  Ticket link is this same page: cash at the door, no booking URL.
- **Same author as huvimylly.com**, which carries the same contact address and is a venue
  this operator programmes. Hence the grammar is `huvimylly.py`'s and `RATING_RE`,
  `TIME_RE`, `STRIP`, `WEEKDAY_WORD` are imported rather than copied.
- **A town heading is a line naming a declared town.** The grey background span on four of
  the five looks like the marker and is not: Toholampi never carries it and Haapajarvi lost
  it in the 2024-12 capture.
- **An unrecognised heading clears the venue**, so its rows are counted against its own
  first word instead of landing under the town above. Kinotour reads the town per row and
  needs no such rule. False positives cost rows: `Suomen Ensi-ilta` took two in 2023-12,
  against seven that `Ylivieska Akustiikka` would have misfiled.
- **Only that first word is ever logged**, and only as one alphabetic 4-20 char word with a
  capital initial. The header carries the operator's email and mobile; no line text leaves
  the parse.
- Rows, dates, two-line titles and the marker rule are `huvimylly.py`'s, including
  consecutive headings sharing one list of times.

Widened against lines this page carries and that one does not:

- bare `k?` closes a title (`Klo 15.00 Lapin Sota k?`, 2 of 13 live rows);
- a leading time with a marker and no `Klo` is a row (`16.30 Kero se kaikille -k12/9-`);
- `Kl` reads as `Klo` (2023-12), a time still required, so `Klovnit` cannot match;
- a year glued on with a dot (`Tiistaina 2.1.2024`); `7.12024` is still refused;
- a row with no date heading is counted, not raised. 2024-08 heads Pudasjarvi `Maanantaina
  9.` with no month, and raising would cost the other four towns their schedule.

No poster: the images are hand-named, sit outside the rows and match no capture's order.
No runtime, genre, language or per-row URL; the page publishes none.

**Price** is the standing `Liput elokuviin vain10-` line, parsed each run. The 2024-05 and
2024-08 captures carry no such line and publish no price, which a hardcoded amount would
have got wrong.

**Empty programme has positive evidence.** 2025-08 lists all five towns under `ELOKUVAT
JATKUU SYYSKUUSSA`; 2025-04 lists all five with nothing under them. In both, no line from
the first town heading on carries a digit: no date and no time, which is checked apart
from the `Klo` pattern the rows are found with. Town headings, no `Klo` line and no digit
under them raises `common.EmptyProgramme`. No town heading at all fails: that is the
template moving, with no listing to read as empty. So does a page whose screening lines
all sit under headings `_town_of` does not read.

**One town is shown empty by its own lines.** The digit check runs per town since
2026-09-24: a town with a date or a time under its heading and no row placed is left out,
and so is every empty town while any line sits under a heading no declared town owns.
Either way its previous file stands and the other towns publish.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import (EmptyProgramme, check_shows, fetch, get_text, resolve_year,
                    weekday_index)
from huvimylly import KAVI_CODES, RATING_RE, STRIP, TIME_RE, WEEKDAY_WORD
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

# The five towns on the programme on 2026-09-19, and the same five in every capture back
# to 2025-04. `town` is the word the heading opens with; `name` is the hall, which is what
# changes while the tour keeps coming back to the town.
SITES = [
    {"provider": "alatalo", "label": "Movie Company Alatalo",
     "base": "http://www.moviecompanyalatalo.fi",
     "listing": "/",
     "venues": [
         {"id": "alatalo-pudasjarvi", "name": "Pohjant\u00e4hti",
          "short": "Pohjant\u00e4hti", "city": "Pudasj\u00e4rvi",
          "town": "Pudasj\u00e4rvi"},
         {"id": "alatalo-haapajarvi", "name": "Teatterisali", "short": "Teatterisali",
          "city": "Haapaj\u00e4rvi", "town": "Haapaj\u00e4rvi"},
         {"id": "alatalo-kiuruvesi", "name": "Kiurusali", "short": "Kiurusali",
          "city": "Kiuruvesi", "town": "Kiuruvesi"},
         {"id": "alatalo-toholampi", "name": "Toholampisali", "short": "Toholampisali",
          "city": "Toholampi", "town": "Toholampi"},
         {"id": "alatalo-kemijarvi", "name": "Kulttuurikeskus",
          "short": "Kulttuurikeskus", "city": "Kemij\u00e4rvi", "town": "Kemij\u00e4rvi"},
     ]},
]

# A town with no row is known empty rather than unread when nothing under its heading
# carries a date or a time and nothing on the page stands under a heading no declared town
# owns. A declared town the page does not list at all counts too, on that second condition:
# this one page is the operator's whole published programme, and Toholampi is absent from
# it on 2026-09-24. `run.py` then publishes a fresh empty file for that venue instead of
# ageing its last visit. A page that places no row under any declared town never reaches
# that loop, because `fetch_site` raises first. Any other town with no row is left out of
# the answer, so its previous file stands: those lines are not the town having nothing on.
EMPTY_VENUES_CONFIRMED = True

# `resolve_year`'s (behind, ahead). The live page reached 40 days out and the 2023-12
# capture 86, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
BLOCK_RE = re.compile(r"</?(?:p|li|h[1-6]|div|br|tr|td|table|ul|ol)\b[^>]*>", re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# One `Weekday D.M`, with the year optional and written either after a space or glued on
# with a dot. Both are in the 2023-12 capture, `Maanantaina 8.1 2024` and `Tiistaina
# 2.1.2024`, and neither reading is a guess.
# The year group comes before the optional trailing dot, or `2.1.2024` would give the dot
# to that and read no year: the group is optional, so nothing backtracks into it.
HEAD_ONE_RE = re.compile(
    rf"({WEEKDAY_WORD})\s+(\d{{1,2}})\.(\d{{1,2}})(?:[.\s]\s*(\d{{4}}))?\.?")
# The line has to be headings and nothing else, which is `huvimylly.py`'s guard and holds
# for the same reason: `Sunnuntaina 7.12024-` leaves digits this pattern cannot take, so
# the line is not a heading and no screening is placed under it.
HEAD_LINE_RE = re.compile(rf"^[-\s]*(?:{WEEKDAY_WORD}\s+\d{{1,2}}\.\d{{1,2}}"
                          rf"(?:[.\s]\s*\d{{4}})?\.?[\s,ja-]*)+$")
# `Kl` as well as `Klo`: `Kl 19.00 Vonkka originaaliversio` is in the 2023-12 capture. The
# word boundary is what makes it safe -- `Klovnit` does not match -- and a line with no
# time after it is counted rather than read.
KLO_RE = re.compile(r"^kl[o]?\b", re.I)
# The dash before `k?` is optional here: the live page reads `Lapin Sota k?`.
UNKNOWN_RATING_RE = re.compile("\\s*[-\u2013]?\\s*k\\s*\\?[-\u2013\\s]*$", re.I)
# `Liput elokuviin vain10-`, with the amount typed against the word. The middle word is
# optional so the shape `huvimylly.py` reads, `Liput vain 10-`, is read here too.
PRICE_RE = re.compile(r"liput\s+(?:\w+\s+)?vain\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*-?\s*\u20ac",
                      re.I)
# The first word of a line that could be a town heading: one alphabetic word, a capital
# initial, four to twenty characters. An email address and a phone number both fail it,
# which is the point -- this is the only string the parse ever carries out to the log.
TOWN_WORD_RE = re.compile(r"^[A-Z\u00c5\u00c4\u00d6][A-Za-z\u00c5\u00c4\u00d6\u00e5\u00e4\u00f6-]{3,19}$")


class ShowRowError(RuntimeError):
    """A line inside the programme this parser could not place.

    The programme is typed freehand, so an unreadable line is as likely to be a real
    screening as a note. Publishing a guess would put a wrong time or a note-laden title
    on the site, so the site fails and the previous files stand.
    """


def _text(fragment):
    s = TAGS_RE.sub(" ", fragment or "")
    s = html_mod.unescape(s).replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", s).strip()


def lines(payload):
    """The page's text, one line per block element, in document order. -> [str].

    Scripts go first: the navigation is a `domMenu_Hash` literal carrying the menu labels,
    and flattening it would put `Elokuvaesitykset` in the programme.
    """
    if "<" not in (payload or ""):
        raise RuntimeError("the page did not answer HTML")
    out = [_text(chunk) for chunk in BLOCK_RE.split(SCRIPT_RE.sub(" ", payload))]
    return [x for x in out if x and not set(x) <= set(".\u2026- ")]


def price_of(rows_):
    """The standing `Liput elokuviin vain10-` amount, or "". One amount or nothing."""
    for line in rows_:
        found = PRICE_RE.findall(line)
        if len(found) == 1:
            return f"{found[0]}\u20ac"
    return ""


def _dates(line):
    """Every `Weekday D.M [YYYY]` a heading line names. -> [(weekday, day, month, year)].

    Empty unless every word in front of a date reads as a weekday. `WEEKDAY_WORD` is any
    six letters, so a place typed with a date, `Lestijärvi 3.10.`, passed as a heading
    and was placed by the nearest year with no weekday to check (audit A4, 2026-09-25).
    `weekday_index` reads the first two letters, which keeps the misspellings the
    captures hold (`Luantaina`, `Sununtaina`) and refuses a word no weekday begins with.
    """
    found = [(m.group(1), int(m.group(2)), int(m.group(3)),
              int(m.group(4)) if m.group(4) else None)
             for m in HEAD_ONE_RE.finditer(line)]
    return found if all(weekday_index(wd) is not None for wd, *_ in found) else []


def _first(line):
    """A line's first word as a town is matched on: up to a slash, since a heading may
    join two towns, `Toholampi/Lestijärvi`."""
    return (line.split() or [""])[0].split("/")[0].strip(STRIP + ".")


def _split_rating(text):
    """`Pirjo -s-` -> ("Pirjo", "S", True). -> (title, rating, marked).

    `huvimylly._split_rating` with this page's `UNKNOWN_RATING_RE`, which does not require
    a dash before the `k?`. `marked` is whether the line closed its own title, which is
    the structural question; `rating` is "" on a line closed with `k?`, which states the
    rating is unknown rather than stating none.
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


def _town_of(line, venues):
    """The venue whose town this line names, or None. Matched on the first word."""
    first = _first(line).casefold()
    return next((v for v in venues if v["town"].casefold() == first), None)


def _heading_candidate(line):
    """The first word of a line shaped like a town heading, or "".

    Four words at most, no digits and no `@` anywhere in it, and a first word that passes
    `TOWN_WORD_RE`. The page's own header lines fail one of those: the email carries an
    `@`, the mobile number is digits, and the announcements that do pass are named only
    when screenings follow them, which they never do.
    """
    words = line.split()
    if not words or len(words) > 4:
        return ""
    if any(c.isdigit() or c == "@" for c in line):
        return ""
    return _first(line) if TOWN_WORD_RE.match(_first(line)) else ""


def rows(site, src, today=None):
    """-> ({venue_id: [show]}, report). One show per time on every `Klo` line."""
    today = today or datetime.datetime.now(FI).date()
    venues = site["venues"]
    url = site["base"].rstrip("/") + site["listing"]
    price = price_of(src)
    per_venue = {v["id"]: [] for v in venues}
    # Counts and one place name, never a line's text: the page's standing header carries
    # the operator's own email address and mobile number, and a report field holding a
    # line is one print away from publishing them.
    # `numbered` is per declared town, `stray` the lines under a heading no declared town
    # owns: a town is shown empty by what stands under its own heading, not by the page.
    report = {"unread": 0, "unplaceable": 0, "undeclared": {}, "towns": 0, "klo": 0,
              "no_price": 0, "numbered": {}, "stray": 0, "unconfirmed": [],
              "unvouched": []}
    tried = set()           # declared towns with a screening line under them
    venue, pending, fresh, candidate = None, [], True, ""
    i = 0
    while i < len(src):
        line = src[i]
        i += 1
        if PRICE_RE.search(line):
            continue
        hit = _town_of(line, venues)
        if hit is not None:
            venue, pending, fresh, candidate = hit, [], True, ""
            report["towns"] += 1
        # A date or a time under a town heading, however it is written, the heading line
        # included. The two empty captures carry none, so this is what an empty town is
        # told apart by, and each town is told apart on its own lines.
        if any(c.isdigit() for c in line):
            if venue is not None:
                report["numbered"][venue["town"]] = report["numbered"].get(venue["town"], 0) + 1
            elif report["towns"]:
                report["stray"] += 1
        if hit is not None:
            continue
        if HEAD_LINE_RE.match(line) and _dates(line):
            if not fresh:
                pending, fresh = [], True
            pending += _dates(line)
            continue
        if HEAD_LINE_RE.match(line):
            # The heading's shape with a place where the weekday goes: a town this repo
            # does not declare, typed with its date. What follows is that town's, never
            # the town above it, so it is counted under the word and withheld.
            report["unread"] += 1
            word = _first(line)
            venue, pending, fresh = None, [], True
            candidate = word if TOWN_WORD_RE.match(word) else ""
            continue
        m0 = KLO_RE.match(line)
        # `16.30 Kero se kaikille -k12/9-` on the live page: a row whose `Klo` was left
        # off. The marker is what makes it safe to read, since a bare date carries none.
        if not m0 and not (TIME_RE.match(line) and _split_rating(line)[2]):
            report["unread"] += 1
            word = _heading_candidate(line)
            if word:
                venue, pending, fresh, candidate = None, [], True, word
            continue
        report["klo"] += 1
        if venue is None:
            if candidate:
                report["undeclared"][candidate] = report["undeclared"].get(candidate, 0) + 1
                continue
            raise ShowRowError(
                f"{site['provider']}: a screening line stands before any town heading, "
                f"so the page's shape is not the one this parser reads")
        fresh = False
        tried.add(venue["id"])
        rest = (line[m0.end():] if m0 else line).strip()
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
            nxt = src[i] if i < len(src) else ""
            if (nxt and not KLO_RE.match(nxt) and _town_of(nxt, venues) is None
                    and _split_rating(nxt)[2]):
                tail, rating, _ = _split_rating(nxt)
                title = f"{title} {tail}".strip()
                i += 1
            else:
                report["unplaceable"] += 1      # no marker closes the title
                continue
        if not title:
            report["unplaceable"] += 1          # `Klo 14.00 -k7/4-`, a row with no film
            continue
        if not pending:
            # `huvimylly.py` raises here and this does not, on the 2024-08 capture:
            # Pudasjarvi is headed `Maanantaina 9.` with the month left off, and raising
            # would have cost Kiuruvesi's four rows and the other three towns their
            # schedule over one town's typo. A row with no date is a row this parser
            # cannot place, and the ratio guard below is what catches a template move.
            report["unplaceable"] += 1
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
                per_venue[venue["id"]].append({
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
    published = sum(len(v) for v in per_venue.values())
    if not price:
        report["no_price"] = published
    placed = len({(s["venue"], s["start"]) for v in per_venue.values() for s in v})
    if report["unplaceable"] > placed:
        raise ShowRowError(
            f"{site['provider']}: {report['unplaceable']} screening line(s) could not be "
            f"placed against {placed} that could, so the template has moved rather than "
            f"the operator having typed a few odd rows")
    # A town with no row is confirmed empty only when nothing under its heading carries a
    # date or a time, and nothing on the page sits under a heading no declared town owns:
    # those lines could be this town's under a heading typed another way. Anything else
    # leaves it out, so its previous file stands and the other towns still publish.
    unowned = bool(report["undeclared"] or report["stray"])
    for v in venues:
        if per_venue[v["id"]]:
            continue
        if v["id"] in tried or report["numbered"].get(v["town"]):
            report["unconfirmed"].append(v["town"])
        elif unowned:
            report["unvouched"].append(v["town"])
        else:
            continue
        del per_venue[v["id"]]
    for shows in per_venue.values():
        shows.sort(key=lambda s: s["start"])
    return per_venue, report


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, today=None):
    pid = site["provider"]
    url = site["base"].rstrip("/") + site["listing"]
    per_venue, report = rows(site, lines(get(url)), today)
    published = sum(len(v) for v in per_venue.values())
    if not published and report["undeclared"]:
        named = ", ".join(f"{t} ({n})" for t, n in sorted(report["undeclared"].items()))
        raise RuntimeError(
            f"{url}: every screening line sits under a heading this parser does not read "
            f"as a declared town ({named}), so no declared town is shown to be empty")
    if not published:
        if (report["towns"] and not report["klo"] and not report["numbered"]
                and not report["stray"]):
            raise EmptyProgramme(
                f"{url}: the page lists {report['towns']} of this operator's towns and no "
                f"date, time or screening under any of them, which is what it publishes "
                f"between tours")
        raise RuntimeError(
            f"{url}: no screening line under a town heading, and {report['towns']} town "
            f"heading(s) found, so this is the template having moved rather than a "
            f"programme that says it has nothing on")
    check_shows(per_venue, pid, {v["id"] for v in site["venues"]})
    print(f"[{pid}] {published} screening(s) in {report['towns']} town heading(s) read")
    if report["undeclared"]:
        named = ", ".join(f"{t} ({n})" for t, n in sorted(report["undeclared"].items()))
        print(f"[{pid}] {sum(report['undeclared'].values())} screening line(s) under "
              f"{len(report['undeclared'])} heading(s) this parser does not recognise as "
              f"a declared town, left out: {named}. Add it to SITES if it is one")
    if report["no_price"]:
        print(f"[{pid}] the standing price line yields no single amount, so "
              f"{report['no_price']} row(s) publish none")
    if report["unplaceable"]:
        print(f"[{pid}] {report['unplaceable']} screening line(s) whose time, title or "
              f"date this parser could not place, left out")
    if report["unconfirmed"]:
        print(f"[{pid}] {', '.join(report['unconfirmed'])}: a date or a time under its "
              f"heading and no screening placed, so not published as empty and the "
              f"previous file stands")
    if report["unvouched"]:
        print(f"[{pid}] {', '.join(report['unvouched'])}: no screening while lines sit "
              f"under a heading no declared town owns, so not published as empty and the "
              f"previous file stands")
    if report["unread"]:
        print(f"[{pid}] {report['unread']} line(s) that are neither a town heading, a "
              f"date heading nor a screening, left out")
    for v in site["venues"]:
        shows = per_venue.get(v["id"], [])
        days = sorted({s["start"][:10] for s in shows})
        print(f"[{pid}] {v['name']}, {v['city']}: {len(shows)} showtimes, "
              f"{len(days)} dates"
              + (f", priced {shows[0]['price']}" if shows and shows[0]["price"] else ""))
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:36]:38} {s['rating']:5} "
                  f"{s['price']:6}")
    sys.exit(0)
