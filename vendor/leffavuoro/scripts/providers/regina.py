"""Kino Regina (Keskustakirjasto Oodi, Helsinki), KAVI's cinema. Stdlib only.

kinoregina.fi is a WordPress site with its own theme, `kinoregina2`, and every showtime
list on it is drawn by the theme's own PHP endpoints. The one the programme page calls,
`getShowtimesMoviesV2.php`, takes a start date in a POST body and returns the whole
published window from that date as server-rendered HTML: a day header, then one block per
screening with the time, the film's title and numeric id, an ISO-like start with the year
("05-09-2026 14:00") and a per-show ticket link into KAVI's shop. A start date in the past
is clamped to today, and a date past the window returns an empty shell. One request per
run covers the programme (5.9. to 17.9. on the day this was written).

Read from a GitHub runner on 2026-09-05: the listing GET, this POST and a film page all
answered 200 with no challenge header, so the site runs on the cloud half.

What shapes the parser:

- **The film id is the key.** Every row links `/elokuva/{id}`, the same id the film page
  and the listing use, so `eventId` is that number and no title arithmetic is needed.
- **Titles are recased.** The site writes every title in capitals ("PIUKAT PAIKAT",
  "THE TURIN HORSE"). A title with no lowercase letter becomes sentence case (Finnish
  convention), roman numerals kept; then the film page's own Kuvaus text is searched for
  the same title in its own casing and that spelling wins ("One Battle After Another",
  "Sátántangó"). Every key that touches a title lowercases it first, so `synmerge.norm`,
  `enrich_tmdb.norm`, the aliases and the client's `normTitle` see the same string.
- **"Myynti on päättynyt." is not sold out.** A row turns `grey` with that note once online
  sales close for the screening; the seats may be free at the door, so `soldOut` stays
  false and the row stays a showtime.
- **The film page carries the rest**: the age limit as an image whose alt reads "Ikäraja:
  K12", the runtime ("162 min"), the subtitle line ("suom. tekstit/svensk text", "English
  subtitles", "ei tekstitystä"), the cinema's series under Teemat, the print under
  Kopiotieto ("35 mm", "70 mm", "DCP") and the synopsis under Kuvaus. Teemat becomes a
  strand tag only when it is a concise named series; Kopiotieto only when it names a film
  gauge; Lisätieto is screening-specific and never part of the synopsis.
- **The year and the original title are on the film page too.** The heading inside the
  main content reads "LUCKY LUKE SOTAPOLULLA (1978)", and `year` is that bracketed number
  only: a heading without one publishes no year, and a screening date never stands in.
  Under the still, `<span class="original-name">` lists the film's other titles separated
  by slashes, original first, then Swedish, then English ("La ballade des Dalton/Lucky
  Luke på krigsstigen/The Ballad of the Daltons"). For a Finnish film the original *is*
  the Finnish title and the span holds the Swedish one alone ("En kotte under ryggen" for
  Käpy selän alla), so the first segment is published as `original` only when the Maa
  row names no Finnish share and the span lists at least two titles. Both feed the TMDB
  search in `enrich_tmdb.py`; the ticket page prints the same line but is read only for
  prices and under a quota, so nothing here depends on it.
- **No images from the site.** The stills are 16:9, the film page's `og:image` too, so
  posters come from TMDB.

An empty first window is asked for once more and then fails the venue, keeping the
previous file; it is never read as a confirmed empty programme. The first version took the
listing page's `shows-coming` count as evidence and published an empty venue on 2026-09-05
at 16:57 UTC: a runner had received a small HTTP 202 challenge shell from SiteGround
(`sg-f-cache`), which `fetch` accepts as success, while an ordinary connection got 21 rows.
A page that is not the page has no `shows-coming` either, so a missing class is not
evidence. A challenge shell is now recognised and named in the log, an empty answer is
retried once and then fails. Moved to the local half 2026-09-06: three of the next six
cloud runs were challenged, and a diagnostics probe from a refused runner got the same shell
for the homepage, so the address is refused for the whole host and a retry cannot help.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

import prices
from common import capped, fetch, get_text
from etiketti import lang_codes

BASE = "https://kinoregina.fi"
SCHEDULE = BASE + "/wp-content/themes/kinoregina2/assets/functions/getShowtimesMoviesV2.php"
LISTING = BASE + "/ohjelmisto/elokuvat/"
FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"
HEADERS = {"user-agent": UA, "accept-language": "fi-FI,fi;q=0.9"}

VENUE = {"id": "regina-helsinki", "provider": "regina", "providerId": "1",
         "name": "Kino Regina", "short": "Kino Regina", "city": "Helsinki"}

# `reads` names kauppa.kavi.fi because the price pass GETs TICKETS pages there, which
# `base` does not cover. Found by the first run to carry the `[run] hosts:` line rather
# than by reading the code: `logs/run-regina.log` on 2026-09-16 reported two hosts
# attempted where the site declared one.
SITES = [{"provider": "regina", "label": "Kino Regina", "base": BASE,
          "reads": ("kauppa.kavi.fi",), "venues": [VENUE]}]

# No EMPTY_VENUES_CONFIRMED here, on purpose: see the module docstring.

BLOCK_RE = re.compile(r'<div class="movie pr col-12 ([a-z]*)">(.*?)(?=<div class="movie pr col-12 |$)', re.S)
FILM_RE = re.compile(r'<a href="(?:https?://kinoregina\.fi)?/elokuva/(\d+)/?"[^>]*class="title[^"]*"[^>]*>(.*?)</a>', re.S | re.I)
START_RE = re.compile(r'class="start">\s*(\d{2})-(\d{2})-(\d{4})\s+(\d{1,2}):(\d{2})\s*<', re.I)
TICKET_RE = re.compile(r'href="(https://kauppa\.kavi\.fi/[^"]+)"', re.I)
TAGS_RE = re.compile(r"<[^>]+>")

# Film page: the detail grid, the age-limit image, the synopsis section.
GRID_RE = re.compile(r'<div class="col-4 col-md-2"><b><span>(.*?)</span></b></div>\s*'
                     r'<div class="col-8 col-md-4">(.*?)</div>', re.S | re.I)
AGE_RE = re.compile(r'alt="Ikäraja:\s*(K\s*-?\s*\d+|S|T)"', re.I)
KESTO_RE = re.compile(r"(\d+)\s*min", re.I)
HEADING_RE = re.compile(r'id="main-content"[^>]*>.*?<h1>(.*?)</h1>', re.S | re.I)
YEAR_RE = re.compile(r"\(\s*((?:19|20)\d{2})\s*\)\s*$")
ORIGINAL_RE = re.compile(r'<span class="original-name">(.*?)</span>', re.S | re.I)
KUVAUS_RE = re.compile(r'<a name="kuvaus"></a>.*?<div class="col-12 single-movie-main-content-area">(.*?)</div>',
                       re.S | re.I)
PARA_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
GAUGE_RE = re.compile(r"\b(8|16|35|70)\s*mm\b", re.I)

# A Teemat value is a strand tag when it is a concise named series: short, no subtitle
# after a colon, and not the cinema's generic scheduling words. "PAUL THOMAS ANDERSON"
# and "KESÄJAZZIT" qualify; "JATKOAIKA KESÄ 2026" and "KURITTOMAT SUKUPOLVET: NUORISOA
# SUOMALAISESSA ELOKUVASSA" do not.
SERIES_MAX_LEN = 26
SERIES_MAX_WORDS = 4
GENERIC_SERIES = ("jatkoaika", "ohjelmisto", "elokuvat", "uutuudet", "teemat",
                  "kesä", "syksy", "talvi", "kevät")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))).strip()


def _para(s):
    """Paragraph text with inline markup removed without leaving a gap."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub("", s))).strip()


ROMAN_RE = re.compile(r"^[ivx]+$")
# A title with one of these words is English: Finnish has none of them. It then gets
# English title case, with the small words below in lowercase unless they open the title
# or a subtitle. Everything else is sentence case, the Finnish convention. Words that
# both languages share ("on", "a", "in") are deliberately not triggers.
ENGLISH_MARKERS = {"the", "of", "upon", "and", "with", "from"}
SMALL_WORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "but",
               "with", "from", "by", "vs"}


def recase(title):
    """"PHANTASM - YÖN KAUHUT" -> "Phantasm - Yön kauhut", "THE TURIN HORSE" -> "The Turin
    Horse"; a title that already has a lowercase letter is left alone. Roman numerals stay
    upper; the first word after a colon or a dash gets a capital."""
    t = (title or "").strip()
    if not t or any(ch.islower() for ch in t):
        return t
    words = t.lower().split(" ")
    english = any(w.strip(",.!?") in ENGLISH_MARKERS for w in words)
    out, cap = [], True
    for w in words:
        if not w:
            out.append(w)
            continue
        if ROMAN_RE.fullmatch(w):
            out.append(w.upper())
        elif cap or (english and w.strip(",.!?") not in SMALL_WORDS):
            out.append(w[0].upper() + w[1:])
        else:
            out.append(w)
        cap = w.endswith(":") or w in ("-", "–")
    return " ".join(out)


def cased_in(text, title):
    """The title as `text` spells it, when the text carries the same title in another
    casing; "" otherwise. The cinema's own synopsis is the one source on this site that
    writes a title in mixed case."""
    if not text or not title:
        return ""
    m = re.search(r"(?<![\wÀ-ÿ])" + re.escape(title) + r"(?![\wÀ-ÿ])", text, re.I)
    if not m:
        return ""
    found = m.group(0)
    return found if found != title and any(ch.islower() for ch in found) else ""


def parse_schedule(page):
    """The POST response -> [show]. Rows without a film link (events) are skipped."""
    shows, seen = [], set()
    for m in BLOCK_RE.finditer(page):
        block = m.group(2)
        f = FILM_RE.search(block)
        s = START_RE.search(block)
        if not (f and s):
            continue
        fid, title = f.group(1), recase(_txt(f.group(2)))
        if not title:
            continue
        day, month, year, hh, mm = (int(x) for x in s.groups())
        try:
            start = datetime.datetime(year, month, day, hh, mm, tzinfo=FI).isoformat()
        except ValueError:
            continue
        if (fid, start) in seen:
            continue
        seen.add((fid, start))
        t = TICKET_RE.search(block)
        shows.append({
            "eventId": fid,
            "title": title,
            "original": "",
            "len": "",
            "rating": "",
            "genres": "",
            "method": "",
            "theatre": VENUE["name"],
            "aud": "",
            "start": start,
            # The show's own KAVI ticket page; the film page when a row carries none.
            "url": t.group(1) if t else f"{BASE}/elokuva/{fid}/",
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "",
            "provider": "regina",
            "venue": VENUE["id"],
        })
    shows.sort(key=lambda s: s["start"])
    return shows


# ---------------------------------------------------------------- film pages

# The Tekstitys cell saying outright there are none, `XX-S` as at Kino Engel. Read
# 2026-10-04 on 10 of 110 film pages, Finnish classics and English-language prints; 28
# leave the cell blank, so the words are chosen per print.
NO_SUBS_RE = re.compile(r"^ei tekstityst\u00e4\.?$", re.I)


def _subs(text):
    """"suom. tekstit/svensk text" -> ["FI-S", "SV-S"]; "ei tekstitystä" -> ["XX-S"]."""
    if NO_SUBS_RE.match((text or "").strip()):
        return ["XX-S"]
    low = (text or "").lower()
    out = []
    for key, code in (("suom", "FI"), ("svensk", "SV"), ("ruots", "SV"), ("engl", "EN")):
        if key in low and f"{code}-S" not in out:
            out.append(f"{code}-S")
    return out


# A Lisätieto segment that states the audio, the cell's segments split on " * " (read
# 2026-10-04): "puhumme suomea" (Nalle Puhin elokuva), "suomenkielinen versio" (Tiikerin
# oma elokuva). A whole segment only: "suomenkielisen version ohjaus ..." is a credit.
AUDIO_SEGMENT_RE = re.compile(r"^(?:puhumme (suomea)|([a-zåäö]+kielinen) versio)$", re.I)


def _audio(text):
    """"animaatio ... * suomenkielinen versio" -> ["FI-A"]; [] when no segment states it."""
    out = []
    for seg in (x.strip() for x in (text or "").split(" * ")):
        m = AUDIO_SEGMENT_RE.match(seg)
        codes = lang_codes(m.group(1) or m.group(2)) if m else []
        if len(codes) == 1 and f"{codes[0]}-A" not in out:
            out.append(f"{codes[0]}-A")
    return out


def published_year(page):
    """The bracketed year in the main heading, "LUCKY LUKE SOTAPOLULLA (1978)" -> "1978";
    "" when the heading carries none."""
    m = HEADING_RE.search(page or "")
    if not m:
        return ""
    y = YEAR_RE.search(_txt(m.group(1)))
    return y.group(1) if y else ""


def original_title(page, country):
    """The first segment of the original-name span, where the observed convention holds.

    Observed on five pages (2026-09-13): a foreign film lists original, Swedish and
    sometimes English, slash-separated ("La ballade des Dalton/Lucky Luke på
    krigsstigen/The Ballad of the Daltons"); a Finnish film's original is the title the
    cinema already publishes and its span holds the Swedish title alone ("En kotte under
    ryggen"). Publishing that as the original would put a Swedish title on the English
    UI and into the TMDB search. So the first segment is taken only when the Maa row is
    present and names no Finnish share at all, and the span lists at least two titles;
    a co-production in either order, a missing country and a lone segment are left
    empty, since nothing observed says what they mean. The year is not affected."""
    countries = [c.strip().lower() for c in (country or "").split("/") if c.strip()]
    if not countries or any(c.startswith("suomi") for c in countries):
        return ""
    m = ORIGINAL_RE.search(page or "")
    if not m:
        return ""
    parts = [x.strip() for x in _txt(m.group(1)).split("/") if x.strip()]
    if len(parts) < 2:
        return ""
    return parts[0]


def series_tag(value):
    """A Teemat value as a strand tag, or "" when it is generic or not concise."""
    v = _txt(value)
    if not v or ":" in v or len(v) > SERIES_MAX_LEN or len(v.split()) > SERIES_MAX_WORDS:
        return ""
    if v.lower().split()[0] in GENERIC_SERIES:
        return ""
    return v


def gauge_tag(value):
    """"35 mm" -> "35 mm"; "DCP" and any prose -> ""."""
    m = GAUGE_RE.search(_txt(value))
    return f"{m.group(1)} mm" if m else ""


def details(page, title=None):
    """Film-page metadata. Returns {} for anything the page does not carry. With `title`,
    the Kuvaus text is searched for the same title in the cinema's own casing."""
    d = {}
    grid = {}
    for label, cell in GRID_RE.findall(page):
        grid[_txt(label).lower()] = cell
    m = AGE_RE.search(page)
    if m:
        tok = re.sub(r"\s|-", "", m.group(1).upper())
        d["rating"] = "S" if tok in ("S", "T") else f"K-{tok[1:]}"
    kesto = KESTO_RE.search(_txt(grid.get("kesto", "")))
    if kesto:
        d["len"] = kesto.group(1)
    langs = _audio(_txt(grid.get("lisätieto", ""))) + _subs(_txt(grid.get("tekstitys", "")))
    if langs:
        d["lang"] = ", ".join(langs)
    tags = []
    for a in re.findall(r"<a\b[^>]*>(.*?)</a>", grid.get("teemat", ""), re.S | re.I):
        tag = series_tag(a)
        if tag and tag not in tags:
            tags.append(tag)
    gauge = gauge_tag(grid.get("kopiotieto", ""))
    if gauge:
        tags.append(gauge)
    if tags:
        d["method"] = " · ".join(tags)
    year = published_year(page)
    if year:
        d["year"] = year
    original = original_title(page, _txt(grid.get("maa", "")))
    if original:
        d["original"] = original
    k = KUVAUS_RE.search(page)
    if k:
        # Only Kuvaus, never Lisätieto: the lead paragraphs up to the "***" rule that
        # separates the synopsis from the programme essay below it.
        paras = []
        for p in PARA_RE.findall(k.group(1)):
            text = _para(p)
            if re.fullmatch(r"\*{2,}", text):
                break
            if text:
                paras.append(text)
        text = " ".join(paras)
        if len(text) > 40:
            d["_syn"] = text
        if title:
            # The whole Kuvaus section, essay included: the proper-cased title is often in
            # the essay's first sentence rather than the lead.
            cased = cased_in(_para(k.group(1)), title)
            if cased:
                d["title"] = cased
    return d


def enrich(shows, get=None):
    """One film page per film, folded onto every showtime of it."""
    get = get or (lambda u: get_text(u, fetcher=fetch, tries=2, backoff=3, timeout=20))
    by_film = {}
    for s in shows:
        by_film.setdefault(s["eventId"], []).append(s)
    ok = fail = 0
    for n, (fid, rows) in enumerate(capped(sorted(by_film.items()), "regina")):
        if n:
            time.sleep(0.5)
        url = f"{BASE}/elokuva/{fid}/"
        try:
            d = details(get(url), title=rows[0]["title"])
        except Exception as e:
            fail += 1
            print(f"[regina] film page {fid} failed: {type(e).__name__}: {e}")
            continue
        if not d:
            fail += 1
            print(f"[regina] film page {fid}: nothing parsed")
            continue
        ok += 1
        for s in rows:
            for key, val in d.items():
                if key == "title":
                    s[key] = val            # the cinema's own casing replaces the sentence case
                elif val and not s.get(key):
                    s[key] = val
    print(f"[regina] film pages: {ok} parsed, {fail} with nothing usable, "
          f"{sum(1 for s in shows if s.get('rating'))}/{len(shows)} showtimes rated")
    return shows


def get_schedule(day):
    """One window of the schedule, from `day` (YYYY-MM-DD) onwards."""
    body = f"getShowtimesMovies={day}".encode("ascii")
    return fetch(SCHEDULE, data=body, cache=False,
                 headers={**HEADERS, "content-type": "application/x-www-form-urlencoded"},
                 timeout=40).decode("utf-8", "replace")


# Each answer covers about two weeks and ends with the page's "Lataa lisää" button,
# whose onclick names the day the next window starts. Followed until a window has no
# screenings, and no further than MAX_PAGES windows: the programme is published a few
# weeks ahead, so the second call is normally the empty one.
NEXT_RE = re.compile(r"loadNextTwoWeeks\('(\d{4}-\d{2}-\d{2})'")
MAX_PAGES = 4


def challenged(page):
    """SiteGround's captcha answers a refused address with a ~170-byte meta-refresh shell
    that names `sgcaptcha`; an honest empty window is a ~590-byte fragment with the
    load-more button. Either marker is enough on its own."""
    low = (page or "").lower()
    return "sgcaptcha" in low or "sg-captcha" in low or len(low.strip()) < 300


def fetch_schedule(today=None, get=None, sleep=1.0):
    """Every window from today -> [page html]. The first page is always fetched."""
    get = get or get_schedule
    day = (today or datetime.datetime.now(FI).date()).isoformat()
    pages = []
    for n in range(MAX_PAGES):
        if n:
            time.sleep(sleep)
        page = get(day)
        if challenged(page):
            raise RuntimeError(f"challenged: {len(page)} bytes for the window from {day}, "
                               f"the SiteGround shell rather than the schedule (a refused "
                               f"address; see the module docstring)")
        if n == 0 and not parse_schedule(page):
            # One empty first answer proves nothing: a runner got one at 16:57 UTC on
            # 2026-09-05 while the same POST from elsewhere listed 21 rows. Ask once more
            # before the caller fails the venue, and say what the empty answer looked
            # like, in counts, so the next such log can be read.
            print(f"[regina] first window from {day} has no screenings: {len(page)} bytes, "
                  f"{len(re.findall('day-header', page))} day headers, "
                  f"{'with' if NEXT_RE.search(page) else 'without'} the load-more button; "
                  f"asking once more")
            time.sleep(sleep * 3)
            page = get(day)
            if challenged(page):
                raise RuntimeError(f"challenged on the second try: {len(page)} bytes for "
                                   f"the window from {day}")
        pages.append(page)
        if not parse_schedule(page):
            break
        m = NEXT_RE.search(page)
        if not m or m.group(1) <= day:
            break
        day = m.group(1)
    print(f"[regina] schedule: {len(pages)} window(s), the last from {day}")
    return pages


# ---------------------------------------------------------------- prices

# KAVI's shop page a showtime links to lists ticket categories as rows: a <label> with the
# category and a schema.org Offer carrying <span itemprop="price">10,00 €</span> (twice,
# one per breakpoint). "Peruslippu" is the ordinary ticket; KAVI-klubilaisten lippu and
# Lapsi are not. Probed 2026-09-13 on two screenings: 10,00 € both. The fetch, cache and
# pacing are prices.py's; Regina runs on the local half, so the pages are read from there.
TICKETS = "https://kauppa.kavi.fi/"
ORDINARY = "peruslippu"
PRICE_ROW_RE = re.compile(r'<div class="row[^"]*"[^>]*>(.*?)(?=<div class="row|</form>)', re.S)
LABEL_RE = re.compile(r"<label\b[^>]*>(.*?)</label>", re.S)
OFFER_RE = re.compile(r'itemprop="price"[^>]*>\s*([^<]+?)\s*<', re.S)
AMOUNT_RE = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:\u20ac|EUR)", re.I)


def ordinary_price(page_html):
    """The Peruslippu price on a KAVI shop page -> "10\u20ac" or "" (absent, ambiguous)."""
    amounts = []
    for row in PRICE_ROW_RE.findall(page_html or ""):
        label = LABEL_RE.search(row)
        if not label or _txt(label.group(1)).lower() != ORDINARY:
            continue
        for offer in OFFER_RE.findall(row):
            m = AMOUNT_RE.search(html_mod.unescape(offer))
            if m:
                amounts.append(m.group(1))
    return prices.one_amount(amounts) if amounts else ""


def fetch_site(site=SITES[0], price_sleep=1.0, prices_path=None, now=None, today=None):
    """Runner contract: the schedule windows, one venue. An empty answer, asked twice, is
    a failure and not an empty programme; the previous file stays.

    `today` is the first window's start, the seam every other adapter here carries.
    `run.py` never passes one, so production reads the clock. It exists because the
    runner tests could not otherwise pin the date: their fixture names the later windows
    as literals, and on the two days a year the clock landed on one of those literals the
    first key and a later key collided, one window's body replaced the other's, and three
    tests failed on main for reasons nothing in the diff explained.
    """
    shows = parse_schedule("".join(fetch_schedule(today)))
    if not shows:
        raise RuntimeError("schedule answered twice with no screenings; nothing the site "
                           "publishes can confirm an empty programme, so the previous "
                           "file is kept")
    enrich(shows)
    prices.run(shows, provider=site["provider"], prefix=TICKETS, parse=ordinary_price,
               referer=BASE + "/", path=prices_path, now=now, sleep=price_sleep,
               fetch_fn=lambda url, headers: fetch(url, headers=dict(HEADERS, referer=BASE + "/"),
                                                   tries=2, timeout=20))
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse_schedule(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    dates = sorted({s["start"][:10] for s in data})
    print(f"{len(data)} showtimes, {len({s['eventId'] for s in data})} films, {len(dates)} dates "
          f"({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'})")
    for s in data:
        print(f"  {s['start'][:16]}  {s['title'][:34]:36} {s['rating']:5} {s['len']:4} "
              f"{s['lang']:14} {s['method'][:30]:32} {s['eventId']}")
