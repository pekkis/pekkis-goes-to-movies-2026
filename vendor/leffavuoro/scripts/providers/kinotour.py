"""Kinotour, a touring operator in Varsinais-Suomi. Stdlib only.

One request. `kinotour.fi/varaa-liput-elokuvatapahtumiin/` renders the whole programme as
one card per screening, read 2026-09-29 (the Events Manager table it replaced was read
until that day):

    <article class="kt-event" data-city="Naantali" data-type="indoor">
      <h3>Hetki ennen valoa</h3>
      <p class="kt-event-date"><time datetime="2026-10-04T13:30:00+03:00">4.10.2026 · klo 13.30</time></p>
      <p class="kt-location">Naantali · Kristoffer-sali</p>
      <p class="kt-meta">87 min · K7</p>
      <div class="kt-event-action"><strong>11,00 € <small>/ hlö</small></strong>
        <button class="kt-book" data-event="{...}">Varaa liput</button></div>
    </article>

What shapes the parser:

- **A town this repository does not declare is counted and named, never dropped in
  silence and never a failure.** A touring operator visits a new town as a matter of
  course, so failing the site on one would turn the routine case into breakage. The run
  log carries a line per run until someone adds the town to `SITES`, which is the same
  shape CLAUDE.md gives `reads`.
- **The venue is keyed on the town, `data-city`**, not the hall: the hall changes while
  the tour keeps coming back to the town.
- **The start is the `<time>` element's own instant**, and the printed "4.10.2026 · klo
  13.30" beside it has to agree; a card where they differ fails the site rather than
  publishing a screening at a guessed time.
- **The rating and the price come off the card.** `K7` from "87 min · K7", and one
  amount per card, the screening's own. A card with no amount, or more than one,
  publishes none; the pensioners' and students' euro off at the till is a condition, not
  the ticket's price. The runtime is not read: on 2026-09-29 all three cards printed
  87 min, Rakkautta & Virtahepoja included, which runs 102 everywhere else.
- **The booking is a button on this page**, with no link of its own, so every screening
  links to the listing it was read from. Nothing behind the button is requested.
- **No poster, runtime, genre or language is read.** The shared enrichment fills what
  it can.

**Zero cards fails the site**, and so do cards that all land in undeclared towns: a town
key that stopped reading produces the same page, so it is no evidence the declared towns
are empty. The one exception is the page's own empty state, read 2026-10-10 with nothing
on: the results line reads "Kaikki paikkakunnat \u00b7 0 n\u00e4yt\u00f6st\u00e4", the event list is
empty, and the notice "T\u00e4ll\u00e4 valinnalla ei ole tulevia n\u00e4yt\u00f6ksi\u00e4. ..." is shown.
All three have to hold for `common.EmptyProgramme`, and none of them is what finds a card.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import EmptyProgramme, check_shows, fetch, get_text
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

# The towns read off the programme on 2026-09-18. The operator's own locations list is
# longer and reaches outside this region, so the set grows by observation: a town that
# turns up is named in the run log until it is added here, and nothing is guessed.
SITES = [
    {"provider": "kinotour", "label": "Kinotour",
     "base": "https://www.kinotour.fi",
     "listing": "/varaa-liput-elokuvatapahtumiin/",
     "venues": [
         {"id": "kinotour-kyro", "name": "Kurkisali", "short": "Kurkisali",
          "city": "Kyrö", "town": "Kyrö"},
         {"id": "kinotour-naantali", "name": "Kristoffersali", "short": "Kristoffersali",
          "city": "Naantali", "town": "Naantali"},
         {"id": "kinotour-lieto", "name": "Valtuustosali", "short": "Valtuustosali",
          "city": "Lieto", "town": "Lieto"},
     ]},
]

CARD_RE = re.compile(r'<article\b([^>]*\bclass="[^"]*\bkt-event\b[^"]*"[^>]*)>(.*?)</article>',
                     re.S | re.I)
CITY_RE = re.compile(r'\bdata-city="([^"]*)"', re.I)
TITLE_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S | re.I)
WHEN_RE = re.compile(r'<time[^>]*\bdatetime="([^"]+)"[^>]*>(.*?)</time>', re.S | re.I)
SHOWN_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\D+(\d{1,2})[.:](\d{2})")
PLACE_RE = re.compile(r'class="[^"]*\bkt-location\b[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
META_RE = re.compile(r'class="[^"]*\bkt-meta\b[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
ACTION_RE = re.compile(r'class="[^"]*\bkt-event-action\b[^"]*"[^>]*>\s*<strong[^>]*>(.*?)</strong>',
                       re.S | re.I)
AMOUNT_RE = re.compile(r"\u20ac\s*(\d{1,3})(?:[.,](\d{1,2}))?|(\d{1,3})(?:[.,](\d{1,2}))?\s*\u20ac")
RATING_RE = re.compile(r"^(K-?\d{1,2}|S)$", re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# The page's own empty state, read 2026-10-10. The results line is for the default
# selection, every town, so its zero is the whole programme.
EMPTY_RESULTS = "Kaikki paikkakunnat \u00b7 0 n\u00e4yt\u00f6st\u00e4"
EMPTY_NOTICE = ("T\u00e4ll\u00e4 valinnalla ei ole tulevia n\u00e4yt\u00f6ksi\u00e4. "
                "Katso muut paikkakunnat tai palaa pian uudelleen.")
RESULTS_RE = re.compile(r'<p\b[^>]*\bclass="[^"]*\bkt-results\b[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
LIST_RE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bkt-event-list\b[^"]*"[^>]*>(.*?)</div>',
                     re.S | re.I)
NOTICE_RE = re.compile(r'<p\b([^>]*\bclass="[^"]*\bkt-empty\b[^"]*"[^>]*)>(.*?)</p>', re.S | re.I)

# A town with no card is known empty, not unread, once the page filed a card under some
# other declared town and none under a town this repo does not declare: this page is the
# operator's whole published programme in one request, so a town it does not mention has
# nothing on. An undeclared card may be a declared town's screening under a place that
# reads differently, so while one is on the page `fetch_site` reports only the towns with
# cards, as eTiketti, Nexxo and Alatalo do, and an empty town keeps its previous file.
# `run.py` then publishes a fresh empty file for that venue instead of ageing its last
# visit, which is the case its own comment names: "a touring cinema's town is empty
# between visits". A page with no card under any declared town never reaches that loop,
# because `fetch_site` raises first: cards that all land in undeclared towns are also what
# a town key that stopped reading produces.
EMPTY_VENUES_CONFIRMED = True


class RowError(RuntimeError):
    """A card this parser could not read. Not an undeclared town, which is ordinary.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = TAGS_RE.sub(" ", s)
    return re.sub(r"\s+", " ", html_mod.unescape(s).replace("\xa0", " ")).strip()


def rating_of(token):
    """`K7`, `K-12` or `S` -> "K-7", "K-12", "S"; anything else -> ""."""
    m = RATING_RE.match((token or "").strip())
    if not m:
        return ""
    tail = m.group(1).upper().replace("-", "")
    return "S" if tail == "S" else f"K-{int(tail[1:])}"


def price_of(blob):
    """The card's amount. -> "11\u20ac", or "" unless exactly one amount is stated.

    Trailing zeros come off so 11,00 publishes as 11\u20ac, the shape `biosavoy.py`
    already writes.
    """
    amounts = set()
    for m in AMOUNT_RE.finditer(_txt(blob)):
        whole, cents = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        amounts.add(f"{int(whole)}.{(cents or '0').ljust(2, '0')}")
    if len(amounts) != 1:
        return ""
    return f"{float(amounts.pop()):.2f}".rstrip("0").rstrip(".") + "\u20ac"


def rows(site, page):
    """-> ({venue_id: [show]}, report). `report["undeclared"]` counts the towns this
    repository does not list, by town."""
    by_town = {v["town"]: v for v in site["venues"]}
    per_venue = {v["id"]: [] for v in site["venues"]}
    report = {"undeclared": {}}
    listing = site["base"].rstrip("/") + site["listing"]
    for n, (attrs, card) in enumerate(CARD_RE.findall(page)):
        heading = TITLE_RE.search(card)
        title = _txt(heading.group(1)) if heading else ""
        if not title:
            raise RowError(f"{site['provider']}: card {n + 1} carries no title")
        when = WHEN_RE.search(card)
        try:
            start = datetime.datetime.fromisoformat(when.group(1)) if when else None
        except ValueError:
            start = None
        if start is None or start.tzinfo is None:
            raise RowError(f"{site['provider']}: card {n + 1} for {title!r} has no readable "
                           f"start")
        start = start.astimezone(FI)
        shown = SHOWN_RE.search(_txt(when.group(2)))
        if not shown or tuple(int(g) for g in shown.groups()) != (
                start.day, start.month, start.year, start.hour, start.minute):
            raise RowError(f"{site['provider']}: card {n + 1} for {title!r} prints "
                           f"{_txt(when.group(2))!r} beside {when.group(1)}")
        city = CITY_RE.search(attrs)
        place = PLACE_RE.search(card)
        town = (_txt(city.group(1)) if city else "") or (
            _txt(place.group(1)).split("\u00b7")[0].strip() if place else "")
        if not town:
            raise RowError(f"{site['provider']}: card {n + 1} for {title!r} names no place")
        venue = by_town.get(town)
        if venue is None:
            report["undeclared"][town] = report["undeclared"].get(town, 0) + 1
            continue
        meta = META_RE.search(card)
        facts = [f.strip() for f in _txt(meta.group(1) if meta else "").split("\u00b7")]
        rating = next((rating_of(f) for f in facts if rating_of(f)), "")
        action = ACTION_RE.search(card)
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
            "url": listing,
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": price_of(action.group(1)) if action else "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    for shows in per_venue.values():
        shows.sort(key=lambda s: s["start"])
    return per_venue, report


def says_empty(page):
    """Whether the page states in its own markup that nothing is on. -> bool

    The results line counts zero for every town, the event list holds no element, and the
    empty notice is there with its exact text and not hidden. A card markup change leaves a
    count above zero or a list with something in it, so it cannot pass for this.
    """
    results = [_txt(t) for t in RESULTS_RE.findall(page or "")]
    lists = LIST_RE.findall(page or "")
    shown = [_txt(t) for a, t in NOTICE_RE.findall(page or "")
             if not re.search(r"\bhidden\b", a, re.I)]
    return (results == [EMPTY_RESULTS] and len(lists) == 1
            and not re.search(r"<[a-z]", lists[0], re.I) and EMPTY_NOTICE in shown)


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site):
    pid = site["provider"]
    url = site["base"].rstrip("/") + site["listing"]
    page = get(url)
    per_venue, report = rows(site, page)
    published = sum(len(v) for v in per_venue.values())
    if not published and report["undeclared"]:
        named = ", ".join(f"{t} ({n})" for t, n in sorted(report["undeclared"].items()))
        raise RuntimeError(
            f"{url}: no card under a declared town, every one in a town this repo does not "
            f"list: {named}. A town key that stopped reading looks the same, so no declared "
            f"town is published empty and the previous files stand")
    if not published:
        if says_empty(page):
            raise EmptyProgramme(f"{url}: the page counts 0 screenings for every town and "
                                 f"shows its own notice that nothing is coming up")
        raise RuntimeError(
            f"{url}: no screening card on the page, and the page does not show its own "
            f"empty state (a zero count, an empty list and the notice), so the previous "
            f"files stand")
    check_shows(per_venue, pid, {v["id"] for v in site["venues"]})
    priced = sum(1 for v in per_venue.values() for s in v if s["price"])
    print(f"[{pid}] {published} screening(s) in {len(site['venues'])} declared town(s), "
          f"{priced} priced")
    if report["undeclared"]:
        named = ", ".join(f"{t} ({n})" for t, n in sorted(report["undeclared"].items()))
        print(f"[{pid}] {sum(report['undeclared'].values())} screening(s) in "
              f"{len(report['undeclared'])} town(s) this repo does not list, left out: "
              f"{named}. Add the town to SITES to publish them")
    for v in site["venues"]:
        shows = per_venue[v["id"]]
        days = sorted({s["start"][:10] for s in shows})
        print(f"[{pid}] {v['name']}, {v['city']}: {len(shows)} showtimes, {len(days)} dates")
    if report["undeclared"]:
        # See EMPTY_VENUES_CONFIRMED: an undeclared row vouches for no empty town.
        empty = [v["name"] for v in site["venues"] if not per_venue[v["id"]]]
        if empty:
            print(f"[{pid}] a row sits in an undeclared town, so no declared town is "
                  f"confirmed empty on this read: {', '.join(empty)} keep their files")
        return {k: v for k, v in per_venue.items() if v}
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:4]:
            print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} "
                  f"{s['url'][-34:]}")
    sys.exit(0)
