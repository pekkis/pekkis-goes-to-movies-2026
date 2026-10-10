"""Pyhäsalmen VPK, a volunteer fire brigade that has run a cinema since 1944. Stdlib only.

Two requests. The brigade's WordPress runs the My Calendar plugin, whose REST route is
public and returns occurrences keyed by date:

    GET {base}/wp-json/my-calendar/v1/events?from=YYYY-MM-DD&to=YYYY-MM-DD&category=1
    -> {"2026-09-25": [{"occur_id": "255", "occur_begin": "2026-09-25 18:00:00",
                        "ts_occur_begin": "1790348400", "event_title": "...",
                        "category_id": "1", "category_name": "Elokuvat", ...}]}

What shapes the parser:

- **The category is declared by id and checked on every occurrence.** The route accepts a
  name as well, and the name is display text; `category_id` 1 is `Elokuvat` here. An
  answer carrying anything else fails the site rather than publishing a brigade meeting,
  which is the rule `tribe.py` already states.
- **An empty answer cannot tell a quiet month from a renumbered category**, because the
  route answers `[]` to both, and to `category=999` as well. So an empty window is checked
  against the past year with the same id: events there prove the category is live and the
  window is a gap, which `EMPTY_VENUES_CONFIRMED` then publishes as a fresh empty file.
  The programme has an eight-week summer gap, 2026-05-29 to 07-25, so this is not a rare
  path. No events in either window fails.
- **The time is stated twice and both are read.** `occur_begin` is a local clock and
  `ts_occur_begin` a Unix instant; 2026-09-04 18:00:00 against 1788534000 is
  2026-09-04T18:00+03:00 in Europe/Helsinki. A row where the two disagree fails the site,
  the same cross-check `tribe.py` makes.
- **No runtime is published.** Every occurrence ends exactly one hour after it begins,
  which is the plugin's default rather than the film's length.
- **No rating is published**, because the calendar carries none and the cinema's own page
  says so: the age limit goes on the posters and on Facebook and "aina se ei ole vielä
  selvillä". The shared rating pass fills what another chain has classified.
- **No poster is published.** `event_image` is a full-size upload with no dimensions
  anywhere in the payload, and the four measured on 2026-09-19 run from 188x268 to
  1000x1250. A thumbnail published as a poster looks wrong and, worse, stops the
  enrichment pass filling a real one, since it only writes a poster where a show has none.
- **No synopsis either.** `event_desc` was empty on 56 of the 57 occurrences read and the
  one text was a note about a single screening, which `films-extra.json` would serve as
  that film's synopsis at every other cinema.
- **The price is the cinema's own page, read once a run.** It states `Elokuvalipun hinta:
  12 euroa` with no condition on the day, the format or the film, so it settles every
  screening, which is the test the Kuvakukko tariff was published under. A page that will
  not answer costs the amount and never the programme, because the schedule comes from a
  different endpoint; that is the one place this differs from `kuvakukko.py`, which reads
  both from one page and fails the site.
- **No ticket host exists and none is invented.** Tickets are sold at the door and
  reserved by telephone, so `book="door"` and a showtime opens the cinema's own page. The
  plugin does give each event a page under `/mc-events/`, but the permalinks appear only
  in the calendar page's JSON-LD and carry numeric suffixes (`marsupilami-3`), so they can
  be neither read from this endpoint nor built from a title.

The venue's city is **Pyhäjärvi**, the municipality, where the postal address reads
Pyhäsalmi. Same choice as Kouvola against Kuusankoski, and the label carries Pyhäsalmi so
the picker finds it either way.
"""
import datetime
import html as html_mod
import json
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, fetch, get_text, served
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")
UTC = datetime.timezone.utc

SITES = [
    {"provider": "pyhasalmenvpk", "label": "Pyhäsalmen VPK",
     "base": "https://www.pyhasalmenvpk.fi",
     "category": 1,                  # `Elokuvat`; the id, because the name is display text
     "info": "/pyhasalmen-vpkn-elokuvat",
     "venues": [{"id": "pyhasalmenvpk-pyhajarvi", "name": "Pyhäsalmen VPK",
                 "short": "Pyhäsalmen VPK", "city": "Pyhäjärvi"}]},
]

# How far ahead one run asks for. The programme reached 49 days out when this was written.
HORIZON_DAYS = 180
# How far back the empty-window check looks for evidence that the category is still live.
LOOKBACK_DAYS = 365

PRICE_RE = re.compile(r"Elokuvalipun\s+hinta\s*:?\s*([\d]+(?:[.,]\d{1,2})?)\s*euroa", re.I)

TAGS_RE = re.compile(r"<[^>]+>")

# Set on the evidence in the docstring: an empty forward window is published as empty only
# when the same category still carries events in the past year. Both windows empty never
# reaches this, because that is a changed calendar and it raises.
EMPTY_VENUES_CONFIRMED = True


class FeedError(RuntimeError):
    """The calendar answered and this parser could not trust what it said.

    Publishing half of it would put a schedule on the site with nothing in the log to say
    so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = TAGS_RE.sub(" ", s or "")
    return re.sub(r"\s+", " ", html_mod.unescape(s).replace("\xa0", " ")).strip()


def occurrences(payload):
    """The route's answer -> [event].

    `[]` is how it says 'nothing', in place of `{}`. A list with something in it is a
    shape this endpoint has not been seen to return, so it raises rather than being read
    as either an answer or an emptiness.
    """
    if isinstance(payload, list):
        if payload:
            raise FeedError(f"the calendar answered a list of {len(payload)} item(s), "
                            f"where an answer is keyed by date and an empty list means "
                            f"nothing. This shape has not been seen here")
        return []
    if not isinstance(payload, dict):
        raise FeedError(f"the calendar answered {type(payload).__name__}, which is "
                        f"neither a date-keyed answer nor an empty list")
    out = []
    for day in sorted(payload):
        out.extend(payload[day] or [])
    return out


def _start(site, event):
    """The occurrence's start, with the local clock and the Unix instant cross-checked."""
    local, ts = (event.get("occur_begin") or "").strip(), event.get("ts_occur_begin")
    try:
        start = datetime.datetime.strptime(local, "%Y-%m-%d %H:%M:%S").replace(tzinfo=FI)
    except ValueError as e:
        raise FeedError(f"{site['provider']}: occurrence {event.get('occur_id')!r} carries "
                        f"the unreadable start {local!r}") from e
    try:
        instant = datetime.datetime.fromtimestamp(int(ts), UTC)
    except (TypeError, ValueError) as e:
        raise FeedError(f"{site['provider']}: occurrence {event.get('occur_id')!r} carries "
                        f"no readable ts_occur_begin ({ts!r})") from e
    if instant != start:
        raise FeedError(
            f"{site['provider']}: occurrence {event.get('occur_id')!r} states "
            f"{local} Helsinki and the instant {instant.astimezone(FI).isoformat()}, "
            f"which are different times")
    return start


def parse(site, payload, price=""):
    """-> [show]. One row per occurrence the calendar returned, deduplicated on occur_id."""
    venue = site["venues"][0]
    want = str(site["category"])
    url = site["base"].rstrip("/") + site["info"]
    out, seen = [], set()
    for event in occurrences(payload):
        ids = {str(event.get("category_id") or "")}
        ids |= {str(c.get("category_id") or "") for c in (event.get("categories") or [])}
        if want not in ids:
            raise FeedError(
                f"{site['provider']}: the calendar returned an event in category "
                f"{sorted(ids)} for a request that asked for {want}, so the filter was "
                f"not applied and this is not a film listing")
        oid = str(event.get("occur_id") or "")
        if oid and oid in seen:
            continue
        seen.add(oid)
        title = _txt(event.get("event_title"))
        if not title:
            raise FeedError(f"{site['provider']}: occurrence {oid!r} carries no title")
        out.append({
            "eventId": norm(title),
            "title": title,
            "original": "",
            "len": "",
            "rating": "",
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": _start(site, event).isoformat(),
            "url": url,
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": price,
            "provider": site["provider"],
            "venue": venue["id"],
        })
    out.sort(key=lambda s: s["start"])
    return out


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def events_url(site, start, end):
    return (f"{site['base'].rstrip('/')}/wp-json/my-calendar/v1/events"
            f"?from={start.isoformat()}&to={end.isoformat()}&category={site['category']}")


def window(site, start, end, fetch_json=None):
    """One call to the route. -> the decoded payload."""
    url = events_url(site, start, end)
    body = (fetch_json or get)(url)
    try:
        return json.loads(body)
    except ValueError as e:
        raise FeedError(f"{site['provider']}: {url} did not answer JSON "
                        f"({served(body)})") from e


def tariff(site, fetch_page=None):
    """The cinema's own page -> its ticket price, or "" when it states no single amount."""
    page = (fetch_page or get)(site["base"].rstrip("/") + site["info"])
    found = PRICE_RE.findall(_txt(page))
    if len(set(found)) != 1:
        return ""
    return f"{found[0]}€"


def fetch_site(site, today=None):
    pid = site["provider"]
    venue = site["venues"][0]
    today = today or datetime.datetime.now(FI).date()
    payload = window(site, today, today + datetime.timedelta(days=HORIZON_DAYS))
    if not occurrences(payload):
        back = window(site, today - datetime.timedelta(days=LOOKBACK_DAYS), today)
        if not occurrences(back):
            raise RuntimeError(
                f"{events_url(site, today, today)}: the calendar returned no event in "
                f"category {site['category']} for the coming {HORIZON_DAYS} days or the "
                f"past {LOOKBACK_DAYS}. The route answers the same empty list to a "
                f"category that does not exist, so this is read as a changed calendar "
                f"rather than a quiet season, and the previous files stand")
        print(f"[{pid}] {venue['name']}: no screening in the coming {HORIZON_DAYS} days "
              f"and {len(occurrences(back))} in the past year, so the category is live "
              f"and the venue is confirmed empty")
        return {venue["id"]: []}
    try:
        price = tariff(site)
    except Exception as e:                      # noqa: BLE001 - the schedule is elsewhere
        price = ""
        print(f"[{pid}] the price page would not answer ({type(e).__name__}: {e}), so "
              f"these screenings publish no amount", file=sys.stderr)
    shows = parse(site, payload, price)
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {len({s['eventId'] for s in shows})} film(s), "
          f"{'priced ' + price if price else 'no price'}")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows:
            print(f"   {s['start'][:16]}  {s['title'][:40]:42} {s['price']:6}")
    sys.exit(0)
