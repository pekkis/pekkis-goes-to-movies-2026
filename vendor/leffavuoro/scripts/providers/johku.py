"""Six cinemas whose whole site is a Johku storefront. Stdlib only.

Bio Marilyn (Lapua), Vihdin Kino (Vihti), Bio Forum (Tammisaari), Kinokulma (Oulainen),
Kino Hannikainen (Nurmes) and Kino Virta (Kalajoki).

**Not Kino Engel or Kino Tapiola.** Those are the cinema's own site with a Johku widget
embedded in it, and the widget's show list needs its API key, which is the line "Access and
ethics" draws. Probed 2026-09-18; the evidence is in docs/research/ticketing-platforms.md.

One request per site for the front page, then one film page per distinct product.

**The programme comes from the front page's own data.** The storefront is a Nuxt
application. Its server requests the platform's `showschedule.json` once for each
programme block on the front page and embeds the answers in the `__NUXT_DATA__` script of
the same HTML. The visitor's browser draws the listing from that copy and requests nothing
more. The markup is not read: since 2026-10-01 the server often sends a block as a loading
skeleton while the embedded schedule is already whole, on 25 of 30 reads on 2026-10-09,
all 30 of which carried the schedule.

**What counts as complete.** The storefront's front-page layout names at least one
programme block, the markup draws that many `js-shows` blocks, and each block's
`showschedule-{locale}-f{date}-c{category}` entry is in the payload as a list with no
error recorded for it. Anything less is read again, up to `LISTING_TRIES` times, and then
the site fails with its previous files standing. Every block answering with an empty list
is the platform's own statement that nothing is scheduled, which is
`common.EmptyProgramme`.

An entry, with the fields the page's ShowItem draws:

    {"id": "6463", "text": "Kerro kaikille", "start_date": "2026-10-09 17:00",
     "end_date": "2026-10-09 18:52", "resource_name": "Kulmasali", "agelimit": "K-12",
     "upcoming": "0", "storefronturl": "https://kinokulma.fi/fi_FI/kerro-kaikille",
     "product": {"id": "1122", "enable_catalog": "fi_FI", ...}}

What shapes the parser:

- **`start_date` is the clock the page prints**, the cinema's own local time, and it is
  read as Helsinki time. An offset on it fails the site, because the field would then
  mean something else.
- **The page draws an entry only if its product is in the catalogue for the locale and it
  has not started**, and the same two rules apply here.
- **An entry with `upcoming` set is a coming-soon entry**, filed under a release date with
  no time. They are counted and left out.
- **One screening can sit in two blocks.** Bio Marilyn files some films under both "nyt
  ohjelmistossa" and "tulossa", and the show id publishes each screening once.
- **`resource_name` is declared per venue.** An entry naming a hall the site does not list
  fails rather than landing under the wrong venue.
- **A showtime links to the film page the schedule names** (`storefronturl`), copied
  exactly. Bio Marilyn's links are on biomarilyn.johku.com, which its site entry declares in
  `reads` because the film pages are read from the same links. A link that is not a full
  https URL with a film path, on a host the site reads, fails the site and the previous
  files stand.
- **No price is published.** The entry carries a pricing name and an amount beside
  `multipleprices`, so which ticket the amount is for is not settled, and the tariff
  pages state bands ("Normaali elokuva 13-15 €"). `price` stays empty.
- **The artwork is a landscape banner**, 2048x1365 and 2048x857 on the two measured, so
  `img` stays empty and the TMDB pass supplies a portrait poster.
- **No sold-out state is rendered on a row.** "Loppuunmyyty" appears once per page, inside
  the storefront's own string table.
- **The synopsis carries a language.** Tammisaari publishes Swedish beside Finnish, and the
  slot in films-extra.json is keyed by normalised title and read by every chain showing the
  film. `common.syn_language` places the text and withholds it when nothing is settled.

**A storefront also sells hall hire.** Read 2026-09-18, the day groups held one
("Salivaraus"), and it is the only kind of entry left out. The platform gives a product
with no canonical name the path `/fi_FI/products/{id}-{shop}-{name}`, while every film and
event has a canonical name and a path of its own (`/fi_FI/kerro-kaikille`). That path is
the rule here, and no word in a title is read.

**Thin metadata never withholds a screening.** A film page that answers nothing, or
carries no director and no genre, costs the row its synopsis and its genres and nothing
else. The maintainer's instruction of 2026-09-18: a small film that publishes little about
itself still belongs on the site. The Kinola classifier is not applied here, and the
difference is that this listing carries no live-act problem of the kind Karkkila has.

**Entries but no screening fails the site.** A schedule that lists entries of which none is
a timed screening still to come is not an empty programme, so the previous files stand.
"""
import datetime
import html as html_mod
import http.client
import json
import re
import sys
import time
import urllib.request
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from common import EmptyProgramme, capped, check_shows, fetch, make_opener, syn_language
from etiketti import lang_codes, strict_codes

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

SITES = [
    {"provider": "biomarilyn", "label": "Bio Marilyn",
     "base": "https://www.biomarilyn.com", "listing": "/",
     # The schedule's film links, and so the film pages read, are on the platform's host.
     "reads": ("biomarilyn.johku.com",),
     "venues": [{"id": "biomarilyn-lapua", "name": "Bio Marilyn", "short": "Bio Marilyn",
                 "city": "Lapua", "loc": "Bio Marilyn"}]},
    {"provider": "vihdinkino", "label": "Vihdin Kino",
     "base": "https://vihdinkino.fi", "listing": "/",
     "venues": [{"id": "vihdinkino-vihti", "name": "Vihdin Kino", "short": "Vihdin Kino",
                 "city": "Vihti", "loc": "Vihdin Kino"}]},
    {"provider": "bioforum", "label": "Bio Forum",
     "base": "https://bioforum.fi", "listing": "/",
     "venues": [{"id": "bioforum-tammisaari", "name": "Bio Forum", "short": "Bio Forum",
                 "city": "Tammisaari", "loc": "Bio Forum"}]},
    {"provider": "kinokulma", "label": "Kinokulma",
     "base": "https://kinokulma.fi", "listing": "/",
     "venues": [{"id": "kinokulma-oulainen", "name": "Kinokulma", "short": "Kinokulma",
                 "city": "Oulainen", "loc": "Kulmasali"}]},
    # Added 2026-09-20, the sixth storefront. `kinohannikainen` on cdn.johku.com behind
    # the cinema's own domain, and the root renders the same `showgroup`/`daytitle`/
    # `js-grid-show` listing as the other five: read that day, eight rows over five day
    # groups, every one `data-location="Hannikaisen sali"`.
    {"provider": "kinohannikainen", "label": "Kino Hannikainen",
     "base": "https://www.kinohannikainen.net", "listing": "/",
     "venues": [{"id": "kinohannikainen-nurmes", "name": "Kino Hannikainen",
                 "short": "Kino Hannikainen", "city": "Nurmes",
                 "loc": "Hannikaisen sali"}]},
    # Added 2026-09-20, the seventh, and the one storefront read from johku.com itself:
    # the cinema has no storefront domain of its own and virtasali.fi links here. Read
    # that day, four rows over two day groups, `data-location="Virta-sali"`.
    {"provider": "kinovirta", "label": "Kino Virta",
     "base": "https://kinovirta.johku.com", "listing": "/",
     "venues": [{"id": "kinovirta-kalajoki", "name": "Kino Virta",
                 "short": "Kino Virta", "city": "Kalajoki", "loc": "Virta-sali"}]},
]

LOCALE = "fi_FI"

# The payload script, and the class of the root element of the page's MovieList component,
# one per programme block. Read in the storefront's own bundle on 2026-10-09, where no other
# component uses that class.
NUXT_RE = re.compile(r'<script\b[^>]*\bid=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>',
                     re.S | re.I)
SHOWS_RE = re.compile(r'<div\b[^>]*class=["\'][^"\']*(?<![-\w])js-shows(?![-\w])')

# The page's own mapping from `agelimit` to its rating badge (ShowItem, 2026-10-09). Any
# other value draws "rating-unknown" and publishes no rating.
RATINGS = {"S": "S", "K-S": "S", "KS": "S", "3": "S"}
RATINGS.update({v: f"K-{n}" for n in (7, 12, 16, 18) for v in (str(n), f"K-{n}", f"K{n}")})

HM_RE = re.compile(r'(\d{1,2})\s*h\s*(\d{1,3})\s*min\b', re.I)
MIN_RE = re.compile(r'(\d{1,3})\s*min\b', re.I)
INFO_RE = re.compile(r'class=["\'][^"\']*product-content-infolabel[^"\']*["\'][^>]*>'
                     r'(.*?)</div>\s*<div[^>]*class=["\'][^"\']*product-content-infovalue'
                     r'[^"\']*["\'][^>]*>(.*?)</div>', re.S | re.I)
DESC_RE = re.compile(r'class=["\'][^"\']*product-description__html[^"\']*["\'][^>]*>(.*?)</div>',
                     re.S | re.I)
PARA_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.S | re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# The platform's path for a product with no canonical name. A programme entry never has it
# and the hall hire always does, which separates the two without reading a title.
PRODUCT_PATH = "/fi_FI/products/"

# A paragraph shorter than this is a release note ("Elokuvateattereissa 4.9.") rather than
# a synopsis. The same length kinola.py uses, for the same reason.
SYN_MIN = 120

# How a film page states its language. These are the sentences seen on 2026-10-04 and
# 2026-10-05, and nothing looser is read. Bio Marilyn's opera uses labelled paragraphs:
# "Kieli : Alkuperäinen", "Tekstitys: Suomi". Bio Forum writes "Elokuva on puhuttu
# englanniksi ja tekstitys on sekä suomeksi että ruotsiksi." (Digger misspells it
# "teksitys"), "Elokuva on tekstitetty ruotsiksi, puhe suomi.", "dubattu ruotsinkielelle ja
# tekstitys on vain ruotsiksi." and "Elokuva on ilman tekstitystä." Vihdin Kino writes
# "Esitetään dubattuna versiona eli puhumme suomea." A phrase has to end where the sentence
# ends, so "ruotsiksi ja suomeksi tekstitettynä" gives nothing. A labelled "Tekstitys: Ei
# tekstitystä" is `XX-S` (Bio Marilyn's ballet). "ilman tekstitystä" is only read when the
# subject is "Elokuva on". Lilla Spöket's "Pikku Kummitus Lapanen puhuu ruotsia." is about
# the character and is not read.
LABEL_LINE_RE = re.compile(r"^(kieli|tekstitys)\s*:\s*(.+)$", re.I)
NO_SUBS_RE = re.compile(r"^ei\s+tekstityst\u00e4\.?$", re.I)
TRANSLATIVE = r"[a-zåäö]+ksi(?:\s*(?:,|ja|sekä|että)\s*[a-zåäö]+ksi)*"
SUBS_WORD = r"tekst?itys"
SPOKEN_RE = re.compile(r"\bpuhuttu\s+(" + TRANSLATIVE + r")(?=\s*(?:[.,]|ja\s+(?:" + SUBS_WORD
                       + r"|se)\b|$))", re.I)
SUBTITLED_RE = re.compile(r"\b" + SUBS_WORD + r"\s+on\s+(?:sek\u00e4\s+|vain\s+)?(" + TRANSLATIVE
                          + r")(?=\s*(?:[.,]|$))", re.I)
TEXTED_RE = re.compile(r"\belokuva\s+on\s+tekstitetty\s+(" + TRANSLATIVE
                       + r")(?:\s*,\s*puhe\s+([a-z\u00e5\u00e4\u00f6]+))?(?=\s*(?:[.,]|$))", re.I)
DUBBED_RE = re.compile(r"\bdubattu\s+([a-z\u00e5\u00e4\u00f6]+kielelle)(?=\s*(?:[.,]|ja\s+"
                       + SUBS_WORD + r"\b|$))", re.I)
NO_SUBS_SENTENCE_RE = re.compile(r"\belokuva\s+on\s+ilman\s+tekstityst\u00e4(?=\s*(?:\.|$))",
                                 re.I)
FINNISH_SPOKEN_RE = re.compile(r"\bpuhumme\s+suomea\b", re.I)


class _Response(http.client.HTTPResponse):
    """An HTTP response reader that skips interim 1xx responses.

    These storefronts answer with `103 Early Hints` followed by a 200; on 2026-10-05 all six
    Johku hosts did. `http.client` skips `100 Continue` and nothing else, so urllib reports
    the 103 as the status and `common.fetch` raises on it, while curl reads through to the
    200. See docs/research/ticketing-platforms.md.
    """

    def _read_status(self):
        while True:
            version, status, reason = super()._read_status()
            if status >= 200:
                return version, status, reason
            while True:                       # drain the interim response's own headers
                line = self.fp.readline(http.client._MAXLINE + 1)
                if line in (b"\r\n", b"\n", b""):
                    break


class _Connection(http.client.HTTPSConnection):
    response_class = _Response


class _Handler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_Connection, req, context=self._context)


# Through common.make_opener, so a redirect from https to http is refused here too.
OPENER = make_opener(_Handler())


class ListingRowError(RuntimeError):
    """An entry the schedule marks as a screening and this parser could not read.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _minutes(text):
    """`1 h 27 min` or `87 min` -> "87". -> str, "" when neither shape is there."""
    m = HM_RE.search(text or "")
    if m:
        return str(int(m.group(1)) * 60 + int(m.group(2)))
    m = MIN_RE.search(text or "")
    return m.group(1) if m else ""


# Nuxt's own payload types that wrap a plain value. Any other typed value is left unread,
# and a field that needed it reads as absent.
WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef", "NuxtError"}
UNREAD = object()


def payload(page):
    """The page's `__NUXT_DATA__` as plain values. -> dict, None when there is none.

    The script is devalue's flat form: a list whose first item is the root, where a number
    inside an object or a list is the index of the value it stands for, a negative one is
    undefined or a special number, and a list starting with a string is a typed value.
    """
    m = NUXT_RE.search(page)
    if not m:
        return None
    try:
        values = json.loads(m.group(1))
    except ValueError:
        return None
    if not isinstance(values, list) or not values:
        return None
    done = {}

    def get(i):
        if type(i) is not int or not 0 <= i < len(values):
            return None
        if i in done:
            return done[i]
        v = values[i]
        if isinstance(v, dict):
            out = done[i] = {}
            out.update((k, get(j)) for k, j in v.items())
            return out
        if isinstance(v, list) and v and isinstance(v[0], str):
            done[i] = UNREAD
            if v[0] in WRAPPERS and len(v) == 2:
                done[i] = get(v[1])
            return done[i]
        if isinstance(v, list):
            out = done[i] = []
            out.extend(get(j) for j in v)
            return out
        return v

    root = get(0)
    return root if isinstance(root, dict) else None


def _list(value):
    return value if isinstance(value, list) else []


# Reads of one front page before the site fails, and the pause between them. Every one of
# 30 reads on 2026-10-09 carried the whole schedule, so a second read is the exception.
LISTING_TRIES = 5
LISTING_WAIT = 5.0


def schedule(page, locale=LOCALE):
    """The front page's programme blocks. -> (state, [[entry]] one list per block).

    `state` is "complete" when the storefront's layout names at least one programme block,
    the markup draws as many, and each block's schedule is in the payload as a list with no
    error recorded. Otherwise the blocks are empty and the state says what was short:
    "missing" (no payload, layout or programme block), "unmatched" (the markup draws a
    different number of blocks), "loading" (a block's schedule is absent) or "error" (the
    server recorded its request for one as failed).
    """
    root = payload(page)
    data = root.get("data") if root else None
    if not isinstance(data, dict):
        return "missing", []
    errors = root.get("_errors") if isinstance(root.get("_errors"), dict) else {}
    layouts = [v for k, v in data.items()
               if k.startswith("storefront-") and k.endswith("-" + locale)]
    if len(layouts) != 1 or not isinstance(layouts[0], dict):
        return "missing", []
    items = [item for g in _list(layouts[0].get("groups")) if isinstance(g, dict)
             for item in _list(g.get("items"))
             if isinstance(item, dict) and item.get("view") == "showtimes"]
    if not items:
        return "missing", []
    if len(SHOWS_RE.findall(page)) != len(items):
        return "unmatched", []
    blocks = []
    for item in items:
        category = item.get("category")
        cid = category.get("id") if isinstance(category, dict) else None
        if cid in (None, ""):
            return "missing", []
        key = re.compile(rf"showschedule-{re.escape(locale)}-f\d{{4}}-\d\d-\d\d"
                         rf"-c{re.escape(str(cid))}(?:-p[^-]+)?")
        keys = [k for k in data if key.fullmatch(k)]
        if len(keys) > 1:
            return "unmatched", []
        if not keys:
            return "loading", []
        if errors.get(keys[0]) is not None:
            return "error", []
        answer = data[keys[0]]
        if not isinstance(answer, dict) or not isinstance(answer.get("data"), list):
            return "loading", []
        blocks.append(answer["data"])
    return "complete", blocks


def read_listing(url):
    """-> (blocks, reads) once the front page carries its whole schedule. Raises after
    `LISTING_TRIES` reads that did not: an incomplete answer is not an empty programme."""
    states = []
    for n in range(LISTING_TRIES):
        if n:
            time.sleep(LISTING_WAIT)
        state, blocks = schedule(get(url))
        if state == "complete":
            return blocks, n + 1
        states.append(state)
    raise RuntimeError(
        f"{url}: the schedule was not complete on any of {LISTING_TRIES} reads "
        f"({', '.join(states)}). An incomplete answer is not an empty programme, so the "
        f"previous files stand")


def _clean(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _listed(product, locale=LOCALE):
    """The page's own test before it draws an entry: the product is in the catalogue or in
    a collection for the locale. Each field holds 1 or a list of locales."""
    for field in ("enable_catalog", "enable_collection"):
        value = product.get(field)
        if str(value).strip() == "1" or (isinstance(value, str) and locale in value):
            return True
    return False


def _local(value):
    """"2026-10-09 17:00" -> that clock in Helsinki. None when unreadable or offset."""
    try:
        when = datetime.datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return when.replace(tzinfo=FI) if when and when.tzinfo is None else None


def _film_url(site, n, title, link):
    """The film page the schedule names, exactly as given. -> str.

    It has to be a full https URL with a film path, on the site's own host or one it
    declares in `reads`. Anything else fails the site, so the previous files stand.
    """
    parts = urlsplit(link) if isinstance(link, str) else None
    hosts = {urlsplit(site["base"]).hostname, *site.get("reads", ())}
    if not (parts and parts.scheme == "https" and parts.hostname in hosts
            and parts.path.startswith(f"/{LOCALE}/") and parts.path != f"/{LOCALE}/"
            and not parts.query and not parts.fragment):
        raise ListingRowError(
            f"{site['provider']}: schedule entry {n} for {title!r} carries no usable film "
            f"page link ({link!r})")
    return link


def rows(site, blocks, now):
    """The screenings the page draws from its blocks. -> ([row], report).

    A row is (product, title, venue, start, url, rating, len); everything else comes from
    the film page. `report` holds what is left out: `skipped`, the coming-soon titles, and
    the counts `past` and `unlisted` of entries the page does not draw, and `repeated` of
    screenings it draws in a second block.
    """
    venues = {v["loc"]: v for v in site["venues"]}
    out, seen = [], set()
    report = {"skipped": [], "past": 0, "unlisted": 0, "repeated": 0}
    n = 0
    for block in blocks:
        for entry in block:
            n += 1
            if not isinstance(entry, dict):
                raise ListingRowError(
                    f"{site['provider']}: schedule entry {n} is not an object")
            product = entry.get("product")
            if not isinstance(product, dict) or not _listed(product):
                report["unlisted"] += 1
                continue
            title = _clean(entry.get("text"))
            if not title or product.get("id") in (None, ""):
                raise ListingRowError(
                    f"{site['provider']}: schedule entry {n} has no title or no product id")
            start = _local(entry.get("start_date"))
            if start is None:
                raise ListingRowError(
                    f"{site['provider']}: schedule entry {n} for {title!r} has the "
                    f"start_date {entry.get('start_date')!r}, which is not a local clock")
            if start < now:
                report["past"] += 1
                continue
            if str(entry.get("upcoming")).strip() == "1":
                report["skipped"].append(title)
                continue
            key = str(entry.get("id") or (product["id"], entry["start_date"]))
            if key in seen:
                report["repeated"] += 1
                continue
            seen.add(key)
            loc = _clean(entry.get("resource_name"))
            if loc not in venues:
                raise ListingRowError(
                    f"{site['provider']}: schedule entry {n} names the hall {loc!r}, which "
                    f"this site does not list. Publishing it would file a screening under "
                    f"another venue or drop it without a word")
            end = _local(entry.get("end_date"))
            minutes = int((end - start).total_seconds() // 60) if end else 0
            out.append({
                "product": str(product["id"]),
                "title": title,
                "venue": venues[loc]["id"],
                "start": start.isoformat(),
                "url": _film_url(site, n, title, entry.get("storefronturl")),
                "rating": RATINGS.get(entry.get("agelimit"), "")
                if isinstance(entry.get("agelimit"), str) else "",
                "len": str(minutes) if minutes > 0 else "",
            })
    return out, report


def _translative(phrase):
    """"englanniksi ja ruotsiksi" -> ["EN", "SV"]; [] unless every word names one language."""
    out = []
    for word in re.findall(r"[a-zåäö]+ksi", (phrase or "").lower()):
        codes = lang_codes(word)
        if len(codes) != 1:
            return []
        if codes[0] not in out:
            out.append(codes[0])
    return out


def film_lang(paras):
    """A film page's description paragraphs -> "EN-A, FI-S, SV-S", "" when none states it."""
    audio, subs = [], []
    for t in paras:
        m = LABEL_LINE_RE.match(t)
        if m:
            if m.group(1).lower() == "tekstitys" and NO_SUBS_RE.match(m.group(2).strip()):
                subs.append("XX")
                continue
            (audio if m.group(1).lower() == "kieli" else subs).extend(strict_codes(m.group(2)))
            continue
        spoken, subtitled = SPOKEN_RE.search(t), SUBTITLED_RE.search(t)
        audio += _translative(spoken.group(1)) if spoken else []
        subs += _translative(subtitled.group(1)) if subtitled else []
        texted, dubbed = TEXTED_RE.search(t), DUBBED_RE.search(t)
        if texted:
            subs += _translative(texted.group(1))
            audio += lang_codes(texted.group(2)) if texted.group(2) else []
        audio += lang_codes(dubbed.group(1)) if dubbed else []
        if NO_SUBS_SENTENCE_RE.search(t):
            subs.append("XX")
        if FINNISH_SPOKEN_RE.search(t):
            audio.append("FI")
    parts = [f"{c}-A" for c in dict.fromkeys(audio)] + [f"{c}-S" for c in dict.fromkeys(subs)]
    return ", ".join(parts)


def film_facts(page):
    """One film page -> {len, genres, original, syn, lang}."""
    info = {_txt(k).lower(): _txt(v) for k, v in INFO_RE.findall(page)}
    syn = ""
    body = DESC_RE.search(page)
    paras = [_txt(p) for p in PARA_RE.findall(body.group(1))] if body else []
    for t in paras:
        if len(t) >= SYN_MIN:
            syn = t
            break
    return {"len": _minutes(info.get("kesto", "")),
            "genres": info.get("luokittelu", ""),
            "original": info.get("alkuperäinen nimi", ""),
            "syn": syn, "lang": film_lang(paras)}


def parse(site, blocks, pages, now):
    """-> ({venue_id: [show]}, report). `pages` is {product: film page html}.

    `report` is what `rows` left out, plus `hire`, the hall-hire titles over `hire_shows`
    rows, and `unplaced`, the synopses no language could be settled for. A row with no film
    page read publishes without its genres and synopsis.
    """
    listed, report = rows(site, blocks, now)
    facts = {p: film_facts(h) for p, h in pages.items()}
    per_venue = {v["id"]: [] for v in site["venues"]}
    unplaced, hire, hire_shows = set(), set(), 0
    for r in listed:
        if PRODUCT_PATH in r["url"]:
            hire.add(r["title"])
            hire_shows += 1
            continue
        f = facts.get(r["product"]) or {"len": "", "genres": "", "original": "", "syn": "",
                                        "lang": ""}
        venue = next(v for v in site["venues"] if v["id"] == r["venue"])
        show = {
            "eventId": r["product"],
            "title": r["title"],
            "original": f["original"],
            "len": r["len"] or f["len"],
            "rating": r["rating"],
            "genres": f["genres"],
            "method": "",
            "theatre": venue["name"],
            "aud": "",
            "start": r["start"],
            "url": r["url"],
            "img": "",
            "lang": f["lang"],
            "soldOut": False,
            "price": "",
            "provider": site["provider"],
            "venue": r["venue"],
        }
        if f["syn"]:
            lang = syn_language(f["syn"])
            if lang:
                show["_syn"] = {lang: f["syn"]}
            else:
                unplaced.add(r["title"])
        per_venue[r["venue"]].append(show)
    for shows in per_venue.values():
        shows.sort(key=lambda s: s["start"])
    report.update(hire=hire, hire_shows=hire_shows, unplaced=unplaced)
    return per_venue, report


def get(url, tries=3, timeout=30):
    return fetch(url, cache=True, opener=OPENER,
                 headers={"user-agent": UA, "accept-language": "fi-FI,fi;q=0.9"},
                 tries=tries, timeout=timeout).decode("utf-8", "replace")


def now():
    return datetime.datetime.now(FI)


def fetch_site(site, sleep=1.2):
    """Runner contract: the front page, then one film page per distinct product."""
    pid = site["provider"]
    listing_url = site["base"].rstrip("/") + site["listing"]
    blocks, reads = read_listing(listing_url)
    if reads > 1:
        print(f"[{pid}] the schedule was complete on read {reads} of {LISTING_TRIES}")
    entries = sum(len(b) for b in blocks)
    if not entries:
        raise EmptyProgramme(
            f"{listing_url}: the storefront's schedule answered with no entry for any of "
            f"its {len(blocks)} programme block(s)")
    when = now()
    listed, _ = rows(site, blocks, when)
    if not listed:
        raise RuntimeError(
            f"{listing_url}: {entries} schedule entries and none a timed screening still to "
            f"come. A schedule with entries is not an empty programme, so the previous "
            f"files stand")
    pages = {}
    # The hall-hire rows are dropped before the film pages are chosen: their product page
    # is never read, so the request is not made at all.
    wanted = sorted({(r["product"], r["url"]) for r in listed
                     if PRODUCT_PATH not in r["url"]})
    for n, r in enumerate(capped(wanted, pid)):
        if n:
            time.sleep(sleep)
        product, url = r
        try:
            pages[product] = get(url)
        except Exception as e:
            print(f"[{pid}] film page {url.rsplit('/', 1)[-1]} failed ({e}); the screening "
                  f"publishes without its synopsis and genres")
    per_venue, report = parse(site, blocks, pages, when)
    check_shows(per_venue, pid, {v["id"] for v in site["venues"]})
    print(f"[{pid}] {len(listed)} screening(s) in {len(blocks)} schedule block(s), "
          f"{len(pages)} film page(s) read")
    if report["skipped"]:
        print(f"[{pid}] {len(report['skipped'])} coming-soon entry/entries with no time, "
              f"left out: {', '.join(sorted(set(report['skipped']))[:8])}")
    if report["repeated"]:
        print(f"[{pid}] {report['repeated']} screening(s) listed in a second block, "
              f"published once")
    if report["past"] or report["unlisted"]:
        print(f"[{pid}] left out as the page does: {report['past']} already started, "
              f"{report['unlisted']} not in the catalogue")
    if report["hire"]:
        print(f"[{pid}] {len(report['hire'])} hall-hire title(s) over "
              f"{report['hire_shows']} row(s) left out: "
              f"{', '.join(sorted(report['hire'])[:8])}")
    if report["unplaced"]:
        print(f"[{pid}] {len(report['unplaced'])} synopsis/synopses withheld, no language "
              f"settled: {', '.join(sorted(report['unplaced'])[:8])}")
    if not any(per_venue.values()):
        raise RuntimeError(
            f"{listing_url} holds {len(listed)} screening(s) in its schedule and none "
            f"published. That is a template failure rather than a cinema with nothing on")
    for v in site["venues"]:
        shows = per_venue[v["id"]]
        days = sorted({s["start"][:10] for s in shows})
        print(f"[{pid}] {v['name']}: {len(shows)} showtimes, {len(days)} dates")
    return per_venue


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "biomarilyn"
    site = next(s for s in SITES if s["provider"] == which)
    for vid, shows in fetch_site(site).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:5]:
            print(f"   {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} "
                  f"{s['len']:4} {s['genres'][:20]:22} {s['url'][-28:]}")
