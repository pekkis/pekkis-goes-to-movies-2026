"""Riviera Cinemas (Helsinki: Kallio, Punavuori). WordPress admin-ajax, no auth.

  POST /wp/wp-admin/admin-ajax.php
       action=filter_movies&date=&movie=&area=1040&singlemovie=&initial=1
  -> {"success":true,"data":{"movies":"<ul class=movielist>…</ul>"}}

One request returns every showtime for both venues across the whole published window,
so the adapter splits by the `location` field ("Kallio, Sali 1") rather than by request.

Parameterised by base URL: every field the endpoint needs lives on the site dict, so
another cinema on the same WordPress theme (Gilda) is a SITES entry with no new parser.
Confirm the ajax action matches before adding one.

Prices (2026-09-13): the listing carries none. Each screening's public ticket page,
`{tickets}{id}`, prints a `table.showPrices-table` with one row per ticket category, and
the ordinary seat is "Sohvapaikka tai Nojatuolipaikka". That row's amount is the price
shown; a page without exactly one such row publishes no price. The fetch, cache and
pacing are prices.py's.

Language (2026-09-23): the same page states the screening's audio and subtitles, so the
price pass takes them too (`page_fields`) from the pages it already reads. Entries cached
before this are re-read once, ahead of their expiry, and keep their price until then. A
line that is missing or names anything but languages publishes nothing for that line.
"""
import datetime, html as html_mod, json, re, urllib.parse
from zoneinfo import ZoneInfo

import prices
from common import fetch
from etiketti import EN_NAMES, strict_codes  # noqa: F401 -- EN_NAMES for the test

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

SITE = {"provider": "riviera", "label": "Riviera",
        "base": "https://www.rivieracinemas.fi",
        "ajax": "/wp/wp-admin/admin-ajax.php",
        "listing": "/elokuvat/",
        # Where the site's own "Valitse näytös" button sends a visitor. The
        # listing carries no link at all: the button holds the screening id in
        # data-movieid and the theme's app.js sets the ticket iframe to
        # {tickets}{id}. Publishing that URL is what a click does, one request per run
        # and none per screening.
        "tickets": "https://tickets.rivieracinemas.fi/websales/show/",
        # `prices.run` GETs those ticket pages, up to FETCH_MAX a run, so this site reads a
        # second host and the runner has to know: `base` alone would let another site on
        # tickets.rivieracinemas.fi be read at the same time. The only declared secondary
        # host in the registry as of 2026-09-15.
        "reads": ("tickets.rivieracinemas.fi",),
        # `area` is ignored by their backend (1040 all / 1024 Kallio / 1039 Punavuori),
        # which is why venues carry a `match` against the location field instead.
        "area": "1040",
        "venues": [
    {"id": "rv-kallio",    "match": "kallio",    "name": "Riviera Kallio",
     "short": "Kallio",    "city": "Helsinki"},
    {"id": "rv-punavuori", "match": "punavuori", "name": "Riviera Punavuori",
     "short": "Punavuori", "city": "Helsinki"},
]}
SITES = [SITE]

ITEM_RE = re.compile(r'<li class="movielist__item single-show[^"]*">(.*?)</li>', re.S)
DATE_RE = re.compile(r'class="date">\s*([^<]+?)\s*<')
TIME_RE = re.compile(r'class="time">\s*(\d{1,2})[:.](\d{2})')
LOC_RE = re.compile(r'class="location">\s*([^<]+?)\s*<')
TITLE_RE = re.compile(r'class="movielist__item__title title">\s*([^<]+?)\s*<')
SEATS_RE = re.compile(r"Varatut paikat:\s*(\d+)\s*/\s*(\d+)")
LEN_RE = re.compile(r"Kesto:\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*min)?")
# The actions cell, and the two shapes a screening link takes inside it. An anchor wins
# when the theme ships one, because it is the site's own URL for that screening including
# any query and fragment; the button is what it ships today. Scoped to the cell so a link
# elsewhere in the row (a title, a trailer) cannot answer for the screening.
ACTIONS_RE = re.compile(r'<div class="movielist__item__actions.*?</div>', re.S)
ACTION_HREF_RE = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.S)
SHOW_BTN_RE = re.compile(r'<button\b[^>]*\bshow_tickets\b[^>]*>', re.S)
MOVIEID_RE = re.compile(r'\bdata-movieid="(\d+)"')
DISABLED_RE = re.compile(r"<button[^>]*\bdisabled\b")
TAGS_RE = re.compile(r"<[^>]+>")
# "To 27.8.2026" -> day, month, year
DMY_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _txt(x):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", x or ""))).strip()


def show_url(block, listing="", base="", tickets=""):
    """The URL for one screening: the action cell's own link, else its ticket page.

    An anchor is resolved against `base` with urljoin, so a relative href keeps its
    query and fragment instead of being dropped for not starting with http. That was the
    old rule, and every Riviera showtime published `/elokuvat/` because of it. With no
    anchor, the button's data-movieid is the screening id the theme opens as
    `{tickets}{id}`. With neither, the listing, which at least names the cinema.
    """
    cell = ACTIONS_RE.search(block)
    cell = cell.group(0) if cell else ""
    a = ACTION_HREF_RE.search(cell)
    if a and a.group(1).strip():
        return urllib.parse.urljoin(base or listing, html_mod.unescape(a.group(1).strip()))
    btn = SHOW_BTN_RE.search(cell)
    sid = MOVIEID_RE.search(btn.group(0)) if btn else None
    if sid and tickets:
        return tickets + sid.group(1)
    return listing


def parse(page_html, listing="", base="", tickets=""):
    """-> list of raw showings; venue assignment happens in fetch_site.

    `listing` is the fallback URL for a showing whose cell names no screening.
    """
    out = []
    for block in ITEM_RE.findall(page_html):
        d = DATE_RE.search(block)
        t = TIME_RE.search(block)
        ti = TITLE_RE.search(block)
        if not (d and t and ti):
            continue
        dmy = DMY_RE.search(d.group(1))
        if not dmy:
            continue
        day, mon, year = (int(x) for x in dmy.groups())
        loc = _txt(LOC_RE.search(block).group(1)) if LOC_RE.search(block) else ""
        venue_name, _, room = loc.partition(",")
        seats = SEATS_RE.search(block)
        taken, total = (int(seats.group(1)), int(seats.group(2))) if seats else (None, None)
        ln = LEN_RE.search(block)
        minutes = ""
        if ln and (ln.group(1) or ln.group(2)):
            minutes = str(int(ln.group(1) or 0) * 60 + int(ln.group(2) or 0))
        out.append({
            "loc": venue_name.strip().lower(),
            "aud": room.strip(),
            "title": _txt(ti.group(1)),
            "start": datetime.datetime(year, mon, day, int(t.group(1)), int(t.group(2)),
                                      tzinfo=FI).isoformat(),
            "len": minutes,
            # Every seat taken is sold out. A disabled button decides only where no seat
            # count is printed: one disabled over free seats can be a sale not yet open,
            # and marking it sold out would turn readers away. Read 2026-09-25, both
            # disabled rows showed every seat taken (docs/research/ticketing-platforms.md).
            "soldOut": (bool(total and taken >= total) if seats
                        else bool(DISABLED_RE.search(block))),
            "url": show_url(block, listing, base, tickets),
        })
    return out


# ---------------------------------------------------------------- prices

# The ordinary seat on the ticket page; the fetch, cache and pacing are prices.py's.
ORDINARY = "sohvapaikka tai nojatuolipaikka"
PRICE_TABLE_RE = re.compile(r"<table[^>]*\bshowPrices-table\b[^>]*>(.*?)</table>", re.S)
PRICE_ROW_RE = re.compile(r"<tr\b.*?</tr>", re.S)
CATEGORY_RE = re.compile(r"<td[^>]*\bshowPrices-table-ticketCategory\b[^>]*>(.*?)</td>", re.S)
PRICE_CELL_RE = re.compile(r"<td[^>]*\bshowPrices-table-price\b[^>]*>(.*?)</td>", re.S)
AMOUNT_RE = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:\u20ac|EUR)", re.I)


def ordinary_price(page_html, ordinary=ORDINARY):
    """The ordinary seat's price on a ticket page -> "20\u20ac", "12.5\u20ac", or "".

    Only the row whose category is `ordinary` counts: a wheelchair, concession or other
    restricted ticket listed above it must not become the advertised price, and neither
    may the cheapest or the first amount on the page. No such row, or two of them
    naming different amounts, is "" -- unknown, never zero. `ordinary` is the cinema's
    own name for that category on the same MyCloudCinema page: Bio-Kaari writes
    "Normaali".
    """
    table = PRICE_TABLE_RE.search(page_html or "")
    if not table:
        return ""
    amounts = []
    for row in PRICE_ROW_RE.findall(table.group(1)):
        cat, cell = CATEGORY_RE.search(row), PRICE_CELL_RE.search(row)
        if not (cat and cell) or _txt(cat.group(1)).lower() != ordinary:
            continue
        m = AMOUNT_RE.search(_txt(cell.group(1)))
        if m:
            amounts.append(m.group(1))
    return prices.one_amount(amounts) if amounts else ""


# ---------------------------------------------------------------- language

# The same ticket page states the screening's audio and subtitles, 2026-09-23:
#   <p class="spokenLanguage"> Kieli: <b>Englanti</b> </p>
#   <p class="showSubtitles"> Tekstitys : <b>Suomi, Ruotsi</b> </p>
# In capitalised Finnish names, except that one film's audio read "Spanish". 22 pages
# across 11 films read that day all had the audio line; three had no subtitle line.
# Probe: docs/research/screening-language-sources.md.
SPOKEN_RE = re.compile(r'<p[^>]*\bspokenLanguage\b[^>]*>(.*?)</p>', re.S)
SUBTITLES_RE = re.compile(r'<p[^>]*\bshowSubtitles\b[^>]*>(.*?)</p>', re.S)
BOLD_RE = re.compile(r"<b\b[^>]*>(.*?)</b>", re.S)


def _codes(cell):
    """The value of one line -> its language codes in page order; see strict_codes."""
    if not cell:
        return []
    b = BOLD_RE.search(cell)
    return strict_codes(_txt(b.group(1) if b else cell.split(":", 1)[-1]))


def screening_language(page_html):
    """A ticket page's audio and subtitles -> "EN-A, FI-S, SV-S", Finnkino's tags, or ""
    for what the page does not state. A missing subtitle line is not "no subtitles"."""
    spoken, subs = SPOKEN_RE.search(page_html or ""), SUBTITLES_RE.search(page_html or "")
    parts = [f"{c}-A" for c in _codes(spoken.group(1) if spoken else "")]
    parts += [f"{c}-S" for c in _codes(subs.group(1) if subs else "")]
    return ", ".join(parts)


def page_fields(page_html):
    """What the price pass takes off a ticket page besides the price."""
    return {"lang": screening_language(page_html)}


def fetch_site(site=SITE, tries=3, price_sleep=1.0, prices_path=None, now=None):
    base = site["base"].rstrip("/")
    ajax = base + site.get("ajax", "/wp/wp-admin/admin-ajax.php")
    listing = base + site.get("listing", "/elokuvat/")
    body = urllib.parse.urlencode({"action": "filter_movies", "date": "", "movie": "",
                                   "area": site.get("area", "1040"),
                                   "singlemovie": "", "initial": "1"}).encode()
    # POST, so `data` is passed to common.fetch; same tries=3, 5 s * n backoff and 30 s
    # timeout as the loop this replaces. The parse sits outside the retry now.
    payload = json.loads(fetch(ajax, data=body, headers={
        "user-agent": UA, "accept": "application/json, text/javascript, */*",
        "content-type": "application/x-www-form-urlencoded",
        "x-requested-with": "XMLHttpRequest",
        "referer": listing}, tries=tries).decode("utf-8", "replace"))

    rows = parse((payload.get("data") or {}).get("movies") or "", listing, base,
                 site.get("tickets", ""))
    per_venue = {v["id"]: [] for v in site["venues"]}
    unmatched = 0
    for r in rows:
        venue = next((v for v in site["venues"] if v["match"] in r["loc"]), None)
        if not venue:
            unmatched += 1
            continue
        per_venue[venue["id"]].append({
            "eventId": "", "title": r["title"], "original": "", "len": r["len"],
            "rating": "", "genres": "", "method": "",
            "theatre": venue["name"], "aud": r["aud"], "start": r["start"],
            "url": r["url"], "img": "", "lang": "", "soldOut": r["soldOut"],
            "price": "", "provider": site["provider"], "venue": venue["id"],
        })
    if unmatched:
        print(f"[{site['provider']}] {unmatched} showtimes with an unrecognised location")
    for k in per_venue:
        per_venue[k].sort(key=lambda s: s["start"])
        for s in per_venue[k]:
            s["eventId"] = re.sub(r"[^\w]+", "-", s["title"].lower()).strip("-")
    # After the schedule is complete, and never able to take it down: a failure here
    # publishes the showtimes without prices, which is what the site did before.
    prices.run([s for v in per_venue.values() for s in v], provider=site["provider"],
               prefix=site.get("tickets", ""), parse=ordinary_price, fields=page_fields,
               referer=base + "/",
               path=prices_path, now=now, sleep=price_sleep,
               fetch_fn=lambda url, headers: fetch(url, headers=headers, tries=2, timeout=20))
    return {k: v for k, v in per_venue.items() if v}
