"""Kino Vaakuna, Lohja: film cards, an age limit in an image name, and no year anywhere.

The fixtures follow `kinovaakuna.fi/etusivu.html` as read on 2026-09-15: one
`div.MovieCard` per film with the film-page link, the poster, `Liput:`, `Kesto:`, an
`Ikäraja:` image whose filename is the number, and a table of `Ti 15.09.   klo 18:40`
rows.

`today` is passed in everywhere rather than read from the clock, because the year is the
one thing this page does not publish and a test that resolved it against the real date
would pass in September and fail in January. `common.resolve_year` has its own tests; what
is pinned here is that this parser uses it and skips a row it cannot place.
"""
import datetime
import unittest

import _ctx                                                # noqa: F401
import common
import vaakuna

BASE = "https://www.kinovaakuna.fi"
TODAY = datetime.date(2026, 9, 15)


def card(slug, title, shows, price="13 €", kesto="1 h 27 min", icon="12", poster=True):
    rows = "".join(f'<tr><td class="">{s}</td></tr>' for s in shows)
    img = (f'<img class="MovieCard__Poster img-fluid" '
           f'src="{BASE}/media/cache/{slug}.png" alt="{title} Juliste">') if poster else ""
    age = (f'<li>Ikäraja: <img src="{BASE}/media/layout/img/icon/{icon}.png" '
           f'style="width: 1.5rem;"></li>') if icon is not None else ""
    return (f'<div class="MovieCard card h-100 border-0 rounded-0 shadow-sm">'
            f'<a href="{BASE}/elokuvat/{slug}.html" class="MovieCard__PosterLink">{img}</a>'
            f'<div class="card-body d-flex flex-column text-center">'
            f'<h2 class="font-size-h5 mb-3">{title}</h2>'
            f'<ul class="list-unstyled mb-0 font-size-2">'
            f'<li class="mb-2"><strong>Liput: {price}</strong></li>'
            f'<li class="mb-2">Kesto: {kesto}</li>{age}</ul>'
            f'<div class="mt-2 mb-1">Näytösajat:</div>'
            f'<table class="table table-sm mb-0 font-size-1">{rows}</table></div>'
            f'<a class="btn btn-primary" href="{BASE}/elokuvat/{slug}.html">'
            f'Varaa liput &raquo;</a></div>')


def page(*cards):
    return "<html><body><main>" + "".join(cards) + "</main></body></html>"


LISTING = page(
    card("the-odyssey", "The Odyssey", ["Ti 15.09.   klo 18:40"],
         price="15€ (lahja/sarjalippu +2€)", kesto="2 h 53 min", icon="16"),
    card("hetki-ennen-valoa", "Hetki Ennen Valoa",
         ["Ti 15.09.   klo 17:00", "Ke 16.09.   klo 15:00"], icon="7"),
    # The site publishes an empty icon name for a film it gives no age limit.
    card("resident-evil", "Resident Evil", ["Pe 18.09.   klo 20:45"],
         kesto="1 h 34 min", icon=""),
)


class ProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.shows = vaakuna.parse(LISTING, today=TODAY)

    def test_every_row_in_every_card_is_a_screening(self):
        self.assertEqual(len(self.shows), 4)
        self.assertEqual(sorted({s["eventId"] for s in self.shows}),
                         ["hetki-ennen-valoa", "resident-evil", "the-odyssey"])

    def test_each_card_keeps_its_own_price_runtime_and_rating(self):
        by = {s["title"]: s for s in self.shows}
        self.assertEqual((by["The Odyssey"]["rating"], by["The Odyssey"]["len"]),
                         ("K-16", "173"))
        self.assertEqual(by["The Odyssey"]["price"], "15€ (lahja/sarjalippu +2€)")
        self.assertEqual((by["Hetki Ennen Valoa"]["rating"], by["Hetki Ennen Valoa"]["len"]),
                         ("K-7", "87"))
        self.assertEqual(by["Hetki Ennen Valoa"]["price"], "13 €")

    def test_the_age_limit_is_read_from_the_image_name(self):
        self.assertEqual(vaakuna._rating("16"), "K-16")
        self.assertEqual(vaakuna._rating("7"), "K-7")
        self.assertEqual(vaakuna._rating("S"), "S")
        self.assertEqual(vaakuna._rating(""), "",
                         "the site writes icon/.png for a film it does not rate")
        self.assertEqual(vaakuna._rating("kuva"), "")

    def test_a_film_the_site_does_not_rate_publishes_no_rating(self):
        by = {s["title"]: s for s in self.shows}
        self.assertEqual(by["Resident Evil"]["rating"], "")

    def test_no_auditorium_is_invented(self):
        self.assertEqual({s["aud"] for s in self.shows}, {""})

    def test_the_destination_is_the_films_own_page(self):
        for s in self.shows:
            self.assertRegex(s["url"], rf"^{BASE}/elokuvat/[^/]+\.html$")

    def test_every_show_meets_the_contract(self):
        common.check_shows({vaakuna.VENUE["id"]: self.shows}, "vaakuna",
                           {vaakuna.VENUE["id"]})


class YearTest(unittest.TestCase):
    """The page publishes no year. These pin that the parser resolves one rather than
    assuming the current year, and that it never moves a row to a date the page did not
    publish."""

    def test_a_date_later_this_year_stays_in_this_year(self):
        out = vaakuna.parse(page(card("a", "A", ["Ke 23.09.   klo 19:20"])), today=TODAY)
        self.assertEqual(out[0]["start"][:10], "2026-09-23")

    def test_a_january_row_read_in_december_rolls_forward(self):
        """2027-01-05 is a Tuesday and 2026-01-05 is a Monday, so `Ti` settles it."""
        out = vaakuna.parse(page(card("a", "A", ["Ti 05.01.   klo 19:00"])),
                            today=datetime.date(2026, 12, 28))
        self.assertEqual(out[0]["start"][:10], "2027-01-05")

    def test_a_december_row_read_in_january_stays_in_the_past(self):
        """The case a next-occurrence rule gets wrong: on 2 January a page still showing
        28.12. means five days ago, not in eleven months. 2025-12-28 is a Sunday and
        2026-12-28 is a Monday, so the published `Su` says which, without relying on the
        nearest-occurrence tie-break at all."""
        out = vaakuna.parse(page(card("a", "A", ["Su 28.12.   klo 19:00"])),
                            today=datetime.date(2026, 1, 2))
        self.assertEqual(out[0]["start"][:10], "2025-12-28")

    def test_a_weekday_that_would_place_a_row_a_year_out_is_refused(self):
        """15.09. is a Monday in 2025, a Tuesday in 2026 and a Wednesday in 2027. Read on
        2026-09-15 only the Tuesday is within the plausibility bound; `Ma` and `Ke` select
        a candidate roughly a year away, which is what a mistyped weekday looks like, and
        those rows are dropped rather than published as phantom screenings."""
        out = vaakuna.parse(page(card("a", "A", ["Ti 15.09.   klo 19:00"])), today=TODAY)
        self.assertEqual(out[0]["start"][:10], "2026-09-15")
        for wd in ("Ma", "Ke"):
            out = vaakuna.parse(page(card("a", "A", [f"{wd} 15.09.   klo 19:00",
                                                     "Ke 16.09.   klo 20:00"])), today=TODAY)
            self.assertEqual([s["start"][:16] for s in out], ["2026-09-16T20:00"], wd)

    def test_a_weekday_matching_no_candidate_year_is_skipped(self):
        """Only three of the seven weekdays can be right for a given day and month. A
        page printing one of the other four contradicts itself, and the row is not
        placed."""
        out = vaakuna.parse(page(card("a", "A", ["To 15.09.   klo 19:00",
                                                 "Ti 15.09.   klo 20:00"])), today=TODAY)
        self.assertEqual([s["start"][11:16] for s in out], ["20:00"])

    def test_a_stale_row_from_before_today_is_still_placed_correctly(self):
        """Manttu-style: a schedule left up after its weekend. 2026-09-12 is a Saturday,
        so `La 12.09.` read on the 15th is four days ago, not next year."""
        out = vaakuna.parse(page(card("a", "A", ["La 12.09.   klo 19:00"])), today=TODAY)
        self.assertEqual(out[0]["start"][:10], "2026-09-12")

    def test_a_day_and_month_that_name_no_date_in_the_window_are_skipped(self):
        out = vaakuna.parse(page(card("a", "A", ["To 29.02.   klo 19:00",
                                                 "Ti 15.09.   klo 19:00"])), today=TODAY)
        self.assertEqual([s["start"][:10] for s in out], ["2026-09-15"])

    def test_a_repeated_row_is_published_once(self):
        r = "Ti 15.09.   klo 18:40"
        out = vaakuna.parse(page(card("a", "A", [r, r])), today=TODAY)
        self.assertEqual(len(out), 1)


class EmptyAndBrokenTest(unittest.TestCase):
    def test_cards_with_no_screening_is_a_failure(self):
        """No empty state is recorded for this site, and a page rendering film cards is
        not one, so zero rows fails rather than being read as nothing on."""
        with self.assertRaises(RuntimeError) as cm:
            vaakuna.parse(page(card("a", "A", []), card("b", "B", [])), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_rows_in_a_format_the_parser_misses_are_a_failure(self):
        """A year printed after the month, `Ti 15.09.2026`, does not match `SHOW_RE`. The
        cards are still there, so this is a format change and must fail."""
        with self.assertRaises(RuntimeError) as cm:
            vaakuna.parse(page(
                card("a", "A", ["Ti 15.09.2026   klo 18:40", "Ke 16.09.2026   klo 15:00"]),
                card("b", "B", ["Pe 18.09.2026   klo 20:45"])), today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_page_without_a_card_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            vaakuna.parse("<html><body><p>Tervetuloa</p></body></html>", today=TODAY)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)


class SiteTest(unittest.TestCase):
    def test_one_venue_in_lohja(self):
        self.assertEqual([v["city"] for v in vaakuna.SITES[0]["venues"]], ["Lohja"])


class ResolveYearTest(unittest.TestCase):
    """`common.resolve_year` itself: three adapters will share it, so it is pinned on its
    own rather than only through one parser."""

    def test_nearest_occurrence_wins_in_both_directions(self):
        self.assertEqual(common.resolve_year(28, 12, datetime.date(2026, 1, 2)), 2025)
        self.assertEqual(common.resolve_year(5, 1, datetime.date(2026, 12, 28)), 2027)

    def test_a_date_in_the_same_year_is_that_year(self):
        self.assertEqual(common.resolve_year(15, 9, datetime.date(2026, 9, 15)), 2026)
        # 1 July is 76 days back, outside the default window but correctly *selected*:
        # without a window it resolves, with one it is refused rather than moved.
        self.assertEqual(common.resolve_year(1, 7, datetime.date(2026, 9, 15),
                                             window=None), 2026)
        self.assertIsNone(common.resolve_year(1, 7, datetime.date(2026, 9, 15)))

    def test_the_window_refuses_a_candidate_it_never_replaces_it(self):
        """Reported 2026-09-15 and fixed here. `18.3.` read on 15 September has its nearest
        occurrence 181 days back; the old code filtered that out *before* choosing and
        returned next March, 184 days ahead, which the documented nearest-occurrence rule
        never says. Selection happens first now, so the answer is that year or nothing."""
        today = datetime.date(2026, 9, 15)
        self.assertEqual(common.resolve_year(18, 3, today, window=None), 2026,
                         "the rule selects the nearer past occurrence")
        self.assertIsNone(common.resolve_year(18, 3, today),
                          "and the window refuses it rather than substituting 2027")

    def test_the_order_is_select_then_bound_shown_at_the_width_it_matters(self):
        """The ordering is only observable once the window is wide enough for a
        non-nearest candidate to fall inside it, which needs about 183 days: below that,
        anything within the window is necessarily the nearest, because the other candidates
        are 365 days from it. The bug was reported at (180, 300), so it is pinned there.

        `18.3.` read on 15 September: nearest is 2026, 181 days back, just outside 180.
        Selecting first gives that year and then refuses it. Filtering first discards it and
        leaves 2027, 184 days ahead, which the nearest-occurrence rule never says."""
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(common.resolve_year(18, 3, today, window=(180, 300)))
        self.assertEqual(common.resolve_year(18, 3, today, window=(182, 300)), 2026,
                         "one day wider and the nearest occurrence itself is admitted")

    def test_a_stale_listing_with_a_wrong_weekday_cannot_reach_far_into_the_future(self):
        """Also reported. `Ti 1.6.` read on 15 September selects 2027, because 1 June 2027
        is the Tuesday, 259 days ahead. No source here publishes near that far, so it is
        refused. This is the failure the window exists for."""
        today = datetime.date(2026, 9, 15)
        self.assertEqual(common.resolve_year(1, 6, today, common.weekday_index("Ti"),
                                             window=None), 2027)
        self.assertIsNone(common.resolve_year(1, 6, today, common.weekday_index("Ti")))

    def test_the_window_is_the_callers_and_each_adapter_measured_its_own(self):
        import kirkkonummi, kuvakukko, vaakuna as vk
        for mod in (vk, kuvakukko, kirkkonummi):
            self.assertEqual(mod.WINDOW, (30, 60), mod.__name__)

    def test_a_tie_goes_to_the_future(self):
        """A real tie, not an approximate one. It needs a leap year to be reachable at
        all: on 2027-08-31, 01.03. is 183 days back to 2027-03-01 and 183 days forward to
        2028-03-01, and the coming one is the one meant. The first case written here was
        181 against 184 days, which is not a tie, and the mutation that flips the
        tie-break scored VOID against it."""
        self.assertEqual(common.resolve_year(1, 3, datetime.date(2027, 8, 31),
                                             window=None), 2028)
        # With the default window the same date is 183 days out and refused. Selection and
        # plausibility are separate questions and this pins both answers.
        self.assertIsNone(common.resolve_year(1, 3, datetime.date(2027, 8, 31)))

    def test_a_weekday_selects_uniquely_within_the_window(self):
        """At most one candidate year can carry a given weekday. That makes the selection
        unambiguous given the window; it does not make it the intended date, which is why
        the bound below exists."""
        self.assertEqual(common.resolve_year(15, 9, datetime.date(2026, 9, 15),
                                             common.weekday_index("Tiistai")), 2026)
        # A weekday naming a candidate inside the bound still selects it.
        self.assertEqual(common.resolve_year(5, 1, datetime.date(2026, 12, 28),
                                             common.weekday_index("Tiistai")), 2027)

    def test_a_candidate_outside_the_plausibility_bound_is_refused(self):
        """`Ma 15.09.` read on 2026-09-15 selects 2025, a year behind, and `Ke` selects
        2027, a year ahead. Both are what a mistyped weekday produces, and a phantom
        screening a year out is the one the client would not hide."""
        for wd in ("Maanantai", "Keskiviikko"):
            self.assertIsNone(common.resolve_year(15, 9, datetime.date(2026, 9, 15),
                                                  common.weekday_index(wd)), wd)

    def test_the_window_is_wide_enough_for_what_these_sources_publish(self):
        """Measured live on 2026-09-15: Vaakuna +0..+9, Kuvakukko +0..+9, Manttu -4..-2,
        Kirkkonummi -1..+9. The window is several times that span in both directions."""
        today = datetime.date(2026, 9, 15)
        for offset in (-20, -4, 0, 9, 45, 59):
            when = today + datetime.timedelta(days=offset)
            self.assertEqual(
                common.resolve_year(when.day, when.month, today, when.weekday()),
                when.year, f"{offset:+d} days should resolve")
        for offset in (-40, 75, 200):
            when = today + datetime.timedelta(days=offset)
            self.assertIsNone(
                common.resolve_year(when.day, when.month, today, when.weekday()),
                f"{offset:+d} days is outside what these cinemas publish")

    def test_a_weekday_no_candidate_year_can_satisfy_resolves_to_nothing(self):
        for wd in ("Torstai", "Perjantai", "Lauantai", "Sunnuntai"):
            self.assertIsNone(common.resolve_year(15, 9, datetime.date(2026, 9, 15),
                                                  common.weekday_index(wd)), wd)

    def test_weekday_index_reads_full_names_and_abbreviations(self):
        self.assertEqual(common.weekday_index("Tiistai"), 1)
        self.assertEqual(common.weekday_index("ti"), 1)
        self.assertEqual(common.weekday_index("TI"), 1)
        self.assertEqual(common.weekday_index("Sunnuntai"), 6)
        self.assertIsNone(common.weekday_index("xx"))
        self.assertIsNone(common.weekday_index(""))
        self.assertIsNone(common.weekday_index(None))

    def test_an_unreadable_weekday_falls_back_to_nearest(self):
        """A row with no weekday, or one this table does not know, still resolves."""
        self.assertEqual(common.resolve_year(28, 12, datetime.date(2026, 1, 2),
                                             common.weekday_index("xx")), 2025)

    def test_no_candidate_year_holds_the_date(self):
        self.assertIsNone(common.resolve_year(29, 2, datetime.date(2026, 9, 15)))
        self.assertEqual(common.resolve_year(29, 2, datetime.date(2024, 3, 1)), 2024)


if __name__ == "__main__":
    unittest.main()
