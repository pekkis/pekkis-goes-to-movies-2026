"""Kino Akustiikka, Ylivieska, on the town's Localhub event calendar. Stdlib only.

One request, to the calendar's own search, with no authentication and no cookie:

    /api/collection/{collection}/content/general-search?lang=fi&country=FI
        &q={q}&mode=event&sort=score

This is the request the visitor-facing calendar makes for the same search. The cinema has
no programme page of its own: `ylivieska.fi` links its ticket shop and this calendar, and
the calendar is where the dated screenings are.

Named after the platform because the payload shape is the platform's rather than this
town's, and a second municipality on it would be a `SITES` entry. That is the whole of the
claim: one tenant has been read, and nothing here is evidence about any other.

What shapes the parser, measured on the live search 2026-09-21, 13 pages of which 10 carry
dates:

- **A page is a film, and `event.dates` is its screenings.** A page with no date is the
  parent the calendar files a run under; all three read that day carried `isSoldOut` at
  event level and no date at all, so they are skipped on the empty `dates` rather than on
  the flag.
- **Two independent things have to agree before a page publishes**: `Movies / Cinema` in
  `globalContentCategories`, and the search term in `hashtags`. The calendar is the whole
  town's, so the venue matching is not enough on its own: a concert in the same hall would
  match the hall and not the category.
- **`start` and `end` are UTC instants with a `Z`.** `event.timezone` is read and required
  to be Europe/Helsinki rather than assumed, and a page declaring another one is counted
  and left out.
- **`end - start` is a booking slot, not a runtime.** Nine of the ten rows measured exactly
  120 minutes and one 101, so the field settles no film's length and `len` stays empty.
  Nothing else fills it: the TMDB pass publishes no runtime (checked 2026-09-24).
- **A price publishes only when the band settles one amount.** `price` is
  `{min, max, currency}` and every row read was `12/12/EUR`. A band with two ends publishes
  "alkaen {min}", and a currency other than EUR settles nothing.
- **Sold out and cancelled are per date, with the event-level flag as the fallback.** A
  cancelled screening is not published at all: the show contract carries `soldOut` and no
  cancelled state, so publishing one as an ordinary row would be worse than omitting it.
  The count goes in the log.
- **The ticket link is per date first, then per event.** All ten rows read fell back to the
  event's, `verkkokauppa.ylivieska.fi/tuote/{slug}`, which is the shop the calendar itself
  sends a reader to; both it and the calendar's own page were fetched and answered 200 on
  2026-09-21. A page with neither link falls back to the calendar's detail page.
- **`imageDesktop` is a content hash and not a URL.** No public pattern that resolves one
  was found, so `img` stays empty and the TMDB pass supplies the poster.
- **The synopsis declares its language.** `common.syn_language` places `descriptionShort`,
  or `descriptionLong` when the short one is missing, and withholds it when nothing is
  settled.

**Zero rows fails the site.** The search answering with an empty `pages` is as consistent
with the calendar having reindexed as with the cinema having nothing on, and this reader
has no second signal to tell those apart, so there is no positive evidence of an empty
programme here and `common.EmptyProgramme` is not raised.

**`book="buy"`.** Every row links to the town's ticket shop, which sells the seat.
"""
import datetime
import json
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, fetch, get_text, syn_language
from etiketti import lang_codes

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kinoakustiikka", "label": "Kino Akustiikka",
     "base": "https://tapahtumat.ylivieska.fi",
     "collection": "65b0e6fdfd13b97001a1b35d",
     "q": "kinoakustiikka",
     "category": "Movies / Cinema",
     "timezone": "Europe/Helsinki",
     "venues": [{"id": "kinoakustiikka-ylivieska", "name": "Kino Akustiikka",
                 "short": "Kino Akustiikka", "city": "Ylivieska",
                 "loc": "Ylivieskan kulttuurikeskus Akustiikka"}]},
]


def search_url(site):
    return (f"{site['base']}/api/collection/{site['collection']}/content/general-search"
            f"?lang=fi&country=FI&q={site['q']}&mode=event&sort=score")


def detail_url(site, page_id):
    return f"{site['base']}/fi-FI/page/{page_id}"


def money(value):
    """12 -> "12", 12.5 -> "12,50". The comma is the Finnish separator the rows use."""
    if float(value) == int(value):
        return str(int(value))
    return f"{float(value):.2f}".replace(".", ",")


def price_of(price):
    """`{min, max, currency}` -> a price string, or "" when it settles no amount."""
    if not isinstance(price, dict) or (price.get("currency") or "").upper() != "EUR":
        return ""
    low, high = price.get("min"), price.get("max")
    if not isinstance(low, (int, float)) or low <= 0:
        return ""
    if isinstance(high, (int, float)) and high > low:
        return f"alkaen {money(low)}€"
    return f"{money(low)}€"


def instant(value):
    """An ISO string -> an aware Helsinki datetime, or None. The API sends UTC with a
    `Z`; a value with no offset is read as Helsinki wall time, the zone the site
    declares, never the host's, which `astimezone` would use."""
    try:
        t = datetime.datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=FI)).astimezone(FI)


def is_film(site, page):
    """The two checks a page passes before any of it is read. -> bool."""
    return (site["category"] in (page.get("globalContentCategories") or [])
            and site["q"] in (page.get("hashtags") or []))


# The language as a calendar page states it, read 2026-10-04: "(suomeksi puhuttu)" in the
# title; "<strong>Tekstitys: </strong>suomenkielinen ja ruotsinkielinen" in the long
# description; and for a film shown both ways a dated list under "Esitykset:",
# "<li>20.10. englanniksi puhuttu</li>", which names the screening's own audio. Nothing
# looser: "Tekstitys: Kuvaileva tekstitys" names no language and publishes none.
TITLE_SPOKEN_RE = re.compile(r"\(([a-zåäö]+ksi) puhuttu\)", re.I)
DATED_SPOKEN_RE = re.compile(r"<li>\s*(\d{1,2})\.(\d{1,2})\.\s+([a-zåäö]+ksi) puhuttu\s*</li>", re.I)
SUBS_ITEM_RE = re.compile(r"<li>\s*<strong>\s*Tekstitys\s*:?\s*</strong>\s*:?\s*([^<]+?)\s*</li>",
                          re.I)


def _one(word, ending):
    """"englanniksi" with "ksi" -> "EN"; "" unless the word names exactly one language."""
    word = word.strip().lower()
    codes = lang_codes(word) if word.endswith(ending) else []
    return codes[0] if len(codes) == 1 else ""


def language(page, start):
    """-> "EN-A, FI-S" for one screening of a page, "" for what it does not state."""
    audio = ""
    for day, month, word in DATED_SPOKEN_RE.findall(page.get("descriptionLong") or ""):
        if (int(day), int(month)) == (start.day, start.month):
            audio = _one(word, "ksi")
    if not audio:
        m = TITLE_SPOKEN_RE.search(page.get("name") or "")
        audio = _one(m.group(1), "ksi") if m else ""
    subs = []
    m = SUBS_ITEM_RE.search(page.get("descriptionLong") or "")
    if m:
        subs = [_one(w, "kielinen") for w in re.split(r",|\bja\b", m.group(1)) if w.strip()]
        subs = subs if all(subs) else []
    parts = ([f"{audio}-A"] if audio else []) + [f"{c}-S" for c in dict.fromkeys(subs)]
    return ", ".join(parts)


def synopsis(page):
    """-> {lang: text} for the page's own blurb, or None when nothing is settled."""
    for key in ("descriptionShort", "descriptionLong"):
        body = (page.get(key) or "").strip()
        if body:
            lang = syn_language(body)
            return {lang: body} if lang else None
    return None


def rows(site, payload, today=None):
    """-> (shows, report). One row per date of every page that is a film here."""
    venue = site["venues"][0]
    out = []
    report = {"pages": 0, "films": 0, "undated": 0, "cancelled": 0,
              "elsewhere": 0, "other_tz": 0, "unreadable": 0, "no_price": 0}
    for page in payload.get("pages") or []:
        report["pages"] += 1
        if not is_film(site, page):
            continue
        report["films"] += 1
        event = page.get("event") or {}
        dates = event.get("dates") or []
        if not dates:
            report["undated"] += 1
            continue
        if (event.get("timezone") or "") != site["timezone"]:
            report["other_tz"] += 1
            continue
        where = [(loc.get("address") or "").strip() for loc in (page.get("locations") or [])]
        if where and venue["loc"] not in where:
            report["elsewhere"] += 1
            continue
        price = price_of(page.get("price"))
        if not price:
            report["no_price"] += 1
        syn = synopsis(page)
        for date in dates:
            if date.get("isCancelled") or event.get("isCancelled"):
                report["cancelled"] += 1
                continue
            start = instant(date.get("start"))
            if start is None:
                report["unreadable"] += 1
                continue
            sold = date.get("isSoldOut")
            if sold is None:
                sold = event.get("isSoldOut")
            url = (date.get("urlPurchaseTicket") or event.get("urlPurchaseTicket")
                   or detail_url(site, page.get("_id")))
            show = {
                "eventId": str(page.get("_id") or ""),
                "title": (page.get("name") or "").strip(),
                "original": "",
                "len": "",
                "rating": "",
                "genres": "",
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": url,
                "img": "",
                "lang": language(page, start),
                "soldOut": bool(sold),
                "price": price,
                "provider": site["provider"],
                "venue": venue["id"],
            }
            if syn:
                show["_syn"] = syn
            out.append(show)
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def get_json(url):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return json.loads(get_text(url, fetcher=fetch))


def fetch_site(site, today=None):
    """Runner contract: one request for the calendar's search."""
    pid, venue = site["provider"], site["venues"][0]
    url = search_url(site)
    shows, report = rows(site, get_json(url), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no dated screening among {report['pages']} page(s). An empty search "
            f"is as consistent with a reindex as with an empty programme and this reader "
            f"cannot tell those apart, so the previous files stand")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['films']} of {report['pages']} page(s) are films")
    for key, note in (("undated", "film page(s) with no date, the calendar's own parents"),
                      ("cancelled", "screening(s) the calendar marks cancelled, left out"),
                      ("elsewhere", "film page(s) at another address, left out"),
                      ("other_tz", "film page(s) declaring another timezone, left out"),
                      ("unreadable", "date(s) whose start does not parse, left out"),
                      ("no_price", "film page(s) whose price band settles no amount")):
        if report[key]:
            print(f"[{pid}] {report[key]} {note}")
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
        print(f"   {s['start'][:16]}  {s['title'][:36]:38} {s['price']:10} "
              f"sold={str(s['soldOut']):5} {s['url'][-38:]}")
    sys.exit(0)
