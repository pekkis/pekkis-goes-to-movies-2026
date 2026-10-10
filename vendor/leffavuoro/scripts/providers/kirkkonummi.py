"""Kino Kirkkonummi, Munkinmäentie 17. Stdlib only.

Probed 2026-09-15. A WordPress site built in Elementor, and the whole cinema is one page.
It was deferred on 2026-09-15 as too fragile to parse, on the grounds that the showtimes
are hand-authored inside page-builder markup with no year and no booking host. That was a
maintenance judgement rather than a demonstration, and it does not survive contact with
the page: the screenings are server-rendered in a consistent shape and three of them a
week is not a hard parse. It is implemented here.

The markup carries no semantic class for a screening. What it does carry is a film title
in a heading and its screenings in a following icon list:

    <p class="elementor-heading-title ...">Myrskyn Ikkuna</p>
    ...<span class="elementor-icon-list-text">20.9. Sunnuntai klo18.00</span>
    ...<span class="elementor-icon-list-text">22.9. Tiistai klo19.00</span>

So the parser walks headings and list items **in document order**, keeping the last
heading as the current film. Four things about this page decide the rest:

- **Every block is published twice**, once for desktop and once for mobile: 21 headings
  and 46 list items for 6 films. Each screening therefore arrives twice and is deduplicated
  on (film, start). A parser that trusted the count would double every showtime.
- **A list item is a screening only if it reads `D.M. Weekday kloHH.MM`.** The same element
  carries cast lists, directors, notes like "vain tämä näytös", the street address and the
  phone number. None of them match, so no exclusion list is needed for those.
- **"Tulossa 25.9. alkaen" is a release date, not a screening.** It names a day and a month
  and no time at all, so the same rule drops it. The word `tulossa` also appears as a
  decorative heading above several films that *do* have screenings, so it is not usable as
  a marker either way; only the shape of the row decides.
- **No year, but every row carries a weekday**, which selects one candidate year
  unambiguously. It does not prove the cinema meant that date, so `common.resolve_year`
  also bounds how far the answer may fall from today. A weekday matching no candidate, or
  one selecting a date roughly a year away, leaves the row unplaced and counted.

The time is written `klo18.00`, with no space and a dot for minutes.

There is no per-film page and no booking host: the site is one page and tickets are
reserved by phone. So a showtime opens that page and the registry entry is `book="list"`,
which is what that mode is for. No auditorium is published either. The page mentions two
seat counts, 112 and 68, but never says which screening is in which, so none is invented.
"""
import datetime
import html as html_mod
import re
import sys
from zoneinfo import ZoneInfo

import synmerge
from common import fetch, get_text, resolve_year, served, weekday_index
from etiketti import strict_codes
from huvimylly import KAVI_CODES

BASE = "https://kinokirkkonummi.fi"
LISTING = BASE + "/"
FI = ZoneInfo("Europe/Helsinki")

VENUE = {"id": "kirkkonummi", "name": "Kino Kirkkonummi", "short": "Kino Kirkkonummi",
         "city": "Kirkkonummi"}

SITES = [{"provider": "kirkkonummi", "label": "Kino Kirkkonummi", "base": BASE,
          "venues": [VENUE]}]

# The horizon this source was measured at on 2026-09-15: 8 dates, -1 to +9 days. 30 behind
# and 60 ahead is several times that and far short of the 365 a mistyped weekday would need.
WINDOW = (30, 60)

CONTAINER_RE = re.compile(r'elementor-icon-list-text', re.I)
HEAD_RE = re.compile(r'<p class="elementor-heading-title[^"]*">(.*?)</p>', re.S | re.I)
ITEM_RE = re.compile(r'<span class="elementor-icon-list-text">(.*?)</span>', re.S | re.I)
SHOW_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})\.\s*([A-Za-zÄÖäö]{2,12})\s*klo\s*'
                     r'(\d{1,2})[.:](\d{2})\s*$', re.I)
# `26-27.9. La,Su klo17.00`: consecutive days at one time, a weekday for each (2026-09-27).
RANGE_RE = re.compile(r'^(\d{1,2})\s*-\s*(\d{1,2})\.(\d{1,2})\.\s*([A-Za-zÄÖäö, ]{2,60}?)\s*'
                      r'klo\s*(\d{1,2})[.:](\d{2})\s*$', re.I)
TIMED_RE = re.compile(r'klo\s*\d{1,2}[.:]\d{2}', re.I)

# Headings that are not films. `tulossa` labels a film that is coming and sits *above* its
# title, so it must not become one; the two seat counts belong to the auditoriums and sit
# in the footer.
NOT_A_TITLE = re.compile(r'^(?:tulossa|elokuvateatteri|\d+\s*paikkaa)$', re.I)
# `<div>Liput 14,50</div>` in the film's own block, beside `Kesto` and `Ikäraja`. Per film
# and not per cinema: 14,50 and 15,50 both appear on the page read 2026-09-16, so a single
# house price would be wrong for some of the programme. No currency symbol is printed.
# `Liput 15e` states whole euros.
SEP = r'(?:\s|&nbsp;|<[^>]+>)*'
PRICE_RE = re.compile(r'Liput' + SEP + r'(\d{1,3}(?:[.,]\d{2}|(?=\s*(?:e|€|eur)\b)))', re.I)
# The block's other facts, `Kesto: <span>102 min</span>`, `Kesto 1h 27min`, `Ikäraja 7`,
# `Genres: <span>draama</span>`, read the same way (2026-09-27).
KESTO_RE = re.compile(r'Kesto:?' + SEP + r'(?:(\d)\s*h(?:\s*(\d{1,2})\s*min)?|(\d{2,3})\s*min)',
                      re.I)
AGE_RE = re.compile(r'Ik(?:ä|&auml;)raja:?' + SEP + r'(S|\d{1,2})\b', re.I)
GENRE_RE = re.compile(r'Genres?:' + SEP + r'([^<]+)', re.I)
# `Kieli: <span>Italia</span>` in the same block (La Grazia, read 2026-10-04): the spoken
# language. A name no table knows publishes nothing.
KIELI_RE = re.compile(r'Kieli:' + SEP + r'([^<]+)', re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def by_title(page, rx, value):
    """What each film's block states for `rx`. -> {title: value(match)}.

    Keyed on the heading above it rather than on its position relative to the screening
    list, because the block prints the two in either order. A `value` of "" is no value.

    **A heading with two different values under it is absent.** Nothing in the markup
    delimits a film's block, so a line in the page's own furniture attaches to the heading
    above it, and the page emits the whole programme twice, so one between the two copies
    lands under the first copy's last film. Where that happens the association is
    ambiguous and neither is published. The same value twice is not ambiguous, which is
    what the duplicated programme produces for every real film.
    """
    heads = [(m.start(), _txt(m.group(1))) for m in HEAD_RE.finditer(page)]
    seen = {}
    for m in rx.finditer(page):
        # The nearest heading of **any** kind. Skipping a `tulossa` label to reach the film
        # title above it would put one film's value on another's screenings, so a value
        # under the label keys on the label, and `parse` looks up film titles only.
        prior = [t for pos, t in heads if pos < m.start()]
        v = value(m)
        if prior and prior[-1] and v:
            seen.setdefault(prior[-1], set()).add(v)
    return {title: next(iter(vs)) for title, vs in seen.items() if len(vs) == 1}


def prices_by_title(page):
    """The price each film's block states. -> {title: "14.5\u20ac"}.

    Keyed on the heading above it rather than on its position relative to the screening
    list, because the block prints the two in either order. The first price under a heading
    wins, so a later mention in prose cannot displace the film's own.

    A film whose block states none is simply absent, and its screenings publish no price:
    this is what the page says, and there is no house price to fall back on.

    **A heading with two different amounts under it is absent too.** Nothing in the markup
    delimits a film's block, so a `Liput NN,NN` in the page's own furniture attaches to the
    heading above it, and the page emits the whole programme twice, so one between the two
    copies lands under the first copy's last film. Where that happens the association is
    ambiguous and neither amount is published -- taking the first would publish an amount
    whose applicability to that film is exactly what is in doubt. The same amount twice is
    not ambiguous, which is what the duplicated programme produces for every real film.

    The page read 2026-09-16 carried three such lines and all three were inside a film's
    block.
    """
    return {t: f"{v:.2f}".rstrip("0").rstrip(".") + "\u20ac" for t, v in by_title(
        page, PRICE_RE, lambda m: float(m.group(1).replace(",", "."))).items()}


def _minutes(m):
    return str(int(m.group(3)) if m.group(3) else int(m.group(1)) * 60 + int(m.group(2) or 0))


def _age(m):
    code = m.group(1).upper().lstrip("0")
    return "" if code not in KAVI_CODES else "S" if code == "S" else f"K-{code}"


def parse(page, today=None):
    """The one page -> [show]. Raises when no icon list is present, and when the lists
    are there with no screening row in them. No empty state is recorded for this site, so
    zero rows is never read as nothing on."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{LISTING}: no icon list on the page ({served(page)}), so this is not the "
            f"programme this parser reads. Treating it as a fetch or template failure "
            f"rather than a cinema with nothing on")
    today = today or datetime.datetime.now(FI).date()
    prices = prices_by_title(page)
    lengths = by_title(page, KESTO_RE, _minutes)
    ratings = by_title(page, AGE_RE, _age)
    genres = by_title(page, GENRE_RE, lambda m: _txt(m.group(1)).strip(" .,"))
    langs = by_title(page, KIELI_RE,
                     lambda m: ", ".join(f"{c}-A" for c in strict_codes(_txt(m.group(1)))))
    # Headings and list items interleaved in document order: the heading above an item is
    # the film it belongs to.
    stream = sorted([(m.start(), "head", m.group(1)) for m in HEAD_RE.finditer(page)] +
                    [(m.start(), "item", m.group(1)) for m in ITEM_RE.finditer(page)])
    shows, seen, unplaced, unread, title = [], set(), [], [], None
    for _, kind, raw in stream:
        text = _txt(raw)
        if kind == "head":
            if text and not NOT_A_TITLE.match(text):
                title = text
            continue
        if not title:
            continue
        rows = _rows(text)
        if rows is None:
            if TIMED_RE.search(text):
                unread.append(text)
            continue                # cast, director, a note, an address, or "Tulossa 25.9."
        for day, month, wd, hh, mm in rows:
            year = resolve_year(day, month, today, weekday_index(wd), WINDOW)
            if year is None:
                unplaced.append(f"{wd} {day}.{month}.")
                continue
            try:
                start = datetime.datetime(year, month, day, hh, mm, tzinfo=FI)
            except ValueError:
                continue
            eid = synmerge.norm(title)
            key = (eid, start.isoformat())
            if key in seen:
                continue            # the desktop and mobile copies of the same screening
            seen.add(key)
            shows.append(_show(title, eid, start, prices, lengths, ratings, genres, langs))
    if unread:
        odd = sorted(set(unread))
        print(f"[kirkkonummi] {len(odd)} row(s) with a time in a shape this parser does not "
              f"read, skipped: {', '.join(odd[:5])}")
    if unplaced:
        print(f"[kirkkonummi] {len(unplaced)} row(s) whose weekday matches no candidate "
              f"year, skipped: {', '.join(unplaced[:5])}")
    if not shows:
        raise RuntimeError(
            f"{LISTING}: icon lists with no screening row this parser places "
            f"({len(unplaced)} unplaced). No empty state is recorded for this site, so "
            f"this is a template or format change rather than a cinema with nothing on")
    shows.sort(key=lambda s: s["start"])
    return shows


def _rows(text):
    """One list item -> [(day, month, weekday, hh, mm)], or None when it is no screening.
    A range needs one weekday per day, or it settles nothing."""
    m = SHOW_RE.match(text)
    if m:
        return [(int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)),
                 int(m.group(5)))]
    m = RANGE_RE.match(text)
    if not m:
        return None
    first, last, month = int(m.group(1)), int(m.group(2)), int(m.group(3))
    wds = [w.strip() for w in m.group(4).split(",") if w.strip()]
    if last <= first or len(wds) != last - first + 1:
        return None
    return [(first + i, month, wd, int(m.group(5)), int(m.group(6))) for i, wd in enumerate(wds)]


def _show(title, eid, start, prices, lengths, ratings, genres, langs):
    return {
        "eventId": eid,
        "title": title,
        "original": "",
        "len": lengths.get(title, ""),
        "rating": ratings.get(title, ""),
        "genres": genres.get(title, ""),
        "method": "",
        "theatre": VENUE["name"],
        "aud": "",
        "start": start.isoformat(),
        "url": LISTING,
        "img": "",
        "lang": langs.get(title, ""),
        "soldOut": False,
        "price": prices.get(title, ""),
        "provider": "kirkkonummi",
        "venue": VENUE["id"],
    }


def get_listing():
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(LISTING, fetcher=fetch)


def fetch_site(site=SITES[0]):
    """Runner contract: one page, one venue."""
    shows = parse(get_listing())
    print(f"[kirkkonummi] {len(shows)} showtimes, "
          f"{len({s['eventId'] for s in shows})} films, "
          f"{len({s['start'][:10] for s in shows})} dates")
    return {VENUE["id"]: shows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site()[VENUE["id"]])
    for s in data:
        print(f"  {s['start'][:16]} {s['title'][:40]:42} {s['eventId'][:24]}")
