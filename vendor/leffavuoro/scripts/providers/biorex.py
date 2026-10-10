"""BioRex provider: WordPress admin-ajax, no auth. Stdlib only.

Venue selection is cookie-based: POST location={id} to /teatterin-valinta/ first.
Without that cookie the ajax endpoint silently returns BioRex Verkatehdas, so a
missing session yields wrong data rather than an error.
"""
import html as html_mod
import http.cookiejar, json, re, time, urllib.parse, urllib.request

from common import capped, fetch, make_opener

BASE = "https://biorex.fi"
AJAX = BASE + "/wp-admin/admin-ajax.php?lang=fi"
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

VENUES = [
    {"id": "br-tripla",      "providerId": "13", "name": "BioRex Tripla",      "short": "Tripla",      "city": "Helsinki"},
    {"id": "br-redi",        "providerId": "14", "name": "BioRex Redi",        "short": "Redi",        "city": "Helsinki"},
    {"id": "br-verkatehdas", "providerId": "1",  "name": "BioRex Verkatehdas", "short": "Verkatehdas", "city": "Hämeenlinna"},
    {"id": "br-sveitsi",     "providerId": "9",  "name": "BioRex Sveitsi",     "short": "Sveitsi",     "city": "Hyvinkää"},
    {"id": "br-kajaani",     "providerId": "7",  "name": "BioRex Kajaani",     "short": "Kajaani",     "city": "Kajaani"},
    {"id": "br-pietarsaari", "providerId": "4",  "name": "BioRex Pietarsaari", "short": "Pietarsaari", "city": "Pietarsaari"},
    {"id": "br-porvoo",      "providerId": "10", "name": "BioRex Porvoo",      "short": "Porvoo",      "city": "Porvoo"},
    {"id": "br-riihimaki",   "providerId": "8",  "name": "BioRex Riihimäki",   "short": "Riihimäki",   "city": "Riihimäki"},
    {"id": "br-rovaniemi",   "providerId": "2",  "name": "BioRex Rovaniemi",   "short": "Rovaniemi",   "city": "Rovaniemi"},
    {"id": "br-seinajoki",   "providerId": "12", "name": "BioRex Seinäjoki",   "short": "Seinäjoki",   "city": "Seinäjoki"},
    {"id": "br-tornio",      "providerId": "3",  "name": "BioRex Tornio",      "short": "Tornio",      "city": "Tornio"},
    {"id": "br-vaasa",       "providerId": "5",  "name": "BioRex Vaasa",       "short": "Vaasa",       "city": "Vaasa"},
]

# One platform, one site: a single set of requests covers every venue, so the runner's
# site list is just VENUES. See run.py for the contract.
#
# `base` names the host this site is read from, which is the runner's pacing key. Nothing
# in this module reads it -- fetch_venue builds every URL from BASE above -- and it was
# absent until 2026-09-15, when `run_cloud.py` started grouping hosts across modules: a
# site with no `base` shares one group with every other base-less site, and BioRex and
# Cinema Orion, the two heaviest single-site modules, would have been read one after the
# other for no reason. Verified before it was written: the three requests fetch_venue
# makes are BASE + a literal path, all on biorex.fi. The film pages are a href the ajax
# fragment carried and are not bounded by this, which was as true of the per-module pool.
SITES = [{"provider": "biorex", "label": "BioRex", "base": BASE, "venues": VENUES}]

# Note: the wrapper class carries a trailing space -> 'showtime-item '
ITEM_RE = re.compile(r'<div class="showtime-item\s*">(.*?)(?=<div class="showtime-item\s*">|\Z)', re.S)
# Double-quoted with &quot;-escaped JSON inside.
DL_RE = re.compile(r'data-click-data-layer="([^"]+)"')
# Attributes are newline-separated and href comes before class, so match the URL directly.
HREF_RE = re.compile(r'href="(https://biorex\.fi/secure-redirect/[^"]+)"')
PLACE_RE = re.compile(r'class="showtime-item__place__value">\s*(.*?)\s*</div>', re.S)
RATING_RE = re.compile(r'class="showtime-item__movie-rating">\s*\(?([^)<]*?)\)?\s*</span>', re.S)
FORMAT_RE = re.compile(r'class="showtime-item__format">(.*?)</span>', re.S)
SRCSET_RE = re.compile(r'data-srcset="([^"]+)"')
MOVIEURL_RE = re.compile(r'class="showtime-item__movie-name"[^>]*href="([^"]+)"')
# An age limit that belongs to the *screening*, not to the film, and it is only claimed
# when BioRex says so: an explicit "(K-nn)" in the auditorium name, as at Seinäjoki's
# "2 REX (K-18)".
#
# It used to be inferred from the Anniskelu tag as well, and that was wrong. Finnkino
# publishes the two ideas as separate attributes and the data proves they differ: plain
# `Anniskelu` sits on 460 of their screenings including S- and K-7-rated films, while
# `Annisk_K18` — the one minors cannot attend — is a distinct marking that appears even
# on S-rated films. So the word marks a licensed auditorium, not a restricted screening.
# The inference put a K-18 badge on 99 BioRex screenings including an S-rated
# documentary, telling people a screening was closed to them when it was not. If BioRex
# ever states that their anniskelu screenings are 18+, bring it back with that citation.
AGE_IN_AUD_RE = re.compile(r"\(\s*K-?\s*(\d{1,2})\s*\)")


def _age(tags, aud):
    """-> ('K-18', cleaned_aud). Blank unless the room name states a limit."""
    m = AGE_IN_AUD_RE.search(aud or "")
    if m:
        return f"K-{m.group(1)}", re.sub(r"\s{2,}", " ", AGE_IN_AUD_RE.sub("", aud)).strip()
    return "", aud


# Film pages carry what the ajax response omits: Finnish synopsis, runtime, genres.
SYN_RE = re.compile(r'class="movie-description__synopsis[^"]*">\s*(.*?)\s*</div>', re.S)
KESTO_RE = re.compile(r'Kesto:</span>\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?', re.I)
GENRE_RE = re.compile(r'Genre:</span>\s*([^<]+)', re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# Format spans mix event/venue tags (Plus, Anniskelu, Senioribio…) with language codes
# (EN, FI&SV, ES). Language codes are the trailing all-caps tokens.
LANG_TOKEN_RE = re.compile(r"^[A-Z]{2}(?:&[A-Z]{2})*$")
WS_RE = re.compile(r"\s+")


def _text(s):
    return WS_RE.sub(" ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _split_formats(fmts):
    """-> (tags, audio, subs). Trailing caps tokens are languages; the rest are tags."""
    langs = []
    while fmts and LANG_TOKEN_RE.match(fmts[-1]):
        langs.insert(0, fmts.pop())
    audio = langs[0] if langs else ""
    subs = langs[1] if len(langs) > 1 else ""
    return fmts, audio, subs


def _lang_str(audio, subs):
    """Tags the client understands, so the existing 'Suom. puhe' filter keeps working.
    BioRex publishes SV for Swedish, which is the ISO 639-1 code and what this app now
    uses, so the codes pass through untouched."""
    parts = [f"{a}-A" for a in audio.split("&") if a]
    parts += [f"{x}-S" for x in subs.split("&") if x]
    return ", ".join(parts)


def _poster(chunk):
    m = SRCSET_RE.search(chunk)
    if not m:
        return ""
    best, best_w = "", -1
    for part in m.group(1).split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                continue
            if w > best_w:
                best, best_w = bits[0], w
    return best


class VenueMismatch(RuntimeError):
    """The response is not the venue's own programme, or cannot be shown to be. The
    cookie failed, or failed and took the evidence with it; either way it fails the site."""


def cinemas(posts_html):
    """The cinema each item names, from BioRex itself and never from the venue asked for.
    -> [name, or "" for an item that names none].

    The data layer's `showCinemaName`, else the place line up to its last comma ("BioRex
    Tripla, Sali 6"). `parse()` falls back to the venue's own name for display, which is
    why the guard cannot read `theatre`.
    """
    out = []
    for chunk in ITEM_RE.findall(posts_html):
        m = DL_RE.search(chunk)
        if not m:
            continue
        try:
            dl = json.loads(html_mod.unescape(m.group(1)))
        except Exception:
            continue
        if not dl.get("showDateTime"):
            continue
        name = (dl.get("showCinemaName") or "").strip()
        if not name:
            pm = PLACE_RE.search(chunk)
            place = _text(pm.group(1)) if pm else ""
            name = place.rsplit(",", 1)[0].strip() if "," in place else ""
        out.append(name)
    return out


def parse(posts_html, venue):
    """HTML fragment -> normalized showtime dicts."""
    shows, untitled = [], 0
    for chunk in ITEM_RE.findall(posts_html):
        m = DL_RE.search(chunk)
        if not m:
            continue
        try:
            dl = json.loads(html_mod.unescape(m.group(1)))
        except Exception:
            continue
        start = dl.get("showDateTime") or ""
        if not start:
            continue
        if not (dl.get("movieName") or "").strip():
            untitled += 1               # never "?": see the count below
            continue
        place = _text(PLACE_RE.search(chunk).group(1)) if PLACE_RE.search(chunk) else ""
        aud = place.split(",")[-1].strip() if "," in place else place
        rating_raw = _text(RATING_RE.search(chunk).group(1)) if RATING_RE.search(chunk) else ""
        fmts = [f for f in (_text(x) for x in FORMAT_RE.findall(chunk)) if f]
        tags, audio, subs = _split_formats(fmts)
        age, aud = _age(tags, aud)
        href = HREF_RE.search(chunk)
        movie = MOVIEURL_RE.search(chunk)
        shows.append({
            "eventId": str(dl.get("movieId") or ""),
            "title": dl["movieName"].strip(),
            "original": "",
            "len": "",
            "rating": rating_raw,
            "age": age,
            "genres": "",
            "method": " · ".join(tags),
            "theatre": dl.get("showCinemaName") or venue["name"],
            "aud": aud,
            "start": start,
            "url": href.group(1) if href else (movie.group(1) if movie else BASE),
            "img": _poster(chunk),
            "lang": _lang_str(audio, subs),
            "soldOut": False,   # BioRex exposes no seat availability in this response
            # No price on the listing; docs/research/prices.md has the probe.
            "price": "",
            "provider": "biorex",
            "venue": venue["id"],
            "movieUrl": movie.group(1) if movie else "",
        })
    if untitled:
        # A renamed `movieName` drops every row, and a site with no row fails the run.
        print(f"[biorex] {venue['name']}: {untitled} row(s) with no title, dropped")
    return shows


def film_meta(url):
    """Fetch one film page -> {'syn','len','genres'}. Cheap: ~15 pages per run."""
    page = fetch(url, cache=True, headers={"user-agent": UA,
                               "accept-language": "fi-FI,fi;q=0.9"}
                 ).decode("utf-8", "replace")
    syn = SYN_RE.search(page)
    k = KESTO_RE.search(page)
    g = GENRE_RE.search(page)
    minutes = ""
    if k and (k.group(1) or k.group(2)):
        minutes = str(int(k.group(1) or 0) * 60 + int(k.group(2) or 0))
    return {
        "syn": _text(syn.group(1)) if syn else "",
        "len": minutes,
        "genres": ", ".join(x.strip() for x in _text(g.group(1)).split(",") if x.strip())
                  if g else "",
    }


def _opener():
    jar = http.cookiejar.CookieJar()
    return make_opener(urllib.request.HTTPCookieProcessor(jar))


def _post(op, url, data):
    return fetch(url, data=urllib.parse.urlencode(data).encode(),
                 headers={"user-agent": UA, "accept": "*/*",
                          "content-type": "application/x-www-form-urlencoded",
                          "referer": BASE + "/elokuvat/"}, opener=op)


def fetch_venue(venue):
    op = _opener()
    fetch(BASE + "/elokuvat/", headers={"user-agent": UA}, opener=op)
    _post(op, BASE + "/teatterin-valinta/", {"location": venue["providerId"]})
    raw = _post(op, AJAX, {"action": "br_movies_handler", "genre": "-1", "date": "-1",
                           "format": "-1", "language": "-1", "activeType": "showtimes"})
    payload = json.loads(raw.decode("utf-8", "replace"))
    posts = payload.get("posts") or ""
    shows = parse(posts, venue)
    # Cookie failure shows up as another venue's data, so verify before trusting it, on
    # what the response itself says: see `cinemas`.
    names = set(cinemas(posts))
    if shows and "" in names:
        raise VenueMismatch(f"asked {venue['name']}: {len(shows)} showtime(s), and the "
                            f"response names no cinema on some, so it cannot be verified")
    if names and venue["name"] not in names:
        raise VenueMismatch(f"venue mismatch: asked {venue['name']}, got {sorted(names)}")
    return shows


def fetch_all(sleep=0.6, with_meta=True):
    out, mismatched = {}, []
    for v in VENUES:
        try:
            out[v["id"]] = fetch_venue(v)
            print(f"[biorex] {v['name']}: {len(out[v['id']])} showtimes")
        except VenueMismatch as e:
            mismatched.append((v["name"], str(e)))
            print(f"[biorex] {v['name']} FAILED: {e}")
        except Exception as e:
            print(f"[biorex] {v['name']} FAILED: {e}")
        time.sleep(sleep)
    # One venue answered with a programme that is not its own, or that names no cinema:
    # the cookie that selects the venue is not taking, and the venues that passed may be
    # passing on a name that happened to match. Nothing publishes and the previous files
    # stand, which is how a whole-site failure is handled everywhere else.
    if mismatched:
        raise RuntimeError(f"the venue cookie did not hold for {len(mismatched)} of "
                           f"{len(VENUES)} venue(s) ({', '.join(n for n, _ in mismatched)}), "
                           f"first: {mismatched[0][1]}; publishing no venue of this site")

    if with_meta:
        # One page per distinct film, then fill runtime/genres on every showtime.
        pages, meta = {}, {}
        for shows in out.values():
            for s in shows:
                if s.get("movieUrl"):
                    pages.setdefault(s["title"], s["movieUrl"])
        for title, url in capped(sorted(pages.items()), 'biorex'):
            try:
                meta[title] = film_meta(url)
            except Exception as e:
                print(f"[biorex] meta {title}: {e}")
            time.sleep(0.4)
        print(f"[biorex] film pages: {len(meta)}/{len(pages)}")
        for shows in out.values():
            for s in shows:
                m = meta.get(s["title"])
                if not m:
                    continue
                s["len"] = s["len"] or m["len"]
                s["genres"] = s["genres"] or m["genres"]
                if m["syn"]:
                    s["_syn"] = m["syn"]
    return out


def fetch_site(site=SITES[0], **kw):
    """Runner contract. fetch_all covers every venue in one pass and already handles
    per-venue failures, so `site` is accepted for symmetry and not used to subset."""
    return fetch_all(**kw)
