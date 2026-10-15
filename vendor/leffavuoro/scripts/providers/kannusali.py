"""Kannusali, Espoo's culture house in Espoon keskus. Stdlib only.

Reads the POST to `https://www.espoo.fi/api/events` that the venue's own event listing
sends, filtered to the place `tprId` 21430 and the topic "Elokuvat", paged until `total`
is covered. Two kinds of hit are dropped and counted: a span over 24 hours, which is a
festival row with no screening time, and a second hit at a start minute already taken,
since the one hall cannot hold two screenings at once (the smallest id is kept).
The age rating is read from the mark that closes the title, the only place it is stated.
The published title leaves out that mark and a leading "Elokuva:".
"""
import datetime
import json
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import UA, check_shows, fetch, get_text

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kannusali", "label": "Kannusali",
     "base": "https://www.espoo.fi",
     "path": "/api/events",
     "tpr": "21430", "topic": "Elokuvat",
     "venues": [{"id": "kannusali-espoo", "name": "Kannusali", "short": "Kannusali",
                 "city": "Espoo"}]},
]

# The listing page's own page size.
PER_PAGE = 12
# 20 pages is 240 hits; the live film topic held 11 on 2026-10-13.
MAX_PAGES = 20
PAUSE = 1.0
SPAN_MAX = datetime.timedelta(hours=24)
# `Elokuva: Flow. (K7)`. Only the KAVI classes, and only as the last thing in the title.
RATING_RE = re.compile(r"\((S|K-?(7|12|16|18))\)$")
FILM_PREFIX = "elokuva:"


class EventRowError(RuntimeError):
    """A hit this parser could not read. It fails the site so the previous files stand."""


def body(site, offset):
    """The listing page's request body, as captured from its own fetch."""
    return {"filters": {"age": "", "areas": [], "attributes": [], "categories": [],
                        "endDate": None, "languages": [], "startDate": None,
                        "targetGroups": [], "topics": [site["topic"]], "extras": [],
                        "fixedFilters": {"areas": [], "keyword": None, "targetGroups": [],
                                         "topics": [], "tprId": site["tpr"]}},
            "langcode": "fi",
            "pagination": {"offset": offset, "perPage": PER_PAGE},
            "showLongLastingEvents": True,
            "type": "event"}


def post(site, offset):
    url = site["base"] + site["path"]
    data = json.dumps(body(site, offset)).encode("utf-8")
    return json.loads(get_text(url, fetcher=fetch, data=data, cache=False,
                               headers={"content-type": "application/json",
                                        "accept": "application/json",
                                        "user-agent": UA}))


def total_of(answer):
    total = answer.get("total") if isinstance(answer, dict) else None
    if isinstance(total, dict):
        total = total.get("value")
    if not isinstance(total, int) or isinstance(total, bool):
        raise RuntimeError(f"the events service answered no integer total ({str(answer)[:120]})")
    return total


def read_all(site):
    """Every hit's `_source`, page by page. -> [dict]."""
    out, offset, total = [], 0, None
    for n in range(MAX_PAGES):
        if n:
            time.sleep(PAUSE)
        answer = post(site, offset)
        total = total_of(answer)
        hits = answer.get("hits")
        if not isinstance(hits, list):
            raise RuntimeError(f"the events service answered no hits list at offset {offset}")
        if offset < total and not hits:
            raise RuntimeError(f"the events service answered no hits at offset {offset} "
                               f"of a total of {total}")
        out += [h.get("_source") or {} for h in hits]
        offset += len(hits)
        if offset >= total:
            return out, total
    raise RuntimeError(f"the events service has {total} hits, more than {MAX_PAGES} pages "
                       f"of {PER_PAGE}")


def instant(value, field, hit_id):
    """`2026-11-04T12:00:00Z` -> an aware Helsinki datetime."""
    try:
        t = datetime.datetime.fromisoformat(str(value))
    except ValueError:
        t = None
    if t is None or t.tzinfo is None:
        raise EventRowError(f"hit {hit_id!r}: {field} {value!r} is not an instant with an offset")
    return t.astimezone(FI)


def slug_of(title):
    return re.sub(r"-{2,}", "-", re.sub(r"[^\w]+", "-", (title or "").lower(),
                                        flags=re.UNICODE)).strip("-")


def rating_of(title):
    """`Elokuva: Flow. (K7)` -> "K-7", `(S)` -> "S", and "" when no mark closes the title."""
    m = RATING_RE.search(title)
    if not m:
        return ""
    return f"K-{m.group(2)}" if m.group(2) else "S"


def shown_title(title):
    """`Elokuva: Flow. (K7)` -> "Flow.". A title that would be left empty stays as it is."""
    t = RATING_RE.sub("", title).rstrip()
    if t.lower().startswith(FILM_PREFIX):
        t = t[len(FILM_PREFIX):].strip()
    return t or title


def rows(site, hits):
    """-> (shows, report). One row per screening minute."""
    venue = site["venues"][0]
    report = {"hits": len(hits), "long": [], "collapsed": []}
    kept = {}
    for hit in hits:
        hid = str(hit.get("id") or "")
        title = (hit.get("title") or "").strip()
        path = hit.get("path") or ""
        if not title:
            raise EventRowError(f"hit {hid!r} has no title")
        # The topic filter runs on the server, so a hit without it means the filter changed.
        if site["topic"] not in (hit.get("topics") or []):
            raise EventRowError(f"hit {hid!r} ({title}) is not under the topic {site['topic']!r}")
        if not isinstance(path, str) or not path.startswith("/"):
            raise EventRowError(f"hit {hid!r} ({title}) has no path: {path!r}")
        if not hit.get("eventStartTime"):
            raise EventRowError(f"hit {hid!r} ({title}) has no eventStartTime")
        start = instant(hit["eventStartTime"], "eventStartTime", hid)
        if hit.get("eventEndTime"):
            end = instant(hit["eventEndTime"], "eventEndTime", hid)
            if end - start > SPAN_MAX:
                report["long"].append(f"{hid} ({title})")
                continue
        minute = start.replace(second=0, microsecond=0)
        row = (hid, title, path, minute, hit.get("isFreeEvent") is True)
        other = kept.get(minute)
        if other is None:
            kept[minute] = row
            continue
        keep, drop = (row, other) if hid < other[0] else (other, row)
        kept[minute] = keep
        report["collapsed"].append(f"{drop[0]} ({drop[1]}), same start as {keep[0]}")
    out = []
    for hid, title, path, minute, free in kept.values():
        out.append({
            "eventId": slug_of(shown_title(title)),
            "title": shown_title(title),
            "original": "",
            "len": "",
            "rating": rating_of(title),
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": minute.isoformat(),
            "url": site["base"] + path,
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "Vapaa pääsy" if free else "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def fetch_site(site):
    """Runner contract: the listing's own POST, one request per page."""
    pid, venue = site["provider"], site["venues"][0]
    hits, total = read_all(site)
    # Zero hits cannot be told from a broken server-side filter, so it is never empty.
    if not hits:
        raise RuntimeError(f"{site['base']}{site['path']}: no hit for place {site['tpr']} "
                           f"and topic {site['topic']!r}")
    shows, report = rows(site, hits)
    if not shows:
        raise RuntimeError(f"{site['base']}{site['path']}: {total} hit(s) and no screening "
                           f"among them")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, from {len(hits)} hit(s) of a total of {total}")
    if report["long"]:
        print(f"[{pid}] {len(report['long'])} hit(s) spanning over 24 h left out: "
              f"{', '.join(report['long'])}")
    for note in report["collapsed"]:
        print(f"[{pid}] collapsed {note}")
    return per_venue


if __name__ == "__main__":
    for s in fetch_site(SITES[0])[SITES[0]["venues"][0]["id"]]:
        print(f"   {s['start'][:16]}  {s['title'][:44]:46} {s['price']:12} {s['url']}")
    sys.exit(0)
