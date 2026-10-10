"""Elokuvateatteri Bio-Kaari, Forssa. Stdlib only.

Probed 2026-09-15. WordPress with a site-specific plugin (`wp-content/plugins/biokaari/`)
that renders the whole programme server-side, so nothing here depends on its JavaScript.

**It is a MyCloudCinema cinema, and that does not make it a `SITES` entry.** Its posters
come from `mcswebsites.blob.core.windows.net` and its ticket host is
`bio-kaari.azurewebsites.net/websales/`, the same platform BioRex and Gilda run on. All
three render it differently: BioRex is `admin-ajax` returning HTML in JSON, Gilda is
MyCloudCinema's own document, and this is a bespoke WordPress plugin. A platform
fingerprint is a lead, not an adapter, which is the same conclusion `docs/research`
reached about Johku.

**One request for the programme.** The front page carries a `<select id="dateSelection">`
of the next ten days and one `<div class="searchResults" id="DDMMYYYY">` per day, all of
them present in the markup with the later ones merely `display:none`:

    <div class="searchResults" id="15092026">
      <div class="searchItem">
        <div class="searchItemImage"><a href="tapahtuma/?event=31671"><img src="...jpg"></a></div>
        <div class="searchItemData"><a href="tapahtuma/?event=31671">
          <h2>Hetki ennen valoa<small><span> (2026)</span></small></h2></a>
          <ul class="searchItemShows">
            <li><P class="searchItemEventTime">17:30</P>
                <DIV class="searchItemEventLink"><A href="http://.../websales/show/984056/">

Four things that shape the parser:

- **The date is the container's id**, `DDMMYYYY`, complete with its year. The film rows
  inside repeat the same title and time across days, so a parser that read the rows
  without their container would publish one day's times on every day. The date is never
  inferred from the clock.
- **A film can hold several `<li>` rows on one day**, which is more than one screening,
  and each has its own time and its own ticket id.
- **The tag names are upper case** in the screening rows (`<P>`, `<DIV>`, `<A>`) and lower
  case elsewhere, so every pattern here is case-insensitive.
- **The published ticket link is `http://`** on a host that answers `https://` and
  redirects there (checked 2026-09-15). It is upgraded, and it is read from the page
  rather than constructed: building a ticket URL from a copied path is what shipped six
  dead Nexxo links. The page it opens is read for the price and the language; see below.

The title carries a release year, `(2026)`, which becomes the optional `year` field rather
than being left in the title: `title` is the TMDB and merge key and the year is not part
of the film's name.

`enrich()` reads one film page per distinct film for the age limit, runtime and genre,
which the programme itself does not carry. Bio-Kaari runs a handful of films at a time, so
that is a few requests a run rather than the dozens a larger cinema would cost.

**The ticket page is read since 2026-10-09, on the maintainer's decision.** The showtime's
own page, `bio-kaari.azurewebsites.net/websales/show/{id}/`, is the MyCloudCinema page
Riviera's price pass already reads, with the same markup: `Kieli: <b>Suomi</b>`,
`Tekstitys : <b>Suomi</b>` and a `showPrices-table` whose ordinary row is "Normaali".
`prices.run` reads it once per screening, cached for 48 h, paced and capped, and nothing
past that page is requested. Its "No Subtitles" line is not read, even next to a stated
audio language. The maintainer decided this because the platform shows the line when
nobody has set the subtitles: Riviera's page for an English film has it with no language
line at all.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

import prices
import riviera
from common import capped, fetch, get_text, served

BASE = "https://www.bio-kaari.fi"
# The ticket pages' host, declared in `reads` because the price pass requests it.
TICKETS = "https://bio-kaari.azurewebsites.net/websales/show/"
ORDINARY = "normaali"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "biokaari-forssa", "name": "Bio-Kaari", "short": "Bio-Kaari",
         "city": "Forssa"}

SITES = [{"provider": "biokaari", "label": "Bio-Kaari", "base": BASE,
          "reads": ("bio-kaari.azurewebsites.net",), "venues": [VENUE]}]

# The day containers are the programme. Absent means the plugin's markup changed. Present
# with no screening is not evidence of nothing on either: no empty state has been read off
# this site, so zero rows fails the site rather than raising `common.EmptyProgramme`.
CONTAINER_RE = re.compile(r'<div class="searchResults"', re.I)
DAY_RE = re.compile(r'<div class="searchResults" id="(\d{2})(\d{2})(\d{4})"[^>]*>', re.I)
ITEM_RE = re.compile(r'<div class="searchItem">(.*?)<!--\s*tapahtuma loppuu\s*-->', re.S | re.I)
EVENT_RE = re.compile(r'href="[^"]*tapahtuma/\?event=(\d+)"', re.I)
TITLE_RE = re.compile(r'<h2>(.*?)</h2>', re.S | re.I)
YEAR_RE = re.compile(r'<small>\s*<span>\s*\((\d{4})\)\s*</span>\s*</small>', re.I)
IMG_RE = re.compile(r'<img[^>]*src="([^"]+)"', re.I)
SHOW_RE = re.compile(r'<p class="searchItemEventTime">\s*(\d{1,2})[:.](\d{2})\s*</p>\s*'
                     r'<div class="searchItemEventLink">\s*<a href="([^"]+)"', re.I)

# Film page: labelled text.
FIELD_RE = {
    "genres": re.compile(r'Lajityyppi:\s*([^<\n]{1,60}?)\s*(?:<|Ik&auml;raja|Ikäraja|N&auml;yt|Näyt|$)', re.I),
    "rating": re.compile(r'Ik(?:&auml;|ä)raja:\s*([A-ZS]?-?\d{0,2})', re.I),
    "len": re.compile(r'Kesto:\s*(?:(\d+)\s*h)?\s*(\d+)\s*min', re.I),
}
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _rating(raw):
    """`K7` (the page writes `K7/4`, the 4 being the flexibility years) -> `K-7`."""
    r = _txt(raw).strip().upper()
    if not r:
        return ""
    if r.startswith("S"):
        return "S"
    m = re.match(r"K-?(\d{1,2})", r)
    return f"K-{int(m.group(1))}" if m else ""


def parse(page):
    """The front page -> [show]. Raises when no day container is present, and when the
    containers yield no screening."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{BASE}: no day container on the page, so this is not the programme this "
            f"parser reads. Treating it as a fetch or template failure rather than a "
            f"cinema with nothing on")
    days = list(DAY_RE.finditer(page))
    shows, seen = [], set()
    for i, d in enumerate(days):
        day, month, year = (int(x) for x in d.groups())
        chunk = page[d.end():days[i + 1].start() if i + 1 < len(days) else len(page)]
        for block in ITEM_RE.findall(chunk):
            ev = EVENT_RE.search(block)
            t = TITLE_RE.search(block)
            if not (ev and t):
                continue
            raw_title = t.group(1)
            yr = YEAR_RE.search(raw_title)
            title = _txt(YEAR_RE.sub("", raw_title))
            if not title:
                continue
            img = IMG_RE.search(block)
            for hh, mm, href in SHOW_RE.findall(block):
                try:
                    start = datetime.datetime(year, month, day, int(hh), int(mm), tzinfo=FI)
                except ValueError:
                    continue
                url = href.strip()
                if url.startswith("http://"):
                    url = "https://" + url[len("http://"):]
                key = (ev.group(1), start.isoformat(), url)
                if key in seen:
                    continue
                seen.add(key)
                show = {
                    "eventId": ev.group(1),
                    "title": title,
                    "original": "",
                    "len": "",
                    "rating": "",
                    "genres": "",
                    "method": "",
                    "theatre": VENUE["name"],
                    "aud": "",
                    "start": start.isoformat(),
                    "url": url,
                    "img": img.group(1) if img else "",
                    "lang": "",
                    "soldOut": False,
                    "price": "",
                    "provider": "biokaari",
                    "venue": VENUE["id"],
                }
                if yr:
                    show["year"] = yr.group(1)
                shows.append(show)
    if not shows:
        raise RuntimeError(
            f"{BASE}: no screening parsed from {len(days)} day container(s) and "
            f"{len(ITEM_RE.findall(page))} film item(s) ({served(page)}). No empty state is "
            f"known for this site, so this is a parse or template failure")
    shows.sort(key=lambda s: s["start"])
    return shows


def details(page):
    """Film-page metadata. Returns {} for anything the page does not carry."""
    text = _txt(page)
    d = {}
    m = FIELD_RE["rating"].search(text)
    if m:
        r = _rating(m.group(1))
        if r:
            d["rating"] = r
    m = FIELD_RE["len"].search(text)
    if m:
        d["len"] = str(int(m.group(1) or 0) * 60 + int(m.group(2)))
    m = FIELD_RE["genres"].search(text)
    if m:
        g = ", ".join(x.strip().lower() for x in m.group(1).split(",") if x.strip())
        if g:
            d["genres"] = g
    return d


def enrich(shows, get=None, sleep=1.2):
    """One film page per distinct event id, folded onto every screening of it."""
    get = get or (lambda u: get_text(u, fetcher=fetch, tries=2, backoff=3, timeout=20))
    by_film = {}
    for s in shows:
        by_film.setdefault(s["eventId"], []).append(s)
    ok = fail = 0
    for n, (eid, rows) in enumerate(capped(sorted(by_film.items()), "biokaari")):
        if n:
            time.sleep(sleep)
        url = f"{BASE}/tapahtuma/?event={eid}"
        try:
            d = details(get(url))
        except Exception as e:
            fail += 1
            print(f"[biokaari] film page {eid}: {type(e).__name__}: {e}")
            continue
        if not d:
            fail += 1
            print(f"[biokaari] film page {eid}: nothing parsed")
            continue
        ok += 1
        for s in rows:
            for k, v in d.items():
                if v and not s.get(k):
                    s[k] = v
    print(f"[biokaari] film pages: {ok} parsed, {fail} with nothing usable, "
          f"{sum(1 for s in shows if s.get('rating'))}/{len(shows)} showtimes rated")
    return shows


def ordinary_price(page_html):
    """The "Normaali" row's price on a ticket page -> "14\u20ac", or ""."""
    return riviera.ordinary_price(page_html, ORDINARY)


def page_fields(page_html):
    """The audio and subtitle lines, through Riviera's reader of the same markup."""
    return {"lang": riviera.screening_language(page_html)}


def get_page():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(BASE + "/", fetcher=fetch)


def fetch_site(site=SITES[0], prices_path=None, price_sleep=1.0, now=None):
    """Runner contract: one front page, a film page per film, a ticket page per
    screening, one venue."""
    shows = parse(get_page())
    enrich(shows)
    # After the schedule is complete, and never able to take it down: a failure here
    # publishes the showtimes without price and language, as before.
    prices.run(shows, provider="biokaari", prefix=TICKETS, parse=ordinary_price,
               fields=page_fields, referer=BASE + "/", path=prices_path, now=now,
               sleep=price_sleep,
               fetch_fn=lambda url, headers: fetch(url, headers=headers, tries=2, timeout=20))
    print(f"[biokaari] {len(shows)} showtimes, {len({s['eventId'] for s in shows})} films, "
          f"{len({s['start'][:10] for s in shows})} dates")
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    for s in data:
        print(f"  {s['start'][:16]} {s['title'][:30]:32} {s.get('year',''):5} "
              f"{s['rating']:5} {s['len']:4} {s['genres'][:18]:20} {s['url'][-26:]}")
