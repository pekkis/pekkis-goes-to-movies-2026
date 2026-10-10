"""TMB Cinema: one list view per venue, four cinemas that publish the same films.

The fixtures follow the `?lista=1` markup as read on 2026-09-15: a `<small>` carrying the
weekday, the full date with its year, the time and, on the two-screen sites only, a
`, sali N` tail; then the title in an `<h2><a href="?ohjelmisto=N">`; then the age limit
as an image filename in the next cell.

Two venues are built here, single-screen and two-screen, because the chain's own sites
differ that way and a fixture with only one would never exercise the auditorium branch.
The cases this file exists to pin are the ones that would silently corrupt the data: the
age image mapping, which is measured rather than assumed and must not grow a guess; the
weekday guard, which is the only thing that notices the template moving a field; and the
refusal to link to the booking action.
"""
import contextlib
import io
import unittest

import _ctx                                                # noqa: F401
import common
import tmb

TOIJALA = next(s for s in tmb.SITES if s["provider"] == "kinotoijala")
MANIA = next(s for s in tmb.SITES if s["provider"] == "kinomania")


def row(wd, date, time_, fid, title, ika="3", sali=None):
    tail = f", sali&nbsp;{sali}" if sali else ""
    return (f'<tr><td style="padding: 0 20px;"><b><small>{wd}&nbsp;{date} klo&nbsp;{time_}'
            f'{tail}</small></b><h2 style="padding-left: 40px;">'
            f'<a  href="?ohjelmisto={fid}">{title}</a></h2></td>'
            f'<td style="padding: 10px;"><img title="Tutustu ikärajoihin hinnasto-sivulla."\n'
            f'\t\t\t\tsrc="/files/images/ikaraja_{ika}.png" alt="Ikäraja"></td>')


def page(*rows):
    """The list view. The `<title>` names 3D films and no row does, which is the whole
    reason no screening can be priced: the format of each one is unknown."""
    return ('<html><head><title>Kino-Toijala :: elokuvat, 3D-elokuvat</title></head><body>'
            '<nav><a href="?hinnat=2">Hinnasto</a></nav>'
            '<h2>Valkokankaalla...</h2><div class="container"><div class="row">'
            '<div class="12u"><section class="box feature"><table width="100%">'
            + "".join(rows) +
            '</table></section></div></div></div></body></html>')


SINGLE = page(
    row("TI", "15.09.2026", "14:00", "842", "Hetki ennen valoa", ika="2"),
    row("TI", "15.09.2026", "18:00", "833", "Presidentin kyyditys", ika="3"),
    row("KE", "16.09.2026", "17:30", "842", "Hetki ennen valoa", ika="2"),
    # An opera event: ikaraja_1 is not a mapped rating, see the module docstring.
    row("LA", "03.10.2026", "16:00", "834", "Ooppera: Don Giovanni (Vicenza)", ika="1"),
)

TWO_SCREEN = page(
    row("TI", "15.09.2026", "14:00", "833", "Presidentin kyyditys", ika="3", sali="1"),
    row("TI", "15.09.2026", "14:30", "842", "Hetki ennen valoa", ika="2", sali="2"),
    row("TI", "15.09.2026", "18:00", "853", "Insidious: Out of the Further", ika="4", sali="2"),
    row("KE", "16.09.2026", "18:00", "833", "Presidentin kyyditys", ika="3", sali="1"),
)


class ListViewTest(unittest.TestCase):
    def setUp(self):
        self.single = tmb.parse(SINGLE, TOIJALA, TOIJALA["venues"][0])
        self.two = tmb.parse(TWO_SCREEN, MANIA, MANIA["venues"][0])

    def test_every_row_is_a_screening_with_its_own_year(self):
        self.assertEqual(len(self.single), 4)
        self.assertEqual(self.single[0]["start"], "2026-09-15T14:00:00+03:00")
        self.assertEqual(self.single[-1]["start"], "2026-10-03T16:00:00+03:00")

    def test_the_film_id_is_the_event_id_and_recurs_across_days(self):
        runs = [s for s in self.single if s["eventId"] == "842"]
        self.assertEqual(len(runs), 2)
        self.assertEqual({s["start"][:10] for s in runs}, {"2026-09-15", "2026-09-16"})

    def test_a_single_screen_site_publishes_no_auditorium(self):
        self.assertEqual({s["aud"] for s in self.single}, {""})

    def test_a_two_screen_site_keeps_each_row_in_its_own_hall(self):
        by = {(s["start"][11:16], s["aud"]) for s in self.two}
        self.assertIn(("14:00", "Sali 1"), by)
        self.assertIn(("14:30", "Sali 2"), by)
        self.assertEqual(sorted({s["aud"] for s in self.two}), ["Sali 1", "Sali 2"])

    def test_the_age_image_maps_only_where_it_was_measured(self):
        """2, 3 and 4 were checked against this repo's own ratings for films other
        providers carry. 1 appears only on opera events and is deliberately unmapped: a
        guessed classification is worse than none."""
        by_title = {s["title"]: s["rating"] for s in self.single}
        self.assertEqual(by_title["Hetki ennen valoa"], "K-7")
        self.assertEqual(by_title["Presidentin kyyditys"], "K-12")
        self.assertEqual(by_title["Ooppera: Don Giovanni (Vicenza)"], "")
        self.assertEqual({s["title"]: s["rating"] for s in self.two}
                         ["Insidious: Out of the Further"], "K-16")

    def test_a_row_with_no_age_image_does_not_borrow_the_next_rows(self):
        """The image was looked for in the 400 characters after the title, which reach
        into the next row: a "Yllätysnäytös" with no image took the next film's K-16
        (audit A10, 2026-09-25)."""
        bare = row("TI", "15.09.2026", "14:00", "900", "Yllätysnäytös")
        bare = bare[:bare.index('<td style="padding: 10px;">')] + '<td style="padding: 10px;"></td>'
        shows = tmb.parse(page(bare, row("TI", "15.09.2026", "18:00", "853", "Insidious", ika="4")),
                          TOIJALA, TOIJALA["venues"][0])
        self.assertEqual({s["title"]: s["rating"] for s in shows},
                         {"Yllätysnäytös": "", "Insidious": "K-16"})

    def test_an_unknown_age_image_yields_no_rating_rather_than_a_guess(self):
        out = tmb.parse(page(row("TI", "15.09.2026", "18:00", "1", "X", ika="9")),
                        TOIJALA, TOIJALA["venues"][0])
        self.assertEqual(out[0]["rating"], "")

    def test_the_showtime_links_to_the_public_film_page_never_the_booking_action(self):
        for s in self.single + self.two:
            self.assertRegex(s["url"], r"^https://[^/]+/\?ohjelmisto=\d+$")
            self.assertNotIn("varaa", s["url"])

    def test_each_site_files_its_shows_under_its_own_provider_and_venue(self):
        self.assertEqual({s["provider"] for s in self.single}, {"kinotoijala"})
        self.assertEqual({s["venue"] for s in self.single}, {"tmb-toijala"})
        self.assertEqual({s["provider"] for s in self.two}, {"kinomania"})
        self.assertEqual({s["venue"] for s in self.two}, {"tmb-mania"})

    def test_every_show_meets_the_contract(self):
        for shows, site in ((self.single, TOIJALA), (self.two, MANIA)):
            common.check_shows({site["venues"][0]["id"]: shows}, site["provider"],
                               {v["id"] for v in site["venues"]})

    def test_a_repeated_row_is_published_once(self):
        r = row("TI", "15.09.2026", "18:00", "833", "Presidentin kyyditys")
        self.assertEqual(len(tmb.parse(page(r, r), TOIJALA, TOIJALA["venues"][0])), 1)

    def test_the_same_minute_in_two_halls_is_two_screenings(self):
        """Two screens can start together; keying on time alone would drop one."""
        out = tmb.parse(page(row("TI", "15.09.2026", "18:00", "1", "A", sali="1"),
                             row("TI", "15.09.2026", "18:00", "2", "B", sali="2")),
                        MANIA, MANIA["venues"][0])
        self.assertEqual(len(out), 2)


class GuardTest(unittest.TestCase):
    def test_a_row_whose_weekday_contradicts_its_date_is_skipped_and_counted(self):
        """The only signal that the template moved a field: 15.09.2026 is a Tuesday, so a
        row calling it Saturday is not a screening this parser understands."""
        out = tmb.parse(page(row("LA", "15.09.2026", "18:00", "1", "wrong day"),
                             row("TI", "15.09.2026", "20:00", "2", "right day")),
                        TOIJALA, TOIJALA["venues"][0])
        self.assertEqual([s["title"] for s in out], ["right day"])

    def test_an_impossible_date_does_not_abort_the_page(self):
        out = tmb.parse(page(row("TI", "31.02.2026", "18:00", "1", "X"),
                             row("TI", "15.09.2026", "20:00", "2", "Y")),
                        TOIJALA, TOIJALA["venues"][0])
        self.assertEqual([s["title"] for s in out], ["Y"])

    def test_a_list_with_no_screening_row_fails_rather_than_empties_the_venue(self):
        """No empty state is recorded for this template: 'Valkokankaalla' heads the list
        view whether or not it lists anything, so it is no evidence of an empty programme.
        Zero rows fails until the real empty state is read off the site."""
        with self.assertRaises(RuntimeError) as cm:
            tmb.parse(page(), TOIJALA, TOIJALA["venues"][0])
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_film_rows_the_parser_cannot_read_fail_the_site(self):
        """The rows are there, with their film links, in a time format ROW_RE misses. That
        is a template change, and an empty programme would delete the venue's screenings."""
        with self.assertRaises(RuntimeError) as cm:
            tmb.parse(page(row("TI", "15.09.2026", "14.00", "842", "Hetki ennen valoa"),
                           row("KE", "16.09.2026", "17.30", "833", "Presidentin kyyditys")),
                      TOIJALA, TOIJALA["venues"][0])
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("2 film link", str(cm.exception))

    def test_rows_that_all_fail_the_weekday_guard_fail_the_site(self):
        with self.assertRaises(RuntimeError) as cm, \
                contextlib.redirect_stdout(io.StringIO()):
            tmb.parse(page(row("LA", "15.09.2026", "18:00", "1", "A"),
                           row("SU", "16.09.2026", "18:00", "2", "B")),
                      TOIJALA, TOIJALA["venues"][0])
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_the_venue_is_never_vouched_empty(self):
        """`EMPTY_VENUES_CONFIRMED` would publish a returned [] as a fresh empty file. This
        adapter has no empty state to vouch with, so it raises instead and sets no flag."""
        self.assertFalse(hasattr(tmb, "EMPTY_VENUES_CONFIRMED"))

    def test_a_page_without_the_container_is_a_failure_not_an_empty_programme(self):
        with self.assertRaises(RuntimeError) as cm:
            tmb.parse("<html><head><title>Just a moment...</title></head><body></body></html>",
                      TOIJALA, TOIJALA["venues"][0])
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_the_failure_states_what_was_served(self):
        """All four of these sites failed on 2026-09-16 with "no 'Valkokankaalla'
        container" while serving their real list view to an ordinary connection minutes
        later. The size and the title are what tell those two apart next time."""
        with self.assertRaises(RuntimeError) as cm:
            tmb.parse("<html><head><title>Just a moment...</title></head><body></body></html>",
                      TOIJALA, TOIJALA["venues"][0])
        self.assertIn('titled "Just a moment..."', str(cm.exception))


class PriceTest(unittest.TestCase):
    """The tariff is on the site and no screening is priced from it.

    2D and 3D differ by 2.50 and no row says which it is; the surcharge covers weekday
    public holidays as well as the weekend and no calendar here knows which days those are.
    So the applicability of every tariff amount to every screening is unestablished, and
    the rule in `common.Show` is that nothing is published rather than something nearly
    right. What *is* published, since 2026-09-16, is the amount the film page prints under
    each screening, which needs neither of those questions answered; `ScreeningPriceTest`
    covers it.
    """

    def test_the_list_view_alone_prices_no_screening(self):
        for site, body in ((TOIJALA, SINGLE), (MANIA, TWO_SCREEN)):
            with self.subTest(provider=site["provider"]):
                shows = tmb.parse(body, site, site["venues"][0])
                self.assertEqual({s["price"] for s in shows}, {""})

    def test_the_adapter_reads_the_price_page_from_nowhere(self):
        """It was published for a few hours on 2026-09-16 and withdrawn. The request went
        with it: there is no point asking a cinema for a page nothing publishes."""
        for name in ("price_url", "price_tiers", "price_of", "TIER_RE", "PRICE_LINK_RE"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(tmb, name))

    def test_the_tariff_is_still_read_by_nothing(self):
        """What is published comes from the screening's own line on the film page. The
        `?hinnat=` tariff is not fetched, parsed or applied, and it still could not be:
        the format of a row is unknown and a weekday public holiday is unknowable."""
        for name in ("price_url", "price_tiers", "price_of", "TIER_RE", "PRICE_LINK_RE"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(tmb, name))


def show_block(date, time_, hinta="14.45€ / 12.45€ / 11.45€", wd="KE"):
    """One screening on the film page: the date, the booking button, then its own price.
    The booking link is `?varaa=`, which this adapter never follows or publishes."""
    price = (f'<br><span style="font-size: 0.75em;">Hinta: {hinta}</span>'
             if hinta is not None else "")
    return (f'{wd}&nbsp;{date} klo&nbsp;{time_}&nbsp;'
            f'<a href="?varaa=21009" class="button icon fa-arrow-circle-right">Liput</a>'
            f'{price}<br style="clear: both;"><br>')


def film_page(kesto="1 tuntia 27 minuuttia", kuvaus="Klaus Härön uutuuselokuva.",
              laji="kotimainen", extra="", shows=None):
    """A `?ohjelmisto=` page: the film's own screening list, then its metadata. Every
    metadata field is the same shape, `<p class="info">Label: <b>value</b></p>`, which is
    what the parser reads rather than positions."""
    rows = []
    for label, value in (("Kesto", kesto), ("Kuvaus", kuvaus), ("Lajityyppi", laji)):
        if value is not None:
            rows.append(f'<p class="info">{label}: <b>{value}</b></p>')
    blocks = ("".join(shows) if shows is not None
              else show_block("15.09.2026", "14:00") + show_block("16.09.2026", "17:30"))
    return ('<html><body><section><h3>Näytökset</h3><p id="shows">' + blocks + '</p>'
            '</section><div id="content" class="inner">' + "".join(rows) + extra
            + '<p class="info">Ohjaus: <b>Klaus Härö</b></p></div></body></html>')


FILM_PAGE = film_page()


class FetchHarness(unittest.TestCase):
    """Drives `fetch_site` against fixture pages, counting what it asked for."""

    def drive(self, listing, pages, site=TOIJALA, sleep=0):
        """-> (shows, the urls requested, in order)."""
        calls = []

        def get(url):
            calls.append(url)
            if "lista=1" in url:
                return listing
            fid = url.rsplit("=", 1)[1]
            if fid not in pages:
                raise OSError(f"no page for {fid}")
            return pages[fid]
        real = tmb.get
        tmb.get = get
        self.addCleanup(lambda: setattr(tmb, "get", real))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            data = tmb.fetch_site(site, sleep=sleep)
        return data[site["venues"][0]["id"]], calls


class FetchTest(FetchHarness):
    """`fetch_site`: the list view, then one page per distinct film."""

    def test_the_list_view_comes_first_and_then_one_page_per_distinct_film(self):
        """Three films over four rows: the repeated film is fetched once, not twice."""
        shows, calls = self.drive(SINGLE, {f: film_page() for f in ("842", "833", "834")})
        self.assertEqual(calls[0], "https://toijalan-kino.info/?lista=1")
        self.assertEqual(sorted(calls[1:]),
                         [f"https://toijalan-kino.info/?ohjelmisto={f}"
                          for f in ("833", "834", "842")])
        self.assertEqual(len(shows), 4)
        common.check_shows({"tmb-toijala": shows}, "kinotoijala", {"tmb-toijala"})

    def test_the_runtime_the_synopsis_and_the_genre_reach_every_screening_of_a_film(self):
        """Two of the four rows are the same film, and both carry what its page said."""
        shows, _ = self.drive(SINGLE, {"842": film_page(kesto="2 tuntia", laji="draama",
                                                      kuvaus="Kahden naisen kohtaaminen.")})
        hetki = [s for s in shows if s["eventId"] == "842"]
        self.assertEqual(len(hetki), 2)
        for s in hetki:
            self.assertEqual((s["len"], s["genres"]), ("120", "draama"))
            self.assertEqual(s["_syn"], "Kahden naisen kohtaaminen.")

    def test_a_film_page_that_will_not_answer_costs_that_film_its_metadata_only(self):
        """The schedule is parsed before this runs. The error this prevents: one 500 on a
        film page taking a cinema's whole programme with it."""
        shows, _ = self.drive(SINGLE, {"842": film_page()})
        by_id = {s["eventId"]: s for s in shows}
        self.assertEqual(by_id["842"]["len"], "87")
        self.assertEqual((by_id["833"]["len"], by_id["833"]["genres"]), ("", ""))
        self.assertNotIn("_syn", by_id["833"])
        self.assertEqual(len(shows), 4)

    def test_a_page_stating_no_duration_publishes_no_runtime(self):
        shows, _ = self.drive(SINGLE, {"842": film_page(kesto="ei tiedossa", kuvaus=None)})
        s = next(x for x in shows if x["eventId"] == "842")
        self.assertEqual(s["len"], "")
        self.assertNotIn("_syn", s)

    def test_the_budget_bounds_the_film_pages(self):
        """`capped`, so a film past the ceiling loses metadata and keeps its showtimes."""
        real = common.PAGE_BUDGET
        common.PAGE_BUDGET = 1
        self.addCleanup(lambda: setattr(common, "PAGE_BUDGET", real))
        shows, calls = self.drive(SINGLE, {f: film_page() for f in ("842", "833", "834")})
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(shows), 4)


class ScreeningPriceTest(FetchHarness):
    """The amount the film page prints under each screening, and only that."""

    def test_each_screening_carries_the_amount_printed_under_it(self):
        """The error this prevents: one screening's amount reaching another's row. The
        weekend surcharge is why they differ, and it is already in the printed figure."""
        page = film_page(shows=[show_block("15.09.2026", "14:00"),
                                show_block("16.09.2026", "17:30",
                                           hinta="14.95€ / 12.95€ / 11.95€")])
        self.assertEqual(tmb.screening_prices(page),
                         {"2026-09-15T14:00": "14.45€", "2026-09-16T17:30": "14.95€"})

    def test_the_ordinary_admission_is_the_first_of_the_three(self):
        """`?hinnat=` prints Aikuinen 14.45, Eläkeläinen 12.45, Lapsi 11.45 in that order,
        read 2026-09-16, and the film page prints the same three in the same order. The
        error this prevents: publishing a concession as the price of a ticket."""
        prices = tmb.screening_prices(film_page(shows=[show_block("15.09.2026", "14:00")]))
        self.assertEqual(prices, {"2026-09-15T14:00": "14.45€"})

    def test_a_screening_with_no_amount_under_it_is_not_priced(self):
        page = film_page(shows=[show_block("15.09.2026", "14:00", hinta=None),
                                show_block("16.09.2026", "17:30")])
        self.assertEqual(tmb.screening_prices(page), {"2026-09-16T17:30": "14.45€"})

    def test_one_minute_claimed_twice_with_two_amounts_publishes_neither(self):
        """Nothing in the markup delimits a screening but the next date, so a page that
        states two amounts for one minute has not settled which a ticket costs."""
        page = film_page(shows=[show_block("15.09.2026", "14:00"),
                                show_block("15.09.2026", "14:00",
                                           hinta="16.95€ / 15.95€ / 13.95€"),
                                show_block("16.09.2026", "17:30")])
        self.assertEqual(tmb.screening_prices(page), {"2026-09-16T17:30": "14.45€"})

    def test_a_block_holding_two_amounts_prices_nothing(self):
        """A screening block ends at the next date, so a row this parser cannot read leaves
        its own `Hinta` inside the block above it. Two amounts under one screening is then
        exactly the doubt the rule is about, whether the operator printed them that way or
        a template change put them there."""
        page = film_page(shows=[
            show_block("15.09.2026", "14:00",
                       hinta=("14.45€ / 12.45€ / 11.45€</span><br>"
                              "<span>Hinta: 16.95€ / 15.95€ / 13.95€")),
            show_block("16.09.2026", "17:30")])
        self.assertEqual(tmb.screening_prices(page), {"2026-09-16T17:30": "14.45€"})

    def test_the_same_amount_stated_twice_is_not_a_conflict(self):
        page = film_page(shows=[show_block("15.09.2026", "14:00"),
                                show_block("15.09.2026", "14:00")])
        self.assertEqual(tmb.screening_prices(page), {"2026-09-15T14:00": "14.45€"})

    def test_the_price_reaches_the_showtime_it_belongs_to(self):
        """Both of the film's screenings are in the list view; only one is dear."""
        shows, _ = self.drive(SINGLE, {"842": film_page(shows=[
            show_block("15.09.2026", "14:00"),
            show_block("16.09.2026", "17:30", hinta="14.95€ / 12.95€ / 11.95€")])})
        by_start = {s["start"][:16]: s["price"] for s in shows}
        self.assertEqual(by_start["2026-09-15T14:00"], "14.45€")
        self.assertEqual(by_start["2026-09-16T17:30"], "14.95€")

    def test_a_screening_the_film_page_does_not_list_stays_unpriced(self):
        """The list view is the schedule; the film page only prices what it prints."""
        shows, _ = self.drive(SINGLE, {"842": film_page(shows=[
            show_block("15.09.2026", "14:00")])})
        by_start = {s["start"][:16]: s["price"] for s in shows}
        self.assertEqual(by_start["2026-09-15T14:00"], "14.45€")
        self.assertEqual(by_start["2026-09-16T17:30"], "")
        self.assertEqual(by_start["2026-09-15T18:00"], "")

    def test_a_film_page_that_will_not_answer_prices_nothing(self):
        shows, _ = self.drive(SINGLE, {"842": film_page()})
        self.assertEqual({s["price"] for s in shows if s["eventId"] != "842"}, {""})


class MinutesTest(unittest.TestCase):
    """`Kesto` as the operator writes it."""

    def test_hours_and_minutes_both_count(self):
        self.assertEqual(tmb.minutes("1 tuntia 27 minuuttia"), "87")
        self.assertEqual(tmb.minutes("2 tuntia"), "120")
        self.assertEqual(tmb.minutes("95 minuuttia"), "95")

    def test_a_text_with_no_duration_in_it_yields_nothing(self):
        """Not "0": a zero would render as a runtime and Bio Savoy's `XXh 00min` is the
        standing example of a placeholder published as though it were a fact."""
        for raw in ("", "ei tiedossa", "0 tuntia", "0 tuntia 0 minuuttia"):
            with self.subTest(raw=raw):
                self.assertEqual(tmb.minutes(raw), "")


class SitesTest(unittest.TestCase):
    def test_four_cinemas_in_four_towns_on_four_hosts(self):
        self.assertEqual(len(tmb.SITES), 4)
        self.assertEqual(sorted(v["city"] for s in tmb.SITES for v in s["venues"]),
                         ["Akaa", "Heinola", "Pieksämäki", "Valkeakoski"])
        self.assertEqual(len({s["base"] for s in tmb.SITES}), 4,
                         "four hosts: they are four cinemas, not one mirrored")
        self.assertEqual(len({v["id"] for s in tmb.SITES for v in s["venues"]}), 4)

    def test_each_site_names_exactly_one_venue(self):
        for s in tmb.SITES:
            self.assertEqual(len(s["venues"]), 1, s["provider"])


if __name__ == "__main__":
    unittest.main()
