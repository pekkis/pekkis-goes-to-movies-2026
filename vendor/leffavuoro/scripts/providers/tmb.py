"""TMB Cinema Oy: Kino-Toijala, Kino-Sampo, KinoMania and Elokuvateatteri Elo.

Probed 2026-09-15. Four cinemas, one operator, four sites built on the same template
(footer: "Mediapalvelu W3D"). None of them is on a platform this repo already reads: the
eTiketti listing path answers 200 with no film links on all four, and the
`cdn.etiketti.app/studio123/...` URLs in their markup are syndicated opera posters, not a
sign of an eTiketti tenancy. So this is one adapter for four sites, not four parsers.

**They are four cinemas, not one mirrored four times.** That had to be established before
adding any of them, because the pages look alike and the schedules coincide: Kino-Toijala
and Kino-Sampo published an identical set of 23 screenings on the day this was written,
and KinoMania and Elo an identical set of 32. What separates them is the booking id. For
the same film at the same minute, `?varaa=` is 21001 at Toijala, 21006 at Sampo, 21012 at
Elo and 21015 at Mania: four rows in the operator's system, one per cinema, a chain
booking the same films at the same times. Their screen counts differ too, which a mirror
could not do: Mania and Elo print `, sali 1` / `, sali 2` and the other two print no
auditorium at all.

**One request per venue.** `{base}/?lista=1` is the whole published programme as a list,
each row a screening:

    <small>TI&nbsp;15.09.2026 klo&nbsp;14:00, sali&nbsp;1</small></b>
    <h2 ...><a href="?ohjelmisto=842">Hetki ennen valoa</a></h2></td>
    <td ...><img ... src="/files/images/ikaraja_2.png" alt="Ikäraja">

The date carries its year, so nothing is inferred. Every row in this view is a timed
screening; the coming-soon entries live in the default grid view and are not read here.

Three things this parser deliberately does not do:

- **It does not link to `?varaa=`.** That is the seat-reservation action, and this repo
  does not call booking endpoints, so a link there could never be checked before being
  published. Six Nexxo sites once shipped dead ticket links exactly that way. The showtime
  links to `?ohjelmisto={id}`, the public film page, which carries the screening list and
  the site's own booking buttons. Hence `book="reserve"` in the registry.
- **It does not invent an age limit.** The rating is only in the image filename, and the
  film page states it nowhere in text. `ikaraja_2`, `_3` and `_4` were checked against
  this repo's own committed data for five films that other providers also carry (K-7,
  K-12 twice, K-16 twice) and agree. `ikaraja_1` appears only on opera events, which no
  provider here rates, so it is **not** mapped: a sequence that looks like S, K-7, K-12,
  K-16 is a guess, and a wrong classification is worse than none. An unmapped image
  yields no rating and the TMDB pass fills what it can.
- **It reads the film page, since 2026-09-16.** It did not until then, and the reason
  recorded here was the cost: one request per distinct film per venue, about 68 a run
  against a third party, for a runtime. The maintainer asked for the runtime that day, so
  the trade was theirs to make and it is made. The page also carries a Finnish synopsis and
  a genre, which cost nothing once the page is fetched, and they are published too.
  `film_facts_by_id` fetches one page per **distinct** film, paced, cached and bounded by
  `common.capped`; the schedule is parsed from the list view first, so a film page that
  will not answer costs that film its metadata and never a cinema its programme.

## The price comes from the screening's own line, not from the tariff

The operator states a tariff, and each list view links it in its own nav -- `?hinnat=2` at
Toijala, `3` at Sampo, `4` at Mania, `1` at Elo. Read as a visitor 2026-09-16; all four say
the same thing.

    Liput   2D  Aikuinen 14.45 €  Eläkeläinen 12.45 €  Lapsi 11.45 €
                LA, SU ja arkipyhät +0.50 €
            3D  Aikuinen 16.95 €  Eläkeläinen 15.95 €  Lapsi 13.95 €

**No screening here can be priced from it exactly, so none is priced at all.** Two things
stand between the tariff and a screening, and both are unknowable from what this adapter
reads:

- *Which tariff.* 2D and 3D differ by 2.50, and the list view carries no 3D marker -- the
  three `3D` strings on the page are the `<title>` and the "Mediapalvelu W3D" footer, none
  of them on a row. So the format of every row is unknown, weekend rows included.
- *Arkipyhä.* The surcharge covers Saturday, Sunday **and** weekday public holidays. Which
  days those are is a calendar this repo does not carry, so a weekday row could be either
  amount.

This was published for a few hours on 2026-09-16 with both gaps written down as known
limitations. That was wrong: a price a reader sees is a claim about what they will pay, and
documenting that it is sometimes 0.50 or 2.50 out does not make it accurate. The rule the
`price` field is held to is in `common.Show`: an exact amount only where its applicability
to *that screening* is established, and otherwise nothing.

What would change it is a marker on the row saying 2D or 3D, which would leave only the
arkipyhä gap on weekdays and make Saturday and Sunday exact; or a maintainer's decision to
publish a labelled house tariff, which is a different field and a different product
question. Neither is assumed here. The finding is in `docs/research/prices.md`.

**A third thing settles it, found 2026-09-16 when the film page was first read: that page
states an amount per screening.** `Hinta: 14.45€ / 12.45€ / 11.45€` sits under each date,
and the Sunday row reads 14.95 where the Wednesday reads 14.45. Neither question above has
to be answered for that figure to be right: the operator has applied its own tariff, the
format is whatever it was, and the +0.50 the maintainer confirmed for weekends and public
holidays is already in the printed number. `screening_prices` reads it, keyed by the
screening's own minute, and `fetch_site` gives each row the amount printed under it and
nothing else -- a screening the film page does not list stays unpriced.

The first of the three figures is the ordinary admission: `?hinnat=` prints Aikuinen 14.45,
Eläkeläinen 12.45 and Lapsi 11.45 in that order, read 2026-09-16, and the film page prints
those three numbers in that order. The other two need a card at the counter, so they
describe no ordinary ticket. The tariff page itself is still fetched by nothing.

Two amounts under one screening publish neither: nothing in the markup delimits a block but
the next date, so a row this parser cannot read would otherwise leave its price attached to
the screening above it.


A list view with no screening row fails the venue, as does a page without the
'Valkokankaalla' heading. The heading shows the list view was served; it is not evidence
that the cinema has nothing on. No empty state has been read off these sites, so none is
recognised: `common.EmptyProgramme` is never raised here and no venue is vouched empty.
"""
import datetime
import html as html_mod
import re
import sys
import time
from zoneinfo import ZoneInfo

from common import capped, fetch, get_text, served

FI = ZoneInfo("Europe/Helsinki")

SITES = [
    {"provider": "kinotoijala", "label": "Kino-Toijala", "base": "https://toijalan-kino.info",
     "venues": [{"id": "tmb-toijala", "name": "Kino-Toijala", "short": "Kino-Toijala",
                 "city": "Akaa"}]},
    {"provider": "kinosampo", "label": "Kino-Sampo", "base": "https://kinosampo.info",
     "venues": [{"id": "tmb-sampo", "name": "Kino-Sampo", "short": "Kino-Sampo",
                 "city": "Valkeakoski"}]},
    {"provider": "kinomania", "label": "KinoMania", "base": "https://kino-mania.info",
     "venues": [{"id": "tmb-mania", "name": "KinoMania", "short": "KinoMania",
                 "city": "Pieksämäki"}]},
    {"provider": "kinoelo", "label": "Elokuvateatteri Elo", "base": "https://elokuvat-elo.info",
     "venues": [{"id": "tmb-elo", "name": "Elokuvateatteri Elo", "short": "Elokuvateatteri Elo",
                 "city": "Heinola"}]},
]

CONTAINER_RE = re.compile(r'Valkokankaalla', re.I)
ROW_RE = re.compile(
    r'<small>\s*([A-ZÄÖ]{2})(?:&nbsp;|\s)(\d{1,2})\.(\d{1,2})\.(\d{4})\s*klo(?:&nbsp;|\s)'
    r'(\d{1,2}):(\d{2})([^<]*)</small>\s*</b>\s*'
    r'<h2[^>]*>\s*<a\s+href="\?ohjelmisto=(\d+)"\s*>([^<]+)</a>\s*</h2>',
    re.S | re.I)
AGE_RE = re.compile(r'ikaraja_(\w+)\.png', re.I)
FILM_LINK_RE = re.compile(r'href="\?ohjelmisto=\d+"', re.I)
SALI_RE = re.compile(r'sali(?:&nbsp;|\s)*([\w-]+)', re.I)

# Measured against this repo's own committed ratings for films other providers also carry.
# 1 and 5 are deliberately absent; see the docstring.
AGE = {"2": "K-7", "3": "K-12", "4": "K-16"}

# The row prints the weekday the operator published. It is not used to build the date --
# the date is complete on its own -- but a row whose weekday contradicts its date means
# the template moved fields around, and that is worth counting rather than publishing.
WEEKDAYS = ("MA", "TI", "KE", "TO", "PE", "LA", "SU")

# The film page states its metadata as one shape, `<p class="info">Label: <b>value</b></p>`,
# for Kesto, Kuvaus, Lajityyppi, Ohjaus and Näyttelijät alike. Reading the labels rather
# than positions means a field the operator adds or drops changes nothing here.
INFO_RE = re.compile(r'<p class="info">\s*([^:<]{2,24}):\s*<b>(.*?)</b>\s*</p>', re.S | re.I)
# The film page's own screening list, `<p id="shows">`, one block per screening: the full
# date, the time, the booking button, then `Hinta:` for that screening. A block runs to the
# next date or to the end of the list, which is what keeps one screening's amount off the
# next one.
SHOW_RE = re.compile(
    r"[A-Z\u00c4\u00d6]{2}(?:&nbsp;|\s)(\d{1,2})\.(\d{1,2})\.(\d{4})\s*klo(?:&nbsp;|\s)"
    r"(\d{1,2}):(\d{2})(.*?)(?="
    r"[A-Z\u00c4\u00d6]{2}(?:&nbsp;|\s)\d{1,2}\.\d{1,2}\.\d{4}\s*klo|</p>|\Z)",
    re.S | re.I)
HINTA_RE = re.compile(r"Hinta:\s*([\d]{1,3}[.,]\d{2})\s*\u20ac", re.I)
HOURS_RE = re.compile(r"(\d{1,2})\s*tuntia", re.I)
MINS_RE = re.compile(r"(\d{1,3})\s*minuuttia", re.I)

TAGS_RE = re.compile(r"<[^>]+>")


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def parse(page, site, venue):
    """`{base}/?lista=1` -> [show] for the one venue the site serves."""
    if not CONTAINER_RE.search(page):
        raise RuntimeError(
            f"{site['base']}: no 'Valkokankaalla' programme container in the response "
            f"({served(page)}), so this is not the list view this parser reads. Treating "
            f"it as a fetch or template failure rather than a cinema with nothing on")
    shows, seen, wrong_day = [], set(), 0
    rows = list(ROW_RE.finditer(page))
    for i, m in enumerate(rows):
        wd, day, month, year, hh, mm, tail, fid, title = m.groups()
        title = _txt(title)
        if not title:
            continue
        try:
            start = datetime.datetime(int(year), int(month), int(day), int(hh), int(mm),
                                      tzinfo=FI)
        except ValueError:
            continue
        if WEEKDAYS[start.weekday()] != wd.upper():
            wrong_day += 1
            continue
        sali = SALI_RE.search(tail or "")
        aud = f"Sali {_txt(sali.group(1))}" if sali else ""
        # The age image sits in the row's second cell, just past the title, and is looked
        # for no further than the next row: a row with none took the next row's image.
        stop = min(rows[i + 1].start() if i + 1 < len(rows) else len(page), m.end() + 400)
        age = AGE_RE.search(page[m.end():stop])
        key = (fid, start.isoformat(), aud)
        if key in seen:
            continue
        seen.add(key)
        shows.append({
            "eventId": fid,
            "title": title,
            "original": "",
            "len": "",
            "rating": AGE.get(age.group(1), "") if age else "",
            "genres": "",
            "method": "",
            "theatre": venue["name"],
            "aud": aud,
            "start": start.isoformat(),
            "url": f"{site['base']}/?ohjelmisto={fid}",
            "img": "",
            "lang": "",
            "soldOut": False,
            "price": "",
            "provider": site["provider"],
            "venue": venue["id"],
        })
    if wrong_day:
        print(f"[tmb] {site['provider']}: {wrong_day} row(s) whose weekday contradicts "
              f"their date, skipped")
    if not shows:
        raise RuntimeError(
            f"{site['base']}/?lista=1: no screening row parsed from "
            f"{len(FILM_LINK_RE.findall(page))} film link(s) ({served(page)}). No empty "
            f"state is known for this template, so this is a parse or template failure")
    shows.sort(key=lambda s: (s["start"], s["aud"]))
    return shows


def minutes(raw):
    """`Kesto` as the page writes it -> "87", or "" when it says no duration.

    "1 tuntia 27 minuuttia" and "2 tuntia" are both published; the hours part is there
    alone often enough that requiring minutes would drop half the films. A text with
    neither unit, or one adding to zero, yields nothing rather than a "0".
    """
    h, m = HOURS_RE.search(raw or ""), MINS_RE.search(raw or "")
    total = (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)
    return str(total) if total else ""


def screening_prices(page):
    """The film page's own screening list -> {"2026-09-16T17:30": "14.45\u20ac"}.

    **This is the operator stating what a screening costs, not a tariff to apply.** The
    tariff cannot price a row here: 2D and 3D differ by 2.50 with no marker on any row, and
    the weekend surcharge covers weekday public holidays, which no calendar here knows.
    This line settles both by not needing either -- it is printed under the screening, and
    the surcharge is already in it. Measured 2026-09-16: the same film reads
    `14.45\u20ac / 12.45\u20ac / 11.45\u20ac` on a Wednesday and `14.95\u20ac / ...` on the
    Sunday.

    The first figure is the ordinary admission. `?hinnat=` states the three in one order --
    Aikuinen 14.45, Eläkeläinen 12.45, Lapsi 11.45 -- and the film page prints those three
    numbers in that order, so the first is read and the other two are the concessions a
    counter checks a card for.

    Keyed by the screening's own minute, so it reaches the list view's rows without
    depending on the order of either page. Two rows claiming one minute with **different**
    amounts settle nothing and publish nothing; the same amount twice is not a conflict.
    """
    out, refused = {}, set()
    for day, month, year, hh, mm, tail in SHOW_RE.findall(page):
        found = HINTA_RE.findall(tail)
        if len(found) != 1:
            continue
        try:
            key = datetime.datetime(int(year), int(month), int(day), int(hh),
                                    int(mm)).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        amount = _amount(found[0])
        if key in out and out[key] != amount:
            refused.add(key)
        out[key] = amount
    for key in refused:
        del out[key]
    return out


def _amount(raw):
    return f"{float(raw.replace(',', '.')):.2f}".rstrip("0").rstrip(".") + "\u20ac"


def film_facts(page):
    """One `?ohjelmisto=` page -> {len, syn, genres, prices}, empty for what it omits."""
    info = {_txt(k).lower(): _txt(v) for k, v in INFO_RE.findall(page)}
    return {"len": minutes(info.get("kesto", "")),
            "syn": info.get("kuvaus", ""),
            "genres": info.get("lajityyppi", ""),
            "prices": screening_prices(page)}


BLANK = {"len": "", "syn": "", "genres": "", "prices": {}}


def film_facts_by_id(site, ids, sleep=1.2, get=None):
    """{film id: facts} for every film page that answered. -> dict.

    One request per **distinct** film, paced and cached, and bounded by the shared page
    budget. `capped`, not `budget_or_raise`: these pages carry no screening, so a film past
    the cap loses its runtime and keeps its showtimes, which is the right way round.

    A page that will not answer costs that film's metadata and nothing else. The schedule
    is parsed from the list view before this runs, so no cinema's programme goes stale
    because one film page 500s.
    """
    get = get or globals()["get"]
    out = {}
    for n, fid in enumerate(capped(ids, "tmb")):
        if n:
            time.sleep(sleep)
        try:
            out[fid] = film_facts(get(f"{site['base']}/?ohjelmisto={fid}"))
        except Exception as e:
            print(f"[tmb] {site['provider']} film page {fid}: {type(e).__name__}: {e}",
                  file=sys.stderr)
    return out


def get(url):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch)


def get_list(site):
    return get(site["base"] + "/?lista=1")


def fetch_site(site, sleep=1.2):
    """Runner contract: one list view, then one film page per distinct film."""
    venue = site["venues"][0]
    shows = parse(get_list(site), site, venue)
    facts = film_facts_by_id(site, sorted({s["eventId"] for s in shows}), sleep=sleep)
    for s in shows:
        f = facts.get(s["eventId"]) or BLANK
        s["len"], s["genres"] = f["len"], f["genres"]
        s["price"] = f["prices"].get(s["start"][:16], "")
        if f["syn"]:
            # A bare string is Finnish, which is what this operator writes.
            s["_syn"] = f["syn"]
    print(f"[tmb] {site['provider']}: {len(shows)} showtimes, "
          f"{len({s['eventId'] for s in shows})} films, "
          f"{len({s['start'][:10] for s in shows})} dates, "
          f"{sum(1 for s in shows if s['price'])} priced, "
          f"{sum(1 for s in shows if s['len'])} timed, "
          f"{sum(1 for s in shows if s['genres'])} with a genre, "
          f"{sum(1 for s in shows if s.get('_syn'))} with a synopsis")
    return {venue["id"]: shows}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else None
    for site in SITES:
        if which and site["provider"] != which:
            continue
        data = fetch_site(site)[site["venues"][0]["id"]]
        for s in data[:6]:
            print(f"  {s['start'][:16]} {s['aud'] or '-':8} {s['title'][:34]:36} "
                  f"{s['rating']:5} {s['url'][-22:]}")
