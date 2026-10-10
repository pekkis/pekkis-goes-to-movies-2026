"""Ritz Vaasa and Tähti Kino (Muhos), read through The Events Calendar. Stdlib only.

Both run the WordPress plugin The Events Calendar, whose REST route is public and needs no
key. Probed 2026-09-18; a sweep of the 148 hosts in the Filmikamari directory found four
answering it and these two usable. The evidence, including why Iobio is not here, is in
docs/research/ticketing-platforms.md.

    GET {base}/?rest_route=/tribe/events/v1/events
        &per_page=50&start_date=YYYY-MM-DD&categories={id}

`?rest_route=` rather than `/wp-json/`, because Ritz serves its REST under a language
prefix and this form is independent of the permalink shape.

What shapes the parser:

- **A calendar is not a programme.** Ritz published 6 film events among 56 and Muhos 3
  among 35; the rest are concerts, exhibitions and council meetings. The category is the
  filter and it is declared per site by its **numeric id**, which is stable, rather than by
  its display name. The server does the filtering and this checks the answer: an event
  coming back without the configured category id fails the site, because a filter the
  server ignored would otherwise publish a council meeting as a screening.
- **Pagination is followed to the end.** `total_pages` is what the run reads; a listing cut
  at the first page would drop the later half of the window without a word.
- **Both timestamps are read.** `start_date` is local, `timezone` names the zone and
  `utc_start_date` is the same instant in UTC. They are cross-checked through
  Europe/Helsinki and a disagreement fails the site.
- **`cost_details.values` decides the price**, not the `cost` string. One value is an
  amount for this screening and publishes; two are a band ("10€ – 12€") and publish
  nothing. The rule is in `common.Show`.
- **A generic calendar image is not a poster.** Muhos illustrates every film with the same
  768x470 `Tapahtumakalenteri.png`. Only a portrait image of a reasonable size is published,
  which is what a film poster is, and the TMDB pass fills the rest.
- **An all-day event carries no clock**, so it is left out and counted.
- The API publishes no runtime, age rating or genre as fields. The language is read from
  the description's labelled `Language:` and `Subtitles:` lines where a site writes them,
  and at Ritz the runtime and the synopsis from its facts paragraph, see `facts`.

Two limits, stated rather than guarded:

- **`cost` is published verbatim when there is one value.** A site writing "alk. 10€"
  beside a single `cost_details.values` entry would have a starting price published as a
  settled one. Neither site writes that today, and the price rule in `common.Show` is what
  a third would be measured against.
- **The repeated hour fails rather than guesses.** `datetime.replace(tzinfo=...)` takes
  `fold=0`, so a screening in the hour that repeats when summer time ends is read as the
  first occurrence; if the site meant the second, the UTC stamp disagrees and the site
  fails. A wrong hour published quietly is the worse outcome.

**An empty programme is confirmed against the category, not against zero rows.** Zero
events from a filtered query is what a cinema with nothing on looks like *and* what a
renamed or deleted category looks like. So when the answer is empty the category endpoint
is read once, and only its answering with the configured slug is evidence of a quiet week.
Anything else -- a missing, renamed, unreadable or malformed category, or an endpoint that
will not answer -- fails the site, which keeps the previous files and names it in the log.
Empty means `"events": []`: a page answering without an `events` list fails the site too,
because the category check says nothing about the events route's own schema.

**Confirmed empty publishes a fresh empty file, it does not raise.** Until 2026-09-20 the
quiet-week branch raised `common.EmptyProgramme`, which at the time kept the venue's previous area
file. That file then aged without its timestamp moving, so Tähti Kino read "Päivitys
viivästynyt" on the status page for a cinema that simply had nothing on, and at 17 hours
looked exactly like a venue nobody could reach. The evidence is positive, so it is
published as such: the venue comes back explicitly with an empty list,
`EMPTY_VENUES_CONFIRMED` lets run.py write a fresh empty file and record the venue as
`pending`, the provider stays healthy, and the client says "Ei ohjelmistoa juuri nyt".
Whichever site is quiet, the other is unaffected: each is its own site with its own venue.
"""
import datetime
import html as html_mod
import json
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import check_shows, fetch, syn_language
from etiketti import strict_codes
from synmerge import is_note

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

SITES = [
    {"provider": "ritzvaasa", "label": "Ritz Vaasa", "base": "https://ritz.fi",
     "category": {"id": 19, "slug": "kino"}, "facts": True,
     "venues": [{"id": "ritz-vaasa", "name": "Ritz Vaasa", "short": "Ritz Vaasa",
                 "city": "Vaasa"}]},
    {"provider": "tahtikino", "label": "Tähti Kino", "base": "https://muhos.fi",
     "category": {"id": 106, "slug": "elokuvat"},
     "venues": [{"id": "tahtikino-muhos", "name": "Tähti Kino", "short": "Tähti Kino",
                 "city": "Muhos"}]},
]

PER_PAGE = 50

# A venue this module reports with an empty list is *known* empty: the category endpoint
# answered with the configured slug, which is the check below, and a category that is
# missing, renamed or unreadable fails the site instead of reaching that branch.
EMPTY_VENUES_CONFIRMED = True
# A poster is portrait. Muhos' calendar illustration is 768x470 and Ritz's concert art
# 1200x800, while its film artwork is 1500x2138 and 1080x1592.
POSTER_MIN_RATIO = 1.2
POSTER_MIN_WIDTH = 300

TAGS_RE = re.compile(r"<[^>]+>")
# The description's own labelled lines, as Ritz writes them (read 2026-10-04):
# "Language: French<br />Subtitles: Finnish, Swedish", English names. A line, not a word in
# the prose: the label opens a paragraph or follows a break.
LANG_LINE_RE = re.compile(r"(?:<br\s*/?>|<p[^>]*>)\s*(Language|Subtitles)\s*:\s*([^<]+)", re.I)


# Ritz's description, read 2026-10-04: the synopsis paragraphs, a spacer, then one facts
# paragraph of lines, "Tickets: 12/10€, sold at the door. ...", "Language:", "Subtitles:",
# sometimes "Genre:", and the runtime "87 min". Before the synopsis an event note opens
# with a bold label ("Knitting Cinema:", "Note!"), a promotion names Ritz, and a critic's
# quote ends in a dashed attribution line. Only what is left before the facts is the film's.
PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
BR_RE = re.compile(r"<br\s*/?>", re.I)
FACTS_RE = re.compile(r"^Tickets\s*:", re.I)
RUNTIME_LINE_RE = re.compile(r"^(\d{2,3})\s*min$")
LABEL_OPEN_RE = re.compile(r"^\s*<(?:b|strong)\b", re.I)
ATTRIBUTION_RE = re.compile(r"^[\u2013\u2014-]\s")
SOURCE_LINE_RE = re.compile(r"^\(text from [^)]*\)$", re.I)
VENUE_RE = re.compile(r"\britz\b", re.I)


def facts(desc):
    """A Ritz description -> (synopsis, minutes). ("", "") without a facts paragraph that
    carries a runtime: that is an event, not a film."""
    paras = PARA_RE.findall(desc or "")
    at = next((i for i, p in enumerate(paras) if FACTS_RE.match(_txt(p))), None)
    if at is None:
        return "", ""
    minutes = next((m.group(1) for m in (RUNTIME_LINE_RE.match(_txt(x))
                                         for x in BR_RE.split(paras[at])) if m), "")
    if not minutes:
        return "", ""
    before = paras[:at]
    keep = []
    for i, p in enumerate(before):
        text = " ".join(t for t in (_txt(x) for x in BR_RE.split(p))
                        if t and not SOURCE_LINE_RE.match(t))
        quoted = i + 1 < len(before) and ATTRIBUTION_RE.match(_txt(before[i + 1]))
        if (not text or LABEL_OPEN_RE.match(p) or ATTRIBUTION_RE.match(text) or quoted
                or is_note(text) or VENUE_RE.search(text)):
            continue
        keep.append(text)
    return " ".join(keep), minutes


class EventError(RuntimeError):
    """An event the category filter returned and this parser could not read.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _start(site, e):
    """The event's start as Europe/Helsinki. -> ISO 8601 with offset.

    The local stamp and the UTC one are both the plugin's own, so they agree until
    something upstream changes, and that is the change that would move every screening by
    hours without any other symptom.

    The `timezone` field is read by nothing here and needs no guard of its own: a site in
    another zone either has the same offset as Helsinki, in which case the instant this
    publishes is right anyway, or a different one, in which case the two stamps disagree
    and this raises. A guard on the field name was written first and turned out to refuse
    only what the comparison already refuses.
    """
    local, utc = e.get("start_date"), e.get("utc_start_date")
    if not local or not utc:
        raise EventError(f"{site['provider']}: event {e.get('id')} has no start "
                         f"({local!r}, {utc!r})")
    try:
        naive = datetime.datetime.fromisoformat(local)
        as_utc = datetime.datetime.fromisoformat(utc).replace(
            tzinfo=datetime.timezone.utc)
    except ValueError as exc:
        raise EventError(f"{site['provider']}: event {e.get('id')} has an unreadable "
                         f"start ({local!r}, {utc!r})") from exc
    placed = naive.replace(tzinfo=FI)
    if placed != as_utc:
        raise EventError(
            f"{site['provider']}: event {e.get('id')} says {local} local and {utc} UTC, "
            f"which is {as_utc.astimezone(FI):%Y-%m-%d %H:%M} in Helsinki")
    return placed.isoformat()


def _price(e):
    """-> the screening's price, or "" for a band or nothing.

    `cost_details.values` is the structural answer: one value is an amount that applies to
    this screening, two are the ends of a range and settle none.
    """
    values = ((e.get("cost_details") or {}).get("values")) or []
    if len(values) != 1:
        return ""
    return _txt(e.get("cost")) or ""


def _lang(e):
    """-> "FR-A, FI-S, SV-S" from the description's Language and Subtitles lines, "" without
    them. A line naming a language no table knows publishes nothing for its role."""
    got = {}
    for label, value in LANG_LINE_RE.findall(e.get("description") or ""):
        got.setdefault(label.lower(), _txt(value))
    parts = [f"{c}-A" for c in strict_codes(got.get("language"))]
    parts += [f"{c}-S" for c in strict_codes(got.get("subtitles"))]
    return ", ".join(parts)


def _poster(e):
    """-> the event image when it is a portrait poster, else "".

    A landscape image here is the site's calendar illustration or a concert photo, and
    publishing one would put a wide crop in a place the client draws a poster.
    """
    img = e.get("image") or {}
    url, w, h = img.get("url"), img.get("width"), img.get("height")
    if not url or not isinstance(w, int) or not isinstance(h, int) or not w:
        return ""
    if w < POSTER_MIN_WIDTH or h < w * POSTER_MIN_RATIO:
        return ""
    return url if url.startswith("http") else f"https:{url}" if url.startswith("//") else ""


def parse(site, events):
    """-> ({venue_id: [show]}, report). `events` is every event the pages returned."""
    venue = site["venues"][0]
    cat = site["category"]
    shows, report = [], {"all_day": [], "unplaced_syn": set(), "band_price": 0}
    for e in events:
        ids = {c.get("id") for c in e.get("categories", [])}
        if cat["id"] not in ids:
            raise EventError(
                f"{site['provider']}: event {e.get('id')} came back without category "
                f"{cat['id']} ({cat['slug']}), so the server did not filter on it and a "
                f"row that is not a screening would publish")
        if e.get("all_day"):
            report["all_day"].append(_txt(e.get("title")))
            continue
        price = _price(e)
        if not price and ((e.get("cost_details") or {}).get("values")):
            report["band_price"] += 1
        row = {
            "eventId": str(e.get("id") or ""),
            "title": _txt(e.get("title")),
            "original": "",
            "len": "",
            "rating": "",
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": _start(site, e),
            "url": e.get("url") or "",
            "img": _poster(e),
            "lang": _lang(e),
            "soldOut": False,
            "price": price,
            "provider": site["provider"],
            "venue": venue["id"],
        }
        if not row["title"] or not row["url"]:
            raise EventError(f"{site['provider']}: event {e.get('id')} has no title or no "
                             f"url ({row['title']!r}, {row['url']!r})")
        if site.get("facts"):
            syn, row["len"] = facts(e.get("description"))
        else:
            syn = _txt(e.get("description"))
        if syn:
            lang = syn_language(syn)
            if lang:
                row["_syn"] = {lang: syn}
            else:
                report["unplaced_syn"].add(row["title"])
        shows.append(row)
    shows.sort(key=lambda s: s["start"])
    return {venue["id"]: shows}, report


def get(url, tries=3, timeout=30):
    return fetch(url, cache=True,
                 headers={"user-agent": UA, "accept": "application/json"},
                 tries=tries, timeout=timeout).decode("utf-8", "replace")


def _page(site, start, page):
    url = (f"{site['base'].rstrip('/')}/?rest_route=/tribe/events/v1/events"
           f"&per_page={PER_PAGE}&page={page}&start_date={start}"
           f"&categories={site['category']['id']}")
    try:
        doc = json.loads(get(url))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{url}: the REST route answered something that is not JSON "
                           f"({e})") from e
    # The route says nothing is on with `"events": []`, read live at Muhos 2026-09-24. An
    # answer without that list is a changed schema: read as zero events, the category check
    # would vouch the venue empty, and on a later page the schedule would publish short.
    # nexxo.py requires its `shows` key for the same reason.
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        keys = sorted(doc)[:6] if isinstance(doc, dict) else type(doc).__name__
        raise RuntimeError(f"{url}: the answer carries no 'events' list (keys: {keys}), "
                           f"so this is a schema change rather than an empty programme")
    return doc


def category_exists(site):
    """-> True when the site still has the configured category under its configured slug.

    The one thing that makes an empty answer readable: a category that was renamed or
    deleted returns the same empty list as a cinema with nothing on.
    """
    url = (f"{site['base'].rstrip('/')}/?rest_route=/tribe/events/v1/categories/"
           f"{site['category']['id']}")
    try:
        doc = json.loads(get(url, tries=2))
    except Exception:
        return False
    # `isinstance` and not a bare `.get`: valid JSON that is not an object parses fine and
    # then raises AttributeError out here, past the except, so the site failed with
    # "'str' object has no attribute 'get'" instead of naming the category. It failed
    # safely either way, which is why this was only visible once a test asked for the
    # reason rather than the exit code.
    return isinstance(doc, dict) and doc.get("slug") == site["category"]["slug"]


def fetch_site(site, sleep=1.2, today=None):
    """Runner contract: one request per page of the site's own film category."""
    pid = site["provider"]
    today = today or datetime.datetime.now(FI).date()
    start = today.isoformat()
    first = _page(site, start, 1)
    events = list(first.get("events") or [])
    pages = int(first.get("total_pages") or 1)
    for n in range(2, pages + 1):
        time.sleep(sleep)
        events += list(_page(site, start, n).get("events") or [])
    if not events:
        if category_exists(site):
            # A quiet week, evidenced by the category still answering under its own slug.
            # Reported rather than raised, so run.py publishes a fresh empty file and marks
            # the venue pending instead of letting the last programme age in place.
            print(f"[{pid}] {site['venues'][0]['name']}: no upcoming event in category "
                  f"{site['category']['slug']!r}, which still exists; publishing the venue "
                  f"empty")
            return {v["id"]: [] for v in site["venues"]}
        raise RuntimeError(
            f"{site['base']}: no event under category {site['category']['id']} and the "
            f"category itself did not answer with the slug {site['category']['slug']!r}, "
            f"so this is a renamed or deleted category rather than a quiet week")
    per_venue, report = parse(site, events)
    check_shows(per_venue, pid, {v["id"] for v in site["venues"]})
    shows = per_venue[site["venues"][0]["id"]]
    print(f"[{pid}] {first.get('total')} event(s) in category "
          f"{site['category']['slug']}, {pages} page(s) read")
    if report["all_day"]:
        print(f"[{pid}] {len(report['all_day'])} all-day event(s) left out, no clock: "
              f"{', '.join(sorted(set(report['all_day']))[:6])}")
    if report["band_price"]:
        print(f"[{pid}] {report['band_price']} screening(s) priced as a band, published "
              f"without a price")
    if report["unplaced_syn"]:
        print(f"[{pid}] {len(report['unplaced_syn'])} synopsis/synopses withheld, no "
              f"language settled: {', '.join(sorted(report['unplaced_syn'])[:6])}")
    posters = sum(1 for s in shows if s["img"])
    print(f"[{pid}] {posters} of {len(shows)} screening(s) carry a portrait poster")
    if not shows:
        raise RuntimeError(
            f"{site['base']}: {len(events)} event(s) in the film category and none "
            f"published, which is a shape change rather than a cinema with nothing on")
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {site['venues'][0]['name']}: {len(shows)} showtimes, {len(days)} dates")
    return per_venue


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "ritzvaasa"
    site = next(s for s in SITES if s["provider"] == which)
    for vid, shows in fetch_site(site).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:6]:
            print(f"   {s['start'][:16]}  {s['title'][:40]:42} {s['price']:8} "
                  f"img={'y' if s['img'] else '-'}  {s['url'][-34:]}")
