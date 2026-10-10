"""Kino Kirkkonummi: page-builder markup, published twice, with no year.

The fixtures follow `kinokirkkonummi.fi` as read on 2026-09-15: a film title in
`<p class="elementor-heading-title">` and its screenings in following
`<span class="elementor-icon-list-text">` items, with no semantic class marking either.

Everything the real page does that could corrupt the output is in the fixture: the whole
programme is emitted twice for desktop and mobile, a `tulossa` label sits above several
film titles, one film has only a release line and no screening, and the same list element
carries cast names, a director, a note, a street address and a phone number.
"""
import contextlib
import datetime
import io
import unittest

import _ctx                                                # noqa: F401
import common
import kirkkonummi

BASE = "https://kinokirkkonummi.fi"
TODAY = datetime.date(2026, 9, 15)


def head(text):
    return (f'<div class="elementor-widget-container">'
            f'<p class="elementor-heading-title elementor-size-default">{text}</p></div>')


def item(text):
    return (f'<ul class="elementor-icon-list-items"><li class="elementor-icon-list-item">'
            f'<span class="elementor-icon-list-text">{text}</span></li></ul>')


def facts(*lines):
    """The film's own detail block: `Kesto`, `Ikäraja`, `Liput 14,50`. No semantic class
    on any of them, and the page prints it either side of the screening list."""
    return "".join(f"<div>{l}</div>" for l in lines)


def block():
    """One copy of the programme. The page emits this twice."""
    return "".join([
        head("tulossa"), head("Rakkautta ja virtahepoja"),
        item("Tulossa 25.9. alkaen"),
        item("Pihla Viitala, Aku Sipola, Jenni Vartiainen"),
        head("tulossa"), head("Myrskyn Ikkuna"),
        item("Andrew Scott, Brendan Fraser, Kerry Condon"),
        facts("Kesto 1h 40min", "Ikäraja 12", "Liput 14,50"),
        item("20.9. Sunnuntai klo18.00"),
        item("22.9. Tiistai klo19.00"),
        head("Päivien Lumo"),
        item("Ohjaus Karin Pennanen"),
        # The other order: this film states its price after the screening list.
        item("21.9. Maanantai klo19.00"),
        facts("Kesto 1h 28min", "Liput 14,50"),
        item("vain tämä näytös"),
        head("HETKI ENNEN VALOA"),
        item("Ohjaus Klaus Härö"),
        facts("Kesto 1h 27min Ikäraja 7", "Liput 15,50"),
        item("14.9. Maanantai klo19.00"),
        item("16.9. Keskiviikko klo19.00"),
    ])


def page(body=None, twice=True):
    inner = block() if body is None else body
    return ("<html><body>" + head("Elokuvateatteri") + inner + (inner if twice else "") +
            head("112 paikkaa") + item("Munkinmäentie 17") + item("041 7428871") +
            "</body></html>")


LISTING = page()


class ProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.shows = kirkkonummi.parse(LISTING, today=TODAY)

    def test_the_duplicated_desktop_and_mobile_copies_publish_one_set(self):
        """The page emits the whole programme twice. Five screenings, not ten."""
        self.assertEqual(len(self.shows), 5)
        self.assertEqual(len({(s["eventId"], s["start"]) for s in self.shows}), 5)

    def test_each_screening_belongs_to_the_heading_above_it(self):
        by = {}
        for s in self.shows:
            by.setdefault(s["title"], []).append(s["start"][:10])
        self.assertEqual(sorted(by["Myrskyn Ikkuna"]), ["2026-09-20", "2026-09-22"])
        self.assertEqual(sorted(by["HETKI ENNEN VALOA"]), ["2026-09-14", "2026-09-16"])
        self.assertEqual(by["Päivien Lumo"], ["2026-09-21"])

    def test_a_release_line_with_no_time_is_not_a_screening(self):
        """"Tulossa 25.9. alkaen" names a day and a month and no time. The film has no
        other row, so it publishes nothing at all."""
        self.assertNotIn("Rakkautta ja virtahepoja", {s["title"] for s in self.shows})
        self.assertNotIn("2026-09-25", {s["start"][:10] for s in self.shows})

    def test_the_tulossa_label_never_becomes_a_film(self):
        """It sits above a title, in the same element the titles use."""
        self.assertNotIn("tulossa", {s["title"].lower() for s in self.shows})

    def test_cast_directors_notes_and_the_address_are_not_screenings(self):
        titles = {s["title"] for s in self.shows}
        for junk in ("Ohjaus Klaus Härö", "vain tämä näytös", "Munkinmäentie 17",
                     "041 7428871", "112 paikkaa", "Elokuvateatteri"):
            self.assertNotIn(junk, titles)

    def test_the_time_is_read_without_a_space_after_klo(self):
        self.assertEqual(sorted(s["start"][11:16] for s in self.shows)[0], "18:00")

    def test_no_auditorium_is_invented(self):
        """The page names two seat counts and never says which screening uses which."""
        self.assertEqual({s["aud"] for s in self.shows}, {""})

    def test_every_showtime_opens_the_programme_page(self):
        for s in self.shows:
            self.assertEqual(s["url"], BASE + "/")

    def test_every_show_meets_the_contract(self):
        common.check_shows({kirkkonummi.VENUE["id"]: self.shows}, "kirkkonummi",
                           {kirkkonummi.VENUE["id"]})


class YearTest(unittest.TestCase):
    def _weekday_case(self, wd, want):
        """Parse `15.9. wd klo19.00` beside a placed `16.9.` row; `want` is the date, or
        None for a row the bound refuses, which leaves only the `16.9.` row."""
        body = page(head("A") + item(f"15.9. {wd} klo19.00") +
                    item("16.9. Keskiviikko klo20.00"), twice=False)
        out = kirkkonummi.parse(body, today=TODAY)
        got = [s["start"][:10] for s in out if s["start"][11:16] == "19:00"]
        self.assertEqual(got, [want] if want else [], wd)
        self.assertEqual(out[-1]["start"][:16], "2026-09-16T20:00", wd)

    def test_a_weekday_that_would_place_a_row_a_year_out_is_refused(self):
        """15.9. is a Monday in 2025, a Tuesday in 2026 and a Wednesday in 2027. Read on
        2026-09-15 only the Tuesday is inside the plausibility bound; the other two are a
        year away, which is what a mistyped weekday produces."""
        self._weekday_case("Tiistai", "2026-09-15")
        for wd in ("Maanantai", "Keskiviikko"):
            self._weekday_case(wd, None)


    def test_a_weekday_no_candidate_year_can_satisfy_is_skipped(self):
        out = kirkkonummi.parse(
            page(head("A") + item("15.9. Torstai klo19.00") +
                 item("15.9. Tiistai klo20.00"), twice=False), today=TODAY)
        self.assertEqual([s["start"][11:16] for s in out], ["20:00"])

    def test_a_december_row_read_in_january_stays_in_the_past(self):
        out = kirkkonummi.parse(page(head("A") + item("28.12. Sunnuntai klo19.00"),
                                     twice=False), today=datetime.date(2026, 1, 2))
        self.assertEqual(out[0]["start"][:10], "2025-12-28")

    def test_a_january_row_read_in_december_rolls_forward(self):
        out = kirkkonummi.parse(page(head("A") + item("5.1. Tiistai klo19.00"),
                                     twice=False), today=datetime.date(2026, 12, 28))
        self.assertEqual(out[0]["start"][:10], "2027-01-05")


class EmptyAndBrokenTest(unittest.TestCase):
    def test_rows_in_a_format_the_parser_misses_are_a_failure(self):
        """A year printed after the month, `20.9.2026 Sunnuntai`, does not match `SHOW_RE`.
        Every film heading is still there, so this is a format change and must fail."""
        body = block().replace(".9. ", ".9.2026 ")
        self.assertNotEqual(body, block())
        with self.assertRaises(RuntimeError) as cm:
            kirkkonummi.parse(page(body), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_films_with_no_screening_row_is_a_failure(self):
        """No empty state is recorded for this site, and a page listing films is not one,
        so zero rows fails rather than being read as nothing on."""
        with self.assertRaises(RuntimeError) as cm:
            kirkkonummi.parse(page(head("Rakkautta ja virtahepoja") +
                                   item("Tulossa 25.9. alkaen") + head("Myrskyn Ikkuna") +
                                   item("Andrew Scott, Brendan Fraser, Kerry Condon"),
                                   twice=False), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_page_without_an_icon_list_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            kirkkonummi.parse("<html><body><p>Tervetuloa</p></body></html>", today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_the_failure_states_what_was_served(self):
        """This site failed that way on 2026-09-16 and served its real programme, icon
        list included, to an ordinary connection minutes later. What came back is the
        evidence that separates the two, and no log carried it."""
        with self.assertRaises(RuntimeError) as cm:
            kirkkonummi.parse("<html><head><title>Just a moment...</title></head></html>",
                              today=TODAY)
        self.assertIn('titled "Just a moment..."', str(cm.exception))

    def test_a_screening_before_any_heading_is_ignored(self):
        out = kirkkonummi.parse(page(item("20.9. Sunnuntai klo18.00") + head("A") +
                                     item("21.9. Maanantai klo19.00"), twice=False),
                                today=TODAY)
        self.assertEqual([(s["title"], s["start"][:10]) for s in out], [("A", "2026-09-21")])


class SiteTest(unittest.TestCase):
    def test_one_venue_in_kirkkonummi(self):
        self.assertEqual([v["city"] for v in kirkkonummi.SITES[0]["venues"]],
                         ["Kirkkonummi"])


class PriceTest(unittest.TestCase):
    """Each film's block states its own price, in the page the adapter already fetches.

    Per film and not per cinema: 14,50 and 15,50 both appear on the page read 2026-09-16,
    so a single house price would be wrong for part of the programme. No extra request.
    """

    def setUp(self):
        self.shows = kirkkonummi.parse(page(), TODAY)
        self.by_title = {}
        for s in self.shows:
            self.by_title.setdefault(s["title"], set()).add(s["price"])

    def test_each_film_carries_the_price_its_own_block_states(self):
        self.assertEqual(self.by_title["Myrskyn Ikkuna"], {"14.5\u20ac"})
        self.assertEqual(self.by_title["HETKI ENNEN VALOA"], {"15.5\u20ac"})

    def test_a_price_after_the_screening_list_belongs_to_the_same_film(self):
        """The block prints the two in either order, so position relative to the list
        cannot be what ties them together."""
        self.assertEqual(self.by_title["Päivien Lumo"], {"14.5\u20ac"})

    def test_every_screening_of_a_film_carries_it(self):
        for title, prices in self.by_title.items():
            with self.subTest(title=title):
                self.assertEqual(len(prices), 1)

    def test_a_film_whose_block_states_none_publishes_none(self):
        """There is no house price to fall back on, and inventing one from the film beside
        it is how a reader is told the wrong amount."""
        body = (head("Ei Hintaa") + item("Ohjaus Joku") +
                item("20.9. Sunnuntai klo18.00") +
                head("HETKI ENNEN VALOA") + facts("Liput 15,50") +
                item("21.9. Maanantai klo19.00"))
        shows = kirkkonummi.parse(page(body), TODAY)
        got = {s["title"]: s["price"] for s in shows}
        self.assertEqual(got["Ei Hintaa"], "")
        self.assertEqual(got["HETKI ENNEN VALOA"], "15.5\u20ac")

    def test_two_different_amounts_under_one_heading_publish_neither(self):
        """The association is what is in doubt, so taking the first would publish an
        amount whose applicability to this film is exactly what is unestablished."""
        body = (head("Yksi") + facts("Liput 12,00") +
                item("Liput 99,00 ei tarkoita tätä") +
                item("20.9. Sunnuntai klo18.00"))
        shows = kirkkonummi.parse(page(body), TODAY)
        self.assertEqual({s["price"] for s in shows}, {""})

    def test_the_same_amount_twice_is_not_ambiguous(self):
        """Which is what the page produces for every real film: it emits the whole
        programme twice, so each price is found once per copy."""
        body = head("Yksi") + facts("Liput 12,00") + item("20.9. Sunnuntai klo18.00")
        self.assertEqual({s["price"] for s in kirkkonummi.parse(page(body), TODAY)},
                         {"12\u20ac"})

    def test_a_price_above_every_film_title_is_not_attached_to_one(self):
        """`prices_by_title` needs a film heading before it; a price in the page's own
        furniture belongs to no film. One copy of the programme here, because the page
        emits two and a stray price in the second falls after the first copy's last
        heading -- which is the limitation the function's docstring states."""
        body = (facts("Liput 9,00") + head("Yksi") +
                item("20.9. Sunnuntai klo18.00"))
        shows = kirkkonummi.parse(page(body, twice=False), TODAY)
        self.assertEqual({s["price"] for s in shows}, {""})

    def test_a_price_under_a_tulossa_label_belongs_to_no_film(self):
        """`tulossa` sits above a coming film's title. A price between the label and that
        title is under neither: attaching it to the film *above* the label would put one
        film's amount on another's screenings, which is worse than publishing none."""
        body = (head("Yksi") + item("20.9. Sunnuntai klo18.00") +
                head("tulossa") + facts("Liput 9,00") +
                head("Kaksi") + item("21.9. Maanantai klo19.00"))
        got = {s["title"]: s["price"] for s in kirkkonummi.parse(page(body, twice=False),
                                                                TODAY)}
        self.assertEqual(got, {"Yksi": "", "Kaksi": ""})

    def test_the_cents_are_dropped_only_when_they_are_zero(self):
        self.assertEqual(kirkkonummi.prices_by_title(
            head("A") + facts("Liput 14,00")), {"A": "14\u20ac"})
        self.assertEqual(kirkkonummi.prices_by_title(
            head("A") + facts("Liput 14,50")), {"A": "14.5\u20ac"})

    def test_every_show_still_meets_the_contract(self):
        common.check_shows({kirkkonummi.VENUE["id"]: self.shows}, "kirkkonummi",
                           {kirkkonummi.VENUE["id"]})



class RangeRowTest(unittest.TestCase):
    """`26-27.9. La,Su klo17.00` is two screenings. Read 2026-09-27: three of Rakkautta ja
    virtahepoja's five rows were ranges, and all three were dropped without a word."""

    def parse(self, *rows):
        body = head("Rakkautta ja virtahepoja") + "".join(item(r) for r in rows)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            shows = kirkkonummi.parse(page(body), TODAY)
        return [s["start"][:16] for s in shows], out.getvalue()

    def test_a_range_is_one_screening_per_day(self):
        starts, _ = self.parse("26-27.9. La,Su klo17.00", "28-29.9. Ma,Ti klo18.30",
                               "30.9. Ke klo18.30")
        self.assertEqual(starts, ["2026-09-26T17:00", "2026-09-27T17:00", "2026-09-28T18:30",
                                  "2026-09-29T18:30", "2026-09-30T18:30"])

    def test_a_range_without_a_weekday_for_each_day_settles_nothing(self):
        starts, log = self.parse("26-28.9. La,Su klo17.00", "30.9. Ke klo18.30")
        self.assertEqual(starts, ["2026-09-30T18:30"])
        self.assertIn("1 row(s) with a time in a shape this parser does not read", log)

    def test_a_wrong_weekday_in_a_range_skips_that_day(self):
        starts, log = self.parse("26-27.9. Su,Ma klo17.00", "30.9. Ke klo18.30")
        self.assertEqual(starts, ["2026-09-30T18:30"])
        self.assertIn("whose weekday matches no candidate year, skipped: Su 26.9., Ma 27.9.", log)


class FilmFactsTest(unittest.TestCase):
    """Runtime, age limit and genres from the film's own block, as the price is. The live
    page carried all three on 2026-09-27 and none was published."""

    def facts_of(self, *lines, title="Presidentin kyyditys"):
        body = head(title) + facts(*lines) + item("28.9. Maanantai klo19.00")
        s = kirkkonummi.parse(page(body), TODAY)[0]
        return s["len"], s["rating"], s["genres"], s["price"]

    def test_the_shapes_the_page_prints(self):
        self.assertEqual(self.facts_of('Kesto: <span class="x">87 min</span>', "Liput 15e",
                                       'Genre: <span class="x">komedia, draama</span>',
                                       "<p>Ikäraja 12</p>"),
                         ("87", "K-12", "komedia, draama", "15\u20ac"))
        self.assertEqual(self.facts_of("Kesto 1h 27min&nbsp; Ikäraja 7"), ("87", "K-7", "", ""))
        self.assertEqual(self.facts_of("Kesto 2h 9min", "ikäraja 12")[:2], ("129", "K-12"))
        self.assertEqual(self.facts_of("Kesto 2h")[0], "120")

    def test_a_class_that_is_not_a_legal_one_is_no_rating(self):
        self.assertEqual(self.facts_of("Ikäraja 13")[1], "")

    def test_a_bare_number_after_liput_is_no_price(self):
        self.assertEqual(self.facts_of("Liput 2 kpl")[3], "")

    def test_a_film_with_no_facts_publishes_none(self):
        self.assertEqual(self.facts_of(), ("", "", "", ""))

    def test_the_kieli_line_is_the_spoken_language(self):
        """La Grazia, read 2026-10-04: `Kieli: <span>Italia</span>` beside Genre."""
        def lang_of(*lines):
            body = head("La Grazia") + facts(*lines) + item("28.9. Maanantai klo19.00")
            return kirkkonummi.parse(page(body), TODAY)[0]["lang"]
        self.assertEqual(lang_of('Kieli: <span class="x">Italia</span>'), "IT-A")
        self.assertEqual(lang_of('Kieli: <span class="x">englanti, ranska</span>'), "EN-A, FR-A")
        self.assertEqual(lang_of('Kieli: <span class="x">Alkuperäinen</span>'), "")
        self.assertEqual(lang_of(), "")

if __name__ == "__main__":
    unittest.main()
