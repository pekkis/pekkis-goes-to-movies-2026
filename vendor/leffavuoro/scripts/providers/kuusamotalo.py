"""Kino Kuusamotalo, in the Oulankasali hall of Kuusamotalo. Stdlib only.

One request, to WordPress's own REST route:

    /wp-json/wp/v2/posts?per_page=40&_fields=id,link,title,content,categories

The cinema keeps its own site, kinokuusamotalo.fi, and the town's culture house at
kuusamotalo.fi only links to it: that page names no film and its programme block is a
Flockler embed. The cinema's site is where the programme is, one post per film, and the
REST route is the same content the front page renders.

What shapes the parser, measured 2026-09-20 over the whole post set, which is five:

- **A film post is one that carries `Esitysajat:`**; the two notices on the site, a gift
  card advert from 2024 and a door-locking note from 2023, carry none and are counted
  rather than dropped in silence. Category is not the test: both notices sit in
  `nykyinen-ohjelmisto` alongside the films, and one of them in `tuleva-ohjelmisto` too.
- **No date carries a year**, and the weekday is abbreviated to two letters: `Su 20.9. klo
  15`. `common.resolve_year` places it and `common.weekday_index` gives it the weekday, so
  a post left up past its run cannot become a future screening.
- **The clock may have no minutes.** `klo 15` and `klo 13.30` both appear, so the minutes
  are optional and default to the hour.
- **A day may carry two clocks**, `La 10.10. klo 15 ja 19`, read 2026-10-10. Each one is
  a screening, and the line publishes one row per distinct clock.
- **A coming-soon post states a start date and no clock.** `Pirjo i Sverige` read that day
  carried `Pe 9.10. alkaen.` and no `Esitysajat:` line at all, so it counts with the posts
  that have none. A dateless line *inside* a marked post is counted separately and left
  out for the same reason: publishing one would invent an hour.
- **The fields are the first three lines**, typed freehand: `-K7-`, `Kesto 1h 27min`,
  `Liput 12€`. The rating marker is read from its dashes, and a price publishes only when
  the line yields one bare amount.
- **No poster is published from this site.** The featured images are the cinema's own
  uploads and they are 160 px wide, 160x228 and 160x240 on the two films read, against the
  342 px the client renders a poster from and `mirror_posters` downscales to. Nothing is
  upscaled, so mirroring one would serve a blurred half-width image where the TMDB pass
  supplies a full one.
- **The synopsis is the long paragraph before `Esitysajat:`.** `common.syn_language`
  places it, because the slot in films-extra.json is keyed by normalised title and read by
  every chain showing the film.

**Zero film posts fails the site.** Nothing on it says the programme is empty; the closest
is a 2023 notice about a closure, which is prose and names no state this could read. So
there is no evidence of an empty programme and `common.EmptyProgramme` needs that.

**`book="door"`.** The site sells nothing online: its menu is programme, coming soon,
technical details, services, pictures and contacts, and the ticket desk opens an hour
before the screening. The showtime links to the film's own post.
"""
import datetime
import html as html_mod
import json
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, get_text, resolve_year, syn_language, weekday_index

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kuusamotalo", "label": "Kino Kuusamotalo",
     "base": "https://kinokuusamotalo.fi",
     "listing": ("/wp-json/wp/v2/posts?per_page=40"
                 "&_fields=id,link,title,content,categories"),
     "venues": [{"id": "kuusamotalo-kuusamo", "name": "Kino Kuusamotalo",
                 "short": "Kino Kuusamotalo", "city": "Kuusamo",
                 "loc": "Oulankasali"}]},
]

# `resolve_year`'s (behind, ahead). The films read carried a week; the coming-soon post
# reached 19 days out, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

MARKER = "esitysajat"
TAGS_RE = re.compile(r"<[^>]+>")
SHOW_RE = re.compile(r'^([A-Za-zÅÄÖåäö]{2})\s+(\d{1,2})\.(\d{1,2})\.?\s*klo\s*'
                     r'(\d{1,2}(?:[.:]\d{2})?(?:\s+ja\s+\d{1,2}(?:[.:]\d{2})?)*)\s*$', re.I)
CLOCK_RE = re.compile(r'(\d{1,2})(?:[.:](\d{2}))?')
# A day and month with no clock: the coming-soon shape, counted and never published.
DATELESS_RE = re.compile(r'^[A-Za-zÅÄÖåäö]{2}\s+\d{1,2}\.\d{1,2}\.', re.I)
RATING_RE = re.compile(r'^-\s*(K\s*\d{1,2}|S)\s*-$', re.I)
LEN_RE = re.compile(r'(?:(\d{1,2})\s*(?:t|h)\s*)?(\d{1,3})\s*min', re.I)
PRICE_LINE_RE = re.compile(r'^liput\b(.*)$', re.I)
PRICE_RE = re.compile(r'^(?:€\s*)?(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|eur)?$', re.I)
# Shorter than this is a note ("Tervetuloa!") rather than a synopsis. The same length
# johku.py and kinola.py use, for the same reason.
SYN_MIN = 120


def lines_of(rendered):
    """A post's rendered content -> its non-empty text lines, in order."""
    text = html_mod.unescape(TAGS_RE.sub("\n", rendered or ""))
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]


def rating_of(lines):
    """`-K7-` -> "K-7", `-S-` -> "S". Anything else -> ""."""
    for ln in lines:
        m = RATING_RE.match(ln)
        if m:
            v = re.sub(r"\s+", "", m.group(1)).upper()
            return "S" if v == "S" else f"K-{int(v[1:])}"
    return ""


def minutes_of(lines):
    """`Kesto 1h 27min` -> "87"."""
    for ln in lines:
        if ln.lower().startswith("kesto"):
            m = LEN_RE.search(ln)
            if m:
                return str(int(m.group(1) or 0) * 60 + int(m.group(2)))
    return ""


def price_of(lines):
    """`Liput 12€` -> "12€". A line stating more than one amount settles nothing."""
    for ln in lines:
        m = PRICE_LINE_RE.match(ln)
        if m:
            p = PRICE_RE.match(m.group(1).strip())
            return f"{p.group(1)}€".replace(".", ",") if p else ""
    return ""


def synopsis_of(lines, marker_at):
    """The long paragraph before `Esitysajat:` -> {lang: text}, or None."""
    for ln in lines[:marker_at]:
        if len(ln) >= SYN_MIN:
            lang = syn_language(ln)
            return {lang: ln} if lang else None
    return None


def rows(site, payload, today=None):
    """-> (shows, report). One row per placed `Esitysajat:` line of every film post."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    out = []
    report = {"posts": 0, "films": 0, "notices": 0, "undated": 0, "no_clock": 0,
              "no_price": 0, "unplaced_syn": set()}
    for post in payload:
        report["posts"] += 1
        lines = lines_of((post.get("content") or {}).get("rendered", ""))
        at = next((i for i, ln in enumerate(lines)
                   if ln.lower().rstrip(":").strip() == MARKER), None)
        if at is None:
            report["notices"] += 1
            continue
        report["films"] += 1
        title = html_mod.unescape(
            TAGS_RE.sub("", (post.get("title") or {}).get("rendered", ""))).strip()
        rating, length = rating_of(lines), minutes_of(lines)
        price = price_of(lines)
        if not price:
            report["no_price"] += 1
        syn = synopsis_of(lines, at)
        if syn is None and any(len(ln) >= SYN_MIN for ln in lines[:at]):
            report["unplaced_syn"].add(title)
        for ln in lines[at + 1:]:
            m = SHOW_RE.match(ln)
            if not m:
                if DATELESS_RE.match(ln):
                    report["no_clock"] += 1
                continue
            day, month = int(m.group(2)), int(m.group(3))
            year = resolve_year(day, month, today, weekday_index(m.group(1)), WINDOW)
            if year is None:
                report["undated"] += 1
                continue
            clocks = {(int(h), int(mm or 0)) for h, mm in CLOCK_RE.findall(m.group(4))}
            for hour, minute in sorted(clocks):
                start = datetime.datetime(year, month, day, hour, minute, tzinfo=FI)
                show = {
                    "eventId": str(post.get("id", "")),
                    "title": title,
                    "original": "",
                    "len": length,
                    "rating": rating,
                    "genres": "",
                    "method": "",
                    "theatre": venue["name"],
                    "aud": venue["loc"],
                    "start": start.isoformat(),
                    "url": post.get("link") or site["base"],
                    "img": "",
                    "lang": "",
                    "soldOut": False,
                    "price": price,
                    "provider": site["provider"],
                    "venue": venue["id"],
                }
                if syn:
                    show["_syn"] = syn
                out.append(show)
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def fetch_site(site, today=None):
    """Runner contract: one request for the whole post set."""
    pid = site["provider"]
    venue = site["venues"][0]
    url = site["base"].rstrip("/") + site["listing"]
    body = get_text(url)
    try:
        payload = json.loads(body)
    except ValueError as e:
        raise RuntimeError(f"{url}: the posts route did not answer JSON ({e})") from None
    if not isinstance(payload, list):
        raise RuntimeError(f"{url}: the posts route answered {type(payload).__name__}, "
                           f"not a list of posts")
    shows, report = rows(site, payload, today)
    if not shows:
        raise RuntimeError(
            f"{url}: no post carries a placed screening line. This site publishes no "
            f"sentence saying there are none, so there is no evidence of an empty "
            f"programme to read this as and the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['films']} film post(s) of {report['posts']}")
    if report["notices"]:
        print(f"[{pid}] {report['notices']} post(s) with no Esitysajat line, left out")
    if report["no_clock"]:
        print(f"[{pid}] {report['no_clock']} row(s) announced for a day with no clock "
              f"time, left out")
    if report["undated"]:
        print(f"[{pid}] {report['undated']} screening line(s) whose date no candidate year "
              f"holds inside the window, left out")
    if report["no_price"]:
        print(f"[{pid}] {report['no_price']} film post(s) state no single ticket amount, "
              f"so their rows publish none")
    if report["unplaced_syn"]:
        print(f"[{pid}] {len(report['unplaced_syn'])} synopsis/synopses withheld, no "
              f"language settled: {', '.join(sorted(report['unplaced_syn']))}")
    return per_venue


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src:
        with open(src, encoding="utf-8") as fh:
            shows, report = rows(SITES[0], json.load(fh))
        print(report)
    else:
        shows = fetch_site(SITES[0])[SITES[0]["venues"][0]["id"]]
    for s in shows:
        print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} "
              f"{s['price']:7} {s['len']:4}")
    sys.exit(0)
