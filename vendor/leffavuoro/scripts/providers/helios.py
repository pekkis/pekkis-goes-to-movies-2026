"""Kino Helios, the Malmitalo hall in Helsinki. Stdlib only.

One request, a POST to the culture house's own event calendar service:

    /services/Resurssivaraus/EventCalendarService.svc/GetEvents
    {"StartTime": "YYYY-MM-DD", "EndTime": "YYYY-MM-DD", "Language": "fi"}

This is the request the visitor-facing calendar makes. The answer is a JSON object whose
`EventData` is itself a JSON *string*, and the rows inside it are the whole house's
programme: concerts, talks, exhibitions and the cinema together.

What shapes the parser, measured on the live service 2026-09-21:

- **Three string fields pick this cinema out**, and all three are needed:
  `eventLocation == "42"`, `mainEventType == "29"` and `subtitle == "Kino Helios"`. The
  location and type alone answered 33 rows: 22 Kino Helios, 8 with a blank subtitle
  (HopeaCine and the Syysloma strand), 2 `Yleisön suosikit` and 1 **`Doc Helios`**, which
  is a different strand of the same house and is not this cinema.
- **`start` is `/Date(milliseconds)/`, a UTC instant**, and `timeSpanToShow` states the
  same moment in Helsinki. Both are read. A row where they disagree is left out and
  counted in the log; a dropped offset makes every row disagree, so nothing is left and
  the site fails, where it would otherwise publish every screening three hours out. All
  22 rows agreed when this was written.
- **`end - start` is a booking slot, not a runtime.** Twenty-one of the 22 rows measured
  exactly 120 minutes and one 300, so the field settles no film's length and `len` stays
  empty. Nothing else fills it: the TMDB pass publishes no runtime (checked 2026-09-24).
- **The age limit is a suffix on the title**, `Practical Magic: Lumotut sisaret (12)`.
  It is read into `rating` and taken off the published title, because the title is the key
  for `normTitle()`, `films-extra.json` and the combined city view: the same film screens
  at Iso-Hannu and Kino Akustiikka as `Practical Magic: Lumotut sisaret`, and a title
  carrying the house's age marker would key as a different film and lose its TMDB match.
  `enrich_tmdb.clean` does not strip a bare `(12)` and is not changed for this.
- **No price is published.** `priceinfo` and `ticketinfo` are the string `"None"` on every
  row, and the house tariff is a page rather than a per-screening amount.
- **`specificLocation` is the hall**, `Malmitalon Pieni sali` on all 22 rows. It is
  published as `aud` and asserted rather than used as the filter: the filter is the three
  fields above, so the cinema keeps working if the house renames a hall.
- **The synopsis declares its language.** `common.syn_language` places `description` and
  withholds it when nothing is settled.

**Zero rows fails the site.** The service answers the whole house, so zero Kino Helios rows
among a payload full of other events is as consistent with a renamed subtitle as with a
dark fortnight, and this reader cannot tell those apart. `common.EmptyProgramme` takes
positive evidence and there is none here.

**`book="buy"`.** Every row carries a `lippu.fi` ticket link.
"""
import datetime
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

import prices
from common import check_shows, fetch, get_text, syn_language
from etiketti import strict_codes

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "helios", "label": "Kino Helios",
     "base": "https://www.malmitalo.fi",
     "path": "/services/Resurssivaraus/EventCalendarService.svc/GetEvents",
     "location": "42", "type": "29", "subtitle": "Kino Helios",
     "hall": "Malmitalon Pieni sali",
     "venues": [{"id": "helios-helsinki", "name": "Kino Helios", "short": "Kino Helios",
                 "city": "Helsinki"}]},
]

# Days ahead to ask for. The live programme reached 33 days out; 90 leaves room for a
# season announcement and keeps the response inside a megabyte.
HORIZON = 90

DATE_RE = re.compile(r"/Date\((-?\d+)\)/")
# `ke  23.9.2026 klo 15.00`, the clock the service prints beside the instant.
SPAN_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*klo\s*(\d{1,2})[.:](\d{2})")
# A trailing age limit in brackets: `(7)`, `(12)`, `(S)`.
AGE_RE = re.compile(r"\s*\((S|\d{1,2})\)\s*$", re.I)


def instant(value):
    """`/Date(1790164800000)/` -> an aware Helsinki datetime, or None."""
    m = DATE_RE.match(value or "")
    if not m:
        return None
    return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000, FI)


def stated(value):
    """`timeSpanToShow` -> (day, month, year, hour, minute), or None."""
    m = SPAN_RE.search(value or "")
    return tuple(int(g) for g in m.groups()) if m else None


def split_title(title):
    """`Hetki ennen valoa (7)` -> ("Hetki ennen valoa", "K-7"). No suffix -> rating ""."""
    t = (title or "").strip()
    m = AGE_RE.search(t)
    if not m:
        return t, ""
    rest = t[:m.start()].strip()
    if not rest:
        return t, ""
    mark = m.group(1).upper()
    return rest, "S" if mark == "S" else f"K-{int(mark)}"


def text_of(value):
    """The service writes a missing string as the literal `None`."""
    v = (value or "").strip()
    return "" if v in ("", "None") else v


def rows(site, payload, today=None):
    """-> (shows, report). One row per screening this cinema publishes."""
    venue = site["venues"][0]
    out = []
    report = {"rows": 0, "mine": 0, "other_hall": 0, "unreadable": 0, "clock_clash": 0}
    for event in payload:
        report["rows"] += 1
        if (event.get("eventLocation") != site["location"]
                or event.get("mainEventType") != site["type"]
                or (event.get("subtitle") or "") != site["subtitle"]):
            continue
        report["mine"] += 1
        start = instant(event.get("start"))
        if start is None:
            report["unreadable"] += 1
            continue
        said = stated(event.get("timeSpanToShow"))
        if said and said != (start.day, start.month, start.year, start.hour, start.minute):
            report["clock_clash"] += 1
            continue
        hall = text_of(event.get("specificLocation"))
        if hall and hall != site["hall"]:
            report["other_hall"] += 1
        title, rating = split_title(event.get("title"))
        show = {
            "eventId": str(event.get("masterID") or event.get("key") or ""),
            "title": title,
            "original": "",
            "len": "",
            "rating": rating,
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": hall,
            "start": start.isoformat(),
            "url": text_of(event.get("ticketLink")),
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "",
            "provider": site["provider"],
            "venue": venue["id"],
            "_event": text_of(event.get("key")),
        }
        syn = text_of(event.get("description"))
        if syn:
            lang = syn_language(syn)
            if lang:
                show["_syn"] = {lang: syn}
        out.append(show)
    out.sort(key=lambda s: (s["start"], s["title"]))
    return out, report


def get_json(site, today=None):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    today = today or datetime.datetime.now(FI).date()
    body = json.dumps({"StartTime": today.isoformat(),
                       "EndTime": (today + datetime.timedelta(days=HORIZON)).isoformat(),
                       "Language": "fi"}).encode("utf-8")
    url = site["base"] + site["path"]
    answer = json.loads(get_text(url, fetcher=fetch, data=body, cache=False,
                                 headers={"content-type": "application/json",
                                          "user-agent": "Leffavuoro/1.0 "
                                                        "(+https://leffavuoro.fi)"}))
    return json.loads(answer["EventData"])


# Each screening's own record, the page a visitor opens from the calendar before the ticket
# shop, ends its `breadtext` with the film's facts: "Kieli: suomi<br />Tekstitys: suomi".
# Read 2026-09-29, one POST per screening. The answer is cached per screening under its
# ticket link, which is the key prices.enrich reads and is never requested.
SINGLE_PATH = "/services/Resurssivaraus/EventCalendarService.svc/GetSingleEvent"
TICKETS = "https://www.lippu.fi/event/"
LANG_CACHE = "film-lang-helios.json"
LANG_MAX = int(os.environ.get("KINO_FILM_PAGE_MAX") or 12)
FIELD_RE = re.compile(r"(Kieli|Tekstitys)\s*:\s*([^<\r\n]+)", re.I)
# The dubbed films' records say "Kieli: puhuttu suomeksi" (4 of 17 screenings that day).
SPOKEN_RE = re.compile(r"^puhuttu\s+", re.I)


def event_language(answer):
    """GetSingleEvent's answer -> {"lang": "FI-A, FI-S"}, or {} for what it does not state
    in names every word of which is a language."""
    event = json.loads(json.loads(answer)["EventData"])
    if not isinstance(event, dict):
        return {}
    got = {k.lower(): SPOKEN_RE.sub("", v.strip()) for k, v in
           FIELD_RE.findall(event.get("breadtext") or "")}
    parts = [f"{c}-A" for c in strict_codes(got.get("kieli"))]
    parts += [f"{c}-S" for c in strict_codes(got.get("tekstitys"))]
    return {"lang": ", ".join(parts)} if parts else {}


def screening_language(site, shows, *, path=None, now=None, sleep=1.5, limit=None):
    """Put each screening's language on it from its own record. -> counts dict. Never
    raises: a record that cannot be read leaves its screening without a language."""
    keys = {s["url"]: s.pop("_event", "") for s in shows}

    def read(url, headers):
        body = json.dumps({"Key": keys[url], "Language": "fi"}).encode("utf-8")
        return get_text(site["base"] + SINGLE_PATH, fetcher=fetch, data=body, cache=False,
                        headers={"content-type": "application/json",
                                 "user-agent": "Leffavuoro/1.0 (+https://leffavuoro.fi)"})
    asks = [s for s in shows if keys.get(s["url"])]
    try:
        return prices.enrich(asks, provider=site["provider"], prefix=TICKETS,
                             parse=lambda answer: "", fields=event_language,
                             path=path or (prices._out() / LANG_CACHE), now=now, sleep=sleep,
                             limit=LANG_MAX if limit is None else limit, fetch_fn=read,
                             label="event records")
    except Exception as e:                         # noqa: BLE001 -- the language is optional
        print(f"[{site['provider']}] languages skipped: {type(e).__name__}: {str(e)[:80]}")
        return {}


def fetch_site(site, today=None):
    """Runner contract: one POST to the calendar service, then one per screening's record
    for its language."""
    pid, venue = site["provider"], site["venues"][0]
    shows, report = rows(site, get_json(site, today), today)
    if not shows:
        raise RuntimeError(
            f"{site['base']}{site['path']}: no Kino Helios row among {report['rows']} "
            f"event(s). The service answers the whole house, so an empty result is as "
            f"consistent with a renamed strand as with a dark fortnight and the previous "
            f"files stand")
    st = screening_language(site, shows)
    if st:
        print(f"[{pid}] languages: {sum(1 for s in shows if s['lang'])} of {len(shows)} "
              f"screenings, {st['fetched']} records read, {st['failed']} failed, "
              f"{st['deferred']} deferred")
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}, {venue['city']}: {len(shows)} showtimes, "
          f"{len(days)} dates, {report['mine']} of {report['rows']} event(s) are this cinema")
    for key, note in (("clock_clash", "row(s) whose instant and printed clock disagree, left out"),
                      ("unreadable", "row(s) whose start does not parse, left out"),
                      ("other_hall", "row(s) in a hall this site does not name")):
        if report[key]:
            print(f"[{pid}] {report[key]} {note}")
    return per_venue


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src:
        with open(src, encoding="utf-8") as fh:
            shows, report = rows(SITES[0], json.loads(json.load(fh)["EventData"]))
        print(report)
    else:
        shows = fetch_site(SITES[0])[SITES[0]["venues"][0]["id"]]
    for s in shows:
        print(f"   {s['start'][:16]}  {s['title'][:38]:40} {s['rating']:5} {s['aud'][:22]:24} "
              f"{s['url'][-30:]}")
    sys.exit(0)
