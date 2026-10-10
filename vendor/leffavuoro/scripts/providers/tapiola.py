"""Kino Tapiola (Mäntyviita 2, Espoo): the server-rendered programme list. Stdlib only.

kinotapiola.fi is a WordPress site with its own theme. Johku sells the tickets, but only
through embeds: the basket script on every page and, on each film page, a schedule
widget that draws the ticket table client-side. Nothing of that is readable here, and
nothing of it is needed: `/elokuvat/` renders **one block per screening** with the film
title, the date written out with its year ("lauantai 5.9.2026 – Klo 15:30") and a link
to the film page. That is the whole schedule, one request.

Three things about this site that shape the parser:

- **A slug is a film run, not a film.** Each week's booking of a film is a new post:
  `autofiktio-4`, `autofiktio-5` and `autofiktio-6` are three screenings of one film on
  three dates, with three identical pages (checked field by field on 2026-09-05; only
  the Johku show ids differ). The `eventId` is therefore the normalised title, the same
  key `synmerge.norm` and the client's `normTitle` use, and never the slug with a number
  cut off: a title that ends in a number ("Fez Summer 55") would lose it.
- **The film page carries what the list does not**: the age limit as a class
  (`info-icon age-limit-K-12`), the runtime ("1h 52min"), the spoken language ("OV" for
  an original version, otherwise a Finnish language name), the subtitle languages
  ("Suomi/Ruotsi") and the cinema's own synopsis. One page per film, not per run.
- **The images are stills, not posters.** The list paints a 3:2 press still behind each
  title and the film page shows a distributor image without any `og:image`. Neither is
  taken: posters come from TMDB, which is the poster rule since Heureka.

No empty state of this site has been seen, so a listing that yields no screening fails
the site whether the list container is there or not. The container proves the page
rendered, not that the cinema has nothing on: rows under a renamed class, or dates written
another way, leave it standing and parse to nothing. The `filter-no-results` phrase is no
evidence either, because the populated listing carries it too, for the client-side filter.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

import synmerge
from common import capped, fetch, get_text
from etiketti import lang_codes

BASE = "https://www.kinotapiola.fi"
LISTING = BASE + "/elokuvat/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "tapiola-espoo", "provider": "tapiola", "providerId": "1",
         "name": "Kino Tapiola", "short": "Kino Tapiola", "city": "Espoo"}

SITES = [{"provider": "tapiola", "label": "Kino Tapiola", "base": BASE, "venues": [VENUE]}]

# No EMPTY_VENUES_CONFIRMED here, on purpose: see the module docstring. The one venue
# is never returned empty.

CONTAINER_RE = re.compile(r'<div class="movie-list">', re.I)
ROW_RE = re.compile(r'<div class="movie-list-movie([^"]*)">\s*<a href="([^"]+)">(.*?)</a>\s*</div>',
                    re.S | re.I)
TITLE_RE = re.compile(r'<div class="title">(.*?)</div>', re.S | re.I)
DATE_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[–-]\s*klo\s*(\d{1,2})[:.](\d{2})', re.I)
CAT_RE = re.compile(r'\bcat-([a-z0-9-]+)')
TAGS_RE = re.compile(r"<[^>]+>")

# A strand class on the row, and the label the client should show for it. Only the one
# class seen so far; an unknown `cat-` class is passed through capitalised rather than
# dropped, so a new strand shows up instead of vanishing.
CATEGORIES = {"seniorikino": "Seniorikino"}

# Film page: the age limit is a class, the rest are labelled text boxes.
AGE_RE = re.compile(r'info-icon age-limit-(K-\d+|S)\b', re.I)
ICON_RE = re.compile(r'<div class="info-icon ([a-z-]+)">\s*(?:<a[^>]*>\s*)?<div class="info-icon-inner">'
                     r'.*?<div class="text">(.*?)</div>', re.S | re.I)
DESC_RE = re.compile(r'<div class="description">(.*?)</div>\s*<div class="info-icons">', re.S | re.I)
PARA_RE = re.compile(r'<p\b[^>]*>(.*?)</p>', re.S | re.I)
KESTO_RE = re.compile(r'(?:(\d+)\s*h)?\s*(\d+)\s*min', re.I)
# A paragraph naming the cinema, or speaking of its bar, hall or screenings in the first
# person, is the venue's notice and not the film's synopsis. Every opera and ballet page
# opens with two: "Kino Tapiolassa ooppera- ja baletti-iltoihin kuuluu ..." and
# "Viinibaarimme palvelee ... kaikissa näytöksissämme.", and films-extra.json served both
# as the Finnish synopsis of six Royal Opera and Ballet titles to every chain showing them
# (2026-09-25). Gilda and Cinemahouse drop theirs by name through
# `synmerge.drop_notes_html(names=)`; a production's own text never says "our bar".
NOTE_NAME_RE = re.compile(r"\bTapiola|\b(?:viini)?baari\w*mme\b|\bnäytöks\w*mme\b"
                          r"|\bsali\w*mme\b|\bkahvila\w*mme\b", re.I)

# The opera and ballet pages carry no language box. Their description states it as a
# line, read 2026-10-04: "Kieli: ranska, tekstitetty englanniksi" (Carmen, Tosca and two
# more). Read only where the boxes say nothing.
KIELI_LINE_RE = re.compile(r"(?:<br\s*/?>|<p\b[^>]*>)\s*Kieli:\s*([a-zåäö]+)"
                           r"(?:\s*,\s*tekstitetty\s+([a-zåäö]+ksi))?\s*(?=<)", re.I)

LANGS = {"suomi": "FI", "ruotsi": "SV", "englanti": "EN", "saksa": "DE", "ranska": "FR",
         "espanja": "ES", "italia": "IT", "venäjä": "RU", "viro": "ET", "tanska": "DA",
         "norja": "NO", "islanti": "IS", "japani": "JA", "kiina": "ZH", "korea": "KO",
         "arabia": "AR", "puola": "PL", "portugali": "PT", "hollanti": "NL", "ukraina": "UK"}


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _para(s):
    """Paragraph text: inline markup removed without leaving a gap, so "<em>The
    Odyssey</em>, on" does not come out as "The Odyssey , on"; a <br> still separates."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub("", s))).strip()


def parse(page):
    """The listing -> [show]. Raises when the list container is missing or no row on it
    reads as a screening."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError("programme list container missing: the template has changed")
    shows, seen = [], set()
    for m in ROW_RE.finditer(page):
        cls, href, block = m.groups()
        d = DATE_RE.search(_txt(block))
        t = TITLE_RE.search(block)
        if not (d and t):
            continue            # the "tulossa" list has the same rows with no time
        title = _txt(t.group(1))
        if not title:
            continue
        day, month, year, hh, mm = (int(x) for x in d.groups())
        try:
            start = datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()
        except ValueError:
            continue
        eid = synmerge.norm(title)
        if (eid, start) in seen:
            continue
        seen.add((eid, start))
        cats = [CATEGORIES.get(c, c.capitalize()) for c in CAT_RE.findall(cls)]
        url = href if href.startswith("http") else BASE + href
        shows.append({
            "eventId": eid,
            "title": title,
            "original": "",
            "len": "",
            "rating": "",
            "genres": "",
            "method": " · ".join(cats),
            "theatre": VENUE["name"],
            "aud": "",
            "start": start,
            "url": url,
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "",
            "provider": "tapiola",
            "venue": VENUE["id"],
        })
    if not shows:
        raise RuntimeError(f"no screening read from the programme list "
                           f"({len(ROW_RE.findall(page))} row(s) matched): a changed template "
                           f"or an empty programme, and no empty state of this site is known")
    shows.sort(key=lambda s: s["start"])
    return shows


# ---------------------------------------------------------------- film pages

def _codes(text, suffix):
    """"Suomi/Ruotsi" -> ["FI-S", "SV-S"]; "OV" and unknown names give nothing."""
    out = []
    for name in re.split(r"[,/;]| ja ", text or ""):
        code = LANGS.get(name.strip().lower())
        if code and f"{code}-{suffix}" not in out:
            out.append(f"{code}-{suffix}")
    return out


def details(page):
    """Film-page metadata. Returns {} for anything the page does not carry."""
    d = {}
    m = AGE_RE.search(page)
    if m:
        d["rating"] = m.group(1).upper()
    boxes = {}
    for kind, text in ICON_RE.findall(page):
        label, _, value = _txt(text).partition(" ")
        boxes[kind.split()[0]] = (label, value)
    kesto = KESTO_RE.search(_txt(page[page.find("Elokuvan kesto"):][:60])) if "Elokuvan kesto" in page else None
    if kesto:
        d["len"] = str(int(kesto.group(1) or 0) * 60 + int(kesto.group(2)))
    spoken = _codes(boxes.get("language", ("", ""))[1], "A")
    subs = _codes(boxes.get("subtitles", ("", ""))[1], "S")
    line = KIELI_LINE_RE.search(page) if not (spoken or subs) else None
    if line and LANGS.get(line.group(1).lower()):
        spoken = [f"{LANGS[line.group(1).lower()]}-A"]
        sub = lang_codes(line.group(2) or "")
        subs = [f"{sub[0]}-S"] if len(sub) == 1 else []
    if spoken or subs:
        d["lang"] = ", ".join(spoken + subs)
    desc = DESC_RE.search(page)
    if desc:
        # The first paragraph is usually a press quote with a star rating. The synopsis
        # is the cinema's own text, so the quote and its stars are left out.
        paras = [_para(p) for p in PARA_RE.findall(desc.group(1))]
        paras = [p for p in paras if p and "★" not in p and not p.startswith(("”", "“", '"'))
                 and not NOTE_NAME_RE.search(p) and not synmerge.is_note(p)]
        text = " ".join(paras)
        if len(text) > 40:
            d["_syn"] = text
    return d


def enrich(shows, get=None):
    """One film page per distinct film, folded onto every run of it."""
    get = get or (lambda u: get_text(u, fetcher=fetch, tries=2, backoff=3, timeout=20))
    by_film = {}
    for s in shows:
        by_film.setdefault(s["eventId"], []).append(s)
    ok = fail = 0
    for n, (eid, rows) in enumerate(capped(sorted(by_film.items()), "tapiola")):
        if n:
            time.sleep(0.5)
        url = rows[0]["url"]            # every run of the film has the same page content
        try:
            d = details(get(url))
        except Exception as e:
            fail += 1
            print(f"[tapiola] film page {url.rstrip('/').rsplit('/', 1)[-1]} failed: "
                  f"{type(e).__name__}: {e}")
            continue
        if not d:
            fail += 1
            print(f"[tapiola] film page {url.rstrip('/').rsplit('/', 1)[-1]}: nothing parsed")
            continue
        ok += 1
        for s in rows:
            for k, v in d.items():
                if v and not s.get(k):
                    s[k] = v
    print(f"[tapiola] film pages: {ok} parsed, {fail} with nothing usable, "
          f"{sum(1 for s in shows if s.get('rating'))}/{len(shows)} showtimes rated")
    return shows


def get_listing():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(LISTING, fetcher=fetch)


def fetch_site(site=SITES[0]):
    """Runner contract: one listing, one venue. parse() raises rather than return none."""
    shows = parse(get_listing())
    enrich(shows)
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = parse(open(src, encoding="utf-8", errors="replace").read()) if src else fetch_site()[VENUE["id"]]
    films = {s["eventId"] for s in data}
    dates = sorted({s["start"][:10] for s in data})
    print(f"{len(data)} showtimes, {len(films)} films, {len(dates)} dates "
          f"({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'})")
    for s in data:
        print(f"  {s['start'][:16]}  {s['title'][:38]:40} {s['rating']:5} {s['len']:4} "
              f"{s['method']:12} {s['eventId'][:28]}")
