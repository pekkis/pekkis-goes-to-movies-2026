"""A screening with no title is dropped and counted, never published as "?".

eTiketti, Nexxo, BioRex and the Finnkino pass wrote `title or "?"`, so a moved H1 or a
renamed `movieTitle` / `movieName` / `title` key would put every row out titled "?" with
real times and exit 0 (audit A6, 2026-09-25). Kinola, Johku and tribe raise instead. The
row goes, the log says how many, and a site whose every row went this way still fails:
nothing about a missing title may turn into an empty programme.
"""
import contextlib
import io
import json
import unittest

import _ctx                                                # noqa: F401
import common
import fetch_data
import nexxo
from test_biorex import TRIPLA, item
from test_etiketti_empty_venue import KEUDA_FILM, Stubbed, cine_listing
import test_finnkino_partial as tfp
from test_nexxo_rooms import PLAIN_VENUE, SITE, row
import biorex


def quiet(fn, *a, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        got = fn(*a, **kw)
    return got, out.getvalue()


class NexxoTest(unittest.TestCase):

    def test_a_row_with_no_title_is_dropped_and_counted(self):
        bare = dict(row(1, "Sali 1", "x"), movieTitle="")
        p = {"shows": {"2026-10-14": [bare, row(1, "Sali 1", "Film B")]}}
        shows, log = quiet(nexxo.parse, p, SITE, PLAIN_VENUE)
        self.assertEqual([s["title"] for s in shows], ["Film B"])
        self.assertIn("1 row(s) with no title", log)

    def test_every_row_without_a_title_is_a_parser_break_not_an_empty_programme(self):
        bare = dict(row(1, "Sali 1", "x"), movieTitle="")
        with self.assertRaises(RuntimeError) as ctx:
            quiet(nexxo.parse, {"shows": {"d": [bare, dict(bare)]}}, SITE, PLAIN_VENUE)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)


class BioRexTest(unittest.TestCase):

    def test_an_item_with_no_movie_name_is_dropped_and_counted(self):
        bare = item(1, "2026-09-26T18:00:00+03:00", TRIPLA["name"]).replace(
            "&quot;movieName&quot;: &quot;Autofiktio&quot;, ", "")
        page = bare + item(2, "2026-09-26T20:00:00+03:00", TRIPLA["name"], title="Troija")
        shows, log = quiet(biorex.parse, page, TRIPLA)
        self.assertEqual([s["title"] for s in shows], ["Troija"])
        self.assertIn("1 row(s) with no title", log)


class ETikettiTest(Stubbed):

    def test_a_film_page_with_no_title_drops_its_rows_and_vouches_for_no_venue(self):
        (out, log) = quiet(self.stub({
            "/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
            "/elokuvat/13/hetki": KEUDA_FILM.replace("<h1>Hetki ennen valoa</h1>", "")
        }).fetch_site, __import__("test_etiketti_empty_venue").site(), sleep=0)
        self.assertEqual(out, {}, "no row published, and no venue confirmed empty")
        self.assertIn("2 row(s) with no title", log)


class FinnkinoTest(unittest.TestCase):
    # The harness, borrowed rather than inherited: a subclass would run its tests again.
    setUp = tfp.SevenDayPublishTest.setUp
    restore_env = tfp.SevenDayPublishTest.restore_env
    stub = tfp.SevenDayPublishTest.stub
    published = tfp.SevenDayPublishTest.published

    def test_a_film_with_no_title_is_dropped_and_counted(self):
        self.stub()
        orig = tfp.showtimes_for

        def titleless(date):
            doc = orig(date)
            doc["relatedData"]["films"][1]["title"] = {"text": ""}
            return doc
        tfp.showtimes_for = titleless
        self.addCleanup(lambda: setattr(tfp, "showtimes_for", orig))
        rc = fetch_data.main()
        self.assertEqual(rc, 0, self.err.getvalue())
        titles = {s["title"] for n in ("area-1.json", "area-2.json")
                  for s in self.published()[n]["shows"]}
        self.assertEqual(titles, {"Filmi A"})


if __name__ == "__main__":
    unittest.main()
