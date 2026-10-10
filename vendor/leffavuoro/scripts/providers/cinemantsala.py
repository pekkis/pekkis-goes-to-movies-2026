"""Cine Mäntsälä, mantsala.cine.fi. Stdlib only.

MyCloudCinema, read through the three requests the visitor's own page makes. Established
2026-09-15; the evidence is in `docs/research/ticketing-platforms.md`.

**Not a `SITES` entry on `gilda.py`, which reads the same platform.** Gilda's programme
comes through a WordPress facade (`/wp-json/gilda-react-booking/v1/movies`) that returns
every film and showtime in one response. This site has no such facade: it serves
MyCloudCinema's own `/webservices/show_times/` endpoints, one date window at a time. The
row shape is the platform's and is shared, which is why `FORMATS` and `LANG` are imported
from that module rather than copied; the fetch is not.

**The price is published and no screening can carry one.** `webservices/content/getContent`
with `content_id=10` returns the site's own `Liput` page: ma–to 12,50 € (3D 13,50), pe–su and
arkipyhät 14,50 € (3D 15,50), −1 € for children, students and pensioners. 3D is readable here,
unlike TMB -- the schedule rows carry `version_3d` -- but three things are not: an *arkipyhä*
shares the weekend price and no calendar here knows those days; a Wednesday premiere is priced
as a weekend and what `premiere` means was not established; and the page states its own escape,
that special or long films are priced separately and the price should be checked at the
screening. So the tariff settles nothing per screening and `price` stays empty. See
`common.Show` for the rule and `docs/research/prices.md` for the reading.

**Not the JSON-LD feed the page also injects.** `/webservices/structured_data/get` carries
today only (4 of the 37 screenings this week when measured) and drops the `Z` off a UTC
instant, so reading it as a local time publishes every showtime three hours early.

The three requests, all on the cinema's own host, all answering 200 with no key and no
session:

    GET {base}/webservices/show_times/getShowDates?cinema_id=1
      -> {"resultCode": 0, "data": [{"show_date": "2026-09-14T21:00:00.000Z"}, ...]}
    GET {base}/webservices/show_times/getShowTimesDays?cinema_id=1&date=&number_of_days=7
      -> {"resultCode": 0, "data": [ {screening}, ... ]}

`getShowTimes?cinema_id=1&date=` serves one date and is not used: the window covers seven
for the same one request.

**`number_of_days` behaves as a cap of 7.** Asked for 7, 14 and 120 from 2026-09-15 the
endpoint returned the same 37 rows over 09-15 to 09-20 every time, while a window from
2026-12-01 did reach 12-05. So the date list is walked and covered with as few seven-day
windows as it takes: 17 dates out to 2026-12-22 took nine requests on 2026-09-15. Windows
can overlap, and a screening is deduplicated on `show_time_id`.

**`show_date` is a real UTC instant, not a date.** Local midnight arrives as the preceding
`21:00:00.000Z` before the 2026-10-25 DST change and `22:00:00.000Z` after it, which is
the source's own statement that it keeps Europe/Helsinki, and it is why the date is
converted rather than sliced. `show_time` is UTC the same way: `2026-09-15T13:45:00.000Z`
is the 16.45 screening the site's own booking page prints. `business_date` on the same row
is the *local* date stamped `T00:00:00.000Z`, a different convention in one payload, and
nothing here reads it.

Notes from the 48 rows measured on 2026-09-15:

- **Two screens**, "Sali 1" and "Sali 2", so `aud` carries the screen name.
- `rating_name` is Finnish: `K7`, `K12`, `K16`, `K18`, "Sallittu kaikenikäisille",
  "Ikäraja tulossa!", "Luokittelematon". The last two publish nothing.
- `subtitle_lang` is a Finnish phrase, not a code: "Suomeksi ja ruotsiksi", "Ruotsiksi",
  "suomeksi", "Ei". `audio_lang` is a code (`FI`, `EN`, `SE`).
- `movie_audio_style_name` is "Original language" or "Dubbed" and is **not** published:
  all five dubbed rows are Finnish-language children's films whose `audio_lang` is
  already `FI`, so `lang` says it and a second pill would repeat it.
- `title_extension` is the strand field ("Cine Matinea", "Leffa & Kaffe - näytös",
  "Ennakkonäytös!"). `strands.py` puts a strand in `method`, and here it arrives in its
  own field, so no prefix has to come off the title and nothing is added to
  `EVENT_PREFIXES`.
- `version_digital` is the only `version_*` flag ever set and `FORMATS` omits it on
  purpose, so the format list is usually empty.
- No `original_title` and no synopsis: `short_desc` repeats the title on every row.
- Posters are `/media/posters/{movie_id}/{width}/{movie_poster}` and only widths 216 and
  1080 exist; 300, 500, 720, 1024 and 2048 all answer 404.

**The ticket link is read, not constructed.** The rendered programme emits one
`#/book/{id}` anchor per screening, and on 2026-09-15 the 37 ids it emitted were exactly
the 37 `show_time_id` values the window returned, as sets. `#/book/13394` loaded directly
resolves to the seat-selection page for that screening. The booking flow itself is never
called by this adapter.

**A failed window raises.** These requests carry the schedule rather than metadata, so the
rule in `common.budget_or_raise` applies: half a programme is worse than none, because
`run.py` keeps the previous file when a site fails and the health line then ages honestly.
"""
import datetime
import json
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import EmptyProgramme, budget_or_raise, fetch
from gilda import FORMATS, LANG

BASE = "https://mantsala.cine.fi"
FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

VENUE = {"id": "cm-mantsala", "name": "Cine Mäntsälä", "short": "Cine Mäntsälä",
         "city": "Mäntsälä"}

SITES = [{
    "provider": "cinemantsala",
    "label": "Cine Mäntsälä",
    "base": BASE,
    "api": "/webservices/show_times",
    "cinema_id": 1,
    "posters": "/media/posters",
    "poster_width": 1080,
    "venues": [VENUE],
}]

# What the endpoint honours, measured rather than documented anywhere on the site.
WINDOW_DAYS = 7
# A ceiling on the requests one run can make, for the same reason budget_or_raise exists:
# the window count comes from the cinema's own date list, so a list that ever spans years
# would otherwise turn into a sweep. Nine windows covered the programme on 2026-09-15.
WINDOW_BUDGET = 30

# The subtitle field is prose. "Ei" is the cinema saying there are none, and an unknown
# word publishes nothing rather than a guess.
SUBS = {"suomeksi": "FI", "ruotsiksi": "SV", "englanniksi": "EN", "ei": ""}
SUB_SPLIT = re.compile(r"\s*(?:,|/|\bja\b)\s*")


def get(url, tries=3, timeout=30):
    """MyCloudCinema's own webservices, JSON.

    A malformed body raises out of json.loads without a retry: common.fetch retries the
    request, not the parse, and a 200 that is not JSON is a shape change to look at.
    """
    body = fetch(url, cache=True,
                 headers={"user-agent": UA, "accept": "application/json"},
                 tries=tries, timeout=timeout).decode("utf-8", "replace")
    return json.loads(body)


def _rows(payload, url):
    """-> the `data` list, or raise if the envelope is not the one this parser reads."""
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"{url}: no `data` key, so this is not the webservices "
                           f"envelope this parser reads")
    code = payload.get("resultCode")
    if code not in (0, "0", None):
        raise RuntimeError(f"{url}: resultCode {code!r}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        # `[]` is how this envelope says "none"; `null` or an object is a shape change.
        raise RuntimeError(f"{url}: `data` is {type(rows).__name__}, not a list")
    return rows


def show_dates(site, tries=3):
    """-> [datetime.date] in Europe/Helsinki, from the cinema's own date list.

    A listed date this cannot read raises rather than being dropped: dropping it loses
    that date's window, and dropping every one would turn a changed date format into
    the empty list `fetch_site` reads as the cinema having nothing on.
    """
    url = f"{site['base']}{site['api']}/getShowDates?cinema_id={site['cinema_id']}"
    out = []
    for row in _rows(get(url, tries=tries), url):
        raw = (row.get("show_date") or "").strip() if isinstance(row, dict) else ""
        try:
            t = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            raise RuntimeError(f"{url}: unreadable show_date {raw!r}") from None
        if t.tzinfo is None:
            # A naive show_date would be the JSON-LD's mistake again.
            raise RuntimeError(f"{url}: show_date {raw!r} has no UTC offset")
        out.append(t.astimezone(FI).date())
    return sorted(set(out))


def windows(dates, span=WINDOW_DAYS):
    """-> [date] window starts covering every date in `dates`, fewest first.

    A window from S covers S to S+span-1, so the next start is the first date the
    previous window cannot reach. Two dates a fortnight apart cost two requests; six
    consecutive days cost one.
    """
    out = []
    for d in sorted(set(dates)):
        if not out or (d - out[-1]).days >= span:
            out.append(d)
    return out


def _start(show):
    raw = (show.get("show_time") or "").strip()
    if not raw:
        return ""
    try:
        t = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if t.tzinfo is None:
        return ""             # naive means the source changed; do not assume a zone
    return t.astimezone(FI).isoformat()


def _rating(show):
    """Finnish rating strings -> the Finnkino-style tags the client filters on.

    "Ikäraja tulossa!" and "Luokittelematon" carry no number and publish nothing: a
    pending rating is not a rating, and the client shows no tag rather than a wrong one.
    """
    v = (show.get("rating_name") or "").strip()
    if v.lower().startswith("sallittu"):
        return "S"
    m = re.search(r"(\d+)", v)
    return f"K-{m.group(1)}" if m else ""


def _lang(show):
    """-> "FI-A, SV-S" using Finnkino's tags, so one client filter serves every provider."""
    out = []
    a = LANG.get((show.get("audio_lang") or "").strip().lower(), "")
    if a:
        out.append(a + "-A")
    for part in SUB_SPLIT.split((show.get("subtitle_lang") or "").strip().lower()):
        s = SUBS.get(part.strip())
        if s and s + "-S" not in out:
            out.append(s + "-S")
    return ", ".join(out)


def _method(show):
    """Format pills plus the strand, which arrives in `title_extension` on this site."""
    out = [label for flag, label in FORMATS.items() if show.get(flag)]
    ext = (show.get("title_extension") or "").strip()
    if ext:
        out.append(ext)
    return " · ".join(out)         # the client's tag separator; ", " made one tag of two


def _aud(show):
    """The screen, verbatim. Two screens here, so it always says something."""
    name = (show.get("screen_name") or "").strip()
    return "" if name.lower() in (VENUE["short"].lower(), VENUE["name"].lower()) else name


def _img(show, site):
    poster = (show.get("movie_poster") or "").strip()
    mid = show.get("movie_id")
    if not (poster and mid):
        return ""
    return (f"{site['base']}{site['posters'].rstrip('/')}/{mid}/"
            f"{site.get('poster_width', 1080)}/{poster}")


def parse(rows, site=None):
    """-> {venue_id: [show, ...]}, deduplicated on `show_time_id`.

    `rows` is the concatenation of every window's `data`, so overlapping windows and a
    repeated screening are expected rather than an error.
    """
    site = site or SITES[0]
    base = site["base"].rstrip("/")
    per_venue = {VENUE["id"]: []}
    seen = set()
    dropped = 0
    for s in rows:
        sid = s.get("show_time_id")
        start = _start(s)
        if sid is None or not start:
            continue
        if sid in seen:
            dropped += 1
            continue
        seen.add(sid)
        per_venue[VENUE["id"]].append({
            "eventId": str(s.get("movie_id") or ""),
            "title": (s.get("title") or "").strip(),
            "original": "",
            "len": str(s.get("running_time") or ""),
            "rating": _rating(s),
            "genres": (s.get("genre") or "").strip(),
            "method": _method(s),
            "theatre": VENUE["name"],
            "aud": _aud(s),
            "start": start,
            "url": f"{base}/#/book/{sid}",
            "img": _img(s, site),
            "lang": _lang(s),
            "soldOut": bool(s.get("sold_out")),
            "price": "",
            "provider": site["provider"],
            "venue": VENUE["id"],
        })
    if dropped:
        print(f"[cinemantsala] dropped {dropped} showtime(s) already read in an "
              f"earlier window")
    per_venue[VENUE["id"]].sort(key=lambda r: r["start"])
    return per_venue


def fetch_site(site=SITES[0], sleep=1.5):
    """Runner contract: the date list, then one request per seven-day window.

    An empty date list, `data: []` in the expected envelope with no row dropped on the
    way, is the cinema's own statement that it has nothing on, which is `EmptyProgramme`.
    A window that fails raises, so run.py keeps the previous file rather than publishing
    whichever windows happened to answer.

    Dates listed with no screening in any window is **not** `EmptyProgramme`: the dates
    are derived from the screenings, so a list of them beside an empty parse is the
    contradiction CLAUDE.md names as the broken case, and it fails the site instead.
    """
    dates = show_dates(site)
    if not dates:
        raise EmptyProgramme(f"{site['base']} lists no show date at all")
    starts = budget_or_raise(windows(dates), "cinemantsala", WINDOW_BUDGET)
    print(f"[cinemantsala] {len(dates)} date(s) to {dates[-1]}, "
          f"{len(starts)} window(s) of {WINDOW_DAYS} days")
    rows = []
    for n, start in enumerate(starts):
        if n:
            time.sleep(sleep)
        url = (f"{site['base']}{site['api']}/getShowTimesDays"
               f"?cinema_id={site['cinema_id']}&date={start.isoformat()}"
               f"&number_of_days={WINDOW_DAYS}")
        rows += _rows(get(url), url)
    per_venue = parse(rows, site)
    shows = per_venue[VENUE["id"]]
    if not shows:
        raise RuntimeError(
            f"{site['base']} lists {len(dates)} show date(s) but no window returned a "
            f"screening. The date list is derived from the screenings, so this is a "
            f"shape or fetch failure rather than a cinema with nothing on, and failing "
            f"keeps the last good data")
    days = sorted({r["start"][:10] for r in shows})
    print(f"[cinemantsala] Cine Mäntsälä: {len(shows)} showtimes, {len(days)} dates")
    return per_venue


if __name__ == "__main__":
    if len(sys.argv) > 1:          # offline: one or more saved getShowTimesDays dumps
        rows = []
        for path in sys.argv[1:]:
            rows += json.load(open(path, encoding="utf-8")).get("data") or []
        res = parse(rows)
    else:
        res = fetch_site()
    for vid, shows in sorted(res.items()):
        days = sorted({s["start"][:10] for s in shows})
        print(f"{vid}: {len(shows)} showtimes, {len(days)} dates -> {days[-1]}")
        for s in shows[:4]:
            print(f"   {s['start'][:16]}  {s['title'][:28]:30} {s['rating']:5} "
                  f"{s['aud'][:8]:10} {s['lang']:16} {s['method'][:24]}")
