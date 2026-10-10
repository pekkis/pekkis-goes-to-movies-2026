"""Kino Kuvakukko (Kuopio) and Nilsiän Kino Manttu, on one page. Stdlib only.

Probed 2026-09-15. Both cinemas are the city of Kuopio's, and both schedules live on a
single WordPress page, `/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/`. One provider,
two venues, one listing request, the shape `vista.py` and `nexxo.py` already use for an
operator whose venues share a source. Each film's own page is then read once per run for
its runtime, age limit and language, see `film_facts`.

    <h2 class="wp-block-heading">Kino Kuvakukon esitysaikataulu</h2>
    <p class="wp-block-paragraph">Tiistai 15.9.<br>
      Klo 13: <a href="https://isak.fi/hopeatahti-elokuvasarja/">Hopeatähti-sarja: ...</a><br>
      Klo 17.30: <a href=".../tulossa-hetki-ennen-valoa/" data-id="2698">Hetki ennen valoa</a></p>
    ...
    <h2 class="wp-block-heading">Nilsiän Kino Mantun esitysaikataulu</h2>

Five things that shape the parser:

- **The two headings are the venue boundary.** Everything between one `<h2>` and the next
  belongs to that cinema. Reading the page without them would file Nilsiä's weekend under
  Kuopio, which is the kind of error nothing downstream would catch.
- **A paragraph is a day**, and only if it opens with a weekday and a date. The same
  element type carries the addresses, the prices and the opening hours, and those simply
  do not match, so no list of things to exclude is needed.
- **The date has no year but the day has a weekday**, `Tiistai 15.9.`, which selects one
  candidate year unambiguously: the same day and month falls on a different weekday in each
  of them. That is a selection, not proof of the intended date, so `common.resolve_year`
  also bounds how far the answer may fall from today. A weekday matching none of them, or
  one selecting a date roughly a year away, leaves the row unplaced and counted.
- **Manttu publishes every other weekend**, so its section is routinely a schedule that has
  already passed. That is correct output, not staleness to correct: the weekday places the
  rows in the past where they belong and the client filters them. Nothing here treats a
  past date as a reason to shift a year.
- **The time is written two ways**, `Klo 13:` and `Klo 17.30:`, hours alone or hours and
  minutes with a dot.

Titles are published verbatim, including a strand prefix like "Hopeatähti-sarja: ". The
central pass in `run.py` splits the prefixes `strands.EVENT_PREFIXES` names, and that list
is exact on purpose; adding a name to it is its own decision and is not made here.

**The price comes from `/liput/`, one request a run for both cinemas.** That page states
one ordinary admission per cinema -- 11,50 € in Kuopio, 11 € in Nilsiä, read 2026-09-16 --
and makes neither depend on a day, a format, a running length or a kind of film, so an
ordinary screening of the cinema's own is settled by it. The programme page states Manttu's
line as well, with the concession groups named, which is what establishes that the first of
`11 € / 9 €` is the ordinary ticket.

Two things take the tariff back, and `price_of` says why in full: a screening billed by an
outside organiser, which the label on the row or a destination off this site is evidence
of, and a row that states its own amount, which outranks the house statement. An on-site
link establishes nothing on its own and is not read as though it did.

`book="door"` for both: the page states "Lipunmyynti vain Kuvakukossa" and, for Manttu,
"Ei ennakkovarauksia, lipunmyynti vain Mantulla. Maksuvälineenä käy vain käteinen." There
is no online sale to link to, so a showtime opens the film's own page on this site when it
has one and the programme page when it does not.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

import synmerge
from common import capped, fetch, get_text, resolve_year, weekday_index
from etiketti import strict_codes

BASE = "https://www.kuvakukko.fi"
LISTING = BASE + "/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/"
FI = ZoneInfo("Europe/Helsinki")

VENUES = [
    {"id": "kk-kuopio", "match": "kuvakuk", "name": "Kino Kuvakukko",
     "short": "Kuvakukko", "city": "Kuopio"},
    {"id": "kk-nilsia", "match": "mantu", "name": "Kino Manttu", "short": "Manttu",
     "city": "Nilsiä"},
]

SITES = [{"provider": "kuvakukko", "label": "Kuvakukko", "base": BASE, "venues": VENUES}]

# One cinema's heading present with no day paragraph under it, while the other has rows,
# is positive evidence that it is between programmes: both schedules are on the same page,
# so the read cannot have half-failed. `parse` checks both halves of that: a cinema whose
# heading was not read fails the site, and one whose section holds a line opening like a
# day or a screening while no row was read is left out, so its previous file stands. Both
# empty fails the site, because no empty programme has been seen on this page and there is
# no evidence of what one looks like.
EMPTY_VENUES_CONFIRMED = True

# The horizon these two were measured at on 2026-09-15: Kuvakukko 9 dates at +0 to +9,
# Manttu 3 dates at -4 to -2, its fortnightly weekend already past. 30 behind and 60 ahead
# covers both with room and stays far short of the 365 a mistyped weekday would need.
WINDOW = (30, 60)

# `/liput/` states one ordinary admission per cinema, "Liput: 11,50 € / 9,50 €", and the
# parenthesis after it names who the second figure is for. Nothing on the page makes either
# amount depend on a day, a format, a running length or a kind of film, and neither block
# prints the escape clause other cinemas do, so the first amount is what an ordinary ticket
# to that cinema costs. `Sarjaliput` and `Lahjalippu` state no colon and are other products.
PRICES = BASE + "/liput/"
TARIFF_RE = re.compile(r"liput:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*\u20ac", re.I)
AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*\u20ac")
# A cinema saying its own tariff is not the last word: read 2026-09-16, neither block says
# anything of the sort, and if one starts to, that venue publishes nothing rather than an
# amount the page has just disclaimed.
EXCEPTION_RE = re.compile(r"erikseen|poikkeu|erikoisn\u00e4yt|vaihtelee|riippuu", re.I)
# An outside organiser's screening. Read 2026-09-16, four Kuopio rows carry one of these
# labels and all four link to isak.fi or hyvätkuvat.fi rather than to this site.
ORGANISER_RE = re.compile(r"^[^:]{0,40}(?:sarja|kerho|festivaali|klubi|seura|yhdistys)"
                          r"[^:]{0,12}:", re.I)

CONTAINER_RE = re.compile(r'<h2[^>]*>[^<]*esitysaikataulu', re.I)
HEADING_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S | re.I)
PARA_RE = re.compile(r'<p[^>]*class="[^"]*wp-block-paragraph[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
DAY_RE = re.compile(r'^\s*([A-Za-zÄÖäö]{2,12})\s+(\d{1,2})\.(\d{1,2})\.', re.I)
# The first anchor with text: Nilsiä's 9.10. row read 2026-10-04 opens with an empty one,
# `Klo 17: <a href=".../kino-manttu-presidentin-kyyditys/"></a><a ...>Rakkautta ja ...`.
ROW_RE = re.compile(r'Klo\s*(\d{1,2})(?:[.:](\d{2}))?\s*:\s*(?:<a\b[^>]*>\s*</a>\s*)*'
                    r'(?:<a\s+href="([^"]*)"[^>]*>(.*?)</a>|([^<]{2,80}))',
                    re.S | re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# A cinema's section as lines, whatever element holds them: `DAY_RE` and `ROW_RE` read the
# classed paragraphs, and this reads what they may have stopped matching.
LINE_SPLIT_RE = re.compile(r"<br\s*/?>|</?(?:p|li|h[1-6]|div|tr|td|ul|ol|table|figure)\b[^>]*>",
                           re.I)
# A line that opens the way a day or a screening does: `Klo 13:`, `n. klo 15:`, `Pe 25.9`,
# `25.9.`. The notes under both headings, read 2026-09-24, open with none of these.
TIME_LINE_RE = re.compile(r"^(?:n\.\s*)?klo\s*\d|^\d{1,2}\.\d{1,2}\.", re.I)
WEEKDAY_DATE_RE = re.compile(r"^([A-Za-z\u00c4\u00d6\u00e4\u00f6]{2,12})\s+\d{1,2}\.\d{1,2}")


# The film page's facts line, read 2026-10-04 on 15 pages: segments joined by " • ",
# "Italia 2025 • draama • 133 min • K7 • kieli: italia • tekstitys: suomi/ruotsi".
# Only the runtime, the age limit and the two labelled language fields are read. The
# cinema reuses a page for a later film (`/the-invite/` holds La Grazia), so a page whose
# heading is not the row's title states nothing for it; a series page lists several films
# and its heading never is one. A facts segment is short: on Päivien lumo's page a quoted
# paragraph ran into the line and made a second candidate whose first segment is prose.
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
FACTS_SPLIT_RE = re.compile(r"<br\s*/?>|</?(?:p|li|div|h[1-6])\b[^>]*>", re.I)
MIN_SEG_RE = re.compile(r"^(\d{2,3})\s*min$")
AGE_SEG_RE = re.compile(r"^(?:K\s?(\d{1,2})|-?S-?)$")
LABEL_SEG_RE = re.compile(r"^(kieli|tekstitys)\s*:\s*(.+)$", re.I)
MANTTU_PREFIX_RE = re.compile(r"^kino\s+manttu\s*:\s*", re.I)
FACTS = ("len", "rating", "lang")
SEGMENT_MAX = 80


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _sections(page):
    """-> [(heading text, the markup under it)], split on the `<h2>` headings."""
    heads = list(HEADING_RE.finditer(page))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(page)
        out.append((_txt(h.group(1)), page[h.end():end]))
    return out


def _screening_like(body):
    """Whether a section holds a line opening like a day or a screening. -> bool."""
    for chunk in LINE_SPLIT_RE.split(body):
        line = _txt(chunk)
        if TIME_LINE_RE.match(line):
            return True
        m = WEEKDAY_DATE_RE.match(line)
        if m and weekday_index(m.group(1)) is not None:
            return True
    return False


def _venue_for(heading):
    low = heading.lower()
    for v in VENUES:
        if v["match"] in low:
            return v
    return None


def tariff(page):
    """`/liput/` -> {venue_id: "11.5\u20ac"}. A venue the page does not settle is absent.

    Both cinemas are the city of Kuopio's and both tariffs are on this one page, under a
    heading naming the cinema. The amount is published only where the page says one thing:
    a venue with no `Liput:` statement, with two of them, or whose block also disclaims the
    tariff is left out, and its screenings publish nothing. The page's third heading is the
    footer's contact block, which names a cinema and states no price; requiring exactly one
    statement is what keeps it from being read as a second, priceless answer.
    """
    stated = {}
    for heading, body in _sections(page):
        venue = next((v for v in VENUES if v["short"].lower() in heading.lower()), None)
        if venue is None:
            continue
        text = _txt(body)
        found = TARIFF_RE.findall(text)
        if not found:
            continue
        stated.setdefault(venue["id"], []).append((found, EXCEPTION_RE.search(text)))
    out = {}
    for vid, blocks in stated.items():
        if len(blocks) != 1:
            continue
        found, disclaimed = blocks[0]
        if len(found) != 1 or disclaimed:
            continue
        out[vid] = _amount(found[0])
    return out


def _amount(raw):
    return f"{float(raw.replace(',', '.')):.2f}".rstrip("0").rstrip(".") + "\u20ac"


def price_of(title, href, tail, house):
    """One row's price. -> "11.5\u20ac" or "".

    The cinema's tariff settles an ordinary screening of its own: it names no day, format,
    length or kind of film, so there is nothing about the row left to read. Two things take
    it back.

    **An outside organiser's screening is not priced by this tariff.** A film society, a
    festival or a series billed under its own name is sold by whoever runs it, and the
    house statement does not reach it. The evidence is either the label on the row or a
    destination that leaves this site; both are read, because a label can link here and an
    outside sale can go unlabelled. An on-site link on its own establishes nothing and is
    not treated as evidence that the tariff applies -- it is the absence of the two signals
    that leaves the house statement standing, which is why an unlinked ordinary row is
    priced and a linked series row is not.

    **A row stating its own amount outranks the tariff**, because a screening-specific
    price is the more specific statement. Two amounts on one row settle nothing and publish
    nothing: which one an admission costs is exactly what is then in doubt.
    """
    # An unlinked row is captured whole -- `Klo 19: Ooppera 25 €` has no tag to stop the
    # title at -- so the row's own amount is read out of the title and what follows it
    # together. The title is still published verbatim; this only reads it.
    own = AMOUNT_RE.findall(f"{title} {tail}")
    if own:
        return _amount(own[0]) if len(own) == 1 else ""
    if ORGANISER_RE.match(title):
        return ""
    if href and not href.startswith(BASE):
        return ""
    return house


def parse(page, site=None, today=None, prices=None):
    """The shared page -> {venue_id: [show]}. Raises when no schedule heading is present,
    when the headings are there with no screening under either, and when one cinema has
    no row while its heading is missing. One with no row whose section holds a line
    opening like a day or a screening is left out of the answer.

    `prices` is `tariff()`'s answer, or nothing: a venue it does not name publishes no
    amount, which is what an unreadable or ambiguous `/liput/` leaves behind.
    """
    site = site or SITES[0]
    prices = prices or {}
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{LISTING}: no 'esitysaikataulu' heading on the page, so this is not the "
            f"programme this parser reads. Treating it as a fetch or template failure "
            f"rather than a cinema with nothing on")
    today = today or datetime.datetime.now(FI).date()
    per_venue = {v["id"]: [] for v in VENUES}
    seen, unplaced, untitled = set(), [], []
    headed, dated = set(), set()     # `dated` also holds a section with an unread day line
    for heading, body in _sections(page):
        venue = _venue_for(heading)
        if venue is None or "esitysaikataulu" not in heading.lower():
            continue
        headed.add(venue["id"])
        if _screening_like(body):
            dated.add(venue["id"])
        for para in PARA_RE.findall(body):
            d = DAY_RE.match(_txt(para))
            if not d:
                continue                    # an address, a price list, opening hours
            dated.add(venue["id"])
            wd, day, month = d.group(1), int(d.group(2)), int(d.group(3))
            year = resolve_year(day, month, today, weekday_index(wd), WINDOW)
            if year is None:
                unplaced.append(f"{wd} {day}.{month}.")
                continue
            rows = list(ROW_RE.finditer(para))
            for i, row in enumerate(rows):
                hh, mm, href, linked, plain = row.groups()
                title = _txt(linked or plain)
                if not title:
                    untitled.append(f"{venue['short']} {day}.{month}. klo {hh}")
                    continue
                # What the page prints after this row and before the next one. A row that
                # states its own amount is the only place a screening-specific price can
                # appear here, and `price_of` prefers it to the house tariff.
                stop = rows[i + 1].start() if i + 1 < len(rows) else len(para)
                tail = _txt(para[row.end():stop])
                try:
                    start = datetime.datetime(year, month, day, int(hh), int(mm or 0),
                                              tzinfo=FI)
                except ValueError:
                    continue
                own = (href or "").startswith(BASE)
                # The page's own `data-id` is a WordPress post id, and a film gets a new
                # post per run here ("tulossa-hetki-ennen-valoa"), so it identifies the
                # posting rather than the film. The normalised title is the key
                # `synmerge` and the client's `normTitle` already use.
                eid = synmerge.norm(title)
                key = (venue["id"], eid, start.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                per_venue[venue["id"]].append({
                    "eventId": eid,
                    "title": title,
                    "original": "",
                    "len": "",
                    "rating": "",
                    "genres": "",
                    "method": "",
                    "theatre": venue["name"],
                    "aud": "",
                    "start": start.isoformat(),
                    "url": href if own else LISTING,
                    "img": "",
                    "lang": "",
                    "soldOut": False,
                    "price": price_of(title, href, tail, prices.get(venue["id"], "")),
                    "provider": site["provider"],
                    "venue": venue["id"],
                })
    if unplaced:
        print(f"[kuvakukko] {len(unplaced)} day(s) whose weekday matches no candidate "
              f"year, skipped: {', '.join(unplaced[:5])}")
    if untitled:
        print(f"[kuvakukko] {len(untitled)} screening line(s) with no title, skipped: "
              f"{', '.join(untitled[:5])}")
    if not any(per_venue.values()):
        raise RuntimeError(
            f"{LISTING} has its headings but no screening under them. No empty programme "
            f"has been seen here, so there is no evidence of one to read this as")
    for v in VENUES:
        if per_venue[v["id"]]:
            continue
        if v["id"] not in headed:
            raise RuntimeError(f"{LISTING}: no schedule heading read for {v['name']}, so "
                               f"its section was not read and it is not shown to be empty")
        if v["id"] in dated:
            # Days or screening lines under its heading and no row read is this parser
            # missing a changed shape. Left out, so run.py keeps its previous file and the
            # other cinema still publishes; alatalo.py treats a town the same way.
            del per_venue[v["id"]]
            print(f"[kuvakukko] {v['name']}: lines opening like a day or a screening and "
                  f"no row read, so not published as empty and the previous file stands")
    for shows in per_venue.values():
        shows.sort(key=lambda s: s["start"])
    return per_venue


def film_facts(page, title):
    """One film page -> {len, rating, lang}, each "" unless the page states it for
    `title`."""
    out = dict.fromkeys(FACTS, "")
    h1 = H1_RE.search(page or "")
    heading = MANTTU_PREFIX_RE.sub("", _txt(h1.group(1))) if h1 else ""
    if not heading or synmerge.norm(heading) != synmerge.norm(title):
        return out
    lines = [[x.strip() for x in line.split("\u2022")]
             for line in (_txt(c) for c in FACTS_SPLIT_RE.split(page))]
    lines = [segs for segs in lines if any(MIN_SEG_RE.match(x) for x in segs)
             and all(len(x) <= SEGMENT_MAX for x in segs)]
    if len(lines) != 1:
        return out
    segs = lines[0]
    minutes = [m.group(1) for m in map(MIN_SEG_RE.match, segs) if m]
    ages = [m for m in map(AGE_SEG_RE.match, segs) if m]
    labels = {}
    for m in filter(None, map(LABEL_SEG_RE.match, segs)):
        labels.setdefault(m.group(1).lower(), []).append(m.group(2))
    if len(minutes) == 1:
        out["len"] = minutes[0]
    if len(ages) == 1:
        out["rating"] = f"K-{int(ages[0].group(1))}" if ages[0].group(1) else "S"
    one = {k: v[0] for k, v in labels.items() if len(v) == 1}
    out["lang"] = ", ".join([f"{c}-A" for c in strict_codes(one.get("kieli"))]
                            + [f"{c}-S" for c in strict_codes(one.get("tekstitys"))])
    return out


def enrich(per_venue, sleep=1.5, get=None):
    """Each film's own page, read once per film and never per screening, onto the fields
    its screenings left empty. -> pages read. Never raises: a page that fails or states
    nothing for its title leaves those screenings as the listing gave them."""
    get = get or _get
    films = {}
    for shows in per_venue.values():
        for s in shows:
            if s["url"] != LISTING:
                films.setdefault(s["eventId"], s)
    read = stated = 0
    for n, (eid, first) in enumerate(capped(sorted(films.items()), "kuvakukko")):
        if n:
            time.sleep(sleep)
        try:
            facts = film_facts(get(first["url"]), first["title"])
        except Exception as e:
            print(f"[kuvakukko] film page {first['url']}: {type(e).__name__}: {e}")
            continue
        read += 1
        stated += any(facts.values())
        for shows in per_venue.values():
            for s in shows:
                if s["eventId"] == eid:
                    for k in FACTS:
                        if facts[k] and not s[k]:
                            s[k] = facts[k]
    print(f"[kuvakukko] film pages: {read} read for {len(films)} films, "
          f"{stated} stating facts for their title")
    return read


def _get(url):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch)


def get_listing():
    return _get(LISTING)


def get_prices():
    """The tariff page, once a run, for both venues. -> {venue_id: amount}, or {}.

    A price is the one thing here a reader can do without, so this never fails the site:
    the schedule is already parsed when it is asked for, and a page that will not answer
    leaves the amounts empty rather than taking 45 showtimes down with it.
    """
    try:
        return tariff(_get(PRICES))
    except Exception as e:
        print(f"[kuvakukko] {PRICES}: not read, so no prices this run: {e!r}")
        return {}


def fetch_site(site=SITES[0]):
    """Runner contract: one page, two venues.

    A venue with no row is returned as an empty list only when the other one has rows
    and its own heading was read with no day or screening line under it: both schedules
    are on the same page, so that is positive evidence of one cinema between programmes.
    A venue with such lines and no row is left out; every other empty case has already
    raised in `parse`.
    """
    page = get_listing()
    prices = get_prices()
    per_venue = parse(page, site, prices=prices)
    enrich(per_venue)
    for vid, shows in per_venue.items():
        print(f"[kuvakukko] {vid}: {len(shows)} showtimes, "
              f"{len({s['start'][:10] for s in shows})} dates, "
              f"{sum(1 for s in shows if s['price'])} priced "
              f"(tariff {prices.get(vid) or 'not read'})")
    return per_venue


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    data = (parse(open(src, encoding="utf-8", errors="replace").read()) if src
            else fetch_site())
    for vid, shows in data.items():
        print(f"== {vid} ==")
        for s in shows[:8]:
            print(f"  {s['start'][:16]} {s['title'][:44]:46} {s['eventId'][:18]}")
