"""Kuvakukko and Kino Manttu: two venues on one page, no year, a stale weekend.

The fixtures follow `kuvakukko.fi/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/` as read
on 2026-09-15: an `<h2>` per cinema, then one `<p class="wp-block-paragraph">` per day
opening with a weekday and a date, holding `<br>`-separated `Klo 13:` rows.

Both cinemas are in every fixture, because the boundary between them is the only thing
stopping Nilsiä's weekend being filed under Kuopio, and nothing downstream would catch
that. Manttu's section is deliberately dated before the others: it publishes every other
weekend and its schedule is routinely already past, which is correct output and not
staleness to repair.
"""
import datetime
import io
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import common
import kuvakukko

BASE = "https://www.kuvakukko.fi"
LIST = kuvakukko.LISTING
TODAY = datetime.date(2026, 9, 15)


def row(time_, title, href=None):
    if href is None:
        return f"Klo {time_}: {title}"
    return f'Klo {time_}: <a href="{href}" data-type="page" data-id="2698">{title}</a>'


def day(heading, *rows):
    return f'<p class="wp-block-paragraph">{heading}<br>' + "<br>".join(rows) + "</p>"


def info(text):
    """The same element type carries addresses and prices; it must not become a day."""
    return f'<p class="wp-block-paragraph">{text}</p>'


def page(kuopio_days=(), nilsia_days=(), extra=""):
    return ("<html><body><div class='entry__content'>"
            '<h2 class="wp-block-heading">Kino Kuvakukon esitysaikataulu</h2>'
            + "".join(kuopio_days) + info("Kino Kuvakukko Vuorikatu 27, 70100 KUOPIO") +
            '<h2 class="wp-block-heading">Nilsiän Kino Mantun esitysaikataulu</h2>'
            + "".join(nilsia_days)
            + info("<strong>Kino Mantun liput:</strong> 11 € / 9 €. Ei ennakkovarauksia.")
            # An info line that mentions a date mid-sentence. Anchoring the day pattern to
            # the start of the paragraph is what keeps this out; searching anywhere in it
            # would turn a closure notice into a day of screenings.
            + info("Teatteri on suljettu lauantai 20.6. Klo 18: alkaneet n&auml;yt&ouml;kset "
                   "siirtyv&auml;t syksyyn.")
            + extra + "</div></body></html>")


LISTING_PAGE = page(
    kuopio_days=[
        day("Tiistai 15.9.",
            row("13", "Hopeatähti-sarja: Laula minulle Arja",
                "https://isak.fi/hopeatahti-elokuvasarja/"),
            row("17.30", "Hetki ennen valoa", f"{BASE}/ohjelmisto/tulossa-hetki/"),
            row("19.30", "Presidentin kyyditys", f"{BASE}/ohjelmisto/tulossa-pk/")),
        day("Keskiviikko 16.9.",
            row("13", "Keltaiset kirjeet", f"{BASE}/ohjelmisto/blue-heron/")),
    ],
    # Manttu's weekend, already past on the 15th.
    nilsia_days=[
        day("Perjantai 11.9.",
            row("17.15", "Presidentin kyyditys", f"{BASE}/ohjelmisto/manttu-pk/"),
            row("19", "Hetki ennen valoa", f"{BASE}/ohjelmisto/manttu-hev/")),
        day("Lauantai 12.9.",
            row("13", "Marsupilami (dub)", f"{BASE}/ohjelmisto/manttu-mars/")),
    ],
)


class TwoVenuesTest(unittest.TestCase):
    def setUp(self):
        self.per = kuvakukko.parse(LISTING_PAGE, today=TODAY)

    def test_each_heading_owns_the_days_under_it(self):
        """The error this prevents: Nilsiä's weekend filed under Kuopio."""
        self.assertEqual(len(self.per["kk-kuopio"]), 4)
        self.assertEqual(len(self.per["kk-nilsia"]), 3)
        self.assertEqual({s["start"][:10] for s in self.per["kk-kuopio"]},
                         {"2026-09-15", "2026-09-16"})
        self.assertEqual({s["start"][:10] for s in self.per["kk-nilsia"]},
                         {"2026-09-11", "2026-09-12"})

    def test_each_show_names_its_own_venue_and_theatre(self):
        for s in self.per["kk-kuopio"]:
            self.assertEqual((s["venue"], s["theatre"]), ("kk-kuopio", "Kino Kuvakukko"))
        for s in self.per["kk-nilsia"]:
            self.assertEqual((s["venue"], s["theatre"]), ("kk-nilsia", "Kino Manttu"))

    def test_an_info_paragraph_is_not_a_day(self):
        """Addresses and price lists use the same element. They open with no weekday, so
        they never become screenings and no exclusion list is needed."""
        titles = [s["title"] for v in self.per.values() for s in v]
        self.assertNotIn("Kino Kuvakukko Vuorikatu 27, 70100 KUOPIO", titles)
        self.assertFalse([t for t in titles if "liput" in t.lower()])

    def test_a_closure_notice_naming_a_date_and_a_time_is_not_a_day(self):
        """"Teatteri on suljettu lauantai 20.6. Klo 18: ..." carries a weekday, a date and
        something shaped exactly like a screening row. The day pattern is anchored to the
        start of the paragraph for this reason: matching it anywhere in the text would
        publish a screening on a day the cinema said it was closed."""
        starts = {s["start"][:10] for v in self.per.values() for s in v}
        self.assertNotIn("2026-06-20", starts)
        self.assertEqual(starts, {"2026-09-11", "2026-09-12", "2026-09-15", "2026-09-16"})

    def test_the_time_is_read_both_ways_it_is_written(self):
        times = sorted(s["start"][11:16] for s in self.per["kk-kuopio"])
        self.assertIn("13:00", times)      # "Klo 13:"
        self.assertIn("17:30", times)      # "Klo 17.30:"

    def test_a_manttu_weekend_that_has_already_passed_stays_in_the_past(self):
        """It publishes every other weekend, so a past schedule is the normal state. The
        weekday places it; nothing shifts a year to make it look current."""
        self.assertEqual(sorted({s["start"][:10] for s in self.per["kk-nilsia"]}),
                         ["2026-09-11", "2026-09-12"])

    def test_the_title_is_published_verbatim_including_a_strand_prefix(self):
        """`run.py` splits the prefixes strands.EVENT_PREFIXES names, centrally. This
        adapter does not invent a split of its own."""
        self.assertIn("Hopeatähti-sarja: Laula minulle Arja",
                      [s["title"] for s in self.per["kk-kuopio"]])

    def test_an_external_link_sends_the_reader_to_the_programme_page(self):
        """The Hopeatähti row links to isak.fi, a third party. A showtime opens this
        cinema's own page instead."""
        by = {s["title"]: s for s in self.per["kk-kuopio"]}
        self.assertEqual(by["Hopeatähti-sarja: Laula minulle Arja"]["url"], LIST)
        self.assertTrue(by["Hetki ennen valoa"]["url"].startswith(BASE))

    def test_every_show_meets_the_contract(self):
        common.check_shows(self.per, "kuvakukko", {v["id"] for v in kuvakukko.VENUES})


class YearTest(unittest.TestCase):
    def _weekday_case(self, wd, want):
        """Parse a one-row page for `wd 15.9.`; `want` is the date, or None for a row the
        bound refuses, which leaves the page with no screening at all."""
        body = page(kuopio_days=[day(f"{wd} 15.9.", row("19", "A"))])
        if want is None:
            with self.assertRaises(RuntimeError, msg=wd) as cm:
                kuvakukko.parse(body, today=TODAY)
            self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
            return
        per = kuvakukko.parse(body, today=TODAY)
        self.assertEqual(per["kk-kuopio"][0]["start"][:10], want, wd)

    def test_a_weekday_that_would_place_a_row_a_year_out_is_refused(self):
        """15.9. is a Monday in 2025, a Tuesday in 2026 and a Wednesday in 2027. Read on
        2026-09-15 only the Tuesday is inside the plausibility bound; the other two are a
        year away, which is what a mistyped weekday produces."""
        self._weekday_case("Tiistai", "2026-09-15")
        for wd in ("Maanantai", "Keskiviikko"):
            self._weekday_case(wd, None)


    def test_a_weekday_no_candidate_year_can_satisfy_drops_the_day(self):
        per = kuvakukko.parse(page(kuopio_days=[day("Torstai 15.9.", row("19", "A")),
                                                day("Tiistai 15.9.", row("20", "B"))]),
                              today=TODAY)
        self.assertEqual([s["title"] for s in per["kk-kuopio"]], ["B"])

    def test_a_december_day_read_in_january_stays_in_the_past(self):
        per = kuvakukko.parse(page(kuopio_days=[day("Sunnuntai 28.12.", row("19", "A"))]),
                              today=datetime.date(2026, 1, 2))
        self.assertEqual(per["kk-kuopio"][0]["start"][:10], "2025-12-28")

    def test_a_january_day_read_in_december_rolls_forward(self):
        per = kuvakukko.parse(page(kuopio_days=[day("Tiistai 5.1.", row("19", "A"))]),
                              today=datetime.date(2026, 12, 28))
        self.assertEqual(per["kk-kuopio"][0]["start"][:10], "2027-01-05")


class EmptyAndBrokenTest(unittest.TestCase):
    def test_one_cinema_between_programmes_is_an_empty_list_not_a_failure(self):
        """Both schedules are on one page, so the read cannot have half-failed: Manttu
        with no days while Kuopio has them is positive evidence it is between
        programmes."""
        per = kuvakukko.parse(page(kuopio_days=[day("Tiistai 15.9.", row("19", "A"))]),
                              today=TODAY)
        self.assertEqual(len(per["kk-kuopio"]), 1)
        self.assertEqual(per["kk-nilsia"], [])

    def test_both_empty_fails_the_site(self):
        """No empty programme has been seen on this page, so both headings with nothing
        under them is not evidence of one."""
        with self.assertRaises(RuntimeError) as cm:
            kuvakukko.parse(page(), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_days_listed_under_both_headings_and_no_row_read_fails_the_site(self):
        """Every day and film still on the page, the colon after each time gone: the
        parse yields nothing while the listing lists films."""
        with self.assertRaises(RuntimeError) as cm:
            kuvakukko.parse(LISTING_PAGE.replace(": <a", " <a"), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_cinema_whose_heading_is_not_read_is_not_published_empty(self):
        """Kuopio parses and Manttu's heading no longer says `esitysaikataulu`, so its
        section is never read. That is not Manttu between programmes."""
        with self.assertRaises(RuntimeError) as cm:
            kuvakukko.parse(LISTING_PAGE.replace("Mantun esitysaikataulu", "Mantun ohjelma"),
                            today=TODAY)
        self.assertIn("Kino Manttu", str(cm.exception))

    def test_a_cinema_whose_days_carry_no_readable_row_is_left_out(self):
        """Kuopio parses and Manttu lists two days whose rows this parser misses. Not
        shown to be empty, so left out, and run.py keeps Manttu's previous file."""
        def bad(time_, title, href):
            return row(time_, title, href).replace(":", "", 1)
        body = page(kuopio_days=[day("Tiistai 15.9.", row("19", "A", f"{BASE}/a/"))],
                    nilsia_days=[day("Perjantai 11.9.",
                                     bad("17.15", "Presidentin kyyditys", f"{BASE}/pk/")),
                                 day("Lauantai 12.9.",
                                     bad("13", "Marsupilami (dub)", f"{BASE}/mars/"))])
        per = kuvakukko.parse(body, today=TODAY)
        self.assertEqual(len(per["kk-kuopio"]), 1)
        self.assertNotIn("kk-nilsia", per)

    def test_a_cinema_whose_days_changed_shape_is_left_out_not_published_empty(self):
        """Kuopio parses and Manttu's days no longer match the day pattern. Each shape
        reaches one way a line opens like a day or a screening, so Manttu is left out and
        run.py keeps its previous file."""
        pk = f'<a href="{BASE}/ohjelmisto/manttu-pk/">Presidentin kyyditys</a>'
        shapes = {
            # A note first, then the day in a paragraph that lost its class.
            "no class": [info("Syyskauden ohjelmisto:"),
                         f"<p>Perjantai 11.9.<br>Klo 17.15: {pk}</p>"],
            # No `D.M` anywhere: only the `Klo` rows open like a screening.
            "klo only": [day("Perjantaina 11. syyskuuta", f"Klo 17.15: {pk}")],
            # No `Klo`: the weekday and date without its closing dot.
            "no klo": [day("Perjantai 11.9", f"17.15: {pk}")],
            # The date first, no weekday before it and no `Klo`.
            "date first": [day("11.9. perjantai", f"17.15: {pk}")],
        }
        for name, nilsia in shapes.items():
            with self.subTest(name):
                per = kuvakukko.parse(page(kuopio_days=[day("Tiistai 15.9.", row("19", "A"))],
                                           nilsia_days=nilsia), today=TODAY)
                self.assertEqual(len(per["kk-kuopio"]), 1)
                self.assertNotIn("kk-nilsia", per)

    def test_a_cinema_with_only_notes_under_its_heading_is_still_empty(self):
        """Manttu's section as read 2026-09-24 below its days: when the next weekend is
        published, the address, the ticket line (in `page`), and a price note. None opens
        with a time, a date or a weekday and a date."""
        notes = (info("Mantun ohjelmisto (joka toinen viikonloppu) julkaistaan viimeist&auml;&auml;n "
                      "keskiviikkona.")
                 + info("Kino Manttu, Vesitornintie 1, Nilsi&auml;.")
                 # A price opening a note has the `word D.M` shape; its word is no weekday.
                 + info("Sarjalippu 57.50 &euro; (kuusi n&auml;yt&ouml;st&auml;)."))
        per = kuvakukko.parse(page(kuopio_days=[day("Tiistai 15.9.", row("19", "A"))],
                                   extra=notes), today=TODAY)
        self.assertEqual(per["kk-nilsia"], [])

    def test_a_page_without_a_schedule_heading_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            kuvakukko.parse("<html><body><p>Tervetuloa</p></body></html>", today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_repeated_row_is_published_once(self):
        r = row("19", "A", f"{BASE}/x/")
        per = kuvakukko.parse(page(kuopio_days=[day("Tiistai 15.9.", r, r)]), today=TODAY)
        self.assertEqual(len(per["kk-kuopio"]), 1)


def price_block(heading, *paragraphs):
    return (f'<h2 class="wp-block-heading">{heading}</h2>'
            + "".join(f'<p class="wp-block-paragraph">{x}</p>' for x in paragraphs))


KUOPIO_TARIFF = ("<strong>Liput:</strong> 11,50 &euro; / 9,50 &euro; (alle 12-vuotiaat, "
                 "opiskelijat, el&auml;kel&auml;iset, varusmiehet, ty&ouml;tt&ouml;m&auml;t). "
                 "Sarjaliput (kuusi n&auml;yt&ouml;st&auml;) 57,50 &euro; / 47,50 &euro;. "
                 "Lahjalippu 11,50 &euro;.")
NILSIA_TARIFF = ("Liput: 11 &euro; / 9 &euro; (alle 12-vuotiaat, opiskelijat, "
                 "el&auml;kel&auml;iset, varusmiehet, ty&ouml;tt&ouml;m&auml;t).")


def price_page(kuopio=KUOPIO_TARIFF, nilsia=NILSIA_TARIFF, footer=True):
    """`kuvakukko.fi/liput/` as read 2026-09-16: a block per cinema, and a third heading
    that names a cinema again in the footer's contact card and states no price."""
    return ("<html><body>"
            + price_block("Kino Kuvakukko liput", kuopio,
                          "Lipunmyynti vain Kuvakukossa (Vuorikatu 27, Kuopio).")
            + price_block("Kino Manttu liput", nilsia, "Maksuv&auml;line: vain k&auml;teinen.")
            + (price_block("Kino Kuvakukko", "Vuorikatu 27, 70100 KUOPIO",
                           "Puh. 044 718 2470") if footer else "")
            + "</body></html>")


class TariffTest(unittest.TestCase):
    """`/liput/` states one ordinary admission per cinema and no condition on it."""

    def test_both_cinemas_are_read_and_the_ordinary_ticket_is_the_first_amount(self):
        """The error this prevents: publishing 9,50 (a concession), 57,50 (a six-show
        series ticket) or 47,50, all of which are on the same line as the answer."""
        self.assertEqual(kuvakukko.tariff(price_page()),
                         {"kk-kuopio": "11.5\u20ac", "kk-nilsia": "11\u20ac"})

    def test_the_footer_naming_a_cinema_again_does_not_take_its_price_away(self):
        """The real page has three headings and the third is the contact card. It states
        no amount, so it is not a second, disagreeing answer about the same cinema."""
        self.assertEqual(kuvakukko.tariff(price_page(footer=False)),
                         kuvakukko.tariff(price_page()))

    def test_two_statements_under_one_heading_settle_nothing(self):
        """Which admission a ticket is, is exactly what is then in doubt."""
        two = KUOPIO_TARIFF + " Liput: 13,00 &euro; / 11,00 &euro;."
        self.assertNotIn("kk-kuopio", kuvakukko.tariff(price_page(kuopio=two)))
        self.assertIn("kk-nilsia", kuvakukko.tariff(price_page(kuopio=two)))

    def test_one_cinema_named_twice_with_two_amounts_settles_nothing(self):
        """The footer names a cinema a second time. It prints no price today; if it ever
        prints a different one, the page disagrees with itself and neither figure is the
        admission."""
        page = ("<html><body>"
                + price_block("Kino Kuvakukko liput", KUOPIO_TARIFF)
                + price_block("Kino Kuvakukko", "Liput: 13,00 &euro; / 11,00 &euro;.")
                + "</body></html>")
        self.assertEqual(kuvakukko.tariff(page), {})

    def test_a_block_disclaiming_its_own_tariff_publishes_nothing(self):
        """A cinema saying the price is set separately has said the tariff does not settle
        a screening, which is the whole rule."""
        said = KUOPIO_TARIFF + " Erikoisn&auml;yt&ouml;kset hinnoitellaan erikseen."
        self.assertNotIn("kk-kuopio", kuvakukko.tariff(price_page(kuopio=said)))

    def test_a_page_with_no_tariff_names_nobody(self):
        self.assertEqual(kuvakukko.tariff("<html><body>Liput</body></html>"), {})

    def test_the_tariff_page_failing_leaves_the_amounts_empty(self):
        """The schedule is the thing a reader needs; the price is not worth a site."""
        real, kuvakukko._get = kuvakukko._get, _raise
        try:
            self.assertEqual(kuvakukko.get_prices(), {})
        finally:
            kuvakukko._get = real


def _raise(url):
    raise OSError("down")


class PriceTest(unittest.TestCase):
    """Which screenings the tariff settles, and which it does not reach."""

    def setUp(self):
        self.per = kuvakukko.parse(LISTING_PAGE, today=TODAY,
                                   prices=kuvakukko.tariff(price_page()))
        self.by_title = {(s["venue"], s["title"]): s
                         for v in self.per.values() for s in v}

    def test_an_ordinary_screening_carries_the_cinema_s_own_tariff(self):
        """Keyed by venue as well as title: the two cinemas show the same films, at
        different prices, which is the whole reason the tariff is read per heading."""
        self.assertEqual(self.by_title[("kk-kuopio", "Hetki ennen valoa")]["price"],
                         "11.5\u20ac")
        self.assertEqual(self.by_title[("kk-nilsia", "Hetki ennen valoa")]["price"],
                         "11\u20ac")

    def test_each_cinema_gets_its_own_amount(self):
        """Nilsiä is 11 € and Kuopio 11,50 €; one page states both."""
        self.assertEqual({s["price"] for s in self.per["kk-kuopio"] if s["price"]},
                         {"11.5\u20ac"})
        self.assertEqual({s["price"] for s in self.per["kk-nilsia"]}, {"11\u20ac"})

    def test_an_outside_organiser_s_screening_is_not_priced_by_this_tariff(self):
        """The Hopeatähti row is a series billed under its own name and sold on isak.fi.
        The house statement does not reach it, so it publishes no amount."""
        self.assertEqual(
            self.by_title[("kk-kuopio", "Hopeatähti-sarja: Laula minulle Arja")]["price"], "")

    def test_the_label_is_read_even_when_the_series_links_to_this_site(self):
        """An on-site link is not evidence the tariff applies. The error this prevents:
        a film club's screening priced as an ordinary one because it happens to have a
        page here."""
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.",
                                  row("19", "Hyvät Kuvat-kerho: Perfect Blue",
                                      f"{BASE}/ohjelmisto/perfect-blue/"))]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual(per["kk-kuopio"][0]["price"], "")

    def test_an_unlabelled_screening_sold_elsewhere_is_not_priced_either(self):
        """A destination that leaves this site is the other half of the evidence, and it
        stands on its own: an outside sale need not be labelled."""
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.",
                                  row("19", "Aavesoturi (1987)",
                                      "https://isak.fi/vilimit/"))]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual(per["kk-kuopio"][0]["price"], "")

    def test_a_row_with_no_link_at_all_is_an_ordinary_screening(self):
        """The cinema prints a row without a page when a film is ending. Withholding here
        would be inferring from the *absence* of an on-site link, which says nothing."""
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.", row("15", "Autofiktio (viimeinen näytös)"))]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual(per["kk-kuopio"][0]["price"], "11.5\u20ac")

    def test_a_row_stating_its_own_price_outranks_the_tariff(self):
        """A screening-specific amount is the more specific statement."""
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.",
                                  row("19", "Ooppera") + " 25 &euro;")]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual(per["kk-kuopio"][0]["price"], "25\u20ac")

    def test_a_row_stating_two_amounts_publishes_neither(self):
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.",
                                  row("19", "Ooppera") + " 25 &euro; / 20 &euro;")]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual(per["kk-kuopio"][0]["price"], "")

    def test_one_row_s_own_amount_stays_on_that_row(self):
        """The error this prevents: an amount printed on a later row reaching back to an
        earlier one, which is the shape Kirkkonummi's ambiguity had. A row's own text ends
        where the next row starts, so the 17:00 screening is an ordinary one."""
        per = kuvakukko.parse(
            page(kuopio_days=[day("Tiistai 15.9.",
                                  row("17", "Hetki ennen valoa", f"{BASE}/x/"),
                                  row("19", "Ooppera", f"{BASE}/y/") + " 25 &euro;")]),
            today=TODAY, prices={"kk-kuopio": "11.5\u20ac"})
        self.assertEqual([s["price"] for s in per["kk-kuopio"]], ["11.5\u20ac", "25\u20ac"])

    def test_no_tariff_read_means_no_amount_anywhere(self):
        """A `/liput/` that will not answer leaves 45 showtimes standing and unpriced."""
        per = kuvakukko.parse(LISTING_PAGE, today=TODAY, prices={})
        self.assertEqual({s["price"] for v in per.values() for s in v}, {""})
        self.assertEqual(sum(len(v) for v in per.values()), 7)


class SiteTest(unittest.TestCase):
    def test_one_provider_two_venues_two_towns(self):
        site = kuvakukko.SITES[0]
        self.assertEqual(len(site["venues"]), 2)
        self.assertEqual(sorted(v["city"] for v in site["venues"]), ["Kuopio", "Nilsiä"])
        self.assertTrue(kuvakukko.EMPTY_VENUES_CONFIRMED)


if __name__ == "__main__":
    unittest.main()


class EmptyAnchorTest(unittest.TestCase):
    """Nilsiä's 9.10. row read 2026-10-04 opens with an empty anchor before the titled one,
    and the row was dropped with nothing in the log."""
    EMPTY = (f'<a href="{BASE}/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/'
             'kino-manttu-presidentin-kyyditys/" data-type="page" data-id="2708"></a>')

    def parse(self, *rows):
        html = page(kuopio_days=[day("Tiistai 15.9.", row("13", "Hetki ennen valoa",
                                                          f"{BASE}/ohjelmisto/hev/"))],
                    nilsia_days=[day("Perjantai 18.9.", *rows)])
        from contextlib import redirect_stdout
        import io
        buf = io.StringIO()
        with redirect_stdout(buf):
            per = kuvakukko.parse(html, today=TODAY)
        return per["kk-nilsia"], buf.getvalue()

    def test_the_titled_anchor_after_an_empty_one_is_the_row(self):
        href = f"{BASE}/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/kino-manttu-the-odysseu/"
        shows, log = self.parse(
            "Klo 17: " + self.EMPTY + f'<a href="{href}" data-type="page" data-id="2593">'
            "Rakkautta ja virtahepoja</a>",
            row("19", "Kerro kaikille", f"{BASE}/ohjelmisto/manttu-kk/"))
        self.assertEqual([(s["start"][11:16], s["title"], s["url"]) for s in shows],
                         [("17:00", "Rakkautta ja virtahepoja", href),
                          ("19:00", "Kerro kaikille", f"{BASE}/ohjelmisto/manttu-kk/")])
        self.assertNotIn("no title", log)

    def test_a_row_left_without_a_title_is_named_in_the_log(self):
        shows, log = self.parse("Klo 17: " + self.EMPTY,
                                row("19", "Kerro kaikille", f"{BASE}/ohjelmisto/manttu-kk/"))
        self.assertEqual([s["title"] for s in shows], ["Kerro kaikille"])
        self.assertIn("[kuvakukko] 1 screening line(s) with no title, skipped: Manttu 18.9. klo 17",
                      log)


def film_page(h1, *lines):
    """A film page as read 2026-10-04: the heading, then the facts line in a paragraph."""
    return ('<html><body><h1 class="entry__title">' + h1 + "</h1>"
            + "".join(f'<p class="wp-block-paragraph">{x}</p>' for x in lines)
            + "<p>Elokuvan kuvaus.</p></body></html>")


GRAZIA = film_page("LA GRAZIA", "Italia 2025 • draama • 133 min • K7 • "
                   "kieli: italia • tekstitys: suomi/ruotsi")
PIRJO = film_page("Kino Manttu: PIRJO I SVERIGE", "Suomi 2026 • komedia/koko perheen "
                  "• 88 min • -S- • kieli: suomi • tekstitys: –")


class FilmFactsTest(unittest.TestCase):
    """The labelled facts of a film's own page, and only for the film its heading names."""

    def test_the_facts_line_of_the_rows_film(self):
        self.assertEqual(kuvakukko.film_facts(GRAZIA, "La Grazia"),
                         {"len": "133", "rating": "K-7", "lang": "IT-A, FI-S, SV-S"})
        self.assertEqual(kuvakukko.film_facts(PIRJO, "Pirjo i Sverige"),
                         {"len": "88", "rating": "S", "lang": "FI-A"})

    def test_a_page_about_another_film_states_nothing(self):
        """`/the-invite/` held La Grazia on 2026-10-04: the slug is no evidence, the
        heading is."""
        self.assertEqual(kuvakukko.film_facts(GRAZIA, "The Invite"),
                         {"len": "", "rating": "", "lang": ""})

    def test_prose_run_into_the_line_is_not_a_second_candidate(self):
        """Päivien lumo, read 2026-10-04: a quoted paragraph and the facts line came out as
        one chunk beside the facts line itself."""
        line = ("Suomi 2026 \u2022 dokumentti \u2022 88 min \u2022 -S- \u2022 kieli: suomi "
                "\u2022 tekstitys: \u2013")
        quote = ("Ohjaaja kertoo elokuvastaan n\u00e4in: \u201dMinua on aina kiinnostanut "
                 "marginaalissa tapahtuva, ja Markun asenne saa minut pys\u00e4htym\u00e4\u00e4n.\u201d ")
        page = film_page("P\u00c4IVIEN LUMO", line).replace(
            "<p class", f"<blockquote>{quote}<span>{line}</span></blockquote><p class", 1)
        self.assertEqual(kuvakukko.film_facts(page, "P\u00e4ivien lumo"),
                         {"len": "88", "rating": "S", "lang": "FI-A"})

    def test_a_series_page_states_nothing(self):
        """Kuvin aluesarja lists several films, each with its own line."""
        page = film_page("Kuvin aluesarja", "Jungfrukällan, Ruotsi 1960 • 35 mm • "
                         "suom. tekstit • K16 • 90 min",
                         "Shallow Grave, Iso-Britannia 1994 • 4K DCP • K16 • 89 min")
        self.assertEqual(kuvakukko.film_facts(page, "Kuvin aluesarja: Neidonlähde"),
                         {"len": "", "rating": "", "lang": ""})
        self.assertEqual(kuvakukko.film_facts(page, "Kuvin aluesarja"),
                         {"len": "", "rating": "", "lang": ""})

    def test_an_ambiguous_or_unknown_segment_states_nothing_for_its_field(self):
        page = film_page("KABUL", "Suomi – Norja 2026 • 94 min • K16 • S • "
                         "kieli: dari/pashtu/englanti • tekstitys: suomi")
        self.assertEqual(kuvakukko.film_facts(page, "Kabul"),
                         {"len": "94", "rating": "", "lang": "FI-S"})
        page = film_page("KABUL", "94 min • 95 min • K16")
        self.assertEqual(kuvakukko.film_facts(page, "Kabul")["len"], "")


class EnrichTest(unittest.TestCase):
    """One read per film, never per screening, and nothing the listing gave is lost."""

    def per_venue(self):
        own = f"{BASE}/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/"
        def show(vid, title, url, start, **kw):
            return dict({"eventId": common_norm(title), "title": title, "url": url,
                         "start": start, "len": "", "rating": "", "lang": "", "price": ""},
                        **kw)
        return {"kk-kuopio": [show("kk-kuopio", "La Grazia", own + "the-invite/", "1"),
                              show("kk-kuopio", "La Grazia", own + "the-invite/", "2"),
                              show("kk-kuopio", "Rose", own + "tulossa-autofiktio/", "3",
                                   rating="K-16"),
                              show("kk-kuopio", "Hopeatähti-sarja: Arja", LIST, "4")],
                "kk-nilsia": [show("kk-nilsia", "Pirjo i Sverige",
                                   own + "kino-manttu-hetki-ennen-valoa/", "5"),
                              show("kk-nilsia", "La Grazia", own + "kino-manttu-grazia/", "6")]}

    def test_each_film_is_read_once_and_fills_only_its_blanks(self):
        calls = []
        pages = {"the-invite/": GRAZIA, "kino-manttu-hetki-ennen-valoa/": PIRJO,
                 "tulossa-autofiktio/": film_page("ROSE", "Saksa 2026 • 94 min • K12")}
        def get(url):
            calls.append(url)
            return pages[url.rsplit("/", 2)[-2] + "/"]
        per = self.per_venue()
        with redirect_stdout(io.StringIO()) as log:
            read = kuvakukko.enrich(per, sleep=0, get=get)
        self.assertEqual(read, 3)
        self.assertEqual(len(calls), 3, calls)
        rows = [s for v in per.values() for s in v]
        grazia = [(s["len"], s["rating"], s["lang"]) for s in rows if s["title"] == "La Grazia"]
        self.assertEqual(grazia, [("133", "K-7", "IT-A, FI-S, SV-S")] * 3)
        rose = next(s for s in rows if s["title"] == "Rose")
        self.assertEqual((rose["len"], rose["rating"]), ("94", "K-16"))
        self.assertEqual(next(s for s in rows if s["url"] == LIST)["len"], "")
        self.assertIn("3 read for 3 films", log.getvalue())

    def test_a_failed_page_leaves_its_screenings_as_they_were(self):
        def get(url):
            if "the-invite" in url:
                raise OSError("timed out")
            return PIRJO
        per = self.per_venue()
        with redirect_stdout(io.StringIO()) as log:
            kuvakukko.enrich(per, sleep=0, get=get)
        grazia = [s for v in per.values() for s in v if s["title"] == "La Grazia"]
        self.assertTrue(all((s["len"], s["rating"], s["lang"]) == ("", "", "") for s in grazia))
        self.assertIn("the-invite", log.getvalue())
        pirjo = next(s for s in per["kk-nilsia"] if s["title"] == "Pirjo i Sverige")
        self.assertEqual(pirjo["len"], "88")

    def test_the_runner_reads_the_film_pages_paced(self):
        """`fetch_site` is the runner's call; the facts reach its answer, 1.5 s apart."""
        import _no_sleep as no_sleep
        clock = no_sleep.patch(self, kuvakukko)
        per = self.per_venue()
        real = (kuvakukko.parse, kuvakukko._get)
        self.addCleanup(lambda: (setattr(kuvakukko, "parse", real[0]),
                                 setattr(kuvakukko, "_get", real[1])))
        kuvakukko.parse = lambda page, site, prices=None: per
        kuvakukko._get = lambda url: {"the-invite/": GRAZIA}.get(
            url.rsplit("/", 2)[-2] + "/", PIRJO if "manttu" in url else "<html></html>")
        with redirect_stdout(io.StringIO()):
            got = kuvakukko.fetch_site()
        grazia = next(s for s in got["kk-kuopio"] if s["title"] == "La Grazia")
        self.assertEqual(grazia["len"], "133")
        self.assertEqual(clock.slept, [1.5, 1.5])


def common_norm(title):
    import synmerge
    return synmerge.norm(title)
