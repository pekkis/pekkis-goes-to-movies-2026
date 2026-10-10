"""Kino Hamina: one page, one block per film, one line per screening.

The fixtures are the markup as read on 2026-09-18, cut to the smallest shape that still
exercises a rule. Two screening lines minimum wherever there is a loop.

What they exist to prove:

- **The film's price and the screening's price are different things.** `Liput: 11€` in the
  film's fields is that film's ticket and `| Liput 8€` on a line overrides it for that
  showing alone. A `Liput:` that is a range settles nothing and its rows publish no price.
- **A line prints no year**, so the weekday selects it and a line that cannot be placed
  fails the site rather than disappearing.
- **A block with no screening line is a film with nothing scheduled**, which the page uses
  for a run that has ended. Counted, left out, and not a failure.
- **A landscape image is not a poster.** The films carry portrait artwork with the
  dimensions in the tag.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import hamina as H
import registry
import run


SITE = H.SITES[0]
TODAY = datetime.date(2026, 9, 18)          # a Friday
PAGE_URL = "https://www.hamina.fi/asukkaalle/vapaa-aika/kulttuuri/kino-hamina/"
POSTER = ('<img loading="lazy" width="768" height="1097" '
          'src="https://efeh4kjo5c9.exactdn.com/app/uploads/sites/2/2026/09/juliste.webp" />')
LANDSCAPE = ('<img loading="lazy" width="1200" height="800" '
             'src="https://efeh4kjo5c9.exactdn.com/app/uploads/sites/2/2026/09/banner.webp" />')


def block(title, shows, kesto="1 t 27 min", ikaraja="7", liput="11€", versio="OG",
          img=POSTER):
    meta = "<br />".join(
        [f"Ensi-ilta: 11.09.2026", f"Ikäraja: {ikaraja}", f"Kesto: {kesto}",
         f"Liput: {liput}", f"Versio: <strong>{versio}</strong>", "Levittäjä: B-Plan",
         "Ohjaus: Klaus Härö"])
    lines = "<br />".join(shows)
    return (f'<div class="large-content-showcase columns is-variable is-4">'
            f'<div class="large-content-showcase__image column is-6">{img}</div>'
            f'<div class="large-content-showcase__text column is-6">'
            f'<h3 class="large-content-showcase__title mt-0 mb-5 pb-3 h2">{title}</h3>'
            f'<div class="large-content-showcase__paragraph mt-0 mb-5 is-size-7">'
            f'<p>{meta}</p><p>{lines}</p></div></div></div>')


def page(*blocks):
    return ('<html><body><div class="large-content-showcases__showcases">'
            + "".join(blocks)
            + '</div><div class="large-content-showcases__footer">Tulossa</div>'
              "</body></html>")


TWO = page(block("Hetki ennen valoa",
                 ["Su 20.9. Klo 17:00",
                  "Ke 23.9. Klo 13:00 | <em><strong>Liput 8€</strong></em>"]))


class RowsTest(unittest.TestCase):
    def rows(self, html, today=None):
        return H.rows(SITE, html, today or TODAY)

    def test_the_weekday_places_a_line_that_prints_no_year(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T17:00:00+03:00", "2026-09-23T13:00:00+03:00"])

    def test_a_weekday_no_candidate_year_carries_fails_the_site(self):
        with self.assertRaises(H.ShowRowError):
            self.rows(page(block("A", ["Ma 20.9. Klo 17:00", "Ti 21.9. Klo 13:00"])))

    def test_a_line_outside_the_window_fails_the_site(self):
        with self.assertRaises(H.ShowRowError):
            self.rows(page(block("A", ["Ti 1.6. Klo 17:00", "Ke 2.6. Klo 13:00"])))

    def test_the_line_price_overrides_the_film_price(self):
        shows, report = self.rows(TWO)
        self.assertEqual([s["price"] for s in shows], ["11€", "8€"])
        self.assertEqual(report["no_price"], set())

    def test_a_bracketed_line_price_overrides_it_too(self):
        """The page as read 2026-10-04: `Klo 15:00&nbsp;<strong>(Liput 8€)</strong>`. The
        line above it, with no price of its own, keeps the film's."""
        shows, _ = self.rows(page(block(
            "Rakkautta ja Virtahepoja",
            ["Ke 23.9. Klo 13:00", "To 24.9. Klo 15:00\xa0<strong>(Liput 8€)</strong>"])))
        self.assertEqual([s["price"] for s in shows], ["11€", "8€"])

    def test_a_runtime_reads_hours_as_t_or_h(self):
        """"1 h 42 min" on two films read 2026-10-04 published 42."""
        shows, _ = self.rows(page(block("A", ["Su 20.9. Klo 17:00"], kesto="1 h 42 min"),
                                  block("B", ["Ke 23.9. Klo 13:00"], kesto="1 t 44 min"),
                                  block("C", ["Ke 23.9. Klo 15:00"], kesto="95 min")))
        self.assertEqual({s["title"]: s["len"] for s in shows},
                         {"A": "102", "B": "104", "C": "95"})

    def test_a_film_price_that_is_a_range_settles_nothing(self):
        shows, report = self.rows(page(block(
            "A", ["Su 20.9. Klo 17:00", "Ke 23.9. Klo 13:00 | Liput 8€"],
            liput="8-11€")))
        self.assertEqual([s["price"] for s in shows], ["", "8€"])
        self.assertEqual(report["no_price"], {"A"})

    def test_an_alkaen_film_price_settles_nothing(self):
        shows, _ = self.rows(page(block("A", ["Su 20.9. Klo 17:00", "Ke 23.9. Klo 15:00"],
                                        liput="alk. 8€")))
        self.assertEqual({s["price"] for s in shows}, {""})

    def test_a_block_with_no_screening_line_is_counted_and_left_out(self):
        shows, report = self.rows(page(
            block("Loppunut", ["Elokuva on poistunut ohjelmistosta"]),
            block("Hetki ennen valoa", ["Su 20.9. Klo 17:00", "Ke 23.9. Klo 13:00"])))
        self.assertEqual({s["title"] for s in shows}, {"Hetki ennen valoa"})
        self.assertEqual(report["no_dates"], ["Loppunut"])

    def test_the_portrait_poster_publishes_and_a_landscape_image_does_not(self):
        shows, _ = self.rows(page(
            block("A", ["Su 20.9. Klo 17:00"]),
            block("B", ["Ke 23.9. Klo 13:00"], img=LANDSCAPE)))
        by = {s["title"]: s["img"] for s in shows}
        self.assertTrue(by["A"].endswith("juliste.webp"))
        self.assertEqual(by["B"], "")

    def test_the_version_tag_becomes_the_language(self):
        shows, _ = self.rows(page(
            block("A", ["Su 20.9. Klo 17:00"], versio="OG"),
            block("B", ["Ke 23.9. Klo 13:00"], versio="DUB"),
            block("C", ["To 24.9. Klo 13:00"], versio="3D")))
        self.assertEqual({s["title"]: s["lang"] for s in shows},
                         {"A": "FI-S", "B": "FI-A", "C": ""})

    def test_the_runtime_reads_hours_and_minutes(self):
        for kesto, want in (("1 t 27 min", "87"), ("2 t 10 min", "130"),
                            ("95 min", "95"), ("", "")):
            with self.subTest(kesto=kesto):
                shows, _ = self.rows(page(block("A", ["Su 20.9. Klo 17:00"], kesto=kesto)))
                self.assertEqual(shows[0]["len"], want)

    def test_the_age_limit_reads_a_number_or_s(self):
        for value, want in (("7", "K-7"), ("12", "K-12"), ("S", "S"), ("", "")):
            with self.subTest(value=value):
                shows, _ = self.rows(page(block("A", ["Su 20.9. Klo 17:00"],
                                                ikaraja=value)))
                self.assertEqual(shows[0]["rating"], want)

    def test_every_screening_links_to_the_page_because_there_is_no_ticket_host(self):
        """"Ei ennakkovarauksia" is the page's own line, so nothing is invented."""
        shows, _ = self.rows(TWO)
        self.assertEqual({s["url"] for s in shows}, {PAGE_URL})
        self.assertEqual(registry.by_id("kinohamina")["book"], "door")

    def test_the_show_shape(self):
        shows, _ = self.rows(TWO)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("kinohamina", "kinohamina-hamina", "Kino Hamina", ""))
        self.assertEqual((s["genres"], s["original"], s["method"], s["soldOut"]),
                         ("", "", "", False))
        self.assertEqual(s["eventId"], "hetki ennen valoa")


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
        self._fetch = H.fetch
        self.addCleanup(lambda: setattr(H, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        H.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["hamina"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        return datetime.datetime.now(H.FI).date() + datetime.timedelta(days=days)

    def live_page(self):
        def line(d, clock, price=""):
            wd = ("Ma", "Ti", "Ke", "To", "Pe", "La", "Su")[d.weekday()]
            tail = f" | <strong>Liput {price}</strong>" if price else ""
            return f"{wd} {d.day}.{d.month}. Klo {clock}{tail}"
        return page(block("Hetki ennen valoa",
                          [line(self.soon(1), "17:00"),
                           line(self.soon(2), "13:00", "8€")]))

    def test_the_site_publishes(self):
        self.serve(self.live_page())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-kinohamina-hamina.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertEqual([s["price"] for s in shows], ["11€", "8€"])
        self.assertIn("0 failures", log)

    def test_a_page_with_no_screening_line_fails_and_keeps_the_previous_file(self):
        """No emptied programme has been seen here, so zero rows may not read as one."""
        (run.OUT / "area-kinohamina-hamina.json").write_text(json.dumps(self.PREV))
        self.serve(page(block("Loppunut", ["Elokuva on poistunut ohjelmistosta"])))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("no evidence of one", log)
        self.assertNotIn("no programme published", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinohamina-hamina.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-kinohamina-hamina.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinohamina-hamina.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kinohamina")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Hamina", "hamina.fi", "door", "hamina", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in H.SITES], ["https://www.hamina.fi"])
        self.assertEqual(len(run.host_groups(H.SITES)), 1)

    def test_hamina_is_the_venue_city(self):
        self.assertEqual(SITE["venues"][0]["city"], "Hamina")
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("kinohamina")["label"])


if __name__ == "__main__":
    unittest.main()
