"""Kino Hamina, the town's own cinema on the municipal site. Stdlib only.

One request. `hamina.fi/asukkaalle/vapaa-aika/kulttuuri/kino-hamina/` renders the whole
programme, one `large-content-showcase` block per film:

    <div class="large-content-showcase columns ...">
      <img width="768" height="1094" src="https://efeh4kjo5c9.exactdn.com/app/uploads/...">
      <h3 class="large-content-showcase__title ...">Hetki ennen valoa</h3>
      <div class="large-content-showcase__paragraph ...">
        <p>Ensi-ilta: 11.09.2026<br />Ikäraja: 7<br />Kesto: 1 t 27 min<br />
           Liput: 11€<br />Versio: <strong>OG</strong><br />Levittäjä: B-Plan<br />
           Ohjaus: Klaus Härö</p>
        <p>Su 20.9. Klo 17:00<br />Ke 23.9. Klo 13:00 | <em><strong>Liput 8€</strong></em>
           <br />To 24.9. Klo 17:00</p>

What shapes the parser:

- **Two paragraphs, and they do different jobs.** The first is the film's labelled fields,
  the second one line per screening. A block whose second paragraph holds no readable line
  is a film with nothing scheduled, which the page uses for a run that has ended, so it is
  counted and left out rather than failing the site.
- **A screening line prints no year**, so the weekday selects it through
  `common.resolve_year`, and a line it cannot place raises rather than disappearing. Same
  shape as Kino Myyri's rows.
- **The price is settled per screening and the page says so twice.** `Liput: 11€` in the
  film's own fields is that film's ticket, and a screening line carrying `| Liput 8€`
  overrides it for that showing. The page's own summary, "elokuvalippujen hinnat vaihtelevat
  8-11€ välillä", is the range across the programme rather than a band for any one row, so
  it is not read. A film whose `Liput:` is itself a range or an "alkaen" figure settles
  nothing and its rows publish no price.
- **No ticket URL exists and none is invented.** The page states "Ei ennakkovarauksia.
  Lipunmyynti alkaa n. 30min ennen elokuvan alkamista!", so the provider is registered
  `book="door"` and a showtime opens this page, the way Julia 1&2 does.
- **The version tag is the language.** The page's own legend reads "OG = Alkuperäinen kieli,
  tekstitys suomeksi (ja) ruotsiksi. DUB = Puhuttu suomeksi.", so `DUB` publishes `FI-A` and
  `OG` publishes `FI-S`. Swedish is hedged in that sentence and is not published.
- **The poster is portrait and on the site's own CDN.** 700x1000 and 768x1097 on the films
  read 2026-09-18, with the dimensions in the tag, so a landscape illustration would be
  left out the way `tribe.py` leaves one out.
- The page publishes no synopsis and no genre, so both stay empty and the shared enrichment
  fills what it can.

**Zero rows fails the site.** No emptied programme has been seen here, so there is no
evidence of what one looks like and nothing may claim it: `common.EmptyProgramme` is for the
case where that evidence is in hand.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

from common import check_shows, fetch, get_text, resolve_year, weekday_index
from synmerge import norm

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kinohamina", "label": "Kino Hamina",
     "base": "https://www.hamina.fi",
     "listing": "/asukkaalle/vapaa-aika/kulttuuri/kino-hamina/",
     "venues": [{"id": "kinohamina-hamina", "name": "Kino Hamina",
                 "short": "Kino Hamina", "city": "Hamina"}]},
]

# `resolve_year`'s (behind, ahead). The programme read on 2026-09-18 reached six days out
# and the page is a weekly one, so 120 is headroom rather than a fit.
WINDOW = (30, 120)

BLOCK_RE = re.compile(r'<div class="large-content-showcase columns.*?(?=<div class="large-content-showcase columns|<div class="large-content-showcases__|\Z)',
                      re.S)
TITLE_RE = re.compile(r'class="large-content-showcase__title[^"]*"[^>]*>(.*?)</h3>', re.S | re.I)
PARA_RE = re.compile(r"<p>(.*?)</p>", re.S | re.I)
IMG_RE = re.compile(r'<img[^>]*?width="(\d+)"[^>]*?height="(\d+)"[^>]*?src="([^"]+)"', re.I)
# `To 24.9. Klo 13:00`, with an optional `| Liput 8€` for that showing alone, or
# `(Liput 8€)` as the page wrote it on 2026-10-04.
SHOW_RE = re.compile(r"(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.\s*klo\s*(\d{1,2})[:.](\d{2})"
                     r"(?:[^\n]*?[|(]\s*liput\s*([\d.,]+)\s*€)?", re.I)
LABEL_RE = re.compile(r"^([A-Za-zÄÖÅäöå -]{3,20}):\s*(.+)$")
# "1 t 27 min", and "1 h 42 min" on two films read 2026-10-04.
MIN_RE = re.compile(r"(?:(\d{1,2})\s*[th]\s*)?(\d{1,3})\s*min", re.I)
AMOUNT_RE = re.compile(r"^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$")
TAGS_RE = re.compile(r"<[^>]+>")

POSTER_MIN_RATIO = 1.2
POSTER_MIN_WIDTH = 300


class ShowRowError(RuntimeError):
    """A screening line the page prints and this parser could not place.

    Skipping it would publish a schedule one screening short with nothing in the log to
    say so, so it fails the site and the previous files stand.
    """


def _txt(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = TAGS_RE.sub(" ", s)
    s = html_mod.unescape(s).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")).strip()


def _minutes(text):
    """`1 t 27 min`, `1 h 42 min` or `95 min` -> "87" / "102" / "95". -> str, "" when no
    shape is there."""
    m = MIN_RE.search(text or "")
    if not m:
        return ""
    hours = int(m.group(1) or 0)
    return str(hours * 60 + int(m.group(2)))


def _rating(value):
    v = (value or "").strip()
    m = re.match(r"\d+", v)
    if m:
        return f"K-{int(m.group(0))}"
    return "S" if v.lower().startswith(("s", "sallittu")) else ""


def _price(value):
    """A labelled `Liput` value -> the amount, or "" when it settles nothing.

    A single amount is this film's ticket. Anything else, a range or an "alkaen" figure,
    settles no screening and publishes nothing.
    """
    m = AMOUNT_RE.match((value or "").strip())
    return f"{m.group(1)}€" if m else ""


def fields(block):
    """The film's first paragraph -> {label: value}, lowercased keys."""
    paras = PARA_RE.findall(block)
    out = {}
    for line in _txt(paras[0] if paras else "").split("\n"):
        m = LABEL_RE.match(line)
        if m:
            out.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return out


def poster(block):
    m = IMG_RE.search(block)
    if not m:
        return ""
    w, h, url = int(m.group(1)), int(m.group(2)), html_mod.unescape(m.group(3))
    if w < POSTER_MIN_WIDTH or h < w * POSTER_MIN_RATIO:
        return ""
    return url


def rows(site, page, today=None):
    """-> ([show], report). One row per screening line the page prints."""
    today = today or datetime.datetime.now(FI).date()
    venue = site["venues"][0]
    out, report = [], {"no_dates": [], "no_price": set()}
    for n, block in enumerate(BLOCK_RE.findall(page)):
        title = _txt(TITLE_RE.search(block).group(1)) if TITLE_RE.search(block) else ""
        if not title:
            continue                  # the legend block above the films carries no title
        f = fields(block)
        paras = PARA_RE.findall(block)
        lines = _txt(paras[1]) if len(paras) > 1 else ""
        found = SHOW_RE.findall(lines)
        if not found:
            report["no_dates"].append(title)
            continue
        base = _price(f.get("liput"))
        if not base:
            report["no_price"].add(title)
        version = (f.get("versio") or "").strip().upper()
        for wd, day, month, hh, mm, own in found:
            year = resolve_year(int(day), int(month), today, weekday_index(wd), WINDOW)
            if year is None:
                raise ShowRowError(
                    f"{site['provider']}: {title!r} prints {wd} {day}.{month}. and no "
                    f"candidate year carries that weekday inside the window, so the "
                    f"screening cannot be placed")
            try:
                start = datetime.datetime(year, int(month), int(day), int(hh), int(mm),
                                          tzinfo=FI)
            except ValueError as e:
                raise ShowRowError(f"{site['provider']}: {title!r} prints the impossible "
                                   f"date {day}.{month}.{year}") from e
            out.append({
                "eventId": norm(title),
                "title": title,
                "original": "",
                "len": _minutes(f.get("kesto", "")),
                "rating": _rating(f.get("ikäraja")),
                "genres": "",
                "method": "",
                "theatre": venue["name"],
                "aud": "",
                "start": start.isoformat(),
                "url": site["base"].rstrip("/") + site["listing"],
                "img": poster(block),
                "lang": {"DUB": "FI-A", "OG": "FI-S"}.get(version, ""),
                "soldOut": False,
                "price": f"{own.strip()}€" if own else base,
                "provider": site["provider"],
                "venue": venue["id"],
            })
    out.sort(key=lambda s: s["start"])
    return out, report


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, today=None):
    pid = site["provider"]
    url = site["base"].rstrip("/") + site["listing"]
    shows, report = rows(site, get(url), today)
    if not shows:
        raise RuntimeError(
            f"{url}: no screening line on the page. No emptied programme has been seen "
            f"here, so there is no evidence of one to read this as, and the previous "
            f"files stand")
    venue = site["venues"][0]
    per_venue = {venue["id"]: shows}
    check_shows(per_venue, pid, {venue["id"]})
    print(f"[{pid}] {len(shows)} screening(s) over "
          f"{len({s['eventId'] for s in shows})} film(s)")
    if report["no_dates"]:
        print(f"[{pid}] {len(report['no_dates'])} film(s) with no screening line, left "
              f"out: {', '.join(report['no_dates'][:6])}")
    if report["no_price"]:
        print(f"[{pid}] {len(report['no_price'])} film(s) whose Liput line settles no "
              f"amount: {', '.join(sorted(report['no_price'])[:6])}")
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {venue['name']}: {len(shows)} showtimes, {len(days)} dates")
    return per_venue


if __name__ == "__main__":
    for vid, shows in fetch_site(SITES[0]).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:8]:
            print(f"   {s['start'][:16]}  {s['title'][:32]:34} {s['rating']:5} "
                  f"{s['len']:4} {s['price']:6} {s['lang']:6} img={'y' if s['img'] else '-'}")
    sys.exit(0)
