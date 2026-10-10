"""Forssan Elävienkuvien teatteri, the oldest operating cinema in the Finnish countryside.
Stdlib only.

One request for the listing, then one film page per film. The site is a Foxy CMS and every
page is server-rendered, so a plain fetch is the whole of it.

    /ohjelmisto/            <div class="movielifts"> of <div class="lift">, each an
                            <a href="ohjelmisto/{slug}/">, a portrait poster and a
                            "Seuraava näytös" line this parser does not read
    /ohjelmisto/{slug}/     <h2> title, <p class="movielength">, <div class="screenings">

What shapes the parser:

- **The film links and the sub-navigation share the path space.** `ohjelmisto/` also holds
  `erikoisnaytokset/`, `esityskalenteri/` and `mykkaelokuvafestivaalit/`, which are pages
  rather than films and sit in `<div class="sub_navigation">`. The listing is therefore
  sliced to `movielifts` before any link is read; matching `ohjelmisto/{slug}/` across the
  whole document would fetch three nav pages and publish whatever they parsed to.
- **The poster comes from the listing, not the film page.** Both exist and only one is a
  poster: `{slug}-list.jpg` on the listing is portrait, 316x474 when measured, and
  `{slug}.jpg` on the film page is a 835x369 banner. Publishing the film page's would put a
  cropped landscape still where every other chain has a poster, which is the shape
  `huvimylly.py` records refusing.
- **The screening line carries its own year**, `su 20.9.2026 klo 17:00`, so nothing is
  inferred and `common.resolve_year` is not used. The weekday is printed and redundant; it
  is not read at all, so a wrong one cannot move a screening.
- **The ticket link is the row's own.** `lipunvaraus/?movieid=1360&date=2026-09-20&time=17:00`
  is the cinema's own seat-picker page, the destination a visitor clicks, and it names the
  screening. A row without one falls back to the film page.
- **The rating is the age image's file name and nothing else.** `agelimit_12.png` in an
  `agelimits/` directory, with no `alt`, no title and no text beside it. `kinola.py` records
  the opposite case, where Kilta's file name disagreed with its own `alt`; here there is no
  second source to disagree with, so the file name is read and corroborated instead: every
  rating it yields matches what another chain publishes for the same film, checked for the
  twelve films listed on 2026-09-19. `agelimit_notset` is the site's own "no rating" and
  produces none rather than a guess.
- **Two amounts and nothing to choose between them, so no price is published.** Every row
  ends `| 13€ / 11€`, the adult and the reduced fare, and the row settles neither: nothing
  on it says which applies to the reader. That is the rule CLAUDE.md states, and the same
  call `cinemantsala.py` and `biokaari.py` record for their own tariff pages.

**Zero rows fails the site.** The listing carries no empty-state text and no capture of
this site with nothing on has been seen, so `common.EmptyProgramme` has no evidence to
stand on here.
"""
import datetime
import html as html_mod
import re
import sys
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from common import budget_or_raise, check_shows, fetch, get_text
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "elavienkuvien", "label": "Elävienkuvien teatteri",
     "base": "https://www.elavienkuvienteatteri.fi",
     "listing": "/ohjelmisto/",
     "venues": [{"id": "ekt-forssa", "name": "Elävienkuvien teatteri",
                 "short": "Elävienkuvien teatteri", "city": "Forssa"}]},
]

TAGS_RE = re.compile(r"<[^>]+>")
# The films live here and the sub-navigation does not.
LIFTS_RE = re.compile(r'<div class="movielifts">(.*?)(?:<div class="multifooter">\s*</div>\s*)?$',
                      re.S | re.I)
LIFT_RE = re.compile(r'<div class="lift">(.*?)</div>\s*</div>', re.S | re.I)
HREF_RE = re.compile(r'href="(ohjelmisto/[a-z0-9-]+/)"', re.I)
# Scoped to the poster block. An unscoped search took the age-limit icon out of the same
# lift when a film had no poster, and would have published `agelimit_12.png` as one.
LIFT_IMG_RE = re.compile(r'<div class="lift_image">.*?<img[^>]+src="([^"]+)"', re.S | re.I)
TITLE_RE = re.compile(r"<h2>(.*?)</h2>", re.S | re.I)
LENGTH_RE = re.compile(r'<p class="movielength">(.*?)</p>', re.S | re.I)
AGE_RE = re.compile(r"agelimits/agelimit_([a-z0-9]+)\.png", re.I)
MIN_RE = re.compile(r"(?:(\d+)\s*h\s*)?(\d{1,3})\s*min", re.I)
SCREENINGS_RE = re.compile(r'<div class="screenings">(.*?)</div>', re.S | re.I)
# `su 20.9.2026 klo 17:00`. The year is printed, so nothing is resolved.
ROW_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*klo\s*(\d{1,2})[:.](\d{2})", re.I)
# A film announced for a day whose clock time is not set yet: `pe 2.10.2026`, and nothing
# after it. Read on the Digger page 2026-09-19. It is a real row and it cannot be placed,
# so it is counted and left out rather than invented or raised on; eTiketti's reader makes
# the same call, and failing the site over it would cost the other eleven films their
# schedule every time the cinema announces a date before a time.
DATE_ONLY_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
BUY_RE = re.compile(r'href="(lipunvaraus/[^"]+)"', re.I)


class ListingError(RuntimeError):
    """A film the listing marks and this parser could not read.

    Skipping one would publish a schedule short of a film with nothing in the log to say
    so, so the site fails and the previous files stand.
    """


def _txt(fragment):
    s = TAGS_RE.sub(" ", fragment or "")
    return re.sub(r"\s+", " ", html_mod.unescape(s).replace("\xa0", " ")).strip()


def films(page, base):
    """The listing's films. -> [{slug, url, img}], in document order.

    Sliced to `movielifts` first: the sub-navigation links sit in the same `ohjelmisto/`
    path space and are pages, not films.
    """
    m = LIFTS_RE.search(page)
    if not m:
        raise ListingError("no movielifts container in the listing, so this is not the "
                           "programme page this parser reads")
    out, seen = [], set()
    for block in LIFT_RE.findall(m.group(1)):
        href = HREF_RE.search(block)
        if not href:
            continue
        slug = href.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        img = LIFT_IMG_RE.search(block)
        out.append({"slug": slug, "url": urljoin(base + "/", slug),
                    "img": urljoin(base + "/", html_mod.unescape(img.group(1)))
                           if img else ""})
    return out


def rating_of(fragment):
    """`agelimit_12.png` -> "K-12"; `agelimit_notset` -> "". The file name is the only
    signal this page carries: no alt, no title, no text beside it."""
    m = AGE_RE.search(fragment or "")
    if not m:
        return ""
    v = m.group(1).lower()
    if v == "s":
        return "S"
    return f"K-{int(v)}" if v.isdigit() else ""


def minutes_of(text):
    """`Kesto 1 h 27 min` -> "87". Hours first, or a bare `97 min` reads as 97."""
    m = MIN_RE.search(text or "")
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def shows_of(site, film, page, report=None):
    """One film page -> [show]. Raises when the page is not one.

    `report` counts the rows left out: a date with no time yet is one of them.
    """
    report = {"no_time": 0} if report is None else report
    venue = site["venues"][0]
    t = TITLE_RE.search(page)
    title = _txt(t.group(1)) if t else ""
    if not title:
        raise ListingError(f"{film['url']}: no <h2> title on the film page")
    meta = LENGTH_RE.search(page)
    meta_txt = meta.group(0) if meta else ""
    rating = rating_of(meta_txt)
    length = minutes_of(_txt(meta_txt))
    # The genres are the line after the age image, inside the same paragraph.
    genres = ""
    if meta:
        genres = _txt(re.split(r"<br\s*/?>", meta.group(1))[-1])
    out = []
    block = SCREENINGS_RE.search(page)
    if not block:
        return out                     # a film listed with no screening yet: not an error
    for line in re.split(r"<br\s*/?>", block.group(1)):
        text = _txt(line)
        m = ROW_RE.search(text)
        if not m:
            if DATE_ONLY_RE.search(text):
                report["no_time"] += 1       # announced for a day, no clock time yet
                continue
            if text:
                raise ListingError(
                    f"{film['url']}: a screening line with no readable date. The page "
                    f"marks it as a screening, so dropping it would lose one silently")
            continue
        day, month, year, hh, mm = (int(x) for x in m.groups())
        try:
            start = datetime.datetime(year, month, day, hh, mm, tzinfo=FI)
        except ValueError as e:
            raise ListingError(f"{film['url']}: {day}.{month}.{year} {hh}.{mm:02d} is not "
                               f"a calendar date") from e
        buy = BUY_RE.search(line)
        out.append({
            "eventId": norm(title),
            "title": title,
            "original": "",
            "len": length,
            "rating": rating,
            "genres": genres,
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": start.isoformat(),
            # The row's own seat-picker page when it has one, the film page otherwise.
            "url": urljoin(site["base"] + "/", html_mod.unescape(buy.group(1)))
                   if buy else film["url"],
            "img": film["img"],
            "lang": "",
            "soldOut": False,
            # Two amounts, adult and reduced, and the row settles neither.
            "price": "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    return out


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, sleep=1.2):
    pid = site["provider"]
    venue = site["venues"][0]
    listing_url = site["base"].rstrip("/") + site["listing"]
    listed = films(get(listing_url), site["base"])
    if not listed:
        raise RuntimeError(
            f"{listing_url}: the programme container holds no film. This site publishes "
            f"no empty-state text, so there is no evidence of an empty programme to read "
            f"this as and the previous files stand")
    shows, report = [], {"no_time": 0}
    # budget_or_raise, not capped: these pages carry the screenings themselves, so
    # trimming the loop would drop them rather than cost metadata.
    for n, film in enumerate(budget_or_raise(listed, pid)):
        if n:
            time.sleep(sleep)
        shows += shows_of(site, film, get(film["url"]), report)
    if not shows:
        raise RuntimeError(
            f"{listing_url}: {len(listed)} film(s) listed and no screening on any of "
            f"them, which is a template change rather than a cinema with nothing on")
    shows.sort(key=lambda s: s["start"])
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {len(listed)} film(s) listed, {len(shows)} screening(s) over "
          f"{len(days)} date(s)")
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates")
    if report["no_time"]:
        print(f"[{pid}] {report['no_time']} row(s) announced for a day with no clock "
              f"time yet, left out")
    return per_venue


if __name__ == "__main__":
    for vid, rows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(rows)} showtimes")
        for s in rows:
            print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} {s['len']:4}")
    sys.exit(0)
