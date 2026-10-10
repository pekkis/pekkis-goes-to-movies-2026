"""Kino Akseli: the year a row does not print.

Rows read `Pe 28.08. klo 19:00` and carry no year, so the weekday selects it and
`common.resolve_year` then bounds it. Before 2026-09-19 this module kept a private loop
that took the first candidate year inside a window rather than the nearest one, and a row
46 or more days stale published as next year: `1.8.` read on 2026-09-19 came out as
2027-08-01.

Two rows minimum in every fixture, because the skip is a `continue` inside the row loop.
"""
import contextlib
import datetime
import io
import unittest

import _ctx                                                # noqa: F401
import kinoakseli as K


TODAY = datetime.date(2026, 9, 19)          # a Saturday


def film(slug, title, *rows):
    return ('<p>Draama</p><p>Ikäraja : 12</p><p>Liput : 9€</p>'
            f'<h2 class="elementor-heading-title x"><a href="https://kinoakseli.fi/elokuva-{slug}/">'
            f"{title}</a></h2><p>Näytösajat " + ", ".join(rows) + "</p>")


def parse(page, today=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        shows = K.parse(page, today or TODAY)
    return shows, out.getvalue()


class YearTest(unittest.TestCase):
    def test_the_weekday_places_a_row_that_prints_no_year(self):
        shows, _ = parse(film("autofiktio", "Autofiktio",
                              "Su 20.9. klo 18:00", "Ma 21.9. klo 20:00"))
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T18:00:00+03:00", "2026-09-21T20:00:00+03:00"])

    def test_a_stale_row_is_skipped_and_the_current_one_keeps_its_date(self):
        shows, log = parse(film("autofiktio", "Autofiktio",
                                "La 1.8. klo 18:00", "Su 20.9. klo 18:00"))
        self.assertEqual([s["start"][:10] for s in shows], ["2026-09-20"])
        self.assertIn("1 row(s) whose weekday matches no candidate year", log)
        self.assertIn("La 1.8.", log)

    def test_a_weekday_that_contradicts_its_own_date_is_skipped(self):
        """20 September 2026 is a Sunday; a row calling it Monday selects 2027."""
        shows, log = parse(film("autofiktio", "Autofiktio",
                                "Ma 20.9. klo 18:00", "Su 20.9. klo 20:00"))
        self.assertEqual([s["start"][:16] for s in shows], ["2026-09-20T20:00"])
        self.assertIn("Ma 20.9.", log)

    def test_the_window_is_measured_from_what_the_cinema_publishes(self):
        """The committed programme spanned -1 to +1 day on 2026-09-19 and the site
        publishes about three days at a time."""
        self.assertEqual(K.WINDOW, (30, 60))
        for days, published in ((40, True), (90, False)):
            with self.subTest(days=days):
                d = TODAY + datetime.timedelta(days=days)
                got = K._iso(d.day, d.month, 18, 0, TODAY, d.weekday())
                self.assertEqual(got[:10], d.isoformat() if published else "")


if __name__ == "__main__":
    unittest.main()


def card(slug, title, kesto):
    """The month's-offer card read 2026-10-04: a heading, then the facts, no screening list."""
    return (f'<h2 class="elementor-heading-title x"><a href="https://kinoakseli.fi/elokuva-{slug}/">'
            f'{title}</a></h2><span>Ikäraja : 12</span><span>Draama, Jännitys</span>'
            f'<span>Kesto : {kesto}</span><span>Kuukauden tarjous</span>')


class RuntimeTest(unittest.TestCase):
    """"Kesto : 117min" was on the page and every row published no runtime."""

    def test_a_card_with_the_same_title_gives_the_runtime(self):
        shows, _ = parse(film("verity", "Verityn varjo", "Su 20.9. klo 18:00", "Ma 21.9. klo 20:00")
                         + film("rose", "Rose", "Su 20.9. klo 16:00")
                         + card("verity-2", "Verityn varjo", "117min"))
        self.assertEqual([(s["title"], s["len"]) for s in shows],
                         [("Rose", ""), ("Verityn varjo", "117"), ("Verityn varjo", "117")])

    def test_the_blocks_own_kesto_line_is_read_like_its_rating(self):
        page = film("rose", "Rose", "Su 20.9. klo 16:00").replace(
            "<p>Liput : 9€</p>", "<p>Liput : 9€</p><p>Kesto : 1h 39min</p>")
        shows, _ = parse(page + film("x", "X", "Su 20.9. klo 18:00"))
        self.assertEqual([s["len"] for s in shows], ["99", ""])

    def test_two_cards_disagreeing_settle_nothing(self):
        shows, _ = parse(film("verity", "Verityn varjo", "Su 20.9. klo 18:00", "Ma 21.9. klo 20:00")
                         + card("a", "Verityn varjo", "117min") + card("b", "Verityn varjo", "120min"))
        self.assertEqual({s["len"] for s in shows}, {""})
