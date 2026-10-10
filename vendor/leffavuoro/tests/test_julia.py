"""Julia 1&2, Hyvinkää: one programme page, two halls, a two-digit year.

The fixtures follow `juliaelokuvat.fi/ohjelmisto/` as read on 2026-09-15: one
`div.elokuva` per film holding the film-page link, the poster, a `<div id='bNNNN'>` of
`<br>`-separated screenings and the `<strong>`-labelled metadata.

Two films, not one, and two halls: the page splits on the film block and a single-film
fixture would never show a block regex bleeding one film's metadata into the next, which
is the failure this parser is most exposed to. The index block above the programme, which
repeats every title with no screening, is in the fixture for the same reason: it is the
duplicate the parser has to ignore.
"""
import unittest

import _ctx                                                # noqa: F401
import common
import julia

BASE = "https://juliaelokuvat.fi"


def film(slug, title, shows, price="14€ / 12€", age="7", kesto="1t 27min",
         genre="Draama, Kotimainen", poster=True):
    rows = "<br>".join(shows) + "<br>" if shows else ""
    img = (f'<img width="67" height="96" src="{BASE}/wp-content/uploads/2026/09/{slug}.jpg" '
           f'class="alignleft wp-post-image" alt="" loading="lazy" />') if poster else ""
    return (f'<div class="elokuva" style="padding-top:20px;">'
            f'<a href="{BASE}/elokuvat/{slug}/"><h2 style="padding-top: 20px;">{title}</h2></a>'
            f'{img}<br><strong><div id=\'b1826\'>{rows}</div><br></strong>'
            f'<strong>Hinta:</strong> {price}<br>'
            f'<strong>Ikäraja:</strong> {age}<br>'
            f'<strong>Kesto:</strong> {kesto}<br>'
            f'<strong>Genre:</strong> {genre}<br></div>'
            f'<div style=\'float:left\'><br>Synopsis for {title}.</div>')


def index_block(*slugs):
    """The repeat above the programme: every title again, with no screening."""
    return "".join(
        f'<div><span><a href="{BASE}/elokuvat/{s}/" class="">Katso näytösajat tästä </a>'
        f'</span></div>' for s in slugs)


def page(*films):
    return ('<html><body>' + index_block("hetki-ennen-valoa", "presidentin-kyyditys") +
            '<div class="wrap"><div class="entry-content">' + "".join(films) +
            '</div></div></body></html>')


LISTING = page(
    film("hetki-ennen-valoa", "Hetki ennen valoa",
         ["15.09.26 klo 18:00, 1. sali", "16.09.26 klo 18:00, 1. sali"],
         age="7", kesto="1t 27min", genre="Draama, Kotimainen"),
    film("presidentin-kyyditys", "Presidentin kyyditys",
         ["15.09.26 klo 18:30, 2. sali", "16.09.26 klo 18:30, 2. sali"],
         age="12", kesto="1t 45min", genre="Draama, Komedia, Kotimainen"),
)


class ProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.shows = julia.parse(LISTING)

    def test_every_screening_is_read_once(self):
        self.assertEqual(len(self.shows), 4)
        self.assertEqual(sorted({s["start"][:10] for s in self.shows}),
                         ["2026-09-15", "2026-09-16"])

    def test_the_two_digit_year_is_read_not_guessed(self):
        """`15.09.26` publishes its year in two digits, read as 2000+YY.

        The second row is deliberately in a different year from the fixture's own and from
        whatever year the suite runs in: substituting today's year for the published one
        is invisible while the two agree, and that mutation scored VOID until this case
        existed. A parser that guessed would put both rows in the same year."""
        self.assertEqual(self.shows[0]["start"], "2026-09-15T18:00:00+03:00")
        out = julia.parse(page(film("a", "A", ["15.09.27 klo 18:00, 1. sali",
                                               "15.09.29 klo 18:00, 1. sali"])))
        self.assertEqual([s["start"][:10] for s in out], ["2027-09-15", "2029-09-15"])

    def test_a_row_repeated_inside_one_film_block_is_published_once(self):
        """The page prints each screening on its own line; a duplicated line is one
        screening, not two. Without this, removing the dedupe changed nothing."""
        r = "16.09.26 klo 18:00, 1. sali"
        out = julia.parse(page(film("a", "A", [r, r, "16.09.26 klo 20:00, 1. sali"])))
        self.assertEqual(len(out), 2)
        self.assertEqual([s["start"][11:16] for s in out], ["18:00", "20:00"])

    def test_each_film_keeps_its_own_metadata(self):
        """The bleed a block regex causes: one film's runtime or age limit on the next."""
        by = {s["title"]: s for s in self.shows}
        self.assertEqual((by["Hetki ennen valoa"]["rating"], by["Hetki ennen valoa"]["len"]),
                         ("K-7", "87"))
        self.assertEqual((by["Presidentin kyyditys"]["rating"],
                          by["Presidentin kyyditys"]["len"]), ("K-12", "105"))
        self.assertEqual(by["Hetki ennen valoa"]["genres"], "draama, kotimainen")
        self.assertEqual(by["Presidentin kyyditys"]["genres"],
                         "draama, komedia, kotimainen")

    def test_the_hall_becomes_the_shape_every_provider_publishes(self):
        self.assertEqual(sorted({s["aud"] for s in self.shows}), ["Sali 1", "Sali 2"])

    def test_the_index_block_above_the_programme_adds_no_show(self):
        """It repeats both titles with a film link and no screening. Four shows, not six,
        and no show without a start."""
        self.assertEqual(len(self.shows), 4)
        self.assertTrue(all(s["start"] for s in self.shows))

    def test_price_poster_and_destination(self):
        s = self.shows[0]
        self.assertEqual(s["price"], "14€ / 12€")
        self.assertTrue(s["img"].startswith(f"{BASE}/wp-content/uploads/"))
        self.assertEqual(s["url"], f"{BASE}/elokuvat/hetki-ennen-valoa/")

    def test_the_event_id_is_the_slug_and_folds_a_films_runs_together(self):
        runs = [s for s in self.shows if s["eventId"] == "hetki-ennen-valoa"]
        self.assertEqual(len(runs), 2)

    def test_every_show_meets_the_contract(self):
        common.check_shows({julia.VENUE["id"]: self.shows}, "julia", {julia.VENUE["id"]})


class FieldTest(unittest.TestCase):
    def test_the_age_limit_maps_or_yields_nothing(self):
        self.assertEqual(julia._rating("7"), "K-7")
        self.assertEqual(julia._rating("12"), "K-12")
        self.assertEqual(julia._rating("S"), "S")
        self.assertEqual(julia._rating("Sallittu"), "S")
        self.assertEqual(julia._rating("K-16"), "K-16")
        self.assertEqual(julia._rating("ei tiedossa"), "",
                         "an unreadable age limit yields no rating rather than a guess")
        self.assertEqual(julia._rating(""), "")

    def test_runtime_reads_hours_and_minutes(self):
        self.assertEqual(julia._minutes("1t 27min"), "87")
        self.assertEqual(julia._minutes("2t 5min"), "125")
        self.assertEqual(julia._minutes("95min"), "95")
        self.assertEqual(julia._minutes("ei tiedossa"), "")

    def test_runtime_reads_h_and_m_too(self):
        """One film read 2026-10-04 wrote "1h 41m" beside the others' "1t 28min"."""
        self.assertEqual(julia._minutes("1h 41m"), "101")
        self.assertEqual(julia._minutes("2t 55min + väliaika"), "175")
        self.assertEqual(julia._minutes("Kesto 41 mm"), "")

    def test_a_film_with_no_screening_publishes_nothing_for_itself(self):
        out = julia.parse(page(
            film("tulossa", "Tulossa pian", []),
            film("nyt", "Nyt ohjelmistossa", ["20.09.26 klo 19:00, 1. sali"])))
        self.assertEqual([s["title"] for s in out], ["Nyt ohjelmistossa"])

    def test_an_impossible_date_does_not_abort_the_page(self):
        out = julia.parse(page(film("a", "A", ["31.02.26 klo 18:00, 1. sali",
                                               "16.09.26 klo 18:00, 1. sali"])))
        self.assertEqual(len(out), 1)

    def test_a_screening_without_a_hall_still_publishes(self):
        out = julia.parse(page(film("a", "A", ["16.09.26 klo 18:00"])))
        self.assertEqual(out[0]["aud"], "")


class EmptyAndBrokenTest(unittest.TestCase):
    def test_films_listed_with_no_screening_is_a_failure(self):
        """No empty state is recorded for this site, and a page listing films is not one,
        so zero rows fails rather than being read as nothing on."""
        with self.assertRaises(RuntimeError) as cm:
            julia.parse(page(film("a", "A", []), film("b", "B", [])))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_rows_in_a_format_the_parser_misses_are_a_failure(self):
        """A four-digit year, `15.09.2026`, does not match `SHOW_RE`. The page still lists
        both films, so this is a format change and must fail."""
        with self.assertRaises(RuntimeError) as cm:
            julia.parse(page(
                film("a", "A", ["15.09.2026 klo 18:00, 1. sali", "16.09.2026 klo 18:00, 1. sali"]),
                film("b", "B", ["15.09.2026 klo 18:30, 2. sali"])))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_page_without_a_film_block_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            julia.parse("<html><body><p>Tervetuloa</p></body></html>")
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)


class SiteTest(unittest.TestCase):
    def test_one_venue_in_hyvinkaa_identified_as_the_operating_cinema(self):
        site = julia.SITES[0]
        self.assertEqual(site["base"], BASE)
        self.assertEqual([v["city"] for v in site["venues"]], ["Hyvinkää"])
        self.assertEqual(julia.VENUE["name"], "Julia 1&2")


if __name__ == "__main__":
    unittest.main()
