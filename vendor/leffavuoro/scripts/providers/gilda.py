"""Gilda (Helsinki: Gilda salit 1-3, Bio Rex Lasipalatsi) — MyCloudCinema behind a
WordPress REST facade.

The listing is a React app whose config the page prints for anonymous visitors, so the
API needs no auth:

    GET {base}/wp-json/gilda-react-booking/v1/movies
    -> {"fi": {"data": [ {film..., show_times:[...]} ], "resultCode": 0}}

One request covers every film and showtime (35 films / 101 shows / 22 dates when probed).
The namespace also holds write and administrative routes. They are closed to anonymous
callers, are never called, and are not listed here.

Venues split by **cinema_screen_id**, not by cinema: there is one cinema_id (15) whose
screens 66/67/68 are Gilda 1-3 and screen 69 is the separate Bio Rex Lasipalatsi house.
Add another MyCloudCinema site as a SITES entry once its apiUrl and screen ids are known.

Notes from the fixture (2026-08-27):
- `rating_name` is bare: "12", "16", "S", plus "T" and "EI MÄÄR." for unrated. Map to the
  Finnkino-style tags the client filters on, and leave unrated blank.
- `screen_name` for Lasipalatsi carries "(K-18)", a venue door policy rather than a film
  rating. Strip it or every show there looks adults-only.
- `subtitle_lang` mixes Finnish words ("suomi, ruotsi"), ISO-ish codes ("FI", "SE") and
  "-" for none. `audio_lang` is always a code.
- `show_time` is UTC with a +00:00 offset; convert to Europe/Helsinki.
- Posters are a bare uuid; the React bundle names the host.
"""
import html as html_mod
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from common import capped, fetch, get_text, syn_language
import synmerge

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

SITES = [{
    "provider": "gilda",
    "label": "Gilda",
    "base": "https://www.gilda.fi",
    "api": "/wp-json/gilda-react-booking/v1",
    "listing": "/elokuvat/",
    # Per-film pages live at /elokuva/{slug}/ as WordPress posts of type `movies`.
    # The booking API carries no slug and no permalink, so the mapping comes from the
    # WP REST list and is matched on the title.
    "posts": "/wp-json/wp/v2/movies",
    # MyCloudCinema poster path is {host}/media/posters/{movie_id}/{width}/{uuid}.
    # Only width 1080 exists; 720 and 500 are 404. The same shape serves BioRex
    # (web.biorex.mycloudcinema.com), which is how it was found after a bare
    # /media/posters/{uuid} guess from the React bundle returned 404 for every film.
    "posters": "https://web.atlanticfilm.mycloudcinema.com/media/posters",
    "poster_width": 1080,
    "venues": [
        # Kamppi (Narinkka 2) is how people locate it, and "Gilda Gilda" would be the
        # label otherwise: the client prefixes the chain onto `short` unless it already
        # starts with it.
        {"id": "gd-gilda", "screens": [66, 67, 68],
         "name": "Gilda Kamppi", "short": "Kamppi", "city": "Helsinki"},
        {"id": "gd-lasipalatsi", "screens": [69],
         "name": "Bio Rex Lasipalatsi", "short": "Bio Rex Lasipalatsi",
         "city": "Helsinki"},
    ],
}]

LANG = {"fi": "FI", "suomi": "FI", "en": "EN", "englanti": "EN", "sv": "SV",
        "se": "SV", "ruotsi": "SV", "ja": "JA", "japani": "JA", "fr": "FR",
        "ranska": "FR", "de": "DE", "saksa": "DE", "es": "ES", "espanja": "ES",
        "it": "IT", "italia": "IT", "ru": "RU", "venäjä": "RU", "da": "DA",
        "no": "NO", "et": "ET", "viro": "ET", "pl": "PL", "puola": "PL"}
# version_* flags worth showing as a format pill; the rest are noise
FORMATS = {"version_70mm": "70mm", "version_35mm": "35mm", "version_16mm": "16mm",
           "version_imax": "IMAX", "version_3d": "3D", "version_4k": "4K",
           "version_atmos": "Atmos", "version_luxe": "LUXE", "version_dbox": "D-BOX",
           "version_hfr": "HFR"}
TAGS_RE = re.compile(r"<[^>]+>")
ENTITIES = {"&#8211;": "-", "&#8217;": "'", "&#039;": "'", "&#8216;": "'",
            "&amp;": "&", "&nbsp;": " "}


def _key(title):
    """Loose title key for matching a film to its WordPress post."""
    t = TAGS_RE.sub(" ", title or "")
    for k, v in ENTITIES.items():
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def _code(token):
    t = (token or "").strip().lower()
    return LANG.get(t, t.upper() if re.fullmatch(r"[a-zäöå]{2}", t) else "")


# A screening without subtitles, `XX-S` as at Kino Engel: the audio style "Ei tekstitystä"
# with `subtitle_lang` "-". Read 2026-10-04 that pair held on 18 of 21 screenings carrying
# the style; the other three, The Lighthouse, name "suomi, ruotsi", and keep them.
NO_SUBS_STYLE = "ei tekstityst\u00e4"


def _lang(show):
    """-> "EN-A, FI-S, SE-S" using Finnkino's tags, so one filter serves every provider."""
    out = []
    a = _code(show.get("audio_lang"))
    if a:
        out.append(a + "-A")
    raw = (show.get("subtitle_lang") or "").strip()
    style = (show.get("movie_audio_style_name") or "").strip().lower()
    if raw in ("", "-") and style == NO_SUBS_STYLE:
        out.append("XX-S")
    if raw and raw != "-":
        for part in re.split(r"[,/]", raw):
            s = _code(part)
            if s and s + "-S" not in out:
                out.append(s + "-S")
    return ", ".join(out)


def _rating(show):
    """"12" -> "K-12", "S"/"T" -> "S", "EI MÄÄR." -> "" (unrated, say nothing)."""
    v = (show.get("rating_name") or "").strip()
    if not v or v.upper().startswith(("EI M", "EI_M")):
        return ""
    if v.upper() in ("S", "T"):
        return "S"
    m = re.search(r"(\d+)", v)
    return f"K-{m.group(1)}" if m else ""


def _start(show):
    raw = (show.get("show_time") or "").strip()
    if not raw:
        return ""
    t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    # A value with no offset is Helsinki wall time. `astimezone` would read it in the
    # host's zone, three hours off on a UTC runner.
    if t.tzinfo is None:
        t = t.replace(tzinfo=FI)
    return t.astimezone(FI).isoformat()


def _aud(show, venue):
    """"Bio Rex Lasipalatsi (K-18)" -> "": the (K-18) is a door policy for that venue,
    not this film's rating, and a single-screen house whose screen name repeats the venue
    name must render blank or the stub reads "Bio Rex Lasipalatsi · Bio Rex Lasipalatsi".
    "Gilda 3" is kept, since it distinguishes one of three screens."""
    name = re.sub(r"\s*\(K-?\d+\)\s*$", "", (show.get("screen_name") or "").strip())
    low = name.lower()
    if low in (venue["short"].lower(), venue["name"].lower()):
        return ""
    return name


def _method(show):
    out = [label for flag, label in FORMATS.items() if show.get(flag)]
    style = (show.get("movie_audio_style_name") or "").strip()
    if style and style.lower() not in ("tekstitetty", "ei tekstitystä"):
        out.append(style)          # e.g. a dub tag; the plain cases are already in lang
    return " · ".join(out)         # the client's tag separator; ", " made one tag of two


def get(url, tries=3, timeout=45):
    """MyCloudCinema REST, JSON. 45 s is passed through rather than left to common's
    30 s default: /movies returns the whole programme in one response.

    A malformed body still raises out of json.loads without a retry, same as before:
    common.fetch retries the request, not the parse, and a site answering 200 with
    non-JSON is a shape change to look at rather than a transient to sit out."""
    return json.loads(fetch(url, cache=True,
                            headers={"user-agent": UA, "accept": "application/json"},
                            tries=tries, timeout=timeout).decode("utf-8", "replace"))


def film_pages(site, tries=3):
    """-> {title key: permalink} for every /elokuva/{slug}/ page.

    Paginated at 100. A failure here is not fatal: showtimes fall back to the
    programme listing, which is what every show used before this existed.
    """
    base = site["base"].rstrip("/") + site.get("posts", "")
    out = {}
    for page in range(1, 6):
        url = f"{base}?per_page=100&page={page}&_fields=link,title"
        try:
            chunk = get(url, tries=tries)
        except Exception as e:
            if page == 1:
                print(f"[{site['provider']}] film pages unavailable: {e}")
            break
        if not isinstance(chunk, list) or not chunk:
            break
        for post in chunk:
            k = _key((post.get("title") or {}).get("rendered"))
            if k and k not in out:
                out[k] = post.get("link") or ""
        if len(chunk) < 100:
            break
    return out


DESC_RE = re.compile(r'<div class="single-movie__description">(.*?)</div>', re.S)
H2_RE = re.compile(r"<h2\b.*?</h2>", re.S)


def _page_for(s, film, pages):
    return (pages.get(_key(s.get("movie_name") or film.get("movie_name")))
            or pages.get(_key(s.get("original_title"))) or "")


def _feed_syn(film):
    return synmerge.drop_notes_html(film.get("description") or "", names=("Gilda",))


def _untitled(text, film):
    """`text` without the film's own titles. An English title inside a Finnish blurb reads
    as English to syn_language: "70mm: The Odyssey" and "The Lighthouse" placed nowhere
    (2026-09-28). Used only to judge the language; the text is published as it was."""
    shows = film.get("show_times") or []
    titles = {film.get("movie_name")} | {s.get(k) for s in shows
                                         for k in ("movie_name", "original_title")}
    titles |= {t.split(": ", 1)[1] for t in titles if t and ": " in t}
    for t in sorted((t for t in titles if t and len(t) > 2), key=len, reverse=True):
        text = re.sub(re.escape(t), " ", text, flags=re.I)
    return text


def undescribed(payload, pages):
    """-> [film page] for each film whose feed description is empty."""
    out = []
    for film in (payload.get("fi") or {}).get("data") or []:
        if _feed_syn(film):
            continue
        for s in film.get("show_times") or []:
            page = _page_for(s, film, pages)
            if page and page not in out:
                out.append(page)
    return out


def page_syn(page):
    """{lang: text} from a film page's description block. Placed whole like the feed's
    text; a block no language settles keeps only its paragraphs placed Finnish, the page's
    language, which leaves out Pitchblack Playback's English press quotes and arrival note
    (2026-09-27)."""
    m = DESC_RE.search(page or "")
    if not m:
        return {}
    body = H2_RE.sub("", m.group(1))
    whole = synmerge.drop_notes_html(body, names=("Gilda",))
    lang = syn_language(whole)
    if lang:
        return {lang: whole}
    fi = [t for t in (synmerge.drop_notes_html(p, names=("Gilda",))
                      for p in re.split(r"</p\s*>", body)) if syn_language(t) == "fi"]
    return {"fi": " ".join(fi)} if fi else {}


def parse(payload, site, pages=None, texts=None):
    """-> {venue_id: [show, ...]}. `texts` is page_syn() by film page, for a film the feed
    describes with nothing."""
    by_screen = {}
    for v in site["venues"]:
        for sid in v["screens"]:
            by_screen[int(sid)] = v
    base = site["base"].rstrip("/")
    listing = base + site.get("listing", "/")
    posters = site.get("posters", "").rstrip("/")
    width = site.get("poster_width", 1080)

    pages = pages or {}
    doc = (payload.get("fi") or {}).get("data") or []
    per_venue = {}
    # The feed lists a film twice. Read on 2026-09-07 it held 39 film records for 33
    # distinct `movie_id`s: six films appeared as two copies that differ in one field,
    # `premiere`, and each copy carried the same `show_times`. Both copies parsed, so 44
    # of 183 rows were repeats and the app drew each as its own stub -- "Presidentin
    # kyyditys" showed twice at 14:40 in Gilda 3 on 12 September. Nothing here reads
    # `premiere`, so the copies are interchangeable, and the guard is on the screening
    # rather than the record: venue, start, film and auditorium identify one screening,
    # whatever shape the feed arrives in.
    seen = set()
    dropped = 0
    for film in doc:
        poster = (film.get("movie_poster") or "").strip()
        mid = film.get("movie_id")
        img = (f"{posters}/{mid}/{width}/{poster}"
               if (posters and poster and mid) else "")
        # description is HTML with entities and paragraphs. A senior screening opens
        # with a paragraph of Gilda's own -- the first Tuesday, 9 EUR, coffee included --
        # before the distributor's blurb, and a screening sometimes carries the plain film
        # title, so that paragraph reached the synopsis every cinema showing the film
        # reads (Cinema Niagara displayed Gilda's price for "Keltaiset kirjeet"). Drop the
        # paragraphs that quote a price or name Gilda; keep the rest, unescaped, or the
        # synopsis renders as "Almod&oacute;var" in the movie sheet.
        syn = _feed_syn(film)
        # The feed is keyed "fi" and carries no language per text, yet 6 of 36
        # descriptions were English on 2026-09-24. Placed per text; unplaceable is withheld.
        lang = syn_language(syn) or syn_language(_untitled(syn, film))
        for s in film.get("show_times") or []:
            if s.get("deleted") or not s.get("show_is_visible", 1):
                continue
            venue = by_screen.get(int(s.get("cinema_screen_id") or 0))
            start = _start(s)
            if not venue or not start:
                continue
            # The film page, matched on its own title then the original title. That
            # second rule is what resolves a Finnish release title to an
            # English-slugged post ("Maailman rikkain nainen" ->
            # /elokuva/the-richest-woman-in-the-world-2/). No fuzzy matching: a
            # near-miss sends people to the wrong film, the fallback only costs a click.
            page = _page_for(s, film, pages)
            row = {
                "eventId": str(film.get("movie_id") or s.get("movie_id") or ""),
                "title": (s.get("movie_name") or film.get("movie_name") or "").strip(),
                "original": (s.get("original_title") or "").strip(),
                "len": str(s.get("running_time") or ""),
                "rating": _rating(s),
                "genres": (film.get("genre") or "").strip(),
                "method": _method(s),
                "theatre": venue["name"],
                "aud": _aud(s, venue),
                "start": start,
                "url": page or listing,
                "img": img,
                "lang": _lang(s),
                "soldOut": False,    # seat counts need the closed seatplan endpoint
                "price": "",
                "provider": site["provider"],
                "venue": venue["id"],
            }
            if lang:
                row["_syn"] = {lang: syn}
            elif not syn and (texts or {}).get(page):
                row["_syn"] = texts[page]
            key = (venue["id"], start, row["eventId"], row["aud"])
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            per_venue.setdefault(venue["id"], []).append(row)
    if dropped:
        print(f"[{site['provider']}] dropped {dropped} duplicate showtime(s)")
    return per_venue


def fetch_site(site, sleep=1.5):
    url = site["base"].rstrip("/") + site.get("api", "") + "/movies"
    payload = get(url)
    pages = film_pages(site)
    print(f"[{site['provider']}] film pages indexed: {len(pages)}")
    texts = {}
    for page in capped(undescribed(payload, pages), site["provider"]):
        time.sleep(sleep)
        try:
            texts[page] = page_syn(get_text(page, fetcher=fetch))
        except Exception as e:
            print(f"[{site['provider']}] film page unavailable: {page}: {e}")
    if texts:
        print(f"[{site['provider']}] film pages read for a synopsis: {len(texts)}, "
              f"placed: {sum(1 for v in texts.values() if v)}")
    return parse(payload, site, pages, texts)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pages = {}
        if len(sys.argv) > 2:      # offline: a saved wp/v2/movies dump
            for post in json.load(open(sys.argv[2], encoding="utf-8")):
                pages.setdefault(_key((post.get("title") or {}).get("rendered")),
                                 post.get("link") or "")
        res = parse(json.load(open(sys.argv[1], encoding="utf-8")), SITES[0], pages)
    else:
        res = fetch_site(SITES[0])
    for vid, shows in sorted(res.items()):
        days = sorted({s["start"][:10] for s in shows})
        print(f"{vid}: {len(shows)} showtimes, {len(days)} dates -> {days[-1]}")
        for s in sorted(shows, key=lambda x: x["start"])[:3]:
            print(f"   {s['start'][:16]}  {s['title'][:28]:30} {s['rating']:5} "
                  f"{s['aud'][:20]:22} {s['lang']}")
