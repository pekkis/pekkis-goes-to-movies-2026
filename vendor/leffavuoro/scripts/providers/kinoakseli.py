"""Kino Akseli (Nummela, single screen) — Elementor page scrape. Stdlib only.

kinoakseli.fi challenges datacenter IPs, so this provider
runs from the Mac alongside Finnkino, not in Actions.

The page gives genres, age limit and ticket price, but no booking links (tickets are
sold at the door), no auditorium, and dates carry no year.
"""
import datetime, html as html_mod, json, re, sys
from zoneinfo import ZoneInfo

from common import fetch, get_text, resolve_year, weekday_index

URL = "https://kinoakseli.fi/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "ka-nummela", "provider": "kinoakseli", "providerId": "1",
         "name": "Kino Akseli", "short": "Kino Akseli", "city": "Nummela"}

# Single screen, so one site with one venue. See run.py for the contract.
#
# `base` names the host this site is read from, which is the runner's pacing key.
# Nothing here reads it: fetch_site reads URL above and nothing else, and the
# committed run log records one host attempted, kinoakseli.fi. Added 2026-09-19 with
# Kino Engel's, the only two sites a sweep of the committed logs found declaring none.
SITES = [{"provider": "kinoakseli", "label": "Kino Akseli", "base": URL,
          "venues": [VENUE]}]

# `resolve_year`'s (behind, ahead). This cinema publishes about three days at a time, and
# the committed programme spanned -1 to +1 day on 2026-09-19, so 60 ahead is twenty times
# the widest span seen and far short of the 365 a wrong weekday would need.
WINDOW = (30, 60)

HEAD_RE = re.compile(r'<h2[^>]*class="elementor-heading-title[^"]*"[^>]*>\s*'
                     r'<a href="(https://kinoakseli\.fi/elokuva-[^"]+)"[^>]*>(.*?)</a>', re.S)
SHOWS_RE = re.compile(r'Näytösajat(.*?)</p>', re.S)
SHOW_RE = re.compile(r'([A-Za-zÄÖäö]{2})\s*(\d{1,2})\.(\d{1,2})\.\s*klo\s*(\d{1,2})[:.](\d{2})\s*(\(dub\.?\))?')
RATING_RE = re.compile(r'Ikäraja\s*:\s*([^<]+)')
# "Kesto : 117min", an icon-list item beside the rating. Read 2026-10-04 it is only on the
# month's-offer card, a heading with the facts after it and no screening list.
KESTO_RE = re.compile(r'Kesto\s*:\s*(?:(\d+)\s*[th]\s*)?(\d+)\s*min', re.I)
PRICE_RE = re.compile(r'Liput\s*:\s*([^<]+)')
GENRE_RE = re.compile(r'<p>([^<]{2,80})</p>')
SRCSET_RE = re.compile(r'srcset="([^"]+)"')
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s))).strip()


def _biggest(srcset):
    best, bw = "", -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                continue
            if w > bw:
                best, bw = bits[0], w
    return best


def _minutes(text):
    m = KESTO_RE.search(text)
    return int(m.group(1) or 0) * 60 + int(m.group(2)) if m else 0


def _iso(day, month, hh, mm, today=None, weekday=None):
    """`Pe 28.08. klo 19:00` -> an ISO start, or "" when the row cannot be placed.

    `common.resolve_year` selects the year and then bounds it. The private loop this
    replaced took the first candidate inside a window rather than the nearest one, so a
    row 46 or more days stale resolved to next year: `1.8.` read on 2026-09-19 published
    as 2027-08-01. Every row here prints its weekday, which selects the year outright.
    """
    today = today or datetime.datetime.now(FI).date()
    year = resolve_year(day, month, today, weekday, WINDOW)
    if year is None:
        return ""
    return datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()


def parse(page, today=None):
    shows = []
    unplaced = []
    cards = {}
    heads = list(HEAD_RE.finditer(page))
    for n, m in enumerate(heads):
        url, title = m.group(1), _txt(m.group(2))
        if not title:
            continue
        before = page[heads[n - 1].end():m.start()] if n else page[:m.start()]
        after = page[m.end():heads[n + 1].start()] if n + 1 < len(heads) else page[m.end():]
        block = SHOWS_RE.search(after)
        if not block:
            # A card, not a screening block: its runtime is the film's, by title.
            if _minutes(after):
                cards.setdefault(title, set()).add(_minutes(after))
            continue
        minutes = _minutes(before)
        rating_raw = RATING_RE.search(before)
        rating = _txt(rating_raw.group(1)) if rating_raw else ""
        if rating and rating[0].isdigit():
            rating = "K-" + rating
        price_raw = PRICE_RE.search(before)
        srcset = SRCSET_RE.search(before)
        img = _biggest(srcset.group(1)) if srcset else ""
        # Block is <p>genres</p><p>Ikäraja : n</p><p>Liput : n€</p> — take the last
        # plain paragraph before the title.
        genres = ""
        for g in GENRE_RE.findall(before):
            g = _txt(g)
            if g and not any(k in g for k in ("Ikäraja", "Liput", "Näytösajat", "Kesto")):
                genres = g
        for sm in SHOW_RE.finditer(block.group(1)):
            wd, day, month, hh, mm, dub = sm.groups()
            start = _iso(int(day), int(month), int(hh), int(mm), today,
                         weekday_index(wd))
            if not start:
                unplaced.append(f"{wd} {day}.{month}.")
                continue
            shows.append({
                "eventId": url.rstrip("/").rsplit("/", 1)[-1],
                "title": title,
                "original": "",
                "len": str(minutes) if minutes else "",
                "rating": rating,
                "genres": genres,
                "method": "",
                "theatre": VENUE["name"],
                "aud": "",
                "start": start,
                "url": url,
                "img": img,
                "lang": "FI-A" if dub else "",
                "soldOut": False,
                "price": _txt(price_raw.group(1)) if price_raw else "",
                "provider": "kinoakseli",
                "venue": VENUE["id"],
            })
    for s in shows:
        got = cards.get(s["title"]) or set()
        if not s["len"] and len(got) == 1:
            s["len"] = str(next(iter(got)))
    if unplaced:
        print(f"[kinoakseli] {len(unplaced)} row(s) whose weekday matches no candidate "
              f"year inside the window, skipped: {', '.join(unplaced[:5])}")
    shows.sort(key=lambda s: s["start"])
    return shows


def fetch_page():
    page = get_text(URL, fetcher=fetch)
    if len(page) < 5000 or "sgcaptcha" in page:
        raise RuntimeError("challenged (needs a residential IP)")
    return parse(page)


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one screen, keyed by the venue id."""
    return {VENUE["id"]: fetch_page()}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = parse(open(src, encoding="utf-8", errors="replace").read()) if src else fetch_page()
    print(f"{len(data)} showtimes, {len({s['eventId'] for s in data})} films")
    for s in data:
        print(f"  {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:6} "
              f"{s['price']:7} {s['lang']:5} {s['genres'][:28]}")
