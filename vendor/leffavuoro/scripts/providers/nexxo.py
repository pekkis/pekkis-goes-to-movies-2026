"""Nexxo Scope platform adapter (WordPress plugin used by Finnish cinemas).

One JSON endpoint per site, filtered by locationid:
  GET {base}/wp-content/plugins/nexxo-scope/public_api.php
      ?action=exportdailyshows&locationid=N&days=D&lang=fi&upcoming=0
Response: {"shows": {"YYYY-MM-DD": [ ... ]}}

Adding another Nexxo cinema means adding an entry to SITES, not writing code.
`programme` is the page a showtime links to and it differs per site -- /ohjelmisto/,
/naytokset/, /esitysajat/, /naytoslista/, or the front page. The 2026-08-30 sweep copied
Kinoset's path onto every site unverified and shipped six dead ticket links; fetch the
built URL and check for the plugin's showlist markup before trusting a new entry.
"""
import collections, datetime, json, re, time, urllib.parse
from zoneinfo import ZoneInfo

import common
import synmerge
from common import fetch

# EmptyProgramme is referenced through the module, not from-imported: the test suite
# reloads `common` (test_common_fetch), which rebinds the class in place, and a
# from-import taken at discovery time would raise a class object the reloaded
# `except common.EmptyProgramme` no longer matches. Late binding keeps one identity
# in tests and costs nothing in production.

FI = ZoneInfo("Europe/Helsinki")

UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

# run.py may treat a venue this module reports with an empty list as positive evidence
# of an empty programme ("pending" rather than "unverified"), because parse() only
# returns [] on evidence: the payload passed the shows-key schema check and the venue's
# rows are genuinely absent (an empty payload, a room filter that owns none of them while
# another venue's rooms own some, or rows the upstream itself marks upcoming-only). Rows
# that exist but cannot be parsed raise instead of vanishing, so a renamed row field can
# never read as a quiet empty programme. A payload with rows that no configured room owns
# at all is the roomIds having moved, and fetch_site raises on it rather than report
# every venue []. A roomed venue with no row while other rows sit in rooms nobody owns is
# left out instead of reported []: one town's moved roomId and a new town beside a town
# between visits cannot be told apart, and either way its screenings may be among them.
# An adapter whose venue match is a substring test over markup (etiketti) sets this only
# on evidence the read itself produced, because a rotted match and a drifted screening
# pattern both yield the same empty list while the page still lists films: there, the
# site's own theatre navigation has to name the venue, every film page has to have been
# fetched and parsed, every page with screening blocks has to have produced at least one
# row, and every row has to have been taken by a registered venue. Any miss clears the
# confirmation.
EMPTY_VENUES_CONFIRMED = True

SITES = [
    {"provider": "kinoset", "base": "https://kinoset.fi", "label": "Kinoset",
     "programme": "/ohjelmisto/", "venues": [
         {"id": "ks-huittinen", "locationid": "1", "name": "Kino 1-2",
          "short": "Kino 1-2", "city": "Huittinen"},
         {"id": "ks-loimaa", "locationid": "2", "name": "Kinema",
          "short": "Kinema", "city": "Loimaa"},
         {"id": "ks-sastamala", "locationid": "3", "name": "Bio",
          "short": "Bio", "city": "Sastamala"},
     ]},
    # The 2026-08-30 sweep. Every locationid below was discovered by asking the endpoint,
    # never assumed: kinohirvi.fi answers on 2 and 4 and on nothing else, and its id 4 is
    # a different cinema in a different town.
    {"provider": "kinoaurora", "base": "https://kinoaurora.fi", "label": "Kino Aurora",
     "programme": "/naytokset/", "venues": [
         {"id": "au-jyvaskyla", "locationid": "1", "name": "Kino Aurora",
          "short": "Kino Aurora", "city": "Jyväskylä"},
     ]},
    # Two cinemas on one host, so two entries rather than one provider labelled after
    # whichever came first: Bio Säde is in Mänttä and Kino Hirvi in Äänekoski, and the
    # picker has to name each one. `host` credits the site read, which for both
    # is kinohirvi.fi -- biosade.fi is a separate domain that serves an empty programme.
    {"provider": "kinohirvi", "base": "https://kinohirvi.fi", "label": "Kino Hirvi",
     "programme": "/", "venues": [
         {"id": "hi-aanekoski", "locationid": "2", "name": "Kino Hirvi",
          "short": "Kino Hirvi", "city": "Äänekoski"},
     ]},
    # `site` is where a person is sent, `base` is where the API lives: biosade.fi's own
    # API is empty, and its front page renders location 4 by calling kinohirvi.fi's API
    # from the browser. So the data comes from kinohirvi.fi and the ticket link must not.
    {"provider": "biosade", "base": "https://kinohirvi.fi",
     "site": "https://www.biosade.fi", "label": "Bio Säde",
     "programme": "/", "venues": [
         {"id": "sa-mantta", "locationid": "4", "name": "Bio Säde",
          "short": "Bio Säde", "city": "Mänttä"},
     ]},
    {"provider": "kinomarilyn", "base": "https://kinomarilyn.fi", "label": "Kino Marilyn",
     "programme": "/esitysajat/", "venues": [
         {"id": "ma-loviisa", "locationid": "1", "name": "Kino Marilyn",
          "short": "Kino Marilyn", "city": "Loviisa"},
     ]},
    {"provider": "kinoolympia", "base": "https://kino-olympia.fi", "label": "Kino Olympia",
     "programme": "/naytokset/", "venues": [
         {"id": "ol-hanko", "locationid": "1", "name": "Kino Olympia",
          "short": "Kino Olympia", "city": "Hanko"},
     ]},
    {"provider": "jarvelankino", "base": "https://jarvelankino.fi",
     "label": "Järvelän Kino", "programme": "/naytoslista/", "venues": [
         {"id": "ja-jarvela", "locationid": "1", "name": "Järvelän Kino",
          "short": "Järvelän Kino", "city": "Järvelä"},
     ]},
    # KSEK's touring cinema: one locationid whose rooms are towns, not screens. The
    # data is read from kinoaurora.fi (same deployment as ksek.fi), the visitor pages
    # are ksek.fi/kino-metso/{town}/ -- verified 2026-08-31, each answers 200 with the
    # plugin's showlist filtered to that town's roomId. `rooms` lists the roomIds a
    # venue owns; Riihivuori (roomId 21, a resort hill in Muurame) folds into the
    # Muurame venue because KSEK's own site gives it no page, and the room name stays
    # visible in `aud`. Vaajakoski and Tikkakoski are districts of Jyväskylä, so that
    # is their city. Hankasalmi and Laukaa have pages but no programme today, and are
    # deliberately not added -- the unclaimed-room line in the log announces them the
    # day they publish, and until one is added no empty town here is confirmed empty.
    {"provider": "kinometso", "base": "https://kinoaurora.fi",
     "site": "https://ksek.fi", "label": "Kino Metso", "programme": "/kino-metso/",
     "venues": [
         {"id": "km-muurame", "locationid": "2", "rooms": ["2", "21"],
          "page": "/kino-metso/muurame/", "name": "Muurame",
          "short": "Muurame", "city": "Muurame"},
         {"id": "km-petajavesi", "locationid": "2", "rooms": ["4"],
          "page": "/kino-metso/petajavesi/", "name": "Petäjävesi",
          "short": "Petäjävesi", "city": "Petäjävesi"},
         {"id": "km-tikkakoski", "locationid": "2", "rooms": ["11"],
          "page": "/kino-metso/tikkakoski/", "name": "Tikkakoski",
          "short": "Tikkakoski", "city": "Jyväskylä"},
         {"id": "km-vaajakoski", "locationid": "2", "rooms": ["12"],
          "page": "/kino-metso/vaajakoski/", "name": "Vaajakoski",
          "short": "Vaajakoski", "city": "Jyväskylä"},
     ]},
]


def api_url(site, locationid, days):
    q = urllib.parse.urlencode({"action": "exportdailyshows", "locationid": locationid,
                                "days": days, "lang": "fi", "upcoming": "0"})
    return f"{site['base']}/wp-content/plugins/nexxo-scope/public_api.php?{q}"


# Codes Nexxo writes that are not this app's: Swedish as SE, the country, and Hebrew as
# IW, the ISO 639-1 code withdrawn in 1989 (Kino Aurora, "Naza", 2026-10-02).
CODE_FIX = {"SE": "SV", "IW": "HE"}


def _codes(v):
    """'FI-SE' / 'FI/SE' -> ['FI','SV']; OV (original version) means unspecified.

    The ISO 639-1 code is what this app uses, so `CODE_FIX` corrects a code here rather
    than carrying it into the data."""
    out = [c for c in re.split(r"[^A-Za-z]+", (v or "").upper()) if c and c != "OV"]
    return [CODE_FIX.get(c, c) for c in out]


# Nexxo's code_subtitles for a screening shown without subtitles. Read 2026-10-04: 29 rows
# on five sites, 25 of them Finnish films or dubs; an unknown subtitle is OV, as at Kino
# Hirvi, so XX is chosen. Alone it publishes `XX-S`, Kino Engel's "no subtitles". Beside a
# real subtitle code ("XX/SE") the value contradicts itself and only the code is kept.
NO_SUBTITLES = "XX"


def _lang(row):
    """code_language / code_subtitles -> Finnkino-style FI-A / FI-S tags.

    "FI" / "XX" -> "FI-A, XX-S"; "OV" / "XX" -> "XX-S"; "FI" / "XX/SE" -> "FI-A, SV-S"."""
    parts = [f"{c}-A" for c in _codes(row.get("code_language"))]
    subs = _codes(row.get("code_subtitles"))
    if subs == [NO_SUBTITLES]:
        parts.append(f"{NO_SUBTITLES}-S")
    else:
        parts += [f"{c}-S" for c in subs if c != NO_SUBTITLES]
    return ", ".join(parts)


def _iso(start):
    """'2026-08-26 17:00:00' -> ISO with the correct Helsinki offset (DST-aware)."""
    try:
        naive = datetime.datetime.strptime(start.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""
    return naive.replace(tzinfo=FI).isoformat()


def rating(age):
    """A Nexxo `ageLimit` -> "S", "K-n" or "".

    Only S and K-n are ratings: the client's `kidsRated()` and every `rating ===` test
    compare against exactly those strings. The field is a bare number on most rows, but
    Kino Aurora sent a lowercase "s" on two Animaatioaarteet screenings, published as "s"
    and dropped from Lapsille (2026-09-25). Anything else is no rating, the rule
    `fetch_data.py` applies to OCAPI's "Tulossa" and "-".
    """
    a = re.sub(r"\s+", "", str(age or "")).upper()
    if a == "S":
        return "S"
    m = re.fullmatch(r"(?:K-?)?(\d{1,2})", a)
    return f"K-{int(m.group(1))}" if m else ""


# The cinema's production year, a search hint for the TMDB pass. A range such as
# "1937-1949" on a shorts programme is no one film's year and is left out.
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
BOLD_P = re.compile(r"^\s*<p[^>]*>\s*<(strong|b)>(?:(?!</?(?:strong|b)>).)*</\1>\s*$", re.S)


def intro_syn(text, names=()):
    """{lang: text} from a row's HTML. Nexxo fills `intro`; `description` was empty for all
    74 films on eight sites (2026-09-28). The notes sit between the blurb's paragraphs, so
    each is judged alone: a wholly bold one (festival, dub, free entry), one naming the
    cinema or quoting a price, and one no language places ("Puhuttu suomeksi.") are left
    out, and of the rest those in the most common language are kept."""
    placed = []
    for p in re.split(r"</p\s*>", text or ""):
        if not p.strip() or BOLD_P.match(p):
            continue
        t = synmerge.drop_notes_html(p, names=names)
        lang = common.syn_language(t) if t else ""
        if lang:
            placed.append((lang, t))
    if not placed:
        return {}
    best = collections.Counter(lang for lang, _ in placed).most_common(1)[0][0]
    return {best: " ".join(t for lang, t in placed if lang == best)}


def parse(payload, site, venue):
    # Positive evidence that the endpoint answered in the schema this parser reads,
    # before any of its emptiness is believed. A renamed or restructured key yields zero
    # rows and is otherwise indistinguishable from a cinema with nothing on, which would
    # let a schema change publish stale data behind an EmptyProgramme -- the same trap
    # zero regex matches set for the eTiketti listing. A genuinely empty host answers
    # {"shows": []}, verified live against biojukola.fi and biosalo.fi on 2026-08-31, so
    # requiring the key costs the real case nothing.
    if not isinstance(payload, dict) or "shows" not in payload:
        raise RuntimeError(
            f"{site['base']}: response has no 'shows' key "
            f"(keys: {sorted(payload)[:6] if isinstance(payload, dict) else type(payload).__name__}). "
            f"The schema changed; this is a parser break, not an empty programme")
    groups = payload.get("shows") or {}
    rows = [r for v in groups.values() for r in v] if isinstance(groups, dict) else list(groups)
    # A venue with a `rooms` list owns only the rows whose roomId is in it; several
    # venues can then share one locationid (Kino Metso: five towns on locationid 2).
    # Matching is on roomId, not roomTitle -- the id is what the per-town pages filter
    # on, and a title is one wording change from silently dropping a town.
    if venue.get("rooms"):
        rooms = {str(x) for x in venue["rooms"]}
        rows = [r for r in rows if str(r.get("roomId") or "") in rooms]
    shows = []
    skipped_upcoming = skipped_broken = untitled = 0
    for r in rows:
        iso = _iso(r.get("startTime") or "")
        if not iso or not r.get("startDate"):
            # An upcoming-only entry legitimately has no scheduled showtime yet, and
            # the payload says so itself. Any other row with an unreadable start is a
            # schema change wearing empty clothes, and is counted rather than dropped.
            if str(r.get("isUpcoming") or "") == "1":
                skipped_upcoming += 1
            else:
                skipped_broken += 1
            continue
        title = (r.get("movieTitle") or r.get("title") or "").strip()
        if not title:
            # A renamed title key would otherwise publish every row as "?". Counted as
            # broken, so a venue whose every row went this way raises below rather than
            # reading as an empty programme.
            untitled += 1
            skipped_broken += 1
            continue
        age = str(r.get("ageLimit") or r.get("agelimit") or "").strip()
        year = str(r.get("release_year") or "").strip()
        poster = (r.get("posterurl") or "").strip()
        price = r.get("priceIncludingTax") or ""
        try:
            price = f"{float(price):.2f}".rstrip("0").rstrip(".") + "€" if float(price) else ""
        except (TypeError, ValueError):
            price = ""
        shows.append({
            "eventId": str(r.get("movieId") or r.get("id") or ""),
            "title": title,
            "original": "",   # code_external_title holds a distributor code, not a title
            "len": str(r.get("duration") or "").strip().lstrip("0") or "",
            "year": year if YEAR_RE.fullmatch(year) else "",
            "rating": rating(age),
            "genres": ", ".join(g.strip().capitalize()
                                for g in (r.get("genre") or "").split(",") if g.strip()),
            "method": (r.get("showTypeTitle") or "").replace("Tavallinen näytös", "").strip(),
            "theatre": venue["name"],
            # roomTitle repeats the venue name at single-screen sites — drop it there.
            "aud": ("" if (r.get("roomTitle") or "").strip() in
                    (venue["name"], venue["short"]) else (r.get("roomTitle") or "").strip()),
            "start": iso,
            # A venue with its own page links there without the location query --
            # the page is already filtered. The rest link to the site's programme.
            "url": (f"{site.get('site') or site['base']}{venue['page']}"
                    if venue.get("page") else
                    f"{site.get('site') or site['base']}{site['programme']}"
                    f"?location={venue['locationid']}"),
            "img": (f"{site['base']}/wp-content/plugins/nexxo-scope/banners/{poster}"
                    if poster else ""),
            "lang": _lang(r),
            "soldOut": False,
            "price": price,
            "provider": site["provider"],
            "venue": venue["id"],
            "_syn": intro_syn(r.get("description") or r.get("intro"),
                              names=(site.get("label") or "",)),
        })
    # Rows existed for this venue and not one produced a showtime, for reasons the
    # payload does not explain: that is the row schema changing under the parser, and
    # returning [] here would let EMPTY_VENUES_CONFIRMED read it as a quiet pending
    # programme. Upcoming-only rows are exempt -- a venue whose whole listing is
    # unscheduled premieres is genuinely not showing anything yet.
    if rows and not shows and skipped_broken:
        raise RuntimeError(
            f"{site['base']} locationid {venue['locationid']}: {len(rows)} row(s) for "
            f"{venue['name']}, none parseable ({skipped_broken} with no readable "
            f"startTime/startDate, {skipped_upcoming} upcoming-only). The row schema "
            f"changed; this is a parser break, not an empty programme")
    if untitled:
        print(f"[{site['provider']}] {venue['name']}: {untitled} row(s) with no title, "
              f"dropped")
    shows.sort(key=lambda s: s["start"])
    return shows


def unclaimed(payload, venues):
    """Rooms in the payload that no venue's `rooms` list owns. -> {(id, title): count}

    Only meaningful where at least one venue filters by room; a plain site has one
    venue that takes everything. This is how a new town shows up: Kino Metso added
    Tikkakoski between two probes, and rows nobody owns must be loud in the committed
    log rather than silently unpublished.
    """
    roomed = [v for v in venues if v.get("rooms")]
    if not roomed:
        return {}
    owned = {str(x) for v in roomed for x in v["rooms"]}
    groups = payload.get("shows") or {}
    rows = [r for v in groups.values() for r in v] if isinstance(groups, dict) else list(groups)
    out = {}
    for r in rows:
        rid = str(r.get("roomId") or "")
        if rid and rid not in owned:
            key = (rid, (r.get("roomTitle") or "?").strip())
            out[key] = out.get(key, 0) + 1
    return out


def orphaned(payload, venues):
    """Rows on a room-split locationid when no venue's `rooms` owns one of them. -> count

    0 wherever a venue takes every row or the payload has none. One town owning nothing
    is a town between visits; every town owning nothing while rows exist is not.
    """
    roomed = bool(venues) and all(v.get("rooms") for v in venues)
    if not roomed or not isinstance(payload, dict):
        return 0
    owned = {str(x) for v in venues for x in v["rooms"]}
    groups = payload.get("shows") or {}
    rows = [r for v in groups.values() for r in v] if isinstance(groups, dict) else list(groups)
    if any(str(r.get("roomId") or "") in owned for r in rows):
        return 0
    return len(rows)


def fetch_payload(site, locationid, days=21, tries=3):
    """One locationid's decoded payload. Retry with backoff: the host answers 403
    when hit too often in a short window.

    backoff=6 is kept rather than common's 5: this is the one adapter whose retry
    exists to wait out a rate limit rather than a transient fault, so the longer
    gap is the point. Only the request is retried, not the parse.
    """
    headers = {"user-agent": UA, "accept": "application/json",
               "accept-language": "fi-FI,fi;q=0.9",
               "referer": f"{site['base']}{site['programme']}?location={locationid}"}
    body = fetch(api_url(site, locationid, days), headers=headers, cache=True,
                 tries=tries, backoff=6)
    return json.loads(body.decode("utf-8", "replace"))


def fetch_venue(site, venue, days=21, tries=3):
    return parse(fetch_payload(site, venue["locationid"], days, tries), site, venue)


def fetch_site(site, sleep=2.5):
    out = {}
    answered = shows = 0
    # Venues sharing a locationid ride one request: Kino Metso is four venues on
    # locationid 2, and asking four times for one payload is three wasted requests
    # at someone else's expense.
    by_loc = {}
    for v in site["venues"]:
        by_loc.setdefault(v["locationid"], []).append(v)
    for loc, venues in by_loc.items():
        try:
            payload = fetch_payload(site, loc)
        except Exception as e:
            print(f"[{site['provider']}] locationid {loc} FAILED: {e}")
            time.sleep(sleep)
            continue
        lost = orphaned(payload, venues)
        if lost:
            # Not caught per venue: every venue here would come back [] and be vouched
            # empty, or the site would read as having nothing on.
            seen = ", ".join(f"{r} {t!r}" for r, t in sorted(unclaimed(payload, venues)))
            raise RuntimeError(
                f"{site['base']} locationid {loc}: {lost} row(s) and not one in a room a "
                f"venue owns (rooms seen: {seen}). The roomIds moved; this is a mapping "
                f"break, not an empty programme")
        stray = unclaimed(payload, venues)
        for v in venues:
            try:
                got = parse(payload, site, v)
                if not got and v.get("rooms") and stray:
                    # A moved roomId and a new town beside one between visits look the
                    # same here: rows exist that could be this town's. Left out, so its
                    # previous file stands rather than being vouched empty.
                    raise RuntimeError(
                        f"no row in rooms {', '.join(v['rooms'])} while room(s) "
                        f"{', '.join(r for r, _ in sorted(stray))} carry rows no venue "
                        f"owns, so this town is not shown to be empty")
                out[v["id"]] = got
                answered += 1
                shows += len(out[v["id"]])
                print(f"[{site['provider']}] {v['name']} ({v['city']}): {len(out[v['id']])} showtimes")
            except Exception as e:
                print(f"[{site['provider']}] {v['name']} FAILED: {e}")
        for (rid, title), n in sorted(unclaimed(payload, venues).items()):
            print(f"[{site['provider']}] unclaimed room {rid} \"{title}\": "
                  f"{n} showtime(s) not published -- add a venue or a rooms entry")
        time.sleep(sleep)
    # Every locationid answered with valid JSON and not one of them listed a show. That
    # is a cinema between programmes, not a broken parse -- four Nexxo hosts sit in
    # exactly this state permanently. If any request failed, `answered` is short and this
    # stays a normal failure, because then we do not know what the site holds.
    if answered == len(site["venues"]) and not shows:
        raise common.EmptyProgramme(
            f"{site['base']} answered for {answered} locationid(s) and listed no shows")
    return out
