"""eTiketti renders its screenings in two templates, and etiketti.py reads both.

Kotka's template (nineteen of the twenty hosts) prints "KE 2.9. klo 20.00", a place
line "TRIO 123 | SALI 2", "Lippu 15,00€" and "Vapaat paikat 27/35". Cinema Niagara's
(2026-09-02) prints the time in a `time` div, the price in `show-price`, "Paikkoja
vapaana: 126/127", per-screening tags in `movie-specs`, no place line, a newline between
`<div` and `class`, and labels without a colon. The fixtures are minimal hand-written
reconstructions of those shapes.

Niagara's programme page renders every screening twice, so shows are keyed on the public
screening id the ticket href carries. The href is the outbound link and is never fetched.
Provider modules are imported inside the tests: they bind `common.EmptyProgramme` at
import time and `test_common_fetch` reloads `common`.
"""
import contextlib
import datetime
import importlib
import io
import json
import pathlib
import re
import tempfile
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import common


def load():
    return importlib.import_module("etiketti")


def site(pid):
    return next(s for s in load().SITES if s["provider"] == pid)


HIDDEN = ('<div class="no-results" id="no-results" style="display: none;">'
          "<p>Ei näytöksiä valitsemallasi päivämäärällä.</p></div>")

# --- template 1: Kotka ------------------------------------------------------------------

KOTKA_FILM = """<main>
<h1>Insidious: Out of the Further</h1>
<img class="poster-img" src="https://cdn.example/kotka/poster/insidious_1.webp?w=250" alt="">
<img src="https://cdn.example/kotka/img/ikarajat/fi-16.svg" alt="Sallittu yli 16-vuotiaille">
<div class="description-container"><span>Elokuva on sallittu yli 16-vuotiaille. Sisältää kauhua. Tarina jatkuu siitä, mihin edellinen jäi.</span></div>
<span class="label">Kesto:</span> 1 h 46 min<br />
<span class="label">Kieli:</span> englanti<br />
<span class="label">Tekstitys:</span> Suomi ja ruotsi<br />
<span class="movie-genre">Kauhu</span><span class="movie-genre">Trilleri</span>
<h2>Näytökset</h2>
<div class="screenings">
""" + HIDDEN + """
<div class="item kotka date-2.9.2026"> <div> <p> <strong><span>KE 2.9. klo 20.00</span></strong> </p> <p> TRIO 123 | SALI 2<br /> Lippu 15,00&euro;<br /> Vapaat paikat 27/35 </p> </div> <div> <a class="button-screening" href="/salikartta?id=56106"> Osta tai varaa </a> </div> </div>
<div class="item kotka date-4.9.2026"> <div> <p> <strong><span>PE 4.9. klo 19.30</span></strong> </p> <p> KINOPALATSI<br /> Lippu 12,50&euro;<br /> Vapaat paikat 0/120 </p> </div> <div> <a class="button-screening" href="/salikartta?id=56107"> Osta tai varaa </a> </div> </div>
</div>
</div>
</div>
</main>"""

# --- template 2: Cinema Niagara ---------------------------------------------------------

def niagara_item(date, hhmm, sid, price="13,00", seats="126/127", tags=(), opener=None):
    opener = opener if opener is not None else f'<div\n        class="item tampere date-{date}">'
    tag_html = "".join(f'<span class="tag" style="background-color:#a6d6c4;">{t}</span>'
                       for t in tags)
    price_html = f'<div class="show-price">\n  {price}€\n</div>' if price else ""
    seats_html = (f'<div class="seats-info"><div class="seat-color seats-high">\n</div>\n'
                  f'Paikkoja vapaana: {seats}\n</div>' if seats else "")
    return (f"{opener}\n<div class=\"time\">\n  <span>{hhmm}</span>\n</div>\n"
            f'<div class="movie-specs">\n  {tag_html}\n</div>\n{price_html}\n'
            f'<div class="action">\n<a class="button-screening" href="/salikartta?id={sid}">\n'
            f"  Osta liput\n</a>\n{seats_html}</div>\n</div>\n")


NIAGARA_HEAD = """<main>
<h1>The Invite</h1>
<img class="poster-img" src="https://cdn.example/niagara/poster/the-invite_1.webp?w=250" alt="The Invite">
<img src="https://cdn.example/niagara/img/ikarajat/fi-12.svg" alt="Sallittu yli 12-vuotiaille">
<div class="description-container"><span>Elokuva on sallittu yli 12-vuotiaille. Sisältää seksiä. Joen ja Angelan avioliitto on veitsenterällä.</span></div>
<div class="movie-details-grid">
<div><span class="label">Kieli                </span> englanti, espanja </div>
<div><span class="label">Tekstitys            </span> Suomi ja ruotsi </div>
<div><span class="label">Kesto                </span> 1 h 48 min </div>
<div><span class="label">Näyttelijät</span> Seth Rogen, Olivia Wilde </div>
<div><span class="label">Ohjaaja</span> Olivia Wilde </div>
<div><span class="label">genre</span> Draama, Komedia </div>
</div>
"""

NIAGARA_ITEMS = (
    '<div class="show-date-header">Torstai 3.9.</div>\n'
    + niagara_item("3.9.2026", "16.15", 53882, "13,00", "126/127")
    + niagara_item("3.9.2026", "18.45", 53955, "11,00", "0/127", ("Seniorikino", "Q&amp;A"))
    + '<div class="show-date-header">Torstai 5.11.</div>\n'
    + niagara_item("5.11.2026", "12.00", 60001, "8,00", "40/127", ("Seniorikino",))
)


def niagara_page(items=NIAGARA_ITEMS, twice=True):
    block = f'<div class="screenings shows niagara">\n{HIDDEN}\n{items}</div>\n'
    body = f'<div class="desktop">\n{block}</div>\n'
    if twice:
        body += f'<div class="mobile">\n{block}</div>\n'
    return NIAGARA_HEAD + body + "</main>"


NIAGARA_FILM = niagara_page()

# A film page in neither template: the listing links to it, it renders no screening item.
FOREIGN_FILM = "<main><h1>Elokuva</h1><section><p>Liput ovelta.</p></section></main>"


def listing(*paths, nav=""):
    """The programme listing. `nav` is appended outside `main`, where the site renders its
    theatre navigation, which is what identifies a venue with no screening row."""
    cards = "".join(f'<div class="item tampere date-3.9.2026 name-x"><a href="{p}">x</a></div>'
                    for p in paths)
    return f'<main><div class="screenings movie-list">{cards}</div>{HIDDEN}</main>{nav}'


LISTING = listing("/elokuvat/70/the-invite", "/elokuvat/63/the-dog-stars")
GENUINELY_EMPTY = ('<main><div class="screenings movie-list"><p>Ei ohjelmistoa saatavilla.</p>'
                   f"</div>{HIDDEN}</main>")


def stub_get(mapping):
    """Route `etiketti.get` by URL suffix. Anything unmapped is a test error, and a
    request for /salikartta is the one thing this adapter must never make. A mapped value
    that is an exception is raised instead of returned, which is how a page that fails to
    fetch is staged."""
    def get(url, tries=3):
        if "/salikartta" in url:
            raise AssertionError(f"booking page requested: {url}")
        for suffix, page in mapping.items():
            if url.endswith(suffix):
                if isinstance(page, Exception):
                    raise page
                return page
        raise AssertionError(f"unexpected fetch: {url}")
    return get


class Stubbed(unittest.TestCase):
    def stub(self, mapping):
        e = load()
        real = e.get
        e.get = stub_get(mapping)
        self.addCleanup(lambda: setattr(e, "get", real))
        return e


# --- template 1 still parses exactly as before -------------------------------------------

class KotkaTemplateTest(Stubbed):

    def rows(self):
        e = load()
        return e.parse_movie(KOTKA_FILM, site("kotkanleffat"), "/elokuvat/3268/insidious")

    def test_two_dates_two_rows_with_place_room_price_seats_and_link(self):
        rows, meta = self.rows()
        self.assertEqual(len(rows), 2)
        a, b = rows
        self.assertEqual((a["theatre_raw"], a["aud"]), ("TRIO 123", "SALI 2"))
        self.assertEqual(a["start"], "2026-09-02T20:00:00+03:00")
        self.assertEqual((a["price"], a["free"]), ("15€", 27))
        self.assertEqual(a["url"], "https://kotkanleffat.fi/salikartta?id=56106")
        self.assertEqual((b["theatre_raw"], b["aud"]), ("KINOPALATSI", ""))
        self.assertEqual((b["price"], b["free"]), ("12.5€", 0))

    def test_a_bare_whole_amount_keeps_its_zero_on_kotkas_template_too(self):
        e = load()
        page = KOTKA_FILM.replace("Lippu 15,00", "Lippu 20").replace("Lippu 12,50", "Lippu 10")
        self.assertNotEqual(page, KOTKA_FILM)
        rows, _ = e.parse_movie(page, site("kotkanleffat"), "/elokuvat/3268/insidious")
        self.assertEqual([r["price"] for r in rows], ["20€", "10€"])

    def test_metadata_with_colon_labels_and_genre_spans(self):
        _, meta = self.rows()
        self.assertEqual(meta["title"], "Insidious: Out of the Further")
        self.assertEqual(meta["rating"], "K-16")
        self.assertEqual(meta["len"], "106")
        self.assertEqual(meta["img"], "https://cdn.example/kotka/poster/insidious_1.webp")
        self.assertEqual(meta["lang"], "EN-A, FI-S, SV-S")
        self.assertEqual(meta["genres"], "Kauhu, Trilleri")
        self.assertEqual(meta["syn"], "Tarina jatkuu siitä, mihin edellinen jäi.")

    def test_kotka_rows_carry_no_tags_and_match_by_the_place_line(self):
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/3268/insidious"),
                       "/elokuvat/3268/insidious": KOTKA_FILM})
        out = e.fetch_site(site("kotkanleffat"), sleep=0)
        self.assertEqual(sorted(out), ["kl-kinopalatsi", "kl-trio123"])
        show = out["kl-trio123"][0]
        self.assertEqual(show["method"], "")
        self.assertEqual(show["aud"], "SALI 2")
        self.assertFalse(show["soldOut"])
        self.assertTrue(out["kl-kinopalatsi"][0]["soldOut"])


# --- template 2 ---------------------------------------------------------------------------

# Haapamäen Elokuvat's film page, read 2026-09-29 when the site moved here from Johku:
# Kotka's template, the place line alone with no room, and the venue class in mixed case.
HAAPAMAKI_FILM = """<main>
<h1>Heart of the Beast</h1>
<div class="movie-icons"><img src="https://cdn.example/haapamaki/img/ikarajat/fi-12.svg"
alt="Sallittu yli 12-vuotiaille"></div>
<img class="poster-img" src="https://cdn.example/haapamaki/poster/heart-of-the-beast.webp?w=200" alt="">
<span class="label">Kesto:</span> 1 h 41 min<br /> <span class="label">Kieli:</span> englanti<br />
<span class="label">Tekstitys:</span> Suomi ja ruotsi<br />
<div class="description-container fade" id="movieDesc"><span>Jouduttuaan vakavaan
lentokoneonnettomuuteen entinen erikoisjoukkojen upseeri ja hänen taistelukoiransa jäävät
selviytymään kahdestaan erämaahan, jossa kumpikin joutuu luottamaan toiseen.</span></div>
<div class="screenings">
<div class="item haapam\u00c4ki date-2.10.2026"> <div> <p> <strong><span>PE 2.10. klo 19.00</span></strong>
</p> <p> HAAPAM\u00c4EN ELOKUVAT<br /> Lippu 11,00&euro;<br /> Vapaat paikat 120/120 </p> </div>
<div> <a class="button-screening" href="/salikartta?id=53382"> Osta tai varaa </a> </div> </div>
</div></main>"""


class HaapamakiTest(Stubbed):
    """Haapamäen Elokuvat on this platform from 2026-09-29, under the venue id it had on
    Johku, which keys a saved home cinema and its /teatteri/ URL."""

    def test_the_moved_site_reads_its_screening_under_the_old_venue_id(self):
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/3/heart-of-the-beast"),
                       "/elokuvat/3/heart-of-the-beast": HAAPAMAKI_FILM})
        with contextlib.redirect_stdout(io.StringIO()):
            out = e.fetch_site(site("haapamaki"), sleep=0)
        self.assertEqual(list(out), ["haapamaki-haapamaki"])
        (row,) = out["haapamaki-haapamaki"]
        self.assertEqual((row["start"], row["price"], row["lang"], row["len"], row["rating"]),
                         ("2026-10-02T19:00:00+03:00", "11€", "EN-A, FI-S, SV-S", "101", "K-12"))
        self.assertEqual(row["url"], "https://haapamaenelokuvat.fi/salikartta?id=53382")
        self.assertEqual(row["aud"], "")


class NiagaraTemplateTest(Stubbed):

    def rows(self, page=NIAGARA_FILM):
        e = load()
        return e.parse_movie(page, site("niagara"), "/elokuvat/70/the-invite")

    def fetch(self, film=NIAGARA_FILM):
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/70/the-invite"),
                       "/elokuvat/70/the-invite": film})
        return e.fetch_site(site("niagara"), sleep=0)

    def test_the_items_parse_with_the_newline_before_class(self):
        rows, _ = self.rows()
        self.assertEqual(len(rows), 6)           # three screenings, rendered twice
        self.assertEqual([r["start"] for r in rows[:3]],
                         ["2026-09-03T16:15:00+03:00", "2026-09-03T18:45:00+03:00",
                          "2026-11-05T12:00:00+02:00"])

    def test_finnish_time_zone_follows_the_date(self):
        """September is +03:00, November +02:00: the offset is computed, not pasted."""
        rows, _ = self.rows()
        self.assertTrue(rows[0]["start"].endswith("+03:00"))
        self.assertTrue(rows[2]["start"].endswith("+02:00"))

    def test_responsive_duplicates_collapse_to_one_show_each(self):
        out = self.fetch()
        shows = out["cn-tampere"]
        self.assertEqual(len(shows), 3)
        self.assertEqual(len({s["url"] for s in shows}), 3)

    def test_the_same_id_repeated_is_one_show_even_in_one_wrapper(self):
        page = niagara_page(niagara_item("3.9.2026", "16.15", 1) * 3, twice=False)
        self.assertEqual(len(self.fetch(page)["cn-tampere"]), 1)

    def test_prices_stay_with_their_screening(self):
        shows = self.fetch()["cn-tampere"]
        self.assertEqual([s["price"] for s in shows], ["13€", "11€", "8€"])

    def test_a_bare_whole_amount_keeps_its_zero(self):
        """Stripping zeros from "10" published a 10-euro ticket as 1 euro. Only a decimal
        amount loses its trailing zeros."""
        prices = ("10", "20", "10,00", "12,50", "10.00")
        items = "".join(niagara_item("3.9.2026", f"1{i}.00", 50 + i, price=p)
                        for i, p in enumerate(prices))
        rows, _ = self.rows(niagara_page(items, twice=False))
        self.assertEqual([r["price"] for r in rows], ["10€", "20€", "10€", "12.5€", "10€"])

    def test_seats_derive_sold_out_and_nothing_else(self):
        shows = self.fetch()["cn-tampere"]
        self.assertEqual([s["soldOut"] for s in shows], [False, True, False])
        for s in shows:
            with self.subTest(url=s["url"]):
                self.assertNotIn("free", s)
                self.assertNotIn("seats", s)
                self.assertNotIn("127", json.dumps(s))

    def test_tags_become_method_decoded_and_deduplicated(self):
        shows = self.fetch()["cn-tampere"]
        self.assertEqual([s["method"] for s in shows], ["", "Seniorikino · Q&A", "Seniorikino"])

    def test_the_venue_is_matched_by_the_items_place_class(self):
        rows, _ = self.rows()
        self.assertEqual(rows[0]["theatre_raw"], "tampere")
        self.assertEqual(rows[0]["aud"], "")
        out = self.fetch()
        self.assertEqual(list(out), ["cn-tampere"])
        self.assertEqual(out["cn-tampere"][0]["theatre"], "Cinema Niagara")

    def test_the_ticket_href_is_the_outbound_link_and_is_never_fetched(self):
        """stub_get raises on any /salikartta request, so reaching the assertion at all
        proves the adapter published the href without following it."""
        shows = self.fetch()["cn-tampere"]
        self.assertEqual(shows[0]["url"], "https://cinemaniagara.fi/salikartta?id=53882")

    def test_metadata_without_colons_and_the_genre_label(self):
        _, meta = self.rows()
        self.assertEqual(meta["title"], "The Invite")
        self.assertEqual(meta["rating"], "K-12")
        self.assertEqual(meta["len"], "108")
        self.assertEqual(meta["img"], "https://cdn.example/niagara/poster/the-invite_1.webp")
        self.assertEqual(meta["lang"], "EN-A, ES-A, FI-S, SV-S")
        self.assertEqual(meta["genres"], "Draama, Komedia")
        self.assertEqual(meta["syn"], "Joen ja Angelan avioliitto on veitsenterällä.")

    def test_credits_are_not_published(self):
        show = self.fetch()["cn-tampere"][0]
        self.assertNotIn("Olivia Wilde", json.dumps(show, ensure_ascii=False))

    def test_whitespace_and_trailing_class_variants_parse(self):
        openers = ['<div class="item tampere date-6.9.2026">',
                   '<div class="item tampere date-6.9.2026 name-The-Invite">',
                   '<div\n\t\tclass="item tampere date-6.9.2026">',
                   '<div\n   class="item tampere date-6.9.2026 name-x">']
        for i, op in enumerate(openers):
            with self.subTest(opener=op):
                rows, _ = self.rows(niagara_page(niagara_item("6.9.2026", "10.00", 100 + i, opener=op), twice=False))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["start"], "2026-09-06T10:00:00+03:00")
                self.assertEqual(rows[0]["theatre_raw"], "tampere")

    def test_missing_or_malformed_optional_fields(self):
        item = niagara_item("6.9.2026", "10.00", 7, price="", seats="")
        item = item.replace("</a>\n</div>", '</a>\n<div class="seats-info">Paikkoja vapaana: n/a</div></div>')
        page = niagara_page(item, twice=False).replace(
            '<img class="poster-img" src="https://cdn.example/niagara/poster/the-invite_1.webp?w=250" alt="The Invite">', "")
        rows, meta = self.rows(page)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["price"], rows[0]["free"], rows[0]["method"]), ("", None, ""))
        self.assertEqual(meta["img"], "")
        show = self.fetch(page)["cn-tampere"][0]
        self.assertFalse(show["soldOut"])
        self.assertEqual(show["img"], "")

    def test_an_item_without_a_time_is_skipped_not_invented(self):
        item = niagara_item("6.9.2026", "10.00", 7).replace("<span>10.00</span>", "")
        rows, _ = self.rows(niagara_page(item, twice=False))
        self.assertEqual(rows, [])


class NoScreeningIdFallbackTest(Stubbed):
    """A row without a ticket href has no public screening id. It is keyed on film,
    start, place and auditorium together, and recorded only once a venue took it."""

    @staticmethod
    def kotka_item(date, hhmm, place, sid=None):
        link = (f'<a class="button-screening" href="/salikartta?id={sid}">Osta</a>'
                if sid else "<span>Liput ovelta</span>")
        return (f'<div class="item kotka date-{date}"> <div> <p> <strong><span>KE 2.9. klo '
                f"{hhmm}</span></strong> </p> <p> {place}<br /> Lippu 10,00&euro;<br /> "
                f"Vapaat paikat 5/50 </p> </div> <div> {link} </div> </div>\n")

    def kotka(self, items):
        page = ("<main><h1>Film</h1><div class=\"screenings\">" + HIDDEN + items
                + "</div>\n</div>\n</div></main>")
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/1/film"),
                       "/elokuvat/1/film": page})
        return e.fetch_site(site("kotkanleffat"), sleep=0)

    def test_the_same_no_id_screening_repeated_by_markup_is_one_show(self):
        item = niagara_item("3.9.2026", "16.15", 0).replace(
            '<a class="button-screening" href="/salikartta?id=0">\n  Osta liput\n</a>', "")
        self.assertNotIn("salikartta", item)
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/70/the-invite"),
                       "/elokuvat/70/the-invite": niagara_page(item, twice=True)})
        shows = e.fetch_site(site("niagara"), sleep=0)["cn-tampere"]
        self.assertEqual(len(shows), 1)
        self.assertEqual(shows[0]["url"], "https://cinemaniagara.fi/elokuvat/70/the-invite")

    def test_two_venues_at_the_same_minute_stay_two_shows(self):
        out = self.kotka(self.kotka_item("2.9.2026", "20.00", "KINOPALATSI")
                         + self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 2"))
        self.assertEqual(sorted(out), ["kl-kinopalatsi", "kl-trio123"])
        self.assertEqual(out["kl-kinopalatsi"][0]["start"], out["kl-trio123"][0]["start"])

    def test_two_auditoriums_at_the_same_minute_stay_two_shows(self):
        out = self.kotka(self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 1")
                         + self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 2"))
        self.assertEqual(sorted(s["aud"] for s in out["kl-trio123"]), ["SALI 1", "SALI 2"])

    def test_the_same_hall_repeated_without_an_id_is_still_one_show(self):
        out = self.kotka(self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 2") * 2)
        self.assertEqual(len(out["kl-trio123"]), 1)

    def test_a_malformed_copy_that_matches_no_venue_does_not_suppress_the_valid_one(self):
        """Same public id twice; the first copy names a place no venue owns. Recording
        the key before the venue match would publish nothing for this screening."""
        out = self.kotka(self.kotka_item("2.9.2026", "20.00", "VARASTO", sid=9)
                         + self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 2", sid=9))
        self.assertEqual(len(out["kl-trio123"]), 1)
        self.assertEqual(out["kl-trio123"][0]["url"], "https://kotkanleffat.fi/salikartta?id=9")

    def test_the_public_id_wins_over_the_composite(self):
        """Two rows, one id, same hall, different printed minute -- the platform's id is
        the identity, so one show."""
        out = self.kotka(self.kotka_item("2.9.2026", "20.00", "TRIO 123 | SALI 2", sid=9)
                         + self.kotka_item("2.9.2026", "20.05", "TRIO 123 | SALI 2", sid=9))
        self.assertEqual(len(out["kl-trio123"]), 1)


class LanguageNamesTest(unittest.TestCase):

    def test_names_resolve_in_source_order_without_repeats(self):
        e = load()
        self.assertEqual(e.lang_codes("Suomi ja ruotsi"), ["FI", "SV"])
        self.assertEqual(e.lang_codes("englanti, espanja"), ["EN", "ES"])
        self.assertEqual(e.lang_codes("suom./ruots."), ["FI", "SV"])
        self.assertEqual(e.lang_codes("englanniksi, englanti"), ["EN"])
        self.assertEqual(e.lang_codes("Alkuperäinen"), [])
        self.assertEqual(e.lang_codes(""), [])
        self.assertEqual(e.lang_codes(None), [])

    def test_every_client_language_has_a_finnish_name_here(self):
        """The map is the inverse of the client's LN.fi, so a code it produces is one the
        app can name."""
        e = load()
        client = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
        block = re.search(r"const LN = \{(.*?)\n  \};", client, re.S).group(1)
        fi = dict(re.findall(r"([A-Z]{2}):'([^']*)'", re.search(r"\bfi:\{(.*?)\}", block, re.S).group(1)))
        self.assertEqual({v: k for k, v in fi.items()}, e.LANG_NAMES)


# --- the zero-show rule, both directions ----------------------------------------------------

class ZeroShowsTest(Stubbed):

    def test_a_listing_with_films_whose_pages_render_no_items_yields_nothing(self):
        """The failure case: fetch_site returns no venue at all, and run.py fails a site
        with no shows. It must not look like an empty programme."""
        e = self.stub({"/elokuvat/ohjelmistossa": LISTING,
                       "/elokuvat/70/the-invite": FOREIGN_FILM,
                       "/elokuvat/63/the-dog-stars": FOREIGN_FILM})
        self.assertEqual(e.fetch_site(site("niagara"), sleep=0), {})

    def test_that_failure_fails_the_run_and_keeps_the_previous_data(self):
        import run
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        saved = run.OUT
        run.OUT = pathlib.Path(tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", saved))
        # A day ahead of the real clock: a kept file whose every day has passed is
        # published empty, and this is about one still worth keeping.
        ahead = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        prev = {"generated": "2026-08-01T00:00:00+00:00", "dates": [ahead],
                "horizon": ahead,
                "shows": [{"title": "Dyyni", "start": f"{ahead}T18:00:00+03:00"}]}
        (run.OUT / "area-cn-tampere.json").write_text(json.dumps(prev), encoding="utf-8")
        e = self.stub({"/elokuvat/ohjelmistossa": LISTING,
                       "/elokuvat/70/the-invite": FOREIGN_FILM,
                       "/elokuvat/63/the-dog-stars": FOREIGN_FILM})
        no_sleep.patch(self, e)                 # run.main paces the film pages at 1.2 s
        realimp = importlib.import_module
        mod = type("M", (), {"__name__": "fakemod", "SITES": [site("niagara")],
                             "fetch_site": staticmethod(e.fetch_site)})
        importlib.import_module = lambda n: mod if n == "fakemod" else realimp(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", realimp))
        self.assertEqual(run.main(["fakemod", "--half", "all"]), 1)
        after = json.loads((run.OUT / "area-cn-tampere.json").read_text(encoding="utf-8"))
        self.assertEqual(after, prev)

    def test_a_genuinely_empty_programme_is_the_platforms_empty_state(self):
        e = self.stub({"/elokuvat/ohjelmistossa": GENUINELY_EMPTY})
        with self.assertRaises(common.EmptyProgramme):
            e.fetch_site(site("niagara"), sleep=0)


# --- registry, accent, and what never reaches a page ----------------------------------------

class NiagaraRegistryTest(unittest.TestCase):

    def test_registry_and_sites_agree(self):
        import registry
        p = registry.by_id("niagara")
        self.assertEqual((p["label"], p["host"], p["module"], p["book"], p["accent"]),
                         ("Cinema Niagara", "cinemaniagara.fi", "etiketti", "buy", "#6A4FBF"))
        self.assertIn(p["where"], ("cloud", "local"))
        s = site("niagara")
        self.assertEqual([v["id"] for v in s["venues"]], ["cn-tampere"])
        self.assertEqual(s["venues"][0]["city"], "Tampere")
        self.assertEqual(s["base"], "https://cinemaniagara.fi")

    def test_the_venue_id_is_unique_across_adapters(self):
        import registry
        ids = [v["id"] for m in registry.modules()
               for st in importlib.import_module(m).SITES for v in st["venues"]]
        self.assertEqual(ids.count("cn-tampere"), 1)

    def test_the_accent_clears_finnkino_in_tampere_in_every_vision_model(self):
        """Tampere is a two-chain city. The pair must not become the combined-city set's
        binding constraint, so every model is at or above the worst pair of any city view.
        Region rows are measured on the same scale but twelve established pairs sit far
        below, so their minimum would make the first assertion trivial. The second is the
        margin: comfortably above the 3 px rule's floor."""
        import accent_check as A
        import registry
        niagara = registry.by_id("niagara")["accent"]
        finnkino = registry.by_id("finnkino")["accent"]
        pair = A.dE(niagara, finnkino)
        accents = {p["id"]: p["accent"] for p in registry.PROVIDERS}
        city_worst = min(min(A.dE(accents[a], accents[b]))
                         for kind, _, a, b in A.view_pairs() if kind == "city")
        self.assertGreaterEqual(city_worst, A.FLOOR,
                                "the city baseline itself is below the floor")
        for model, value in zip(("normal", "vienot", "machado"), pair):
            with self.subTest(model=model):
                self.assertGreaterEqual(value, city_worst)
                self.assertGreaterEqual(value, 40.0)
        self.assertNotIn(niagara, {v for k, v in accents.items() if k != "niagara"})

    def test_no_availability_state_reaches_a_page_or_its_json_ld(self):
        import build_pages as bp
        today = datetime.date(2026, 9, 3)
        show = {"eventId": "70", "title": "The Invite", "original": "", "len": "108",
                "rating": "K-12", "genres": "Draama, Komedia", "method": "Seniorikino · Q&A",
                "theatre": "Cinema Niagara", "aud": "", "start": "2026-09-03T18:45:00+03:00",
                "url": "https://cinemaniagara.fi/salikartta?id=53955", "img": "",
                "lang": "EN-A, ES-A, FI-S, SV-S", "soldOut": True, "price": "11€",
                "provider": "niagara", "venue": "cn-tampere"}
        days = {today.isoformat(): {"The Invite": [show]}}
        for lang in ("fi", "en"):
            with self.subTest(lang=lang):
                html = bp.page(
                    lang=lang, paths={"fi": "/teatteri/x/", "sv": "/sv/teatteri/x/",
                          "en": "/en/theatre/x/"},
                    title="X", desc="d", h1="h", sub="s", intro="i", days=days, today=today,
                    t=bp.L[lang], extra={}, gmap={}, city="Tampere", with_venue=False,
                    legend="", also="", og_image="/icon-512.png", app_href="/", area="x",
                    chain_css="", kind="theatre")
                low = html.lower()
                for word in ("soldout", "sold out", "loppuunmyyty", "availability",
                             "paikkoja", "vapaana", "seats"):
                    self.assertNotIn(word, low, word)
                self.assertIn("salikartta?id=53955", html)
                self.assertIn("11", html)


class EscapedMarkupTest(unittest.TestCase):
    """Star's descriptions, read 2026-10-04, carry markup escaped: "&lt;b&gt;...&lt;/b&gt;"
    and "&lt;p&gt;" lines. Unescaped, it was published as literal tags in the synopsis."""

    def syn(self, desc):
        page = ('<main><h1>DIGGER</h1><div class="description-container"><span>' + desc
                + "</span></div></main>")
        return load().parse_movie(page, site("star"), "/elokuvat/1/x")[1]["syn"]

    def test_escaped_tags_leave_the_text(self):
        desc = ("&lt;b&gt;Neulekinossa salin valot pysyv\u00e4t himme\u00e4ll\u00e4.&lt;/b&gt;<br />\r\n"
                "&lt;p&gt;<br />\r\n&lt;p&gt;<br />\r\nMies. Suunnitelma. T\u00e4ydellinen romahdus.")
        self.assertEqual(self.syn(desc), "Neulekinossa salin valot pysyv\u00e4t himme\u00e4ll\u00e4. "
                                         "Mies. Suunnitelma. T\u00e4ydellinen romahdus.")

    def test_an_escaped_ampersand_and_a_lone_angle_stay_text(self):
        self.assertEqual(self.syn("Kätyrit &amp; Monsterit, 3 &lt; 4."),
                         "Kätyrit & Monsterit, 3 < 4.")


class HouseFactsTest(unittest.TestCase):
    """K-Kino's Pirjo i Sverige \u2013 Vauvakino, read 2026-10-04: synopsis, then a "Tiedot"
    block of runtime, age limit, ticket sales, snacks and house rules."""

    TAIL = ("<br />\r\n<br />\r\nTiedot<br />\r\n<br />\r\nKesto: 1 t 28 min<br />\r\n"
            "Ik\u00e4raja: S<br />\r\n<br />\r\nLiput<br />\r\n<br />\r\nV\u00e4lt\u00e4 jonotus! "
            "Ennakkoliput verkkokaupasta www.k-kino.fi.<br />\r\n<br />\r\nLiput ovelta: 30 min "
            "ennen n\u00e4yt\u00f6st\u00e4.<br />\r\n<br />\r\nLeffaherkut<br />\r\n<br />\r\n"
            "K-Kinoon saa tuoda mukana maltilliset omat ev\u00e4\u00e4t.")

    def syn(self, desc):
        page = ('<main><h1>PIRJO</h1><div class="description-container"><span>' + desc
                + "</span></div></main>")
        return load().parse_movie(page, site("kkino"), "/elokuvat/26/x")[1]["syn"]

    def test_the_facts_block_is_not_the_synopsis(self):
        body = ("Kun Pirjo Heikkil\u00e4 nolaa itsens\u00e4 julkisesti, h\u00e4n l\u00e4htee "
                "Ruotsiin.<br />\r\n<br />\r\nPirjo i Sverige on l\u00e4mminhenkinen komedia.")
        self.assertEqual(self.syn(body + self.TAIL),
                         "Kun Pirjo Heikkil\u00e4 nolaa itsens\u00e4 julkisesti, h\u00e4n l\u00e4htee "
                         "Ruotsiin. Pirjo i Sverige on l\u00e4mminhenkinen komedia.")

    def test_the_word_alone_or_without_a_runtime_after_it_stays(self):
        for desc in ("Tiedot<br />\r\nKuka tiet\u00e4\u00e4 totuuden?",
                     "Tiedot ja taidot ratkaisevat kilpailun.<br />\r\nKesto: 1 t 28 min"):
            with self.subTest(desc=desc[:20]):
                self.assertEqual(self.syn(desc), load()._txt(desc.replace("<br />", " ")))


class NoSubtitlesTest(unittest.TestCase):
    """"Tekstitys: Ei tekstitystä" publishes `XX-S`, the shapes read 2026-10-04: Kinopirtti's
    Rakkautta ja virtahepoja beside "Kieli: Suomi", Leffabuumi's beside "Kieli:
    Alkuperäinen". Niagara and Star print it where it cannot hold and are not read."""

    def film(self, h1="Rakkautta ja virtahepoja", kieli="Suomi",
             tekstitys="Ei tekstityst\u00e4"):
        rows = ""
        if kieli:
            rows += f'<span class="label">Kieli:</span> {kieli}<br />\n'
        if tekstitys:
            rows += f'<span class="label">Tekstitys:</span> {tekstitys}<br />\n'
        return (f"<main>\n<h1>{h1}</h1>\n" + rows +
                '<h2>N\u00e4yt\u00f6kset</h2>\n<div class="screenings">\n</div>\n</main>')

    def meta(self, pid, **kw):
        return load().parse_movie(self.film(**kw), site(pid), "/elokuvat/1/x")[1]

    def test_the_two_shapes_publish_no_subtitles(self):
        self.assertEqual(self.meta("kinopirtti")["lang"], "FI-A, XX-S")
        self.assertEqual(self.meta("leffabuumi", kieli="Alkuper\u00e4inen")["lang"], "XX-S")

    def test_niagara_and_star_state_nothing_with_it(self):
        for pid in ("niagara", "star"):
            with self.subTest(site=pid):
                self.assertEqual(self.meta(pid)["lang"], "FI-A")
                self.assertEqual(self.meta(pid, kieli="")["lang"], "")

    def test_named_subtitles_and_a_missing_row_are_unchanged(self):
        self.assertEqual(self.meta("kinopirtti", kieli="englanti",
                                   tekstitys="Suomi ja ruotsi")["lang"], "EN-A, FI-S, SV-S")
        self.assertEqual(self.meta("kinopirtti", tekstitys="")["lang"], "FI-A")

    def test_no_subtitles_alone_keeps_a_version_label(self):
        """The audio is unstated, so DUB is still the only record of the version."""
        m = self.meta("leffabuumi", h1="Kojootti vs. ACME DUB", kieli="Alkuper\u00e4inen")
        self.assertEqual(m["title"], "Kojootti vs. ACME DUB")
        m = self.meta("leffabuumi", h1="Kojootti vs. ACME DUB")
        self.assertEqual(m["title"], "Kojootti vs. ACME")


class VersionSuffixTest(unittest.TestCase):
    """Two sites label the audio version in the film-page H1 as well as in the language
    rows, which cost those rows their TMDB match: no search with a trailing ENG or SUB
    reaches the film. The label is dropped only when the page states a language of its
    own, so nothing the suffix carried is lost."""

    def film(self, h1, kieli="englanti", tekstitys="Suomi ja ruotsi"):
        rows = ""
        if kieli:
            rows += f'<span class="label">Kieli:</span> {kieli}<br />\n'
        if tekstitys:
            rows += f'<span class="label">Tekstitys:</span> {tekstitys}<br />\n'
        return (f"<main>\n<h1>{h1}</h1>\n" + rows +
                '<h2>N\u00e4yt\u00f6kset</h2>\n<div class="screenings">\n</div>\n</main>')

    def title_of(self, h1, **kw):
        e = load()
        _, meta = e.parse_movie(self.film(h1, **kw), site("kinopirtti"), "/elokuvat/1/x")
        return meta["title"]

    def test_the_two_published_examples_lose_the_label(self):
        """Bio Rex Kokkola's ENG and Kinopirtti's SUB, the two rows that went unmatched."""
        self.assertEqual(self.title_of("Kojootti vs. ACME ENG"), "Kojootti vs. ACME")
        self.assertEqual(self.title_of("Kojootti vs. ACME SUB"), "Kojootti vs. ACME")

    def test_the_dub_variant_beside_it_loses_it_too(self):
        self.assertEqual(self.title_of("Kojootti vs. ACME DUB"), "Kojootti vs. ACME")

    def test_a_legitimate_title_ending_in_the_same_word_is_untouched(self):
        """The reason this is not a global strip of ambiguous trailing words. "Dub" ends a
        real title as an ordinary capitalised word; only the all-capitals label goes."""
        for real in ("King of Dub", "The Dog Stars", "Kojootti vs. ACME",
                     "Practical Magic: Lumotut sisaret"):
            with self.subTest(title=real):
                self.assertEqual(self.title_of(real), real)

    def test_a_page_that_states_no_language_keeps_its_title(self):
        """The corroboration is the point: with no language row the label is the only
        record of the version, so removing it would lose the fact."""
        self.assertEqual(
            self.title_of("Kojootti vs. ACME ENG", kieli="", tekstitys=""),
            "Kojootti vs. ACME ENG")

    def test_the_language_the_page_states_still_reaches_the_show(self):
        """Dropping the label must not drop what it stood for."""
        e = load()
        _, meta = e.parse_movie(self.film("Kojootti vs. ACME SUB"), site("kinopirtti"),
                                "/elokuvat/1/x")
        self.assertEqual(meta["title"], "Kojootti vs. ACME")
        self.assertIn("EN-A", meta["lang"])
        self.assertIn("FI-S", meta["lang"])

    def test_a_label_alone_is_not_a_title_to_strip(self):
        self.assertEqual(self.title_of("SUB"), "SUB")

    def test_stripping_never_returns_an_empty_title(self):
        """Called on the function, because parse_movie cannot produce these: `_txt` has
        already trimmed the H1. The guard is what stops a title that is nothing but a
        label, however it is spaced, from being emptied by a later caller."""
        e = load()
        for odd in (" SUB", "  ENG", "DUB "):
            with self.subTest(title=odd):
                self.assertEqual(e.strip_version_suffix(odd, "FI-S"), odd)


if __name__ == "__main__":
    unittest.main()
