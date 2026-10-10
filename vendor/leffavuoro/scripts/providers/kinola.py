"""Kino Kilta (Turku), Kino Laika (Karkkila) and Kino Myyri (Vantaa), on Kinola.
Stdlib only.

Kinola is the platform behind Cinema Orion's ticketing too, and `orion.py` reads its third
front-end template, a `table.kinola-day`. Neither site here renders that table, so
`orion.parse` returns zero on both: this is a separate module with a handler per template
rather than two `SITES` entries. `orion.py` is unchanged.

**Konepaja has no `SITES` entry.** `kinokonepaja.fi` renders the Kinola filters and a
"tulossa" grid of film pages, and its screening list reads "Ei tulevia tapahtumia."
Re-read 2026-09-15, which is the check the build requirements asked for; the 2026-09-14
finding stands. It is a real tenant publishing no screening, the same position as Kino
Kaustinen, and it gets an entry when it lists one.

## The publication policy

Adopted 2026-09-15; the decision is in `docs/archive/2026-09-providers.md` under "Kinola:
the publication policy, adopted" and the evidence in `docs/research/kinola.md`. Concerts
and films are one WordPress `film` post type with nothing structural separating them, and
Laika's own filter lists its concerts under "Kaikki elokuvat". So:

- a screening publishes only when its film page carries **labelled film metadata**;
- everything else is omitted, and the count is logged;
- an override decides before the classifier runs, in either direction.

**Three states, and only one of them a runtime decision.** `film` and `unresolved` are what
the classifier can reach on its own. `non-film` is reachable **only** through a scoped,
evidence-backed exclusion, because these pages carry no structural signal for a live act
and reading a word out of a title or a synopsis is what the policy forbids. So the measured
report says "confirmed non-film" of an exclusion and nothing else: the classifier never
identifies a gig by itself, and this module does not pretend otherwise.

**The precedence.** An exclusion beats generic metadata. A billed live act whose page fills
`Ohjaus` or `Lajityyppi` would otherwise publish, and that is exactly the case an exclusion
exists for, so the override is consulted before the labels are looked at rather than after.

**The limitation this leaves, stated rather than papered over.** Precedence is not
detection. A live act that fills those fields and has **no** recorded exclusion publishes
as a film, and nothing here notices: the classifier sees a director and a genre and has no
further evidence to weigh. The fixture in `tests/test_kinola.py` proves the precedence
holds once an exclusion exists; it does not prove, and cannot, that conflicting
live-event evidence is found automatically.

**And the run log does not close it either**, which this said it did until 2026-09-15. The
log names what was *withheld* -- the confirmed non-films and the unresolved ones -- and the
count of what published. It never names a published title, so an act wrongly included looks
exactly like a film in it, and nobody reading the log sees anything to chase. It is noticed
on the site or in the data, by someone who knows the programme. The remedy is still one
scoped entry with its evidence.

Reading a word out of a title or a synopsis stays forbidden: it would misfile every concert
film, and the policy was adopted on that ground. What is *not* established is that keywords
are the only route left. Nothing has been measured against another structural signal -- a
ticket type, a venue field, a programme list the cinema itself publishes -- because none was
looked for. Do not write that the alternative is keywords or nothing.

**Revalidation, at run time and for every entry.** Each override is scored against the page
as it stands now: `active` when it changes the classifier's verdict, `redundant` when the
classifier already reaches the same outcome, and `evidence-unavailable` when the event is
not in the listing or its page was not read. The third is not the second: a film that has
left the programme proves nothing about whether its override is still needed.

**An age classification and a runtime are not film evidence.** This is the trap the policy
was corrected for: Laika's billed live acts carry both. *Arppa* reads "130 min K-18" and
*Livemusavisa* "120 min K-18", with no director and no genre. Only the labelled director
and genre fields separate a film from a gig here, so only those are read as evidence.

Measured 2026-09-15 over 65 distinct film pages: 53 carry a director or a genre label and
12 carry neither. Eleven of the twelve are billed live acts (Arppa, Tuure Kilpeläinen,
Mariska, Knipi, Antti Autio, Livemusavisa, Ykspihlajan Kino-Orkesteri, Valimo/Bico/These
Boots, Dave Lindholm & Pepe Ahlqvist, 50 vuotta rokkia Karkkilasta, a festival bus trip)
and one is a genuine film, *A Fox Under a Pink Moon*, whose page names its director in
prose but fills no field. That one is the override list's first and only entry.

## The three listing templates

Both wrap each screening in a block carrying the class **token** `kinola-event`, so the
blocks are found by that token and sliced between occurrences rather than by matching tags.
A token, not a whole attribute: `class="kinola-event featured"` is the same block, and
matching the attribute exactly would hide that screening with nothing to show for it.
Neither the longer names inside the block (`kinola-event-title`, `-date`, `-venue`,
`-tickets-link`) nor the container around them (`kinola-events`) is the token.

**A block the listing marks as a screening must produce a row.** One that cannot be read
raises `ListingRowError` and fails the site, which keeps the previous files. Skipping it
published a schedule with a screening missing from it and from the omission report, which
counts only what the classification policy withheld -- so nothing anywhere said a screening
had been dropped, and with every row malformed the site looked like a cinema with nothing
on. Parsing failures and policy omissions are different claims and are kept apart.

    kilta   <li class="kinola-event"> .time "20:00", .date "TI 15.9.2026",
            a.kinola-event-title -> /film/{slug}/, .movie-subtitle (a strand, not a
            subtitle), .duration-info "106 min", a.kinola-event-tickets-link
    laika   <div class="kinola-event"> img.kinola-event-poster,
            a.kinola-event-title -> /film/{slug}/, .kinola-event-venue,
            .kinola-event-date "16/09/2026 14:00", a.kinola-event-tickets-link or
            span.kinola-event-tickets-link-sold-out
    myyri   the laika block, with .kinola-event-date reading "pe 18.9. klo 19:30" and
            a.kinola-event-tickets-link pointing at /checkout/{uuid}

**Kilta and Laika print their year**, `D.M.YYYY` after a weekday and `DD/MM/YYYY HH:MM`.
Myyri prints the weekday, day and month, which `common.resolve_year` resolves; a row it
cannot place raises.

**Myyri's and Sheryl's ticket link is the listing's own href.** Both rows carry a
`/checkout/{uuid}` anchor, and since 2026-09-26, on the maintainer's decision, it is
published like Kilta's and Laika's: copied from the listing and resolved against the site,
never constructed and never requested. A sold-out row, or one with no ticket anchor, opens
the film page. Until then both opened the film page; the record is in
`docs/archive/2026-09-providers.md`. Read 2026-09-18: Myyri had 26 screenings over 15
films, none sold out, so the sold-out branch is covered by fixture.

**Myyri's synopsis declares its language.** Its film pages carry Finnish for some films and
English for others, and the slot is keyed by normalised title and read by every chain
showing the film. `syn_value` places the text with `common.syn_language` and withholds it
when no language is settled. Kilta and Laika keep the bare string; whether those two carry
anything but Finnish was not measured.

**A sold-out row keeps its screening.** Laika drops the checkout anchor and renders
`<span class="kinola-event-tickets-link-sold-out">Loppuunmyyty</span>` instead, so the
destination falls back to the film page's own href, read from the listing and never built,
with `soldOut` true. Dropping those rows would hide four of Laika's screenings.

## The two film-page templates

    kilta   <dl class='info'> of <dt>Label</dt><dd>Value</dd>: Valmistumisvuosi, Maat,
            Ensi-ilta, Ohjaaja, Pääosissa, Lajityyppi, Kieli, Kesto
    laika   <strong>Label</strong> <br> value <br><br>: Ohjaus, Kieli, Tekstitys, with
            the runtime and the classification as bare text above them

One reader handles both, because the classifier has to be template-independent: a label
is a `<dt>`/`<dd>` pair or a `<strong>` followed by text, and both land in one dict.

- **Kilta's rating is an `alt` attribute**, `alt='Ikäraja: K-12'`, and the `alt` is what is
  read. The image beside it is `age-7.svg` on a K-12 film, so the file name is not the
  rating. "sallittu kaikille" maps to `S`.
- **Laika's rating and runtime are bare text** in the block above the first paragraph, so
  they are read from that bounded region and nowhere else.
- The same film can be rated differently by the two cinemas: *Hetki ennen valoa* is K-12 on
  Kilta and K-7 on Laika. Each publishes what its own page says, and `enrich_tmdb` reports
  the disagreement rather than either overwriting the other.
- Kilta publishes no poster: its `og:image` is a landscape still (2026-10-04). Laika's
  comes from the listing row, Myyri's and Sheryl's from `og:image`.
- `LANG` is imported from `gilda.py`, so a code cannot drift between two readers of the
  same vocabulary; `NAMES` adds the names only these pages use, Sheryl's English ones
  among them. A language or subtitle line with a name it does not know publishes nothing
  for that part, and the run log names the film.

## What counts as an empty programme

Zero parsed rows is never the evidence -- `common.EmptyProgramme` says why. The evidence is
what the page carries that the row parser does not read, and it was measured as a visitor on
2026-09-15 across all three tenants; the reading is in `docs/research/kinola.md`.

    kinokilta.fi/naytokset/   57 blocks, a `kinola-events` container, no empty-state text
    kinolaika.fi/ohjelmisto/  47 blocks, a `kinola-events` container, no empty-state text
    kinokonepaja.fi           0 blocks, no `kinola-events` container at all, and
                              "Ei tulevia tapahtumia." where the list would be

So an empty programme is the filter widget rendered, **no** event container, and that text
after the widget. One tenant is the whole sample of the empty state, so the rule is the
conservative one and all three conditions are required: a container that rendered and held
no readable row is a markup change rather than a quiet week, and a page that is not this
listing is neither. Anything short of all three fails the site and the previous files stand.

## Requests

One listing per site, then one film page per distinct film: 41 for Kilta and 24 for Laika
when measured. Those pages carry the classification, so they decide what publishes, and
`common.budget_or_raise` applies rather than `capped`: trimming the loop would drop
screenings instead of costing metadata.
"""
import datetime
import html as html_mod
import json
import pathlib
import re
import sys
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from common import (EmptyProgramme, budget_or_raise, fetch, get_text, resolve_year,
                    syn_language, weekday_index)
from gilda import LANG
from synmerge import is_note

# Every language name the four tenants' film pages used on 2026-10-03, over all their listed
# films: Finnish names Gilda's table lacks, Sheryl's English ones, and the adjectives and
# mistranslations Laika and Myyri publish ("italialainen", "kiillottaa" for Polish). Kilta's
# "Taiwan" beside "mandariinikiina" is Taiwanese Hokkien, and Dari is Persian: both under
# their macrolanguage. Record in docs/research/kinola.md.
NAMES = {**LANG, **{
    "persia": "FA", "farsi": "FA", "dari": "FA", "pa\u0161tu": "PS", "heprea": "HE",
    "kreikka": "EL", "tanska": "DA", "hollanti": "NL", "turkki": "TR", "korea": "KO",
    "hindi": "HI", "islanti": "IS", "norja": "NO", "kiina": "ZH", "mandariinikiina": "ZH",
    "taiwan": "ZH", "tamili": "TA", "liettua": "LT", "romania": "RO", "nepali": "NE",
    "jiddi\u0161": "YI", "italialainen": "IT", "liettualainen": "LT",
    "nepalilainen": "NE", "romanialainen": "RO", "kiillottaa": "PL",
    "dubattu englanniksi": "EN",
    "english": "EN", "finnish": "FI", "swedish": "SV", "spanish": "ES", "german": "DE",
    "french": "FR", "italian": "IT", "russian": "RU", "polish": "PL", "japanese": "JA",
    "korean": "KO", "chinese": "ZH", "cantonese": "ZH", "mandarin": "ZH", "danish": "DA",
    "norwegian": "NO", "icelandic": "IS", "dutch": "NL", "portuguese": "PT",
    "ukrainian": "UK", "arabic": "AR", "turkish": "TR", "persian": "FA",
    "hebrew": "HE", "greek": "EL", "romanian": "RO", "estonian": "ET",
    "lithuanian": "LT", "tamil": "TA", "georgian": "KA", "pashto": "PS",
    "yiddish": "YI"}}

FI = ZoneInfo("Europe/Helsinki")

OVERRIDE_FILE = pathlib.Path(__file__).resolve().parent / "kinola-overrides.json"

SITES = [
    {"provider": "kinokilta", "label": "Kino Kilta", "base": "https://www.kinokilta.fi",
     "listing": "/naytokset/", "template": "kilta",
     "venues": [{"id": "kilta-turku", "name": "Kino Kilta", "short": "Kino Kilta",
                 "city": "Turku"}]},
    {"provider": "kinolaika", "label": "Kino Laika", "base": "https://www.kinolaika.fi",
     "listing": "/ohjelmisto/", "template": "laika",
     "venues": [{"id": "laika-karkkila", "name": "Kino Laika", "short": "Kino Laika",
                 "city": "Karkkila"}]},
    # Added 2026-09-18. Differences from Laika are in `events_myyri`: no year on the row.
    # `declare_syn` makes the synopsis carry a language, because this site's film pages
    # are not all Finnish.
    {"provider": "kinomyyri", "label": "Kino Myyri", "base": "https://kinomyyri.fi",
     "listing": "/ohjelmisto/", "template": "myyri", "declare_syn": True,
     "venues": [{"id": "myyri-vantaa", "name": "Kino Myyri", "short": "Kino Myyri",
                 "city": "Vantaa"}]},
    # Added 2026-09-19. A student-run cinema on the Aalto campus in Otaniemi, and the
    # fourth tenant of this platform. `listing: "/"`: its `/ohjelmisto/` answers 404 and
    # the front page is where the `kinola-event` blocks are, 71 of them when read. The
    # plugin runs in English here, which is what `sheryl` template reads; everything else
    # is Myyri's, including the `/checkout/{uuid}` link copied from the listing.
    {"provider": "sheryl", "label": "Cinema Sheryl", "base": "https://sheryl.fi",
     "listing": "/", "template": "sheryl", "declare_syn": True,
     "venues": [{"id": "sheryl-espoo", "name": "Cinema Sheryl", "short": "Cinema Sheryl",
                 "city": "Espoo"}]},
]

# `resolve_year`'s (behind, ahead) for Myyri. Its listing reached 42 days ahead on
# 2026-09-18; 120 leaves room for a season announcement and still refuses a year-away
# placement from a mistyped weekday.
MYYRI_WINDOW = (30, 120)

# The label whose presence is film evidence. Not the runtime and not the classification:
# see the module docstring, Laika's live acts carry both.
# The labels whose presence makes a page a film. English ones because Cinema Sheryl's
# film pages are written in English -- `Director`, `Cast`, `Language`, `Subtitles` -- while
# its listing localises to whatever `accept-language` asks for. `labels()` lowercases the
# key and already reads the `<strong>` shape those pages use, so the vocabulary is the only
# thing that had to grow. Read 2026-09-19 on sheryl.fi/film/chungking-express-2/.
FILM_LABELS = ("ohjaaja", "ohjaus", "lajityyppi", "director", "genre")

# The policy's three states. NON_FILM is never a runtime verdict; it is what an
# evidence-backed exclusion asserts.
FILM, NON_FILM, UNRESOLVED = "film", "non-film", "unresolved"
# How an override stands against the page as it is now.
ACTIVE, REDUNDANT, UNAVAILABLE = "active", "redundant", "evidence-unavailable"

# The class attribute carrying `kinola-event` as a token. The lookarounds are the whole
# point: without the trailing one this matches `kinola-event-title` and cuts every block
# at its own children, and without a token match at all -- which is what
# `class="kinola-event"` was -- a block carrying a second class is not seen, and its
# screening disappears with nothing in the log or the omission report to say so. Measured
# 2026-09-15 on both live listings: 57 blocks at Kilta and 47 at Laika, every one of them
# with that class alone, so this is hardening and not a repair of anything live.
EVENT_RE = re.compile(r'(?<![-\w])class=["\'][^"\']*(?<![-\w])kinola-event(?![-\w])')
# The container the platform wraps those blocks in, and the widget that renders either
# them or its empty state. Read as tokens for the same reason.
EVENTS_BOX_RE = re.compile(r'(?<![-\w])class=["\'][^"\']*(?<![-\w])kinola-events(?![-\w])')
FILTERS_MARKER = "kinola-filters"
# The platform's own words when a tenant has nothing on. Not a phrase this parser invented:
# see the module docstring and docs/research/kinola.md.
EMPTY_STATE = "ei tulevia tapahtumia"
TITLE_RE = re.compile(r'<a[^>]*class=["\']kinola-event-title["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                      re.S | re.I)
SLUG_RE = re.compile(r'/film/([^/?#"\']+)', re.I)
TICKET_RE = re.compile(r'<a[^>]*class=["\'][^"\']*kinola-event-tickets-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
                       re.S | re.I)
SOLD_OUT_RE = re.compile(r'kinola-event-tickets-link-sold-out', re.I)
DIV_CLASS_RE = r'<div[^>]*class=["\'][^"\']*\b%s\b[^"\']*["\'][^>]*>(.*?)</div>'
SPAN_CLASS_RE = r'<span[^>]*class=["\'][^"\']*\b%s\b[^"\']*["\'][^>]*>(.*?)</span>'
POSTER_RE = re.compile(r'<img[^>]*class=["\'][^"\']*kinola-event-poster[^"\']*["\'][^>]*>', re.I)
SRC_RE = re.compile(r'(?:data-)?src=["\']([^"\']+)["\']', re.I)
KILTA_DATE_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')
KILTA_TIME_RE = re.compile(r'(\d{1,2})[:.](\d{2})')
LAIKA_DATE_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2})[:.](\d{2})')
# `pe 18.9. klo 19:30`. The row prints no year and the weekday selects it: see
# `resolve_year`, which returns None when no candidate carries that weekday.
MYYRI_DATE_RE = re.compile(r'\b(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.\s*'
                           r'klo\s*(\d{1,2})[:.](\d{2})', re.I)
# `su, 20.09 15:00`. Myyri's "no year, the weekday selects it" shape with a comma, no
# trailing dot on the month and no `klo`.
#
# **This site answers in two languages and the weekday is the part that changes.** Read
# 2026-09-19: with `accept-language: fi-FI,fi;q=0.9`, the header `common.TEXT_HEADERS`
# always sends, the rows read `su, 20.09 15:00`; with no such header they read
# `Sun, 20.09 15:00`. The pipeline therefore only ever sees the Finnish form, and the
# English one is read as well because it costs one alternation and the first probe of this
# site saw it. Longer alternatives first: `su` is a prefix of `sun`.
SHERYL_DATE_RE = re.compile(r'\b(mon|tue|wed|thu|fri|sat|sun|ma|ti|ke|to|pe|la|su),\s*'
                            r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2})[:.](\d{2})', re.I)
EN_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _sheryl_weekday(name):
    """Finnish first, then English. -> index, or None.

    `common.weekday_index` reads the first two characters against the Finnish names, so it
    answers for `su` and `ti` whichever language they came from, and None for `mon`, `wed`,
    `thu`, `fri` and `sat`, which the English map then places.
    """
    fi = weekday_index(name)
    return fi if fi is not None else EN_WEEKDAYS.get((name or "").strip().lower()[:3])
MIN_RE = re.compile(r'(\d{1,3})\s*min\b', re.I)
# `2 h 30 min` on Myyri's pages, `106 min` on the other two. `MIN_RE` alone takes the 30
# out of the first and publishes a 150 minute film as 30. Checked against the committed
# data 2026-09-18: Kilta and Laika runtimes are all 76 to 145, so neither moves.
HM_RE = re.compile(r'(\d{1,2})\s*h\s*(\d{1,2})\s*min\b', re.I)
DT_DD_RE = re.compile(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', re.S | re.I)
STRONG_RE = re.compile(r'<strong[^>]*>\s*([A-Za-zÄÖÅäöå]{3,20})\s*</strong>\s*(?:<br\s*/?>)?'
                       r'(.*?)(?=<strong|<br\s*/?>\s*<br|<p[\s>]|</div>|$)', re.S | re.I)
KILTA_RATING_RE = re.compile(r'alt=["\']Ikäraja:\s*([^"\']+)["\']', re.I)
LAIKA_RATING_RE = re.compile(r'\bK-?(\d{1,2})\b|(?<![A-Za-zÄÖÅäöå])(S)(?![A-Za-zÄÖÅäöå])')
OG_IMAGE_RE = re.compile(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']'
                         r'|<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', re.I)
# `<p` then whitespace or `>`: an SVG `<path d=...>` is not a paragraph. Kilta's logo is
# drawn with paths, and `<p[^>]*>` read from it through the site menu to the first `</p>`.
SYN_RE = re.compile(r'<p(?:\s[^>]*)?>(.*?)</p>', re.S | re.I)
TAGS_RE = re.compile(r"<[^>]+>")
# Kilta's film page, read on all 40 listed films 2026-09-24 (docs/research/kinola.md).
# The description is the <p> run between the page title and the info block; a paragraph
# of only dashes or asterisks separates the Finnish section from a Swedish or English
# one, or the notices from the synopsis. Dropped as not the film's own text: a paragraph
# bold throughout (headings, strand lines), one quoting a price, naming the cinema or
# carrying a URL, and a source credit.
# Sheryl's film page, read 2026-09-24: after the page's one <hr>, the title in bold, the
# original title, the country, then an optional release date and the runtime,
# "2026-09-18, 94 min", up to the first blank line before "Director". That block is the
# runtime the page publishes; the text before the first <p> held it only on pages whose
# synopsis is not in <p> elements.
SHERYL_FACTS_RE = re.compile(
    r"<hr\s*/?>\s*(?:<br\s*/?>\s*)*<strong>.*?</strong>(.*?)<br\s*/?>\s*<br\s*/?>",
    re.S | re.I)
KILTA_SEP_RE = re.compile(r"^(?:-{2,}|\*{3,})$")
KILTA_STRONG_RE = re.compile(r"<strong[^>]*>(.*?)</strong>", re.S | re.I)
KILTA_NAME_RE = re.compile(r"\b(?:Kilta|Killa)")
KILTA_URL_RE = re.compile(r"https?://|www\.", re.I)
KILTA_CREDIT_RE = re.compile(r"^(?:Lähde|Källa|Source)\s*:", re.I)


def _txt(s):
    return re.sub(r"\s+", " ", html_mod.unescape(TAGS_RE.sub(" ", s or ""))
                  .replace("\xa0", " ")).strip()


def _minutes(text):
    """`2 h 30 min` or `106 min` -> "150" / "106". -> str, "" when neither shape is there."""
    m = HM_RE.search(text or "")
    if m:
        return str(int(m.group(1)) * 60 + int(m.group(2)))
    m = MIN_RE.search(text or "")
    return m.group(1) if m else ""


def _one(pattern, cls, block):
    m = re.search(pattern % cls, block, re.S | re.I)
    return _txt(m.group(1)) if m else ""


class ListingRowError(RuntimeError):
    """A block the listing marks as a screening and this parser could not read.

    Neither an empty programme nor a policy omission, and not something to skip. The row
    is *there*: dropping it publishes a schedule one screening short, and the omission
    report cannot say so either, because that report counts what the classification policy
    withheld and this was never classified. With every row malformed the site then looked
    like a cinema with nothing on and the run stayed green.

    A RuntimeError, so `run.py` treats it as any other parse failure: the site fails, its
    files are left as they were, and the other cinema on this module still publishes.
    """


def _row_fault(site, n, field, value="", title=""):
    """The message a ListingRowError carries. -> ListingRowError.

    Names the field and quotes the short text it was read from -- a date or a time, never
    the block -- because a committed log in a public repo may not carry a third party's
    markup. `n` is the block's place in the listing, which is what makes the row findable
    on the page without one.
    """
    seen = re.sub(r"\s+", " ", value or "").strip()[:60]
    return ListingRowError(
        f"{site['provider']}: screening block {n + 1} of the listing has no readable "
        f"{field}" + (f" for {title!r}" if title else "") +
        (f" (read {seen!r})" if seen else "") +
        ". The listing marks it as a screening, so skipping it would drop a screening "
        "from the schedule and from the omission report alike; failing keeps the last "
        "good data")


def blocks(page):
    """-> [html] one per screening, sliced between `kinola-event` class tokens.

    A token and not the whole attribute: a block carrying a second class is the same
    block. Not a substring either, since `kinola-event-title`, `-date`, `-venue` and
    `-tickets-link` all start with it and would cut a block into pieces at its own
    children, and `kinola-events` is the container around the lot. See EVENT_RE.
    """
    starts = [page.rfind("<", 0, m.start()) for m in EVENT_RE.finditer(page)]
    starts = [i for i in starts if i >= 0]
    out = []
    for n, i in enumerate(starts):
        out.append(page[i:starts[n + 1] if n + 1 < len(starts) else len(page)])
    return out


def _title_and_slug(block, base):
    m = TITLE_RE.search(block)
    if not m:
        return "", "", ""
    href, inner = html_mod.unescape(m.group(1)), m.group(2)
    sm = SLUG_RE.search(href)
    return _txt(inner), (sm.group(1) if sm else ""), urljoin(base, href)


def _destination(block, base, film_url):
    """The checkout href the row emits, or the film page when the row is sold out.

    Never constructed: a sold-out Laika row has no anchor at all, and building a checkout
    URL from a copied path is what shipped six dead Nexxo links.
    """
    m = TICKET_RE.search(block)
    if m and not SOLD_OUT_RE.search(m.group(0)):
        return urljoin(base, html_mod.unescape(m.group(1))), False
    return film_url, bool(SOLD_OUT_RE.search(block))


def events_kilta(page, site):
    """-> [{slug, title, film_url, start, url, soldOut, method, len}]

    Every block yields a row or raises: see ListingRowError. A missing film slug counts as
    unreadable too, because the film page is where the classification lives, and a row with
    no page to read is a parse failure being reported as an unresolved classification.
    """
    out = []
    for n, b in enumerate(blocks(page)):
        title, slug, film_url = _title_and_slug(b, site["base"])
        dtxt, ttxt = _one(DIV_CLASS_RE, "date", b), _one(DIV_CLASS_RE, "time", b)
        d = KILTA_DATE_RE.search(dtxt)
        t = KILTA_TIME_RE.search(ttxt)
        if not title:
            raise _row_fault(site, n, "title link")
        if not slug:
            raise _row_fault(site, n, "film page link", title=title)
        if not d:
            raise _row_fault(site, n, "date", dtxt, title)
        if not t:
            raise _row_fault(site, n, "time", ttxt, title)
        try:
            start = datetime.datetime(int(d.group(3)), int(d.group(2)), int(d.group(1)),
                                      int(t.group(1)), int(t.group(2)), tzinfo=FI)
        except ValueError as e:
            raise _row_fault(site, n, "calendar date", f"{dtxt} {ttxt}", title) from e
        url, sold = _destination(b, site["base"], film_url)
        dur = _minutes(_one(DIV_CLASS_RE, "duration-info", b))
        out.append({"slug": slug, "title": title, "film_url": film_url,
                    "start": start.isoformat(), "url": url, "soldOut": sold,
                    "method": _one(DIV_CLASS_RE, "movie-subtitle", b),
                    "len": dur, "img": ""})
    return out


def events_laika(page, site):
    """The same contract as events_kilta: a block yields a row or raises."""
    out = []
    for n, b in enumerate(blocks(page)):
        title, slug, film_url = _title_and_slug(b, site["base"])
        dtxt = _one(SPAN_CLASS_RE, "kinola-event-date", b)
        d = LAIKA_DATE_RE.search(dtxt)
        if not title:
            raise _row_fault(site, n, "title link")
        if not slug:
            raise _row_fault(site, n, "film page link", title=title)
        if not d:
            raise _row_fault(site, n, "date", dtxt, title)
        try:
            start = datetime.datetime(int(d.group(3)), int(d.group(2)), int(d.group(1)),
                                      int(d.group(4)), int(d.group(5)), tzinfo=FI)
        except ValueError as e:
            raise _row_fault(site, n, "calendar date", dtxt, title) from e
        url, sold = _destination(b, site["base"], film_url)
        pm = POSTER_RE.search(b)
        src = SRC_RE.search(pm.group(0)) if pm else None
        out.append({"slug": slug, "title": title, "film_url": film_url,
                    "start": start.isoformat(), "url": url, "soldOut": sold,
                    "method": "", "len": "",
                    "img": urljoin(site["base"], html_mod.unescape(src.group(1)))
                           if src else ""})
    return out


def _events_no_year(page, site, today, date_re, weekday):
    """The body Myyri and Sheryl share: a block yields a row or raises.

    Neither row prints a year, so the weekday selects it through `resolve_year`. A weekday
    no candidate year carries, or a date outside `MYYRI_WINDOW`, raises: a block this
    parser cannot place is a screening it would otherwise drop.

    The ticket link is the row's own `/checkout/{uuid}` href, copied and resolved by
    `_destination` and never requested ("Access and ethics" in CLAUDE.md). A row marked
    sold out anywhere in its block, or carrying no ticket anchor, opens the film page.
    `weekday` maps the row's own weekday name to an index, because the two templates
    print it in different languages.
    """
    today = today or datetime.datetime.now(FI).date()
    out = []
    for n, b in enumerate(blocks(page)):
        title, slug, film_url = _title_and_slug(b, site["base"])
        dtxt = _one(SPAN_CLASS_RE, "kinola-event-date", b)
        d = date_re.search(dtxt)
        if not title:
            raise _row_fault(site, n, "title link")
        if not slug:
            raise _row_fault(site, n, "film page link", title=title)
        if not d:
            raise _row_fault(site, n, "date", dtxt, title)
        day, month = int(d.group(2)), int(d.group(3))
        year = resolve_year(day, month, today, weekday(d.group(1)), MYYRI_WINDOW)
        if year is None:
            raise _row_fault(site, n, "year the weekday and date agree on", dtxt, title)
        try:
            start = datetime.datetime(year, month, day,
                                      int(d.group(4)), int(d.group(5)), tzinfo=FI)
        except ValueError as e:
            raise _row_fault(site, n, "calendar date", dtxt, title) from e
        pm = POSTER_RE.search(b)
        src = SRC_RE.search(pm.group(0)) if pm else None
        sold = bool(SOLD_OUT_RE.search(b))
        out.append({"slug": slug, "title": title, "film_url": film_url,
                    "start": start.isoformat(),
                    "url": film_url if sold else _destination(b, site["base"], film_url)[0],
                    "soldOut": sold,
                    "method": "", "len": "",
                    "img": urljoin(site["base"], html_mod.unescape(src.group(1)))
                           if src else ""})
    return out


def events_myyri(page, site, today=None):
    return _events_no_year(page, site, today, MYYRI_DATE_RE, weekday_index)


def events_sheryl(page, site, today=None):
    return _events_no_year(page, site, today, SHERYL_DATE_RE, _sheryl_weekday)


TEMPLATES = {"kilta": events_kilta, "laika": events_laika, "myyri": events_myyri,
             "sheryl": events_sheryl}


def syn_value(site, text):
    """What `_syn` carries for one site. -> str, {lang: str}, or "" to publish none.

    A site without `declare_syn` keeps the bare string, which `synmerge` reads as Finnish:
    Kilta and Laika. A site with it has the text placed by `common.syn_language`, and an
    unplaceable one is withheld.
    """
    if not site.get("declare_syn"):
        return text
    lang = syn_language(text)
    return {lang: text} if lang else ""


def labels(page):
    """-> {lowercased label: value} from either film-page template.

    Both shapes land in one dict so the classifier does not have to know which site it is
    reading: Kilta writes `<dt>Ohjaaja</dt><dd>Klaus Härö</dd>`, Laika writes
    `<strong>Ohjaus</strong> <br> Klaus Härö`.
    """
    out = {}
    for k, v in DT_DD_RE.findall(page):
        key, val = _txt(k).lower(), _txt(v)
        if key and val:
            out.setdefault(key, val)
    for k, v in STRONG_RE.findall(page):
        key, val = _txt(k).lower(), _txt(v)
        if key and val:
            out.setdefault(key, val)
    return out


def _head(page):
    """Laika's bare runtime and classification sit above the first paragraph. Bounded on
    purpose: a `K-12` or a `min` anywhere in a synopsis is not this film's own."""
    i = page.find("<strong>")
    j = page.find("<p", i if i >= 0 else 0)
    return _txt(page[i:j]) if 0 <= i < j else ""


def _rating(page, head):
    """Kilta's `alt` first, then Laika's bare token. "" when the page says nothing: the
    shared classification pass fills a blank from another chain showing the same film."""
    m = KILTA_RATING_RE.search(page)
    if m:
        v = _txt(m.group(1))
        if v.lower().startswith("sallittu"):
            return "S"
        d = re.search(r"(\d+)", v)
        return f"K-{d.group(1)}" if d else ""
    m = LAIKA_RATING_RE.search(head)
    if not m:
        return ""
    return "S" if m.group(2) else f"K-{m.group(1)}"


def _lang(facts):
    """-> ("FI-A, SV-S", [unread names]) from the language and subtitle labels, Finnish or
    English (Sheryl). A role holding a name `NAMES` does not know publishes nothing, and the
    name is returned: a partial list reads as the whole one."""
    out, unread = [], []
    for labels, suffix in ((("kieli", "language"), "-A"), (("tekstitys", "subtitles"), "-S")):
        value = next((facts[k] for k in labels if facts.get(k)), "")
        parts = [p.strip() for p in re.split(r"[,/]|\bja\b|\band\b", value) if p.strip()]
        missing = [p for p in parts if p.lower() not in NAMES]
        if missing:
            unread += missing
            continue
        for code in (NAMES[p.lower()] for p in parts):
            if code + suffix not in out:
                out.append(code + suffix)
    return ", ".join(out), unread


def kilta_synopsis(page):
    """-> ({lang: text}, withheld) for a Kilta film page.

    Each section is kept whole, its paragraphs joined, and placed by
    `common.syn_language`; a section no language settles is withheld and counted, never
    filed as Finnish. Longest-paragraph selection put a Nordic film's Swedish paragraph in
    the Finnish slot on 2026-09-24, because Kilta writes its Finnish synopsis in two."""
    i = page.find("page-title")
    if i < 0:
        return {}, 0
    start = page.find("</div>", i)
    end = page.find("hide-for-l-up", start)
    region = page[start:end if end > 0 else len(page)]
    sections = [[]]
    for raw in SYN_RE.findall(region):
        text = _txt(raw)
        if not text:
            continue
        if KILTA_SEP_RE.match(text):
            sections.append([])
            continue
        bold = _txt(" ".join(KILTA_STRONG_RE.findall(raw)))
        if (text == bold or is_note(text) or KILTA_NAME_RE.search(text)
                or KILTA_URL_RE.search(text) or KILTA_CREDIT_RE.match(text)):
            continue
        sections[-1].append(text)
    out, withheld = {}, 0
    for body in (" ".join(sec) for sec in sections if sec):
        lang = syn_language(body)
        if not lang:
            withheld += 1
            continue
        out[lang] = f"{out[lang]} {body}" if lang in out else body
    return out, withheld


def sheryl_runtime(page):
    """-> minutes as a string from Sheryl's title block, "" when the block or a runtime in
    it is missing. Nothing else on the page is read for it."""
    m = SHERYL_FACTS_RE.search(page)
    return _minutes(_txt(m.group(1))) if m else ""


def film_facts(page, template=None):
    """-> {labels, rating, len, genres, img, syn} for one film page. On Kilta `syn` is the
    {lang: text} of `kilta_synopsis`, and `syn_withheld` counts what it could not place."""
    facts = labels(page)
    head = _head(page)
    dur = _minutes(facts.get("kesto", "")) or _minutes(head)
    if template == "sheryl":
        dur = sheryl_runtime(page)
    og = OG_IMAGE_RE.search(page)
    # The longest paragraph over 120 characters, not the first: Kilta's strand films open
    # with the strand's notice and Laika's with a ticket notice, both long enough to pass.
    syn = max((t for t in map(_txt, SYN_RE.findall(page)) if len(t) > 120),
              key=len, default="")
    withheld = 0
    if template == "kilta":
        syn, withheld = kilta_synopsis(page)
    lang, unread = _lang(facts)
    # Kilta's `og:image` is a film still, not a poster: all 40 films read 2026-10-04 were
    # landscape (342x143 to 342x250 mirrored), one named "still2_photo_by_...". The page
    # carries no other image, so nothing is published and the TMDB pass gives the poster.
    img = (og.group(1) or og.group(2)) if og and template != "kilta" else ""
    return {"labels": facts, "rating": _rating(page, head),
            "len": dur,
            "genres": facts.get("lajityyppi", ""),
            "img": img,
            "syn": syn, "syn_withheld": withheld, "lang": lang, "lang_unread": unread}


def load_overrides(path=None):
    """-> {(provider, slug): entry}. Absent file is no overrides, not an error."""
    path = path or OVERRIDE_FILE
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    out = {}
    for row in doc.get("overrides", []):
        pid, slug, action = row.get("provider"), row.get("slug"), row.get("action")
        if pid and slug and action in ("include", "exclude"):
            out[(pid, slug)] = row
    return out


def default_state(facts):
    """-> FILM or UNRESOLVED: everything the classifier can say without help.

    Never NON_FILM. Nothing on these pages marks a live act structurally, so a runtime
    verdict of "this is not a film" would have to come from a word in a title or a
    synopsis, which the policy forbids.
    """
    return FILM if any(facts["labels"].get(k) for k in FILM_LABELS) else UNRESOLVED


def classify(provider, slug, facts, overrides):
    """-> (publish, state, default).

    `state` is the policy's verdict and `default` is what the classifier would have said
    alone, which is what makes revalidation possible at all.

    The override is consulted before the labels, which is the adopted precedence: explicit
    event-level evidence of a live act prevents automatic inclusion even where generic
    metadata is present. A billed gig whose page fills `Ohjaus` would publish otherwise.
    """
    d = default_state(facts)
    o = overrides.get((provider, slug))
    if o:
        return (True, FILM, d) if o["action"] == "include" else (False, NON_FILM, d)
    return d == FILM, d, d


def override_state(entry, default, listed, page_read):
    """-> ACTIVE, REDUNDANT or UNAVAILABLE for one override, against the page as it is.

    Redundancy is a statement about the decision **and about nothing else**: an `include`
    is redundant once the page classifies as a film on its own, and an `exclude` once it
    does not. It does not mean the entry's evidence was wrong, and it is not a licence to
    delete. An exclusion is worth keeping precisely because a cinema that fills no field
    today may fill a misleading one tomorrow, at which point the same entry goes back to
    `active` and is the only thing withholding a gig. Nothing here removes an entry, and
    no test requires one to be removed to pass.

    An entry whose event is not in the listing, or whose page was not read, is neither
    active nor redundant: the evidence for it is simply unavailable this run, and dropping
    it on that basis would delete a still-needed override the first time a film went off
    programme.
    """
    if not listed or not page_read:
        return UNAVAILABLE
    if entry["action"] == "include":
        return REDUNDANT if default == FILM else ACTIVE
    return ACTIVE if default == FILM else REDUNDANT


def parse(site, listing, pages, overrides=None):
    """-> ({venue_id: [show]}, omissions). `pages` is {slug: film page html}.

    `omissions` counts what the policy left out, as unique films and as screenings, split
    by state: `non_film_*` is what an evidence-backed exclusion asserted, `unresolved_*`
    what the classifier could not resolve. The two are never merged, because only the
    first is a claim that something is not a film and only a person made it.

    `om["overrides"]` scores every entry against the pages this run read: active,
    redundant, or evidence-unavailable.
    """
    overrides = {} if overrides is None else overrides
    venue = site["venues"][0]
    rows = TEMPLATES[site["template"]](listing, site)
    facts_by_slug = {slug: film_facts(html, site.get("template"))
                     for slug, html in pages.items()}
    listed = {e["slug"] for e in rows if e["slug"]}
    shows, seen = [], set()
    om = {"non_film_films": set(), "non_film_shows": 0,
          "unresolved_films": set(), "unresolved_shows": 0, "overrides": {},
          # Films whose blurb this run would not place in a language. The screening
          # publishes; only the synopsis is withheld, and the count is printed.
          "syn_unplaced": set(),
          # Films with a language name `NAMES` does not know: that role publishes blank.
          "lang_unread": set()}
    # Every entry for this provider, not only the ones the listing happens to hold, so an
    # override whose film has left the programme is reported rather than silently ignored.
    for (pid, slug), entry in sorted(overrides.items()):
        if pid != site["provider"]:
            continue
        facts = facts_by_slug.get(slug)
        om["overrides"][slug] = override_state(
            entry, default_state(facts) if facts else UNRESOLVED,
            slug in listed, facts is not None)
    for e in rows:
        slug = e["slug"] or ""
        facts = facts_by_slug.get(slug) or {"labels": {}, "rating": "", "len": "",
                                            "genres": "", "img": "", "syn": "",
                                            "lang": ""}
        publish, state, _ = classify(site["provider"], slug, facts, overrides)
        if not publish:
            if state == NON_FILM:
                om["non_film_films"].add(e["title"])
                om["non_film_shows"] += 1
            else:
                om["unresolved_films"].add(e["title"])
                om["unresolved_shows"] += 1
            continue
        key = (e["start"], slug or e["title"])
        if key in seen:
            continue
        seen.add(key)
        row = {
            "eventId": slug or e["title"].lower(),
            "title": e["title"],
            "original": "",
            "len": e["len"] or facts["len"],
            "rating": facts["rating"],
            "genres": facts["genres"],
            "method": e["method"],
            "theatre": venue["name"],
            "aud": "",
            "start": e["start"],
            "url": e["url"],
            "img": e["img"] or facts["img"],
            "lang": facts["lang"],
            "soldOut": e["soldOut"],
            "price": "",
            "provider": site["provider"],
            "venue": venue["id"],
        }
        if facts.get("lang_unread"):
            om["lang_unread"].add(f"{e['title']} ({', '.join(facts['lang_unread'])})")
        if facts["syn"]:
            syn = syn_value(site, facts["syn"])
            if syn:
                row["_syn"] = syn
            else:
                om["syn_unplaced"].add(e["title"])
        if facts.get("syn_withheld"):
            om["syn_unplaced"].add(e["title"])
        shows.append(row)
    shows.sort(key=lambda s: s["start"])
    return {venue["id"]: shows}, om


def empty_programme_evidence(page):
    """-> "" when the page is positive evidence of an empty programme, else why it is not.

    Every condition is something the row parser does **not** read, which is what
    `common.EmptyProgramme` requires: "my parser found nothing" is the one thing that may
    not be the evidence, because a markup change upstream produces exactly that while the
    page is still full of films.

    The three are the shape measured on 2026-09-15 -- see the module docstring. The empty
    text is looked for after the filter widget rather than anywhere on the page, so a
    cinema writing the same words in its own page copy above the listing does not silence a
    parse that broke underneath it; that is the trap `test_empty_programme.py` already
    records for eTiketti, whose empty phrase had to be scoped to its container.
    """
    i = page.lower().find(FILTERS_MARKER)
    if i < 0:
        return "the Kinola listing widget is not on the page at all"
    if EVENTS_BOX_RE.search(page):
        return ("the event container rendered and held no readable screening, which is a "
                "markup change rather than a cinema with nothing on")
    if EMPTY_STATE not in page[i:].lower():
        return "the widget rendered neither an event list nor its empty state"
    return ""


def get(url, tries=3, timeout=30):
    """`common.get_text` with this module's own `fetch`, which its tests stub."""
    return get_text(url, fetcher=fetch, tries=tries, timeout=timeout)


def fetch_site(site, sleep=1.2):
    """Runner contract: one listing, then one film page per distinct film.

    A listing with no screening block is `EmptyProgramme` **only** on the evidence
    `empty_programme_evidence` asks for; short of it the site fails and keeps its files.
    Zero blocks used to be the whole test, which read an unrelated page, a renamed row
    class and a listing whose every row was malformed as a cinema with nothing on.

    A listing that holds blocks while nothing publishes is a different case and is not an
    empty programme either: the film pages decided it, which is the policy working. That
    check is at the end of this function and stays where it is.
    """
    listing_url = site["base"].rstrip("/") + site["listing"]
    listing = get(listing_url)
    rows = TEMPLATES[site["template"]](listing, site)
    if not rows:
        why = empty_programme_evidence(listing)
        if why:
            raise RuntimeError(
                f"{listing_url}: no screening block, and no evidence of an empty "
                f"programme -- {why}. Zero parsed rows is not evidence on its own, so "
                f"this fails and the previous files stand")
        raise EmptyProgramme(
            f"{listing_url} renders the listing's empty state and no screening")
    slugs = budget_or_raise(sorted({e["slug"] for e in rows if e["slug"]}),
                            site["provider"])
    pages = {}
    for n, slug in enumerate(slugs):
        if n:
            time.sleep(sleep)
        url = next(e["film_url"] for e in rows if e["slug"] == slug)
        try:
            pages[slug] = get(url)
        except Exception as e:
            raise RuntimeError(
                f"{url}: {e}. The film page carries the classification, so a missing one "
                f"would silently omit that film's screenings") from e
    per_venue, om = parse(site, listing, pages, load_overrides())
    shows = per_venue[site["venues"][0]["id"]]
    pid = site["provider"]
    print(f"[{pid}] {len(rows)} screening(s) listed, {len(slugs)} film page(s) read")
    # The two omission classes are reported apart on purpose. "Confirmed non-film" says a
    # person excluded it on recorded evidence; "unresolved" says the classifier could not
    # tell, which is not the same claim and must not be dressed up as one.
    print(f"[{pid}] omitted {len(om['non_film_films'])} confirmed non-film(s) by "
          f"evidence-backed exclusion over {om['non_film_shows']} screening(s), and "
          f"{len(om['unresolved_films'])} unresolved over {om['unresolved_shows']}")
    if om["non_film_films"]:
        print(f"[{pid}] confirmed non-film: "
              f"{', '.join(sorted(om['non_film_films'])[:12])}")
    if om["unresolved_films"]:
        print(f"[{pid}] unresolved: {', '.join(sorted(om['unresolved_films'])[:12])}")
    for slug, state in sorted(om["overrides"].items()):
        print(f"[{pid}] override {slug}: {state}")
    if om["syn_unplaced"]:
        print(f"[{pid}] {len(om['syn_unplaced'])} synopsis/synopses withheld, no language "
              f"settled: {', '.join(sorted(om['syn_unplaced'])[:8])}")
    if om["lang_unread"]:
        print(f"[{pid}] {len(om['lang_unread'])} film(s) with a language name not read, "
              f"that part left blank: {'; '.join(sorted(om['lang_unread'])[:8])}")
    if not shows:
        raise RuntimeError(
            f"{listing_url} lists {len(rows)} screening(s) and none "
            f"published. The listing is not empty, so this is a template or "
            f"classification failure rather than a cinema with nothing on")
    days = sorted({s["start"][:10] for s in shows})
    print(f"[{pid}] {site['venues'][0]['name']}: {len(shows)} showtimes, {len(days)} dates")
    return per_venue


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "kinokilta"
    site = next(s for s in SITES if s["provider"] == which)
    for vid, shows in fetch_site(site).items():
        print(f"{vid}: {len(shows)} showtimes")
        for s in shows[:5]:
            print(f"   {s['start'][:16]}  {s['title'][:30]:32} {s['rating']:5} "
                  f"{s['len']:4} {s['lang']:14} {s['method'][:22]:24} sold={s['soldOut']}")
