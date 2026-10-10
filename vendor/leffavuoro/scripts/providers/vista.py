"""Vista public XML web services — a *platform*, not a site.

Vista is the ticketing platform Finnkino also runs. A site that leaves its /xml/ services
open needs no auth (Korjaamo Kino today, Savon Kinot before 2026-08-30), so any such
cinema is a `SITES` entry here with a base URL and its venue list, no new parser. Check
`{base}/xml/TheatreAreas/` before adding one. Finnkino's own host answers a plain client
with a Cloudflare challenge (403, `cf-mitigated: challenge`, probed 2026-09-13) and is
read through OCAPI with a token by `fetch_data.py` instead; its /xml/ was never probed
past the challenge.

    GET {base}/xml/TheatreAreas/                     -> ID + Name per area
    GET {base}/xml/Schedule/?area={id}&nrOfDays=31    -> every Show in the window
    GET {base}/xml/ScheduleDates/                    -> the published date list
    GET {base}/xml/Events/                           -> per-film synopsis and credits

Notes from probing savonkinot.fi (2026-08-27):
- `nrOfDays=31` is honoured, so **one request per area** covers the whole published
  window (8 days in practice). Areas map to one or two theatres each, and the response
  carries `TheatreID`, so venues are split from the data rather than by request.
- A one-day fetch is not enough: Kitee had zero shows today and seven in the window.
- No auth, no Cloudflare, and a datacenter IP works, unlike Finnkino's own OCAPI. This
  runs on Actions.
- `Rating` is "K-7 (4)" or "Sallittu kaikenikäisille", not Finnkino's bare "K-7", so it
  needs normalising or the kids filter in the client silently stops matching.
- Times come as both local and UTC. Parse the UTC one and convert, so DST is never our
  problem.
- `SubtitleLanguage2` can carry a Name with an empty ISOTwoLetterCode, so fall back to
  mapping the Finnish language name.

Notes from probing korjaamokino.fi (2026-09-05):
- The same four endpoints answer **JSON by default** and XML when the request says
  `Accept: application/xml` (or `?format=xml`). `get()` has always sent an XML accept
  header, so the parser saw XML from the first request and nothing here changed.
- One area (1007 "Korjaamo"), one theatre (1045 "Korjaamo Kino"), one auditorium
  named "Sali". `_aud` blanks that bare word: a room name that only says "the hall"
  tells a reader nothing beside the time.
- `Rating` reads "Ei tiedossa" on most shows, with an empty `RatingLabel` beside it.
  That is "not known", not a rating, and `_rating` maps it to "" so the client shows
  nothing rather than the phrase.
- `Images` is empty on every show, so posters come from TMDB.
- `EventSeries` carries the festival a screening belongs to ("HelAFF"); it lands in
  `method` beside `PresentationMethod`, as it did for Savon Kinot.
- A non-residential fetcher received the schedule, so the site runs on Actions.
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import html as html_mod

import prices
from common import fetch, syn_language

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

# Savon Kinot, the first site here, moved to eTiketti on 2026-08-30 and its entry lives
# in etiketti.py; the module sat with no sites until Korjaamo Kino (2026-09-05). The
# 103-host sweep of 2026-08-29 that found no other Finnish Vista site never probed
# korjaamokino.fi. `theatre` is the Schedule's TheatreID and `area` the TheatreAreas ID,
# both read off the endpoints rather than assumed.
KORJAAMO = {"id": "korjaamo-helsinki", "provider": "korjaamo", "providerId": "1045",
            "theatre": "1045", "area": "1007",
            "name": "Korjaamo Kino", "short": "Korjaamo Kino", "city": "Helsinki"}

SITES = [{"provider": "korjaamo", "label": "Korjaamo Kino",
          "base": "https://korjaamokino.fi", "venues": [KORJAAMO],
          # The public ticket page a showtime links to; see ordinary_price().
          "tickets": "https://korjaamokino.fi/websales/show/"}]

# ---------------------------------------------------------------- prices

# Vista's websales "Select tickets" page lists one <li class="ticket-list__item"> per
# category with a `ticket-list__label` and a `ticket-list__price` ("14,00 €"). The
# categories are per screening and carry no fixed ordinary name (a festival screening
# sells "HelAFF"), so the rule is by exclusion: drop the restricted categories by name,
# and the remaining ones must agree on one amount. Probed 2026-09-13 on two Korjaamo
# screenings: "HelAFF 14,00 €" alone, and "HelAFF" plus "Pyörätuolipaikka" at the same
# amount. The fetch, cache and pacing are prices.py's.
ITEM_RE = re.compile(r'<li class="ticket-list__item"[^>]*>(.*?)</li>', re.S)
LABEL_RE = re.compile(r'class="ticket-list__label[^"]*"[^>]*>(.*?)</p>', re.S)
PRICE_RE = re.compile(r'class="ticket-list__price"[^>]*>(.*?)</span>', re.S)
AMOUNT_RE = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:\u20ac|EUR)", re.I)
# Stems, so "Lasten lippu (alle 10v.)", "Eläkeläislippu" and "Opiskelijalippu" all match.
# Measured 2026-09-13 on a regular Korjaamo screening: Normaali lippu 13,00 € beside
# Eläkeläislippu, Opiskelijalippu and Lasten lippu at 11,00 €.
RESTRICTED_RE = re.compile(r"py\u00f6r\u00e4tuoli|avustaja|opiskelija|laps|lasten|el\u00e4kel|senior"
                           r"|klubi|j\u00e4sen|alennus|varhais|kanta|ty\u00f6t\u00f6n|veteraani"
                           r"|varusmies|nuoriso|juniori|ryhm\u00e4|sarja|lahja",
                           re.I)


def _text(x):
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


def ordinary_price(page_html):
    """The unrestricted ticket price on a websales page -> "14\u20ac" or "".

    "" when no unrestricted category is listed or the unrestricted ones disagree; a
    restricted category alone is never the advertised price.
    """
    amounts = []
    for item in ITEM_RE.findall(page_html or ""):
        label, price = LABEL_RE.search(item), PRICE_RE.search(item)
        if not (label and price) or RESTRICTED_RE.search(_text(label.group(1))):
            continue
        m = AMOUNT_RE.search(_text(price.group(1)))
        if m:
            amounts.append(m.group(1))
    return prices.one_amount(amounts) if amounts else ""

# Finnkino's tag set, so one language filter works across every provider.
ISO = {"fi": "FI", "en": "EN", "sv": "SV", "se": "SV", "ja": "JA", "fr": "FR",
       "de": "DE", "es": "ES", "it": "IT", "ru": "RU", "da": "DA", "no": "NO",
       "et": "ET", "pl": "PL"}
NAMES = {"suomi": "FI", "englanti": "EN", "ruotsi": "SV", "japani": "JA",
         "ranska": "FR", "saksa": "DE", "espanja": "ES", "italia": "IT",
         "venäjä": "RU", "tanska": "DA", "norja": "NO", "viro": "ET", "puola": "PL",
         "arabia": "AR"}
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(node, *path):
    for tag in path:
        if node is None:
            return ""
        node = node.find(tag)
    return (node.text or "").strip() if node is not None else ""


def _code(node, tag):
    """Language code from a SpokenLanguage / SubtitleLanguageN node."""
    sub = node.find(tag)
    if sub is None:
        return ""
    iso = (_txt(sub, "ISOTwoLetterCode") or "").lower()
    if iso in ISO:
        return ISO[iso]
    return NAMES.get((_txt(sub, "Name") or "").lower(), "")


def _lang(show):
    """-> "EN-A, FI-S, SE-S". Audio first, then each subtitle track."""
    out = []
    a = _code(show, "SpokenLanguage")
    if a:
        out.append(a + "-A")
    for tag in ("SubtitleLanguage1", "SubtitleLanguage2"):
        s = _code(show, tag)
        if s and s + "-S" not in out:
            out.append(s + "-S")
    return ", ".join(out)


def _rating(v):
    """"K-7 (4)" -> "K-7", "Sallittu kaikenikäisille" -> "S", "Ei tiedossa" -> ""."""
    v = (v or "").strip()
    if not v or v.lower().startswith("ei tiedossa"):
        # Korjaamo publishes "Ei tiedossa" with an empty RatingLabel for a film KAVI has
        # not classified yet. It is the absence of a rating, so it must not reach the
        # client as one: an unknown string there is rendered as a tag.
        return ""
    if v.lower().startswith(("sallittu", "s ")) or v.upper() == "S":
        return "S"
    m = re.search(r"K[-\s]?(\d+)", v)
    return f"K-{m.group(1)}" if m else v


def _start(show):
    """UTC in, Helsinki ISO out, so DST is the library's problem and not ours."""
    raw = _txt(show, "dttmShowStartUTC")
    if raw:
        t = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return t.astimezone(FI).isoformat()
    local = _txt(show, "dttmShowStart")          # fallback: assume it is already local
    if not local:
        return ""
    return datetime.fromisoformat(local).replace(tzinfo=FI).isoformat()


def _aud(show, venue):
    """"Joensuu, Tapio 4" -> "Tapio 4". Blank when it only repeats the venue name, and
    blank for a bare "Sali": a one-screen cinema's room called "the hall" adds nothing
    beside the time, the same way Orion and Heureka publish no room."""
    raw = _txt(show, "TheatreAuditorium")
    name = raw.split(",", 1)[1].strip() if "," in raw else raw.strip()
    return "" if name.lower() in (venue["short"].lower(), "sali") else name


def _https(url):
    return re.sub(r"^http://", "https://", (url or "").strip())


def get(url, tries=3, timeout=40):
    """Vista's XML web services. The 40 s timeout is passed through rather than left to
    common's 30 s default: a whole area's Schedule response is large and slow."""
    return fetch(url, cache=True,
                 headers={"user-agent": UA, "accept": "application/xml, text/xml, */*"},
                 tries=tries, timeout=timeout).decode("utf-8", "replace")


def parse_schedule(xml_text, site, venues):
    """-> {venue_id: [show, ...]} for the venues present in this area's response."""
    per_venue = {}
    by_theatre = {v["theatre"]: v for v in venues}
    root = ET.fromstring(xml_text)
    shows = root.find("Shows")
    for s in (shows if shows is not None else []):
        venue = by_theatre.get(_txt(s, "TheatreID"))
        if not venue:
            continue        # another theatre in the same area that we do not list
        start = _start(s)
        if not start:
            continue
        img = _https(_txt(s, "Images", "EventMediumImagePortrait")
                     or _txt(s, "Images", "EventSmallImagePortrait"))
        # " · " is the separator every other adapter writes and the one the client
        # splits on. Joined with ", " the pair "2D, HelAFF" was one tag the client could
        # neither drop as 2D nor read as the festival strand.
        method = " · ".join(x for x in (_txt(s, "PresentationMethod"),
                                        _txt(s, "EventSeries")) if x)
        per_venue.setdefault(venue["id"], []).append({
            "eventId": _txt(s, "EventID"),
            "title": _txt(s, "Title"),
            "original": _txt(s, "OriginalTitle"),
            "len": _txt(s, "LengthInMinutes"),
            "rating": _rating(_txt(s, "Rating")),
            "genres": _txt(s, "Genres"),
            "method": method,
            "theatre": venue["name"],
            "aud": _aud(s, venue),
            "start": start,
            "url": _https(_txt(s, "ShowURL")),
            "img": img,
            "lang": _lang(s),
            "soldOut": False,          # seat counts are not in the public XML
            "price": "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    return per_venue


def synopses(xml_text):
    """-> {EventID: finnish synopsis}. Tag names vary between Vista versions, so try a
    few and treat a miss as "no synopsis" rather than an error: TMDB fills the gap."""
    out = {}
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    for e in root.iter("Event"):
        eid = _txt(e, "ID")
        if not eid:
            continue
        for tag in ("Synopsis", "ShortSynopsis", "SynopsisShort", "Description"):
            text = _txt(e, tag)
            if text:
                out[eid] = TAGS_RE.sub(" ", text).replace("&nbsp;", " ").strip()
                break
    return out


def fetch_site(site, sleep=1.5, price_sleep=1.0, prices_path=None, now=None):
    base = site["base"].rstrip("/")
    days = site.get("days", 31)
    venues = site["venues"]

    syn = {}
    try:
        syn = synopses(get(f"{base}/xml/Events/"))
    except Exception as e:
        print(f"[{site['provider']}] Events unavailable, TMDB will cover it: {e}")

    per_venue = {}
    areas = []
    for v in venues:                    # preserve order, one request per distinct area
        if v["area"] not in areas:
            areas.append(v["area"])
    for area in areas:
        here = [v for v in venues if v["area"] == area]
        xml_text = get(f"{base}/xml/Schedule/?area={area}&nrOfDays={days}")
        for vid, shows in parse_schedule(xml_text, site, here).items():
            per_venue.setdefault(vid, []).extend(shows)
        time.sleep(sleep)

    # The feed carries no language per text, and ten Korjaamo synopses in the Finnish
    # slot were English (traced 2026-09-24). Placed per text, as Gilda's are; a text no
    # language settles is withheld and TMDB fills the slot.
    langs = {eid: syn_language(text) for eid, text in syn.items()}
    for shows in per_venue.values():
        for s in shows:
            text = syn.get(s["eventId"])
            if text and langs[s["eventId"]]:
                s["_syn"] = {langs[s["eventId"]]: text}
    if site.get("tickets"):
        prices.run([s for v in per_venue.values() for s in v], provider=site["provider"],
                   prefix=site["tickets"], parse=ordinary_price, referer=base + "/",
                   path=prices_path, now=now, sleep=price_sleep,
                   fetch_fn=lambda url, headers: get(url, tries=2, timeout=20))
    return per_venue


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:               # offline: parse a saved Schedule response
        body = open(sys.argv[1], encoding="utf-8", errors="replace").read()
        res = parse_schedule(body, SITES[0], SITES[0]["venues"])
    else:
        res = fetch_site(SITES[0])
    for vid, shows in sorted(res.items()):
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:3]:
            print(f"   {s['start'][:16]}  {s['title'][:30]:32} {s['rating']:5} "
                  f"{s['aud']:12} {s['lang']}")
    print(json.dumps(next(iter(res.values()))[0], ensure_ascii=False, indent=1))
