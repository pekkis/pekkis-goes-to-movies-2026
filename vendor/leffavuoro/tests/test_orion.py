"""Cinema Orion: the ticket link a row carries is stored as an absolute URL.

The site published absolute `orion.kinola.ee` links until 2026-09-06 and now publishes
site-relative ones (`/checkout/{uuid}`). Nothing downstream resolves a bare path: the
client's `safeUrl` passes a scheme-less URL through, so the browser resolves it against
leffavuoro.fi and the reader gets a 404 instead of a box office. The fixture follows
cinemaorion.fi's own markup, two `table.kinola-day` blocks so the day loop runs more than
once, and mixes the link shapes one page really carries: a site-relative path, a
festival's own absolute box office, a protocol-relative host and a free-admission row
with no link at all.
"""
import contextlib
import io
import unittest
from urllib.parse import urlsplit

import _ctx                                                # noqa: F401
import orion

TODAY = __import__("datetime").date(2026, 9, 4)
SITE = "https://cinemaorion.fi/"


def row(title, time_, date, link_html, price="8€"):
    return f"""
      <tr>
        <td class='date'>{date}</td>
        <td class='time'>{time_}</td>
        <td class='title'>{title}</td>
        <td class='price'>{price}</td>
        <td class='link'>{link_html}</td>
      </tr>"""


def link(href):
    return f"<a href='{href}'>Osta lippu</a>"


def page(*days):
    out = []
    for heading, rows in days:
        out.append(f"<h3><span>Torstai</span> {heading}</h3>")
        out.append(f"<table class='kinola-day'>{''.join(rows)}</table>")
    return "".join(out)


PAGE = page(
    ("04.09.", [
        row("Troija", "19:00", "04.09.", link("/checkout/f7def1e7")),
        row("Four Minus Three", "21:00", "04.09.",
            link("https://boxoffice.espoocine.fi/tickets/99")),
    ]),
    ("05.09.", [
        row("Dance Around the Fire", "17:30", "05.09.",
            link("//orion.kinola.ee/web/screening/9c2f")),
        row("Kerhon ilta", "20:00", "05.09.", "Vapaa pääsy", price="Vapaa pääsy"),
    ]),
)


class OrionTicketUrlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shows = orion.parse(PAGE, today=TODAY)
        cls.by_title = {s["title"]: s for s in cls.shows}

    def test_the_fixture_parses_both_days(self):
        """Guards the fixture itself: a page that stopped parsing would make every URL
        assertion below vacuous."""
        self.assertEqual(len(self.shows), 4)
        self.assertEqual(sorted({s["start"][:10] for s in self.shows}),
                         ["2026-09-04", "2026-09-05"])

    def test_a_site_relative_link_is_resolved_against_the_site(self):
        """The defect: `/checkout/{uuid}` stored bare reaches the client bare, and the
        browser resolves it against leffavuoro.fi, which answers 404."""
        self.assertEqual(self.by_title["Troija"]["url"],
                         "https://cinemaorion.fi/checkout/f7def1e7")

    def test_a_festival_box_office_link_is_left_alone(self):
        """Espoo Ciné and the other festivals sell on their own hosts. Resolving must not
        drag those onto cinemaorion.fi."""
        self.assertEqual(self.by_title["Four Minus Three"]["url"],
                         "https://boxoffice.espoocine.fi/tickets/99")

    def test_a_protocol_relative_link_gets_a_scheme(self):
        self.assertEqual(self.by_title["Dance Around the Fire"]["url"],
                         "https://orion.kinola.ee/web/screening/9c2f")

    def test_a_row_with_no_link_falls_back_to_the_programme_page(self):
        self.assertEqual(self.by_title["Kerhon ilta"]["url"], SITE)

    def test_every_stored_url_is_absolute_http(self):
        """The invariant that would have caught this on the day the site changed. A URL
        without a scheme and a host is a link to this origin, whatever it was meant to be."""
        for s in self.shows:
            with self.subTest(title=s["title"]):
                parts = urlsplit(s["url"])
                self.assertIn(parts.scheme, ("http", "https"))
                self.assertTrue(parts.netloc, f"no host in {s['url']!r}")


class TitleAttributeTest(unittest.TestCase):
    """The anchor's `title` runs to the quote that opened it. Until 2026-09-27 it stopped at
    either quote, so `title ="Oasis: Don't Look Back in Anger"` published "Oasis: Don"."""

    def test_the_title_runs_to_its_own_closing_quote(self):
        cells = [
            ("<a href='/elokuvat/oasis/' title =\"Oasis: Don't Look Back in Anger\"> x </a>",
             "Oasis: Don't Look Back in Anger"),
            ("<a href='/elokuvat/girl/' title='A Girl&#39;s Story'> x </a>", "A Girl's Story"),
            ("<a href='/elokuvat/best/' title='The \"Best\" Film'> x </a>", 'The "Best" Film'),
        ]
        shows = orion.parse(page(("04.09.", [
            row(cell, f"1{i}:00", "04.09.", link(f"/checkout/{i}"))
            for i, (cell, _) in enumerate(cells)])), today=TODAY)
        self.assertEqual([s["title"] for s in shows], [want for _, want in cells])


class YearTest(unittest.TestCase):
    """The table prints no year. Before 2026-09-19 a private loop took the first candidate
    year inside a -45..+320 window rather than the nearest one, so `1.8.` read on
    2026-09-19 published as 2027-08-01. Two rows in every fixture: the skip is a
    `continue` inside the row loop."""

    def parse(self, page, today=TODAY):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            shows = orion.parse(page, today=today)
        return shows, out.getvalue()

    def test_a_stale_row_is_skipped_and_the_current_one_keeps_its_date(self):
        shows, log = self.parse(page(
            ("04.09.", [row("Troija", "19:00", "Perjantai 04.09.", link("/checkout/a"))]),
            ("01.08.", [row("Vanha", "18:00", "Lauantai 01.08.", link("/checkout/b"))])))
        self.assertEqual([s["title"] for s in shows], ["Troija"])
        self.assertIn("1 row(s) whose date no candidate year places", log)
        self.assertIn("Lauantai 01.08.", log)

    def test_the_cells_weekday_selects_the_year(self):
        """4 September 2026 is a Friday, so a cell calling it Thursday selects 2025 and
        the window refuses it."""
        shows, _ = self.parse(page(
            ("04.09.", [row("Oikea", "19:00", "Perjantai 04.09.", link("/checkout/a")),
                        row("Vaara", "21:00", "Torstai 04.09.", link("/checkout/b"))])))
        self.assertEqual([s["title"] for s in shows], ["Oikea"])

    def test_a_cell_with_no_weekday_falls_back_to_the_nearest_occurrence(self):
        """The fixture the rest of this file uses prints a bare date, and the live page
        prints `Perjantai 18.09.`; both have to work."""
        shows, _ = self.parse(page(
            ("04.09.", [row("A", "19:00", "04.09.", link("/checkout/a")),
                        row("B", "21:00", "05.09.", link("/checkout/b"))])))
        self.assertEqual([s["start"][:10] for s in shows], ["2026-09-04", "2026-09-05"])

    def test_the_window_is_measured_from_what_the_cinema_publishes(self):
        """The committed programme reached -1 to +29 days on 2026-09-19."""
        self.assertEqual(orion.WINDOW, (30, 120))
        for days, published in ((100, True), (150, False)):
            with self.subTest(days=days):
                d = TODAY + __import__("datetime").timedelta(days=days)
                got = orion._iso(d.day, d.month, 18, 0, TODAY, d.weekday())
                self.assertEqual(got[:10], d.isoformat() if published else "")


if __name__ == "__main__":
    unittest.main()
