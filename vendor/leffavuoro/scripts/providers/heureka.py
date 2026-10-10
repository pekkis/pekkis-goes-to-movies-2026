"""Heurekan planetaario (Vantaa): the science centre's daily programme. Stdlib only.

Source. heureka.fi is a Shopify storefront. Its "Päivän ohjelma" page renders three
arrays into the HTML from Shopify metaobjects, and the page's own script expands them
into the day a visitor picks:

    window.eventCalendarData      every programme item: kategoria, kesto (min), a date
                                  range, a blog path, and clock strings per weekday
    window.eventExceptionsData    a replacement weekday schedule for one item over one
                                  date range; the newest `alkaa` wins when several apply
    window.disabledHolidays       days the house is closed

There is no feed for the calendar (the page's `.json` is the page object without the
section, the blog's `.json` is 404, the atom feed lists articles without times), so this
adapter reads the same three arrays and expands them the same way for DAYS days ahead.
Only `kategoria == "Planetaarioelokuvat"` is a screening; the calendar also carries the
rat feeding, laboratory sessions, sphere shows and all-day exhibition events.

Admission. Planetarium films are included in the day ticket and there is no planetarium
ticket, so every showtime links to the ticket collection, `price` is empty, and the
registry entry is `book="admission"`. Admission has several visitor categories and
changing promotions (five products from 0 to 26 euro on 2026-09-05), so a single figure
on a showtime would be wrong for most readers.

Age. The planetarium admits from five years, whatever the film: `age = "K-5"` on every
show, the screening-level field a licensed auditorium's 18+ also uses. `rating` stays
empty; no KAVI classification is published. Heureka's per-film "Ikäsuositus" is a
recommendation and travels as a `method` tag, "Suositus yli 10 v", which the client
renders as a passive pill; the rating chip is for classifications.

Film pages. The blog article behind a calendar item gives Kesto, Ikäsuositus, the
description and a "Kielivaihtoehdot" line (Finnish by default, English and Swedish
through headphones). The synopsis is the description block only; the FAQ below it
repeats the admission rules and quotes a school-group price.

Posters. **Nothing of Heureka's is published**, and that is unchanged: its images are
16:9 stills, and its FAQ licenses none of its promotional artwork, so mirroring one would
need written permission nobody has given. What changed on 2026-09-20 is what a reader
sees instead of a two-letter initials tile. Three of the four films get one of
Leffavuoro's own title cards, drawn by scripts/make_cards.py: an abstract background this
repository generates from a seed, with the published title set over it in Archivo. They
are editorial illustrations and must never be described as posters. `Recombination` has
a real TMDB poster and is left alone.

CARDS is keyed on the published title **character for character**, and a title that has
moved on simply gets no card rather than the wrong one. The mapping lives here, in the
one adapter it applies to, so no other provider can pick a card up by publishing the same
title. `isrc` is deliberately not set: enrich_tmdb only reclaims a poster it marked as
TMDB's, so an unmarked local path is treated as the cinema's own and never replaced. The
files sit in data/posters/ because that is the only directory the client loads an image
from and the only one build_pages.py will emit a reference to.

Emptiness. The venue is reported as an empty list only when the calendar lists timed
planetarium items and every one's schedule was read in the page's shape (all seven weekday
keys, each a list) and puts no screening in the window: the runs have ended, or not begun,
or the house is closed. EMPTY_VENUES_CONFIRMED lets run.py publish that as pending. A page
without the arrays, an empty array, no item in the planetarium category, a schedule in
another shape, or planetarium clocks that all fail to parse raise instead, so the previous
file is kept. A filter that matches nothing is what a renamed category produces while the
calendar is full of films.

Conditional requests are off: the calendar page answers If-None-Match with a full 200
and a new ETag every time (checked 2026-09-05).
"""
import datetime
import html as html_mod
import json
import re
import sys
import time
import unicodedata
from zoneinfo import ZoneInfo

import common
from etiketti import LANG_NAMES

BASE = "https://www.heureka.fi"
CALENDAR = "/pages/tapahtumakalenteri"
TICKETS = "https://www.heureka.fi/collections/liput"
CATEGORY = "Planetaarioelokuvat"
DAYS = 21
AGE = "K-5"
FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"
HEADERS = {"user-agent": UA, "accept-language": "fi-FI,fi;q=0.9"}

# Leffavuoro's own title cards, keyed on the published title exactly. See the module
# docstring and docs/archive/2026-09-providers.md; regenerate with scripts/make_cards.py.
CARDS = {
    "Asteroid Quest": "data/posters/card-heureka-asteroid-quest.jpg",
    "Metsän sydän": "data/posters/card-heureka-metsan-sydan.jpg",
    "The Stellars - Tähtijengi": "data/posters/card-heureka-the-stellars.jpg",
}

# `short` is the full name, so labelOf() collapses the chain prefix instead of reading
# "Heureka Heurekan planetaario"; Bio Rex Kokkola does the same.
VENUE = {"id": "hk-vantaa", "provider": "heureka", "name": "Heurekan planetaario",
         "short": "Heurekan planetaario", "city": "Vantaa"}

SITES = [{"provider": "heureka", "label": "Heureka", "base": BASE, "venues": [VENUE]}]

# An empty venue: planetarium items read in schema, none in the window. See the docstring.
EMPTY_VENUES_CONFIRMED = True

WEEKDAYS = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai",
            "lauantai", "sunnuntai"]                        # date.weekday(): 0 = Monday
TIME_RE = re.compile(r"^(\d{1,2})[.:](\d{2})$")
TAGS_RE = re.compile(r"<[^>]+>")
DT_RE = re.compile(r'<dt class="detail-list__term">\s*(.*?)\s*</dt>\s*'
                   r'<dd class="detail-list__desc">\s*(.*?)\s*</dd>', re.S)
DESC_RE = re.compile(r'<div class="image-with-text__text rte body">(.*?)</div>', re.S)
LANGS_RE = re.compile(r"Kielivaihtoehdot:\s*(?:</strong>)?\s*(.*?)</p>", re.S)
MINUTES_RE = re.compile(r"(\d+)\s*min")
REC_OVER_RE = re.compile(r"yli\s+(\d+)-vuot", re.I)
REC_RANGE_RE = re.compile(r"(\d+)\s*[–-]\s*(\d+)-vuot", re.I)
REC_ADULTS_RE = re.compile(r"aikuisille", re.I)


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _slug(title):
    s = unicodedata.normalize("NFKD", _txt(title).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "naytos"


# ---------------------------------------------------------------- the three arrays

def _js_to_json(text):
    """A JavaScript array literal as the page writes it -> JSON text.

    Bare keys are quoted, trailing commas dropped, and the doubled commas an empty
    metaobject reference leaves behind (`["2026-03-13",\\n,\\n"2026-12-24",\\n]`, which
    the page cleans with `filter(Boolean)`) collapsed. String bodies are copied as they
    are: `\\/` and `\\u0026` are JSON already, and a title may contain a colon or a comma.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            body = text[i + 1:j]
            if c == "'":
                body = body.replace("\\'", "'").replace('"', '\\"')
            out.append('"' + body + '"')
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in "\"'":
            j += 1
        seg = text[i:j]
        seg = re.sub(r"([A-Za-z_]\w*)\s*:", r'"\1":', seg)
        seg = re.sub(r",(\s*,)+", ",", seg)
        seg = re.sub(r"([\[{])\s*,", r"\1", seg)
        seg = re.sub(r",(\s*[\]}])", r"\1", seg)
        out.append(seg)
        i = j
    return "".join(out)


def js_array(page, name):
    """The array assigned to `window.{name}` on the page -> list, or None if absent."""
    m = re.search(r"window\." + re.escape(name) + r"\s*=\s*\[", page)
    if not m:
        return None
    start = m.end() - 1
    depth, k, quote = 0, start, None
    while k < len(page):
        c = page[k]
        if quote:
            if c == "\\":
                k += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(_js_to_json(page[start:k + 1]))
        k += 1
    raise RuntimeError(f"window.{name} never closes")


def calendar_arrays(page):
    """-> (events, exceptions, holidays). Raises when the page is not the calendar."""
    events = js_array(page, "eventCalendarData")
    if events is None:
        raise RuntimeError(f"{BASE}{CALENDAR}: no window.eventCalendarData on the page "
                           f"(markup changed?)")
    if not events:
        # The array holds every kind of programme item; none at all means the section
        # did not render.
        raise RuntimeError(f"{BASE}{CALENDAR}: eventCalendarData is empty")
    exceptions = js_array(page, "eventExceptionsData") or []
    holidays = [h for h in (js_array(page, "disabledHolidays") or []) if h]
    return events, exceptions, holidays


# ---------------------------------------------------------------- the expansion

def _in_range(day, start, end):
    return not (start and day < start) and not (end and day > end)


def times_on(ev, exceptions, day):
    """The clock strings an event runs on `day`, as the page's renderDay decides them.

    An exception covering the day replaces the event's weekday schedule and suspends
    its date range; without one, the event runs inside its own range. Blanks dropped.
    """
    iso = day.isoformat()
    active = [ex for ex in exceptions
              if ev.get("nimi") in (ex.get("appliesToEvents") or [])
              and _in_range(iso, ex.get("alkaa") or "", ex.get("paattyy") or "")]
    if active:
        active.sort(key=lambda ex: ex.get("alkaa") or "", reverse=True)
        sched = active[0].get("ajat") or {}
    else:
        if not _in_range(iso, ev.get("alkamispaiva") or "", ev.get("paattymispaiva") or ""):
            return []
        sched = ev.get("ajat") or {}
    raw = sched.get(WEEKDAYS[day.weekday()]) or []
    return [re.sub(r'[\[\]"]', "", str(t)).strip() for t in raw if t and str(t).strip()]


def _iso(day, clock):
    m = TIME_RE.match(clock)
    if not m:
        return ""
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh > 23 or mm > 59:
        return ""
    return datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=FI).isoformat()


def _event_id(ev):
    blog = (ev.get("tapahtumasivu_blog_post") or "").rstrip("/")
    return blog.split("/")[-1] if blog.startswith("/blogs/") else _slug(ev.get("nimi"))


def parse_calendar(page, today=None, days=DAYS):
    """-> (shows, {blog path: eventId}) for the planetarium films in the window.

    An empty list is a confirmed empty programme: planetarium items are listed and their
    schedules, read in the page's shape, run nothing in the window. RuntimeError when
    planetarium clocks were listed and none could be read (the clock format changed), when
    no timed item carries the category, or when a schedule lacks the weekday lists: each
    is a parse that missed, and [] would publish a quiet week over it.
    """
    events, exceptions, holidays = calendar_arrays(page)
    today = today or datetime.datetime.now(FI).date()
    films = [ev for ev in events if ev.get("kategoria") == CATEGORY
             and ev.get("koko_paiva") != "Kyllä"]
    shows, blogs, tokens = [], {}, 0
    for n in range(days):
        day = today + datetime.timedelta(days=n)
        if day.isoformat() in holidays:
            continue
        for ev in films:
            for clock in times_on(ev, exceptions, day):
                tokens += 1
                start = _iso(day, clock)
                if not start:
                    continue
                eid = _event_id(ev)
                blog = (ev.get("tapahtumasivu_blog_post") or "").strip()
                if blog.startswith("/blogs/"):
                    blogs[blog] = eid
                kesto = ev.get("kesto")
                title = _txt(ev.get("nimi"))
                shows.append({
                    "eventId": eid,
                    "title": title,
                    "original": "",
                    "len": str(kesto) if isinstance(kesto, int) and kesto > 0 else "",
                    "rating": "",
                    "genres": "",
                    "method": "",
                    "theatre": VENUE["name"],
                    "aud": "",
                    "start": start,
                    "url": TICKETS,
                    "img": CARDS.get(title, ""),
                    "lang": "",
                    "soldOut": False,
                    "price": "",
                    "age": AGE,
                    "provider": VENUE["provider"],
                    "venue": VENUE["id"],
                    "_syn": "",
                })
    if tokens and not shows:
        raise RuntimeError(f"{BASE}{CALENDAR}: {tokens} planetarium time(s) listed in the "
                           f"next {days} days and none could be read (clock format changed?)")
    if not shows:
        if not films:
            raise RuntimeError(f"{BASE}{CALENDAR}: {len(events)} calendar item(s) and none "
                               f"a timed {CATEGORY!r} item (category renamed?)")
        names = {ev.get("nimi") for ev in films}
        scheds = [ev.get("ajat") for ev in films] + [
            ex.get("ajat") for ex in exceptions
            if names.intersection(ex.get("appliesToEvents") or [])]
        if not all(isinstance(a, dict) and all(isinstance(a.get(d), list) for d in WEEKDAYS)
                   for a in scheds):
            raise RuntimeError(f"{BASE}{CALENDAR}: a planetarium schedule lacks the weekday "
                               f"lists, so an empty window proves nothing (schema changed?)")
    shows.sort(key=lambda s: (s["start"], s["title"]))
    return shows, blogs


# ---------------------------------------------------------------- the film page

def recommendation(text):
    """Heureka's Ikäsuositus -> a labelled tag, or "" when it names no age.

    "Sopii parhaiten yli 10-vuotiaille" -> "Suositus yli 10 v"; "5–10-vuotiaille" ->
    "Suositus 5–10 v"; "...aikuisille" -> "Suositus aikuisille". "yli" is kept because the
    source says over ten. Every tag starts with "Suositus" so it cannot be read as a
    limit.
    """
    t = _txt(text)
    m = REC_RANGE_RE.search(t)
    if m:
        return f"Suositus {m.group(1)}–{m.group(2)} v"
    m = REC_OVER_RE.search(t)
    if m:
        return f"Suositus yli {m.group(1)} v"
    if REC_ADULTS_RE.search(t):
        return "Suositus aikuisille"
    return ""


def languages(page):
    """The 'Kielivaihtoehdot' line -> "FI-A, EN-A, SV-A"; "" when the page has none.
    A film without speech (Recombination) has no such line."""
    m = LANGS_RE.search(page)
    if not m:
        return ""
    codes = []
    for word in re.findall(r"[a-zåäö]+", _txt(m.group(1)).lower()):
        code = LANG_NAMES.get(word)
        if code and code not in codes:
            codes.append(code)
    return ", ".join(f"{c}-A" for c in codes)


def film_meta(page):
    """One blog article -> {len, method, lang, _syn}. Missing parts stay empty."""
    details = {_txt(k): _txt(v) for k, v in DT_RE.findall(page)}
    minutes = MINUTES_RE.search(details.get("Kesto", ""))
    desc = DESC_RE.search(page)
    paras = [_txt(p) for p in re.split(r"</p>", desc.group(1))] if desc else []
    return {
        "len": minutes.group(1) if minutes else "",
        "method": recommendation(details.get("Ikäsuositus", "")),
        "lang": languages(page),
        "_syn": " ".join(p for p in paras if p),
    }


# ---------------------------------------------------------------- the fetch

def get(path):
    return common.fetch(f"{BASE}{path}", headers=HEADERS, timeout=40,
                        cache=False).decode("utf-8", "replace")


def fetch_site(site=SITES[0], sleep=1.2, today=None):
    """Runner contract: the calendar, then one article per film, keyed by the venue."""
    shows, blogs = parse_calendar(get(CALENDAR), today)
    for i, path in enumerate(common.capped(sorted(blogs), "heureka film pages")):
        if i:
            time.sleep(sleep)
        try:
            meta = film_meta(get(path))
        except Exception as e:                       # metadata only; the schedule stands
            print(f"[heureka] film page {path} failed: {e}", file=sys.stderr)
            continue
        for s in shows:
            if s["eventId"] != blogs[path]:
                continue
            for k, v in meta.items():
                if v and not s.get(k):
                    s[k] = v
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    if src:
        data, blogs = parse_calendar(open(src, encoding="utf-8", errors="replace").read())
    else:
        data = fetch_site()[VENUE["id"]]
    print(f"{len(data)} showtimes, {len({s['eventId'] for s in data})} films, "
          f"{len({s['start'][:10] for s in data})} dates")
    for s in data[:40]:
        print(f"  {s['start'][:16]}  {s['title'][:40]:42} {s['len']:>3} min  {s['method']:22} "
              f"{s['lang']}")
