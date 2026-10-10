"""Elokuvateatteri Julia 1&2, Hämeenkatu 34, Hyvinkää. Stdlib only.

**Which Julia this is.** A 2026-09-15 sweep recorded a candidate called "Julia" as a
defunct Turku cinema after reading `turunleffat.biokuva.fi/elokuvateatteri/julia/`, which
is a local cinema-history archive page about a 1980s Eerikinkatu build. That was the wrong
identity. This is a different, operating cinema: Julia 1&2 in Hyvinkää, on its own
WordPress at `juliaelokuvat.fi`, with two halls of 110 and 57 seats.

**One request.** `/ohjelmisto/` carries the whole published programme: one
`<div class="elokuva">` per film, holding the film-page link, the poster, the screenings
and the labelled metadata.

    <a href=".../elokuvat/hetki-ennen-valoa/"><h2>Hetki ennen valoa</h2></a>
    <img ... class="alignleft wp-post-image" src="...juliste.jpg">
    <strong><div id='b1826'>15.09.26 klo 18:00, 1. sali<br>16.09.26 klo 18:00, 1. sali<br></div></strong>
    <strong>Hinta:</strong> 14€ / 12€<br><strong>Ikäraja:</strong> 7<br>
    <strong>Kesto:</strong> 1t 27min<br><strong>Genre:</strong> Draama, Kotimainen<br>

Four things about this page that shape the parser:

- **The films are listed twice.** An index block above the programme repeats every title
  with a "Katso näytösajat tästä" link to the same film page. Only the programme block
  carries screenings, so parsing is anchored on `div.elokuva` and a title with no
  screening row yields nothing rather than a dateless show.
- **The year is two digits**, `15.09.26`. It is published rather than missing, so it is
  read as 2000+YY and nothing is inferred from the current date. A row whose year is
  absent is skipped; this parser never guesses one.
- **The hall is written `1. sali`** and becomes `Sali 1`, which is the shape every other
  provider here publishes.
- **There is no online booking.** The cinema sells at the door and takes reservations by
  phone, so the showtime links to the film's own page and the registry entry is
  `book="door"`. No ticket host exists to link to and none is invented.

`Ikäraja: 7` becomes `K-7`, and a row reading `S` or `sallittu` becomes `S`; anything else
yields no rating rather than a guess.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import fetch, get_text

BASE = "https://juliaelokuvat.fi"
LISTING = BASE + "/ohjelmisto/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "julia-hyvinkaa", "name": "Julia 1&2", "short": "Julia 1&2", "city": "Hyvinkää"}

SITES = [{"provider": "julia", "label": "Julia 1&2", "base": BASE, "venues": [VENUE]}]

# No empty state is recorded for this site. A page without a film block is a changed
# template, and so is one whose film blocks yield no screening: both fail.
CONTAINER_RE = re.compile(r'class="elokuva"', re.I)
FILM_RE = re.compile(
    r'<div class="elokuva"[^>]*>(.*?)(?=<div class="elokuva"|</div>\s*</div>\s*</div>|\Z)',
    re.S | re.I)
LINK_RE = re.compile(r'<a href="[^"]*/elokuvat/([^"/]+)/"[^>]*>\s*<h2[^>]*>(.*?)</h2>', re.S | re.I)
SHOW_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{2})\s*klo\s*(\d{1,2})[:.](\d{2})'
                     r'(?:\s*,\s*(\d+)\.\s*sali)?', re.I)
POSTER_RE = re.compile(r'<img[^>]*class="[^"]*wp-post-image[^"]*"[^>]*src="([^"]+)"', re.I)
POSTER_ALT_RE = re.compile(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*wp-post-image', re.I)
FIELD_RE = {
    "price": re.compile(r'<strong>\s*Hinta:\s*</strong>\s*([^<]{1,40})', re.I),
    "age": re.compile(r'<strong>\s*Ik&auml;raja:\s*</strong>\s*([^<]{1,20})|'
                      r'<strong>\s*Ikäraja:\s*</strong>\s*([^<]{1,20})', re.I),
    "len": re.compile(r'<strong>\s*Kesto:\s*</strong>\s*([^<]{1,30})', re.I),
    "genres": re.compile(r'<strong>\s*Genre:\s*</strong>\s*([^<]{1,80})', re.I),
}
# "1t 28min", and "1h 41m" on one film read 2026-10-04.
KESTO_RE = re.compile(r'(?:(\d+)\s*[th])?\s*(\d+)\s*m(?:in)?\b', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _rating(raw):
    """`7` -> `K-7`, `S` / `Sallittu` -> `S`, anything else -> no rating."""
    r = _txt(raw).strip().rstrip(".")
    if not r:
        return ""
    if r.upper().startswith("S"):
        return "S"
    m = re.fullmatch(r"K?-?(\d{1,2})", r.upper())
    return f"K-{int(m.group(1))}" if m else ""


def _minutes(raw):
    m = KESTO_RE.search(_txt(raw))
    if not m:
        return ""
    return str(int(m.group(1) or 0) * 60 + int(m.group(2)))


def parse(page):
    """`/ohjelmisto/` -> [show]. Raises when the programme container is missing, and
    when it is present with no screening row this parser reads."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{LISTING}: no film block on the page, so this is not the programme this "
            f"parser reads. Treating it as a fetch or template failure rather than a "
            f"cinema with nothing on")
    shows, seen = [], set()
    for block in FILM_RE.findall(page):
        link = LINK_RE.search(block)
        if not link:
            continue
        slug, title = link.group(1), _txt(link.group(2))
        if not title:
            continue
        m = FIELD_RE["age"].search(block)
        rating = _rating((m.group(1) or m.group(2)) if m else "")
        m = FIELD_RE["price"].search(block)
        price = _txt(m.group(1)) if m else ""
        m = FIELD_RE["len"].search(block)
        length = _minutes(m.group(1)) if m else ""
        m = FIELD_RE["genres"].search(block)
        genres = ", ".join(g.strip().lower() for g in _txt(m.group(1)).split(",") if g.strip()) if m else ""
        p = POSTER_RE.search(block) or POSTER_ALT_RE.search(block)
        img = p.group(1) if p else ""
        for day, month, yy, hh, mm, sali in SHOW_RE.findall(block):
            try:
                start = datetime.datetime(2000 + int(yy), int(month), int(day),
                                          int(hh), int(mm), tzinfo=FI)
            except ValueError:
                continue
            aud = f"Sali {int(sali)}" if sali else ""
            key = (slug, start.isoformat(), aud)
            if key in seen:
                continue
            seen.add(key)
            shows.append({
                "eventId": slug,
                "title": title,
                "original": "",
                "len": length,
                "rating": rating,
                "genres": genres,
                "method": "",
                "theatre": VENUE["name"],
                "aud": aud,
                "start": start.isoformat(),
                "url": f"{BASE}/elokuvat/{slug}/",
                "img": img,
                "lang": "",
                "soldOut": False,
                "price": price,
                "provider": "julia",
                "venue": VENUE["id"],
            })
    if not shows:
        raise RuntimeError(
            f"{LISTING}: film blocks with no screening row this parser reads. No empty "
            f"state is recorded for this site, so this is a template or format change "
            f"rather than a cinema with nothing on")
    shows.sort(key=lambda s: (s["start"], s["aud"]))
    return shows


def get_listing():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(LISTING, fetcher=fetch)


def fetch_site(site=SITES[0]):
    """Runner contract: one listing, one venue."""
    shows = parse(get_listing())
    print(f"[julia] {len(shows)} showtimes, {len({s['eventId'] for s in shows})} films, "
          f"{len({s['start'][:10] for s in shows})} dates")
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    for s in data:
        print(f"  {s['start'][:16]} {s['aud'] or '-':7} {s['title'][:32]:34} {s['rating']:5} "
              f"{s['len']:4} {s['price']:12} {s['genres'][:22]}")
