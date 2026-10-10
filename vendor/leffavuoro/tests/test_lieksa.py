"""Lieksan Kino: one section of a hand-written page, one article per film.

The fixtures are the markup as read on 2026-09-19. What they exist to prove:

- **The coming-soon section is not the programme.** `section-c` renders the same
  `article.entry` markup, so every fixture that matters carries one of each.
- **A listed line that cannot be read fails the site.** The block is counted as well as
  parsed, which is the difference between a failure and a schedule one screening short.
- **The year comes from the weekday**, and a line no candidate year carries raises.
- **The price is the film's own cell**, and the page's voucher and members' discount are
  different products the parser never sees.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import lieksa as L
import registry
import run


SITE = L.SITES[0]
PAGE_URL = "https://www.lieksanelokuvat.net/"
TODAY = datetime.date(2026, 9, 19)          # a Saturday
IMG = "data/images/9c17debc-1340-4342-9a73-01a94ecb965f.jpg"


def line(text):
    return f"<li>\n<p>{text}</p>\n<p></p>\n<p></p>\n</li>"


def article(title, lines=(), price="12&thinsp;€", kesto="75 min", rating="7",
            img=IMG, text="MARKKU PÖLÖSEN UUSIN ELOKUVA!<br />\nKertoo kahdesta ihmisestä."):
    side = ""
    if price or kesto or rating:
        cells = ""
        if price:
            cells += f'<div class="side-row-cell"><h4>Liput:</h4>{price}\n</div>'
        if kesto:
            cells += f'<div class="side-row-cell"><h4>Kesto:</h4>{kesto}\n</div>'
        if rating:
            cells += ('<div class="side-row-cell"><img class="entry-rating-icon" '
                      f'src="graphics/rating-icon-{rating}.svg" alt="Sallittu."></div>')
        shows = ""
        if lines:
            shows = ('<div class="showtimes"><h4>Esitysajat:</h4><ul>'
                     + "".join(lines) + "</ul></div>")
        side = f"<side><div class=\"side-row\">{cells}</div>{shows}</side>"
    image = f'<img class="entry-image" src="{img}" alt="">' if img else ""
    return ('<article class="entry"><div class="entry-top">' + image
            + '<a class="entry-anchor" href="https://www.youtube.com/watch?v=x">Traileri</a>'
            + '</div><div class="entry-bottom">'
            + f"<h3>{title}</h3>"
            + f'<p class="entry-text">{text}</p>{side}</div></article>')


def page(*articles, coming=("RAKKAUTTA JA VIRTAHEPOJA",)):
    later = "".join(article(t, lines=(), price="", kesto="", rating="") for t in coming)
    return ('<html><body><main><div id="main-content-wrap">'
            '<section id="section-a" class="main-section"><h2>Tiedotukset</h2>'
            '<article class="entry"><div class="entry-bottom"><h3>Hyvä asiakas</h3>'
            '<p class="entry-text">Liput ovat ostettavissa aulasta.</p></div></article>'
            "</section>"
            '<section id="section-b" class="main-section"><h2>Elokuvissa nyt</h2>'
            '<div class="upcoming-movie-container">' + "".join(articles) + "</div></section>"
            '<section id="section-c" class="main-section"><h2>Tulossa esitettäväksi</h2>'
            '<div class="upcoming-movie-container">' + later + "</div></section>"
            '<section id="section-d" class="main-section"><h2>Ikärajat</h2></section>'
            "</div></main></body></html>")


TWO = page(article("ORTOTOPOLOGIAN LOPUTTOMAT ALKEET",
                   [line("Su 20.09. 15.00"), line("Ti 22.09. 13.00")]),
           article("MYRSKYN IKKUNA", [line("Su 27.09. 17.00")],
                   price="13&thinsp;€", kesto="100 min", rating="12"))


class RowsTest(unittest.TestCase):
    def rows(self, html, today=None):
        return L.rows(SITE, html, today or TODAY)

    def test_the_weekday_places_a_line_that_prints_no_year(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T15:00:00+03:00", "2026-09-22T13:00:00+03:00",
                          "2026-09-27T17:00:00+03:00"])

    def test_a_weekday_no_candidate_year_carries_fails_the_site(self):
        with self.assertRaises(L.ShowRowError):
            self.rows(page(article("A", [line("Ma 20.09. 15.00"), line("Ti 22.09. 13.00")])))

    def test_a_line_outside_the_window_fails_the_site(self):
        with self.assertRaises(L.ShowRowError):
            self.rows(page(article("A", [line("Ti 01.06. 15.00"), line("Ke 02.06. 13.00")])))

    def test_an_impossible_date_fails_the_site(self):
        with self.assertRaises(L.ShowRowError):
            self.rows(page(article("A", [line("Su 20.09. 15.00"), line("La 31.02. 13.00")])))

    def test_a_listed_line_the_parser_cannot_read_fails_the_site(self):
        """Counted as well as parsed, so a row whose shape moves is never simply missing."""
        with self.assertRaises(L.ShowRowError):
            self.rows(page(article("A", [line("Su 20.09. 15.00"),
                                         line("sunnuntaina kello kolme")])))

    def test_a_film_whose_every_line_moved_shape_fails_the_site(self):
        """The count ran only after `if not found: continue`, so a film whose lines all
        changed shape was dropped as a finished run and the site stayed green (audit A9,
        2026-09-25). One unreadable line beside a readable one already raised."""
        with self.assertRaises(L.ShowRowError):
            self.rows(page(article("A", [line("Su 20.09. klo 18.00"),
                                         line("Ti 22.09. klo 13.00")]),
                           article("B", [line("Su 27.09. 17.00")])))

    def test_the_coming_soon_section_publishes_nothing(self):
        shows, report = self.rows(TWO)
        self.assertEqual({s["title"] for s in shows},
                         {"ORTOTOPOLOGIAN LOPUTTOMAT ALKEET", "MYRSKYN IKKUNA"})
        self.assertEqual(report["no_dates"], [])

    def test_a_coming_soon_film_that_gains_a_date_still_publishes_nothing(self):
        """The section is the boundary, not the presence of a screening line."""
        html = page(article("A", [line("Su 20.09. 15.00")]))
        dated = article("TULOSSA OLEVA", [line("Su 27.09. 19.00")])
        html = html.replace('<h2>Tulossa esitettäväksi</h2>'
                            '<div class="upcoming-movie-container">',
                            '<h2>Tulossa esitettäväksi</h2>'
                            '<div class="upcoming-movie-container">' + dated)
        shows, _ = self.rows(html)
        self.assertEqual([s["title"] for s in shows], ["A"])

    def test_a_film_in_the_programme_with_no_line_is_counted_and_left_out(self):
        shows, report = self.rows(page(
            article("LOPPUNUT", []),
            article("A", [line("Su 20.09. 15.00"), line("Ti 22.09. 13.00")])))
        self.assertEqual({s["title"] for s in shows}, {"A"})
        self.assertEqual(report["no_dates"], ["LOPPUNUT"])

    def test_a_single_amount_publishes_and_anything_else_does_not(self):
        shows, report = self.rows(page(
            article("A", [line("Su 20.09. 15.00")]),
            article("B", [line("Ti 22.09. 13.00")], price="12&thinsp;€ / 10&thinsp;€"),
            article("C", [line("Su 27.09. 17.00")], price="alk. 11&thinsp;€")))
        self.assertEqual([s["price"] for s in shows], ["12€", "", ""])
        self.assertEqual(report["no_price"], {"B", "C"})

    def test_the_rating_is_the_icon_filename(self):
        for icon, want in (("7", "K-7"), ("12", "K-12"), ("16", "K-16"), ("18", "K-18"),
                           ("s", "S"), ("", "")):
            with self.subTest(icon=icon):
                shows, _ = self.rows(page(
                    article("A", [line("Su 20.09. 15.00")], rating=icon),
                    article("B", [line("Ti 22.09. 13.00")], rating=icon)))
                self.assertEqual({s["rating"] for s in shows}, {want})

    def test_an_icon_name_that_is_not_a_classification_publishes_none(self):
        """An unrecognised icon is not a rating to pass through: the client prints
        `rating` verbatim."""
        shows, _ = self.rows(page(
            article("A", [line("Su 20.09. 15.00")], rating="7a"),
            article("B", [line("Ti 22.09. 13.00")], rating="ei-tiedossa")))
        self.assertEqual([s["rating"] for s in shows], ["", ""])

    def test_a_list_elsewhere_in_the_article_does_not_count_as_a_screening_line(self):
        """The count guard is scoped to the showtimes block, so an ordinary list in the
        film's own text cannot fail the site."""
        html = page(article("A", [line("Su 20.09. 15.00"), line("Ti 22.09. 13.00")],
                            text="Palkinnot:<ul><li>Jussi 2026</li></ul>"))
        shows, _ = self.rows(html)
        self.assertEqual(len(shows), 2)

    def test_the_runtime_is_the_kesto_cell(self):
        shows, _ = self.rows(page(
            article("A", [line("Su 20.09. 15.00")], kesto="75 min"),
            article("B", [line("Ti 22.09. 13.00")], kesto="")))
        self.assertEqual([s["len"] for s in shows], ["75", ""])

    def test_the_poster_is_the_articles_own_image_made_absolute(self):
        shows, _ = self.rows(page(
            article("A", [line("Su 20.09. 15.00")]),
            article("B", [line("Ti 22.09. 13.00")], img="")))
        self.assertEqual(shows[0]["img"], "https://www.lieksanelokuvat.net/" + IMG)
        self.assertEqual(shows[1]["img"], "")

    def test_the_synopsis_is_the_films_own_text(self):
        shows, _ = self.rows(TWO)
        self.assertTrue(shows[0]["_syn"].startswith("MARKKU PÖLÖSEN UUSIN ELOKUVA!"))
        self.assertIn("Kertoo kahdesta ihmisestä.", shows[0]["_syn"])
        self.assertNotIn("Liput", shows[0]["_syn"])

    def test_every_screening_links_to_the_page_because_there_is_no_ticket_host(self):
        shows, _ = self.rows(TWO)
        self.assertEqual({s["url"] for s in shows}, {PAGE_URL})
        self.assertEqual(registry.by_id("lieksankino")["book"], "door")

    def test_the_show_shape(self):
        shows, _ = self.rows(TWO)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("lieksankino", "lieksankino-lieksa", "Lieksan Kino", ""))
        self.assertEqual((s["original"], s["method"], s["genres"], s["lang"], s["soldOut"]),
                         ("", "", "", "", False))
        self.assertEqual(s["title"], "ORTOTOPOLOGIAN LOPUTTOMAT ALKEET")
        self.assertEqual(s["eventId"], "ortotopologian loputtomat alkeet")


class RunnerTest(unittest.TestCase):
    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
            "horizon": "2026-09-01",
            "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = L.fetch
        self.addCleanup(lambda: setattr(L, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        L.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["lieksa"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        return datetime.datetime.now(L.FI).date() + datetime.timedelta(days=days)

    def live_page(self):
        def row(d, clock):
            wd = ("Ma", "Ti", "Ke", "To", "Pe", "La", "Su")[d.weekday()]
            return line(f"{wd} {d.day:02d}.{d.month:02d}. {clock}")
        return page(article("A", [row(self.soon(1), "15.00"), row(self.soon(3), "17.00")]),
                    article("B", [row(self.soon(2), "19.00")], price="13&thinsp;€"))

    def test_the_site_publishes(self):
        self.serve(self.live_page())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-lieksankino-lieksa.json").read_text())["shows"]
        self.assertEqual(len(shows), 3)
        self.assertEqual({s["price"] for s in shows}, {"12€", "13€"})
        self.assertIn("0 failures", log)

    def test_a_programme_section_with_no_line_fails_and_keeps_the_previous_file(self):
        """No emptied programme has been seen on this template, so zero rows may not read
        as one."""
        (run.OUT / "area-lieksankino-lieksa.json").write_text(json.dumps(self.PREV))
        self.serve(page(article("LOPPUNUT", [])))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("no evidence", log)
        self.assertNotIn("no programme at the moment", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-lieksankino-lieksa.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-lieksankino-lieksa.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-lieksankino-lieksa.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("lieksankino")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Lieksan Kino", "lieksanelokuvat.net", "door", "lieksa", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in L.SITES],
                         ["https://www.lieksanelokuvat.net"])
        self.assertEqual(len(run.host_groups(L.SITES)), 1)

    def test_the_label_is_the_venue_name(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("lieksankino")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Lieksa")


if __name__ == "__main__":
    unittest.main()
