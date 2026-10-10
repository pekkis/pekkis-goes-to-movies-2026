"""Elokuvateatteri Iso-Hannu (Nortamonkatu 15, Rauma): the front page's show table.

Probed 2026-09-15. The site is its own PHP, on none of the platforms this repo already
reads: no `nexxo-scope`, no `etiketti.app`, no MyCloudCinema, no Johku, no open Vista
`/xml/`. So this is a parser rather than a `SITES` entry, which is the only reason one
is written here.

**The whole programme is one request.** `https://www.isohannu.fi/` renders
`<div id="showtable">` with a `<h3 class="showtable-title">` per day ("Tiistai
15.09.2026", the year included), then one `div.showtable-container` per hall, each a
table whose `<td class="showtable-hall">` names the hall and whose rows are the
screenings. 66 screenings over 7 days and 3 halls on the day this was written. The film
pages add the metadata and are one request per film, not per screening: 26 of them for
those 66 rows.

Four things about this site that shape the parser:

- **The row's own anchor carries the film id**, `/leffasivu.php?id=2190`, and that id is
  the film rather than the run: the same id recurs across days and halls. It is therefore
  the `eventId`, which is what the contract asks for, and no title normalisation is
  needed to fold a film's screenings together.
- **The ticket link is per screening** and the site writes it as `http://`, while
  `lipunmyynti.isohannu.fi` answers `https://` perfectly well (checked 2026-09-15, 200).
  It is upgraded here rather than published as plain http: the client sends the reader
  there, and there is no reason to send them over http when the host offers https.
- **The age limit is written `K12`, not `K-12`.** Every other provider in this repo
  publishes the hyphenated form and the committed data holds only `K-7`, `K-12`, `K-16`,
  `K-18` and `S`, so it is normalised here. The stub prints `rating` verbatim, so an
  un-normalised `K12` would be visibly the odd one out.
- **Subtitles are not published at all.** The film page carries `Puhekieli` and no
  `Tekstitys`, so `lang` gets the spoken language only and no subtitle role is invented.

Tag labels are the site's own text ("Lapsille", "Ensi-ilta"), taken verbatim rather than
mapped to wording this repo made up. `showtable-tickets` is the buy button on every row
and is not a strand, so it is excluded by name.

No screening parsed is a failure, never `EmptyProgramme`. This site's empty programme has
not been read, so nothing on the page is known to mean "nothing on": an empty
`<div id="showtable">` is also what a change to the row markup inside it produces. The
day, hall and row-anchor counts go into the error so the log says which.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import capped, fetch, get_text

BASE = "https://www.isohannu.fi"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "ih-rauma", "name": "Iso-Hannu", "short": "Iso-Hannu", "city": "Rauma"}

SITES = [{"provider": "isohannu", "label": "Iso-Hannu", "base": BASE, "venues": [VENUE]}]

TABLE_RE = re.compile(r'<div id="showtable">', re.I)
DAY_RE = re.compile(r'<h3 class="showtable-title">[^<]*?(\d{1,2})\.(\d{1,2})\.(\d{4})\s*</h3>', re.I)
HALL_RE = re.compile(r'<td class="showtable-hall">([^<]*)</td>', re.I)
ROW_RE = re.compile(r'<a href="/leffasivu\.php\?id=(\d+)"\s*>\s*'
                    r'<div class="showtable-row">(.*?)</div>\s*</a>', re.S | re.I)
TIME_RE = re.compile(r'<span class="showtable-time">\s*(\d{1,2})[:.](\d{2})\s*</span>', re.I)
NAME_RE = re.compile(r'<span class="showtable-name">([^<]*)', re.I)
TICKET_RE = re.compile(r'<a href="(https?://lipunmyynti\.isohannu\.fi/[^"]+)"', re.I)
TAG_RE = re.compile(r'<span class="showtable-tag showtable-(\w+)"\s*>([^<]*)</span>', re.I)

# Film page: labelled text, one label per line of the info block.
FIELD_RE = {
    "len": re.compile(r"Elokuvan kesto:\s*(\d+)\s*min", re.I),
    "rating": re.compile(r"Elokuvan ikäraja:\s*([KS][-\s]?\d*)", re.I),
    "genres": re.compile(r"Genre:\s*([^<\n]{1,80}?)\s*(?:<|Puhekieli|Ensi-ilta|Katso|$)", re.I),
    "spoken": re.compile(r"Puhekieli:\s*([^<\n]{1,60}?)\s*(?:<|Genre|Ensi-ilta|Katso|$)", re.I),
}
POSTER_RE = re.compile(r'(https://lipunmyynti\.isohannu\.fi/images/posters/[^"\'\s>]+)', re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# The house tariff, in the front page's own `LIPUT` block, so reading it costs no request:
#
#     LIPUT  Ma-to 13,50 €  Pe-su ja arkipyhä 14,50 €
#
# Read as a visitor 2026-09-16. Two amounts and the days each covers, in that order, so the
# pair is read as a pair rather than by matching the Finnish day names, which the page
# writes as ranges. The discounts printed beside it -- student, pensioner, under-12, and
# S-Etukortti Tuesdays at 10,00 € -- all need a card shown at the counter, so the ordinary
# ticket is the one figure that describes what a visitor pays without one.
#
# **Only Friday to Sunday is published.** The dearer tariff covers `Pe-su ja arkipyhä`, so
# a Friday, Saturday or Sunday screening is 14,50 whatever else the day is -- established.
# A Monday-to-Thursday screening is 13,50 *unless* the day is an arkipyhä, a weekday public
# holiday, and which days those are is a calendar this repo does not carry. So those publish
# nothing. Both amounts are still read, because a block that states only one cannot say
# which days either covers; see `tariff`.
TARIFF_RE = re.compile(
    r"LIPUT\s+Ma-?to\s*(\d{1,3}[.,]\d{2})\s*\u20ac\s*Pe-?su[^\d]{0,30}?(\d{1,3}[.,]\d{2})\s*\u20ac",
    re.I)

# `Puhekieli` is a Finnish language name; the codes are the app's own tags. A name this
# table does not carry yields no tag rather than a guess, the way tapiola.py does it.
LANGS = {"suomi": "FI", "ruotsi": "SV", "englanti": "EN", "saksa": "DE", "ranska": "FR",
         "espanja": "ES", "italia": "IT", "venäjä": "RU", "viro": "ET", "tanska": "DA",
         "norja": "NO", "islanti": "IS", "japani": "JA", "kiina": "ZH", "korea": "KO",
         "arabia": "AR", "puola": "PL", "portugali": "PT", "hollanti": "NL",
         "ukraina": "UK", "liettua": "LT", "turkki": "TR"}


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _rating(raw):
    """`K12` -> `K-12`, `S` -> `S`. The house shape, see the docstring."""
    r = re.sub(r"[\s-]+", "", (raw or "").upper())
    if not r:
        return ""
    if r == "S":
        return "S"
    m = re.fullmatch(r"K(\d+)", r)
    return f"K-{m.group(1)}" if m else raw.strip()


def parse(page):
    """The front page -> [show]. Raises when the table container is missing or holds
    no screening this parser can read; see the docstring for why the latter is not
    `EmptyProgramme`."""
    if not TABLE_RE.search(page):
        raise RuntimeError("no <div id=\"showtable\"> in the response: this is not the "
                           "page this parser reads, so it is a fetch or template failure "
                           "rather than a cinema with nothing on")
    shows, seen = [], set()
    cheap, dear = tariff(page)
    days = list(DAY_RE.finditer(page))
    for i, d in enumerate(days):
        day, month, year = (int(x) for x in d.groups())
        chunk = page[d.end():days[i + 1].start() if i + 1 < len(days) else len(page)]
        # One container per hall, so the hall header and its rows stay together: splitting
        # on the table instead would attach every row to the first hall of the day.
        for part in chunk.split('<div class="showtable-container">')[1:]:
            hall = HALL_RE.search(part)
            hall = _txt(hall.group(1)) if hall else ""
            for fid, body in ROW_RE.findall(part):
                t = TIME_RE.search(body)
                n = NAME_RE.search(body)
                if not (t and n):
                    continue
                title = _txt(n.group(1))
                if not title:
                    continue
                try:
                    start = datetime.datetime(year, month, day, int(t.group(1)),
                                              int(t.group(2)), tzinfo=FI).isoformat()
                except ValueError:
                    continue
                url = TICKET_RE.search(body)
                url = url.group(1).replace("http://", "https://", 1) if url else ""
                strands = [_txt(v) for k, v in TAG_RE.findall(body)
                           if k.lower() != "tickets" and _txt(v)]
                key = (fid, start, hall)
                if key in seen:
                    continue
                seen.add(key)
                shows.append({
                    "eventId": fid,
                    "title": title,
                    "original": "",
                    "len": "",
                    "rating": "",
                    "genres": "",
                    "method": " · ".join(strands),
                    "theatre": VENUE["name"],
                    "aud": hall,
                    "start": start,
                    "url": url,
                    "img": "",
                    "lang": "",
                    "soldOut": False,
                    "price": price_of(cheap, dear,
                                      datetime.datetime.fromisoformat(start)),
                    "provider": "isohannu",
                    "venue": VENUE["id"],
                })
    if not shows:
        halls = page.count('<div class="showtable-container">')
        anchors = len(re.findall(r"/leffasivu\.php\?id=", page))
        raise RuntimeError(
            f"{BASE}: the show table holds {len(days)} day heading(s), {halls} hall(s) "
            f"and {anchors} film anchor(s), and not one screening parsed. No empty state "
            f"of this page is known, so this is a parse or template failure rather than a "
            f"cinema with nothing on")
    shows.sort(key=lambda s: (s["start"], s["aud"]))
    return shows


def tariff(page):
    """The two ordinary ticket prices. -> (Mon-Thu, Fri-Sun), or (None, None).

    Both or neither. The block states the cheaper amount and the days it covers before the
    dearer one, and half a tariff cannot say which days an amount belongs to -- an
    unanchored reader that found one amount could not tell `Ma-to 13,50` from a discount.
    Only the second is published; `price_of` says why.
    """
    m = TARIFF_RE.search(_txt(page))
    if not m:
        return None, None
    return tuple(float(g.replace(",", ".")) for g in m.groups())


def price_of(cheap, dear, start):
    """One screening's price, where the tariff settles it. -> "14.5\u20ac" or "".

    `Pe-su ja arkipyhä 14,50 €` covers Friday, Saturday and Sunday outright, so a screening
    on one of those is that amount and nothing about the day can change it.

    `Ma-to 13,50 €` does not settle a Monday-to-Thursday screening, because the same line
    puts an *arkipyhä* -- a weekday public holiday -- on the dearer tariff, and no calendar
    here knows which days those are. Such a screening is 13,50 or 14,50 and this cannot say
    which, so it publishes neither. Guessing the common case would put a wrong amount in
    front of a reader on the days a cinema is busiest, and a note that it is sometimes 0.50
    out is not the same as it being right.

    `cheap` is read and not published: see `tariff`.
    """
    if dear is None or start.weekday() <= 3:
        return ""
    return f"{dear:.2f}".rstrip("0").rstrip(".") + "\u20ac"


def details(page):
    """Film-page metadata. Returns {} for anything the page does not carry."""
    text = _txt(page)
    d = {}
    m = FIELD_RE["len"].search(text)
    if m:
        d["len"] = m.group(1)
    m = FIELD_RE["rating"].search(text)
    if m:
        r = _rating(m.group(1))
        if r:
            d["rating"] = r
    m = FIELD_RE["genres"].search(text)
    if m:
        g = ", ".join(p.strip().lower() for p in m.group(1).split(",") if p.strip())
        if g:
            d["genres"] = g
    m = FIELD_RE["spoken"].search(text)
    if m:
        # "suomi, ruotsi, venäjä" (Punainen peto, read 2026-10-04) is three names. Each must
        # be known or none is published: a partial list would read as the whole one.
        codes = [LANGS.get(n.strip().lower()) for n in re.split(r",|\bja\b", m.group(1))
                 if n.strip()]
        if codes and all(codes):
            d["lang"] = ", ".join(f"{c}-A" for c in dict.fromkeys(codes))
    m = POSTER_RE.search(page)
    if m:
        d["img"] = m.group(1)
    return d


def enrich(shows, get=None, sleep=1.2):
    """One film page per distinct film id, folded onto every screening of it."""
    get = get or (lambda u: get_text(u, fetcher=fetch, tries=2, backoff=3, timeout=20))
    by_film = {}
    for s in shows:
        by_film.setdefault(s["eventId"], []).append(s)
    ok = fail = 0
    for n, (fid, rows) in enumerate(capped(sorted(by_film.items()), "isohannu")):
        if n:
            time.sleep(sleep)
        url = f"{BASE}/leffasivu.php?id={fid}"
        try:
            d = details(get(url))
        except Exception as e:
            fail += 1
            print(f"[isohannu] film page {fid}: {type(e).__name__}: {e}")
            continue
        if not d:
            fail += 1
            print(f"[isohannu] film page {fid}: nothing parsed")
            continue
        ok += 1
        for s in rows:
            for k, v in d.items():
                if v and not s.get(k):
                    s[k] = v
    print(f"[isohannu] film pages: {ok} parsed, {fail} with nothing usable, "
          f"{sum(1 for s in shows if s.get('rating'))}/{len(shows)} showtimes rated")
    return shows


def get_page():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(BASE + "/", fetcher=fetch)


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one venue."""
    shows = parse(get_page())
    enrich(shows)
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    dates = sorted({s["start"][:10] for s in data})
    print(f"{len(data)} showtimes, {len({s['eventId'] for s in data})} films, "
          f"{len(dates)} dates ({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}), "
          f"halls {sorted({s['aud'] for s in data})}")
    for s in data[:12]:
        print(f"  {s['start'][:16]} {s['aud']:7} {s['title'][:34]:36} {s['rating']:5} "
              f"{s['len']:4} {s['lang']:6} {s['method'][:12]:12} {s['url'][-28:]}")
