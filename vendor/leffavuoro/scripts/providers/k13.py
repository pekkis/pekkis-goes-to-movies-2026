"""Kino K13, the Finnish Film Foundation's screen on Katajanokka, Helsinki. Stdlib only.

One request, to the cinema's own page:

    /kinok13/

The programme is server-rendered inside `<section id=ohjelmisto>`, under the heading
"Avoimet yleisonaytokset", as free prose rather than a list. Checked for a structured
source first and there is none: `ses.fi` is WordPress but publishes no screening route,
and the section's paragraphs are where the programme lives.

What shapes the parser, measured on the live page 2026-09-21:

- **Only a line carrying a weekday, a date and a clock becomes a row.**
  `ma 5.10. klo 18: LUVATTU MAA (Ziemia obiecana) 1974, 179 min.` is a screening. The four
  Kinokka evenings on the same page give a date and a title and **no time**, so they
  publish nothing: the organiser page they link, `kaupunginosat.fi/skatta/ohjelmisto/`,
  was fetched on 2026-09-21 and contains no clock anywhere, so nothing publicly fetchable
  settles them and a default hour would be invented. They are counted in the log instead.
- **A festival heading is not a screening.** `5.-9.10.2026 Puolan elokuvaviikot` and
  `6.-8.11.2026 Serbian elokuvapaivat` are date ranges introducing a block. They are read
  as block boundaries, never as rows.
- **Free admission is a property of the block, not of the page.** "Naytoksiin on vapaa
  paasy." sits under a festival heading and applies to the rows beneath it until the next
  heading. `price` is "Vapaa paasy" for those and empty elsewhere, which is what the page
  settles and no more.
- **No date carries a year**, so `common.resolve_year` places each row from its weekday.
  The heading above prints one, and it is deliberately not read: the weekday is the
  stronger check and it is on the row itself.
- **The trailing sentence is the rating.** `Sallittu yli 16-vuotiaille.` is K-16 and
  `Sallittu kaikenikaisille` is S. A row without one leaves `rating` empty, as
  `STUDIO MUNKA, 3 lyhytelokuvaa.` does.
- **A parenthesised title is the original**, `(Ziemia obiecana)`, and the runtime is
  `179 min`. Neither is invented when the row omits it.
- **The showtime links to the cinema's own page.** The screenings are free and there is no
  ticket to buy, so `url` is the programme section itself.

**Zero rows fails the site.** The page publishes no sentence saying there is no programme,
so a zero-row parse is a broken read rather than evidence of an empty one, and
`common.EmptyProgramme` needs that evidence.

**`book="list"`.** There is no per-screening booking URL and nothing is sold: a showtime
opens the programme, which is the mode Gilda already uses.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, get_text, resolve_year, weekday_index

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "k13", "label": "Kino K13",
     "base": "https://www.ses.fi",
     "listing": "/kinok13/",
     "anchor": "#ohjelmisto",
     "venues": [{"id": "k13-helsinki", "name": "Kino K13", "short": "Kino K13",
                 "city": "Helsinki"}]},
]

# `resolve_year`'s (behind, ahead). The live section reached 83 days out, a December
# Kinokka evening, so this is headroom rather than a fit.
WINDOW = (30, 180)

SECTION_RE = re.compile(r'<section[^>]*\bid=["\']?ohjelmisto\b["\']?[^>]*>(.*?)</section>',
                        re.S | re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# `ma 5.10. klo 18:` and `to 8.10 klo 18:`, with the minutes optional.
ROW_RE = re.compile(r"^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s*klo\s*"
                    r"(\d{1,2})(?:[.:](\d{2}))?\s*[:\-–]\s*(.+)$", re.I)
# A block heading: one date or a range, always with a year.
# The range form opens a festival; a single date with no clock is a screening this page
# gives no hour for, which is counted rather than guessed at.
HEAD_RE = re.compile(r"^\d{1,2}\.(?:\s*[–-]\s*\d{1,2}\.)?\d{1,2}\.\d{4}\b")
RANGE_HEAD_RE = re.compile(r"^\d{1,2}\.\s*[\u2013-]\s*\d{1,2}\.\d{1,2}\.\d{4}\b")
FREE_RE = re.compile(r"vapaa\s+p[aä]{1,2}sy", re.I)
RATING_RE = re.compile(r"sallittu\s+(?:yli\s+(\d{1,2})[\s-]*vuotiaille|kaikenik[aä]isille)",
                       re.I)
LEN_RE = re.compile(r"\b(\d{1,3})\s*min\b", re.I)
ORIGINAL_RE = re.compile(r"\(([^()]{2,60})\)")


def lines_of(page):
    """The programme section -> its visible lines, in order."""
    m = SECTION_RE.search(page)
    if not m:
        return []
    text = html_mod.unescape(TAGS_RE.sub("\n", m.group(1)))
    return [re.sub(r"\s+", " ", x).strip() for x in text.split("\n") if x.strip()]


def rating_of(rest):
    """`Sallittu yli 16-vuotiaille.` -> "K-16", `kaikenikaisille` -> "S", else ""."""
    m = RATING_RE.search(rest or "")
    if not m:
        return ""
    return f"K-{int(m.group(1))}" if m.group(1) else "S"


def title_of(rest):
    """The text after the clock -> (title, original).

    The title runs to the first bracket, comma or release year, which is where this page
    stops naming the film and starts describing it.
    """
    body = (rest or "").strip()
    cut = len(body)
    for pat in (r"\s*\(", r"\s*,", r"\s+(?:19|20)\d{2}\b"):
        m = re.search(pat, body)
        if m:
            cut = min(cut, m.start())
    title = body[:cut].strip(" .:-–")
    o = ORIGINAL_RE.search(body)
    original = o.group(1).strip() if o else ""
    if original.lower().startswith("sallittu") or LEN_RE.fullmatch(original or ""):
        original = ""
    return title, original


def slug_of(title):
    return re.sub(r"-{2,}", "-", re.sub(r"[^\w]+", "-", (title or "").lower(),
                                        flags=re.UNICODE)).strip("-")


def rows(site, page, today=None):
    """-> (shows, report). One row per timed screening line."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"] + site["anchor"]
    out = []
    report = {"lines": 0, "headings": 0, "no_time": 0, "undated": 0, "untitled": 0}
    free = False
    for line in lines_of(page):
        report["lines"] += 1
        if HEAD_RE.match(line):
            report["headings"] += 1
            free = bool(FREE_RE.search(line))
            if not ROW_RE.match(line):
                # A range heading opens a festival block. A single date with no clock is
                # a screening this page does not give an hour for, and it is counted.
                if "klo" not in line.lower() and not RANGE_HEAD_RE.match(line):
                    report["no_time"] += 1
                continue
        if FREE_RE.search(line):
            free = True
        m = ROW_RE.match(line)
        if not m:
            continue
        day, month = int(m.group(2)), int(m.group(3))
        year = resolve_year(day, month, today, weekday_index(m.group(1)), WINDOW)
        if year is None:
            report["undated"] += 1
            continue
        title, original = title_of(m.group(6))
        if not title:
            report["untitled"] += 1
            continue
        rest = m.group(6)
        length = LEN_RE.search(rest)
        out.append({
            "eventId": slug_of(title),
            "title": title,
            "original": original,
            "len": length.group(1) if length else "",
            "rating": rating_of(rest),
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": datetime.datetime(year, month, day, int(m.group(4)),
                                       int(m.group(5) or 0), tzinfo=FI).isoformat(),
            "url": url,
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "Vapaa pääsy" if free else "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def fetch_site(site, today=None):
    """Runner contract: one request for the programme page."""
    pid, venue = site["provider"], site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    shows, report = rows(site, get_text(url), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no screening line with a weekday, a date and a clock. This site "
            f"publishes no sentence saying there are none, so there is no evidence of an "
            f"empty programme to read this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['headings']} block heading(s)")
    for key, note in (("no_time", "dated entry(ies) with no clock, which this parser will "
                                  "not invent"),
                      ("undated", "line(s) whose date no candidate year holds, left out"),
                      ("untitled", "line(s) with a clock and no title, left out")):
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
        print(f"   {s['start'][:16]}  {s['title'][:30]:32} {s['rating']:5} {s['len']:4} "
              f"{s['price']:12} {s['original'][:20]}")
    sys.exit(0)
