"""Pyhäsalmen VPK: a My Calendar route, a declared category and a tariff page.

The fixtures are the payload as read on 2026-09-19. What they exist to prove:

- **The category filter is checked rather than trusted**, because the route answers the
  same empty list to a category that does not exist as to a quiet season.
- **An empty window is confirmed against the past year**, which is what separates the
  cinema's eight-week summer gap from a calendar that has been renumbered.
- **Both times are read.** The local clock and the Unix instant have to agree.
- **The tariff is the cinema's own page**, and a page that will not answer costs the
  amount and never the programme.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import registry
import run
import vpk as V


SITE = V.SITES[0]
INFO_URL = "https://www.pyhasalmenvpk.fi/pyhasalmen-vpkn-elokuvat"
TODAY = datetime.date(2026, 9, 19)
FI = V.FI
PRICE_PAGE = ("<html><body><h2>Liput ja hinnat</h2>"
              "<p>Elokuvien lipunmyynnin puhelin: 044 7769 724</p>"
              "<p>Lipunmyynti avoinna: 0,5 h ennen esitystä.</p>"
              "<p>Elokuvalipun hinta: 12 euroa.</p>"
              "<p>Maksuvälineenä käy: Pankkikortti, käteinen.</p></body></html>")


def event(occur_id, title, local, category="1", extra=None):
    start = datetime.datetime.strptime(local, "%Y-%m-%d %H:%M:%S").replace(tzinfo=FI)
    out = {
        "occur_id": str(occur_id),
        "occur_event_id": str(occur_id),
        "occur_begin": local,
        "occur_end": local,
        "ts_occur_begin": str(int(start.timestamp())),
        "event_title": title,
        "event_desc": "",
        "event_image": "http://www.pyhasalmenvpk.fi/wp-content/uploads/poster.jpg",
        "category_id": str(category),
        "category_name": "Elokuvat" if str(category) == "1" else "Muut",
        "categories": [{"category_id": str(category),
                        "category_name": "Elokuvat" if str(category) == "1" else "Muut"}],
    }
    out.update(extra or {})
    return out


def payload(*events):
    out = {}
    for e in events:
        out.setdefault(e["occur_begin"][:10], []).append(e)
    return out


TWO = payload(event(255, "Rakkautta ja Virtahepoja", "2026-09-25 18:00:00"),
              event(256, "Lapin sota", "2026-10-23 18:00:00"))


class ParseTest(unittest.TestCase):
    def test_every_occurrence_becomes_a_screening(self):
        shows = V.parse(SITE, TWO, "12€")
        self.assertEqual([(s["title"], s["start"]) for s in shows],
                         [("Rakkautta ja Virtahepoja", "2026-09-25T18:00:00+03:00"),
                          ("Lapin sota", "2026-10-23T18:00:00+03:00")])

    def test_an_event_outside_the_declared_category_fails_the_site(self):
        """The route takes the filter as a request, so the answer is checked."""
        with self.assertRaises(V.FeedError):
            V.parse(SITE, payload(event(255, "Rakkautta ja Virtahepoja", "2026-09-25 18:00:00"),
                                  event(256, "Kuukausikokous", "2026-10-01 18:00:00",
                                        category="2")))

    def test_a_row_whose_two_times_disagree_fails_the_site(self):
        bad = event(256, "Lapin sota", "2026-10-23 18:00:00")
        bad["ts_occur_begin"] = str(int(bad["ts_occur_begin"]) + 3600)
        with self.assertRaises(V.FeedError):
            V.parse(SITE, payload(event(255, "A", "2026-09-25 18:00:00"), bad))

    def test_a_row_with_no_readable_instant_fails_the_site(self):
        bad = event(256, "Lapin sota", "2026-10-23 18:00:00", extra={"ts_occur_begin": ""})
        with self.assertRaises(V.FeedError):
            V.parse(SITE, payload(event(255, "A", "2026-09-25 18:00:00"), bad))

    def test_a_row_with_no_readable_clock_fails_the_site(self):
        bad = event(256, "Lapin sota", "2026-10-23 18:00:00", extra={"occur_begin": "pian"})
        with self.assertRaises(V.FeedError):
            V.parse(SITE, payload(event(255, "A", "2026-09-25 18:00:00"), bad))

    def test_a_row_with_no_title_fails_the_site(self):
        bad = event(256, "", "2026-10-23 18:00:00")
        with self.assertRaises(V.FeedError):
            V.parse(SITE, payload(event(255, "A", "2026-09-25 18:00:00"), bad))

    def test_one_occurrence_listed_twice_publishes_once(self):
        e = event(255, "Rakkautta ja Virtahepoja", "2026-09-25 18:00:00")
        shows = V.parse(SITE, {"2026-09-25": [e, dict(e)],
                               "2026-10-23": [event(256, "Lapin sota", "2026-10-23 18:00:00")]})
        self.assertEqual(len(shows), 2)

    def test_the_route_says_nothing_with_an_empty_list(self):
        self.assertEqual(V.occurrences([]), [])
        self.assertEqual(V.parse(SITE, []), [])

    def test_a_list_with_something_in_it_is_a_shape_this_parser_refuses(self):
        """Reading it as nothing would empty the venue on a changed payload, and reading
        it as events would guess at a shape the endpoint has never returned."""
        with self.assertRaises(V.FeedError):
            V.occurrences([event(255, "A", "2026-09-25 18:00:00")])
        with self.assertRaises(V.FeedError):
            V.occurrences("[]")

    def test_the_fields_the_calendar_cannot_settle_stay_empty(self):
        """The one-hour end is the plugin's default, the image has no dimensions anywhere,
        and `event_desc` was empty on 56 of 57 occurrences."""
        s = V.parse(SITE, TWO, "12€")[0]
        self.assertEqual((s["len"], s["rating"], s["img"], s["lang"], s["genres"]),
                         ("", "", "", "", ""))
        self.assertNotIn("_syn", s)

    def test_the_show_shape(self):
        s = V.parse(SITE, TWO, "12€")[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("pyhasalmenvpk", "pyhasalmenvpk-pyhajarvi", "Pyhäsalmen VPK", ""))
        self.assertEqual((s["price"], s["url"], s["soldOut"], s["original"], s["method"]),
                         ("12€", INFO_URL, False, "", ""))
        self.assertEqual(s["eventId"], "rakkautta ja virtahepoja")
        self.assertEqual(registry.by_id("pyhasalmenvpk")["book"], "door")


class TariffTest(unittest.TestCase):
    def test_the_pages_one_amount_is_the_price(self):
        self.assertEqual(V.tariff(SITE, fetch_page=lambda url: PRICE_PAGE), "12€")

    def test_two_different_amounts_settle_nothing(self):
        page = PRICE_PAGE.replace("</body>", "<p>Elokuvalipun hinta: 10 euroa</p></body>")
        self.assertEqual(V.tariff(SITE, fetch_page=lambda url: page), "")

    def test_the_same_amount_twice_is_not_ambiguous(self):
        page = PRICE_PAGE.replace("</body>", "<p>Elokuvalipun hinta: 12 euroa</p></body>")
        self.assertEqual(V.tariff(SITE, fetch_page=lambda url: page), "12€")

    def test_a_page_stating_no_amount_settles_nothing(self):
        page = "<html><body><p>Lipunmyynti avoinna 0,5 h ennen esitystä.</p></body></html>"
        self.assertEqual(V.tariff(SITE, fetch_page=lambda url: page), "")

    def test_the_url_is_the_cinemas_own_page(self):
        asked = []
        V.tariff(SITE, fetch_page=lambda url: asked.append(url) or PRICE_PAGE)
        self.assertEqual(asked, [INFO_URL])


class WindowTest(unittest.TestCase):
    def test_the_request_names_the_window_and_the_category(self):
        url = V.events_url(SITE, TODAY, TODAY + datetime.timedelta(days=180))
        self.assertIn("/wp-json/my-calendar/v1/events", url)
        self.assertIn("from=2026-09-19", url)
        self.assertIn("to=2027-03-18", url)
        self.assertIn("category=1", url)

    def test_an_answer_that_is_not_json_fails_the_site(self):
        with self.assertRaises(V.FeedError):
            V.window(SITE, TODAY, TODAY, fetch_json=lambda url: "<html>Just a moment...</html>")


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
        self._fetch = V.fetch
        self.addCleanup(lambda: setattr(V, "fetch", self._fetch))

    def serve(self, ahead, back=None, price=PRICE_PAGE):
        """`ahead` answers the forward window, `back` the look-back one."""
        state = {"calls": 0}

        def fetch(url, **kw):
            if "/wp-json/" in url:
                state["calls"] += 1
                body = ahead if state["calls"] == 1 else (back if back is not None else [])
                if isinstance(body, Exception):
                    raise body
                return json.dumps(body).encode("utf-8")
            if isinstance(price, Exception):
                raise price
            return price.encode("utf-8")
        V.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["vpk"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        d = datetime.datetime.now(FI) + datetime.timedelta(days=days)
        return d.replace(hour=18, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%d %H:%M:%S")

    def test_the_site_publishes(self):
        self.serve(payload(event(255, "Rakkautta ja Virtahepoja", self.soon(6)),
                           event(256, "Lapin sota", self.soon(34))))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads(
            (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertEqual({s["price"] for s in shows}, {"12€"})
        self.assertIn("0 failures", log)

    def test_a_quiet_season_with_a_live_category_writes_a_fresh_empty_file(self):
        (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").write_text(json.dumps(self.PREV))
        self.serve([], back=payload(event(9, "Passenger", "2026-05-29 18:00:00")))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme at the moment", log)
        body = json.loads((run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").read_text())
        self.assertEqual(body["shows"], [])
        self.assertNotEqual(body["generated"], self.PREV["generated"])

    def test_an_empty_category_in_both_windows_fails_and_keeps_the_previous_file(self):
        (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").write_text(json.dumps(self.PREV))
        self.serve([], back=[])
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("changed calendar", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").read_text()), self.PREV)

    def test_a_price_page_that_will_not_answer_costs_the_amount_only(self):
        self.serve(payload(event(255, "Rakkautta ja Virtahepoja", self.soon(6))),
                   price=RuntimeError("HTTP Error 500"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads(
            (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").read_text())["shows"]
        self.assertEqual([s["price"] for s in shows], [""])
        self.assertIn("publish no amount", log)

    def test_a_refused_route_keeps_the_previous_file(self):
        (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-pyhasalmenvpk-pyhajarvi.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("pyhasalmenvpk")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Pyhäsalmen VPK", "pyhasalmenvpk.fi", "door", "vpk", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in V.SITES], ["https://www.pyhasalmenvpk.fi"])
        self.assertEqual(len(run.host_groups(V.SITES)), 1)

    def test_the_category_is_declared_by_id(self):
        self.assertEqual(SITE["category"], 1)
        self.assertIsInstance(SITE["category"], int)

    def test_the_label_is_the_venue_name_and_the_city_is_the_municipality(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("pyhasalmenvpk")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Pyhäjärvi")


if __name__ == "__main__":
    unittest.main()
