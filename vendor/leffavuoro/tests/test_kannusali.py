"""The Kannusali reader: the listing's own POST to espoo.fi's events service, paged.

Hits follow the shape read on 2026-10-13, seven of them over two pages of four.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import common
import kannusali as K
import registry
import run


SITE = K.SITES[0]
VENUE = SITE["venues"][0]["id"]
URL = SITE["base"] + SITE["path"]
EVENT = "/fi/tapahtumat/espooevents:"


def hit(hid, title, start, end=None, free=True):
    if end is None:
        two = datetime.datetime.fromisoformat(start) + datetime.timedelta(hours=2)
        end = two.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": "event:espooevents:" + hid, "title": title, "path": EVENT + hid,
            "eventStartTime": start, "eventEndTime": end,
            "topics": ["Elokuvat", "Kulttuuritapahtumat"], "isFreeEvent": free,
            "location": "Kannusali", "eventImages": [{"url": "https://example.invalid/i.jpg"}]}


KEVLAR = hit("agqam3geym", "Elokuva: Kevlarsjäl (K12)", "2026-10-21T11:00:00Z")
ISANPAIVA = hit("agqaol4qfu", "Elokuva: Isänpäivä (K7)", "2026-11-08T12:00:00Z")
FLOW_KIDS = hit("agqaw7ipcm", "Lasten viikonloppu, Elokuva: Flow. (K7)", "2026-11-22T12:00:00Z")
FLOW = hit("agqaw5sf2u", "Elokuva: Flow. (K7)", "2026-11-22T12:00:00Z")
FESTIVAL = hit("agqfestiva", "Espoo Ciné Film Festival Kannusalissa 2026",
               "2026-08-21T14:00:00Z", "2026-08-23T15:00:00Z", free=False)
SNOWMAN = hit("agqbi7fj4u", "Lumiukko - Elokuvakonsertti", "2026-12-16T16:00:00Z",
              "2026-12-16T16:30:00Z", free=False)
SNOWMAN2 = hit("agqbi7q5w4", "Lumiukko - Elokuvakonsertti", "2026-12-16T17:30:00Z",
               "2026-12-16T18:00:00Z", free=False)
# The Flow row with the larger id sits on page 1 and its twin on page 2.
HITS = [KEVLAR, FLOW_KIDS, FESTIVAL, ISANPAIVA, FLOW, SNOWMAN, SNOWMAN2]


class RowsTest(unittest.TestCase):
    def rows(self, *hits):
        return K.rows(SITE, list(hits))

    def test_the_utc_instant_is_published_as_helsinki_local_on_both_sides_of_the_change(self):
        shows, _ = self.rows(KEVLAR, ISANPAIVA)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-10-21T14:00:00+03:00", "2026-11-08T14:00:00+02:00"])

    def test_a_span_over_24_hours_is_left_out_and_counted(self):
        shows, report = self.rows(FESTIVAL, KEVLAR)
        self.assertEqual([s["title"] for s in shows], ["Kevlarsjäl"])
        self.assertEqual(report["long"], ["event:espooevents:agqfestiva "
                                          "(Espoo Ciné Film Festival Kannusalissa 2026)"])

    def test_a_span_of_exactly_24_hours_is_kept(self):
        day = hit("agqday", "Elokuva: Päivä", "2026-11-01T10:00:00Z", "2026-11-02T10:00:00Z")
        shows, report = self.rows(day)
        self.assertEqual((len(shows), report["long"]), (1, []))

    def test_a_hit_outside_the_film_topic_fails_the_site(self):
        concert = dict(hit("agqconcert", "Megamuskari", "2026-11-03T10:00:00Z"),
                       topics=["Musiikki", "Kulttuuritapahtumat"])
        with self.assertRaises(K.EventRowError) as e:
            self.rows(KEVLAR, concert)
        self.assertIn("Elokuvat", str(e.exception))

    def test_two_hits_at_one_start_collapse_to_the_smallest_id_in_either_order(self):
        for order in ((FLOW_KIDS, FLOW), (FLOW, FLOW_KIDS)):
            with self.subTest(first=order[0]["id"]):
                shows, report = self.rows(*order)
                self.assertEqual([(s["title"], s["url"]) for s in shows],
                                 [("Flow.", "https://www.espoo.fi" + EVENT + "agqaw5sf2u")])
                self.assertEqual(report["collapsed"], [
                    "event:espooevents:agqaw7ipcm (Lasten viikonloppu, Elokuva: Flow. (K7)), "
                    "same start as event:espooevents:agqaw5sf2u"])

    def test_hits_at_different_minutes_are_all_kept(self):
        shows, report = self.rows(SNOWMAN, SNOWMAN2)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-12-16T18:00:00+02:00", "2026-12-16T19:30:00+02:00"])
        self.assertEqual(report["collapsed"], [])

    def test_a_free_hit_is_free_admission_and_a_paid_one_publishes_no_price(self):
        shows, _ = self.rows(KEVLAR, SNOWMAN)
        self.assertEqual([(s["title"], s["price"]) for s in shows],
                         [("Kevlarsjäl", "Vapaa pääsy"),
                          ("Lumiukko - Elokuvakonsertti", "")])

    def test_the_title_drops_its_prefix_and_its_closing_mark_which_is_the_rating(self):
        allowed = hit("agqsallit", "Elokuva: Muumit (S)", "2026-11-29T12:00:00Z")
        shows, _ = self.rows(KEVLAR, ISANPAIVA, allowed, SNOWMAN)
        self.assertEqual([(s["title"], s["rating"], s["eventId"]) for s in shows], [
            ("Kevlarsjäl", "K-12", "kevlarsjäl"),
            ("Isänpäivä", "K-7", "isänpäivä"),
            ("Muumit", "S", "muumit"),
            ("Lumiukko - Elokuvakonsertti", "", "lumiukko-elokuvakonsertti"),
        ])

    def test_only_a_leading_prefix_and_a_closing_kavi_mark_come_off_the_title(self):
        for title, shown in (("Lasten viikonloppu, Elokuva: Flow. (K7)",
                              "Lasten viikonloppu, Elokuva: Flow."),
                             ("Elokuva: Yö (K13)", "Yö (K13)"),
                             ("Elokuva: Flow. (K7) ja keskustelu", "Flow. (K7) ja keskustelu"),
                             ("Elokuvakonsertti: Lumiukko", "Elokuvakonsertti: Lumiukko"),
                             ("ELOKUVA:Sininen (K16)", "Sininen"),
                             ("Elokuva: (K7)", "Elokuva: (K7)")):
            with self.subTest(title=title):
                self.assertEqual(K.shown_title(title), shown)

    def test_a_mark_that_is_not_a_closing_kavi_class_is_no_rating(self):
        for title in ("Elokuva: Flow. (K7) ja keskustelu", "Elokuva: Yö (K13)",
                      "Elokuva: Sininen (7)", "ELLIMEI S/K18"):
            with self.subTest(title=title):
                self.assertEqual(K.rating_of(title), "")

    def test_the_link_is_the_event_page_and_no_image_is_published(self):
        s = self.rows(KEVLAR)[0][0]
        self.assertEqual(s["url"], "https://www.espoo.fi/fi/tapahtumat/espooevents:agqam3geym")
        self.assertEqual(s["img"], "")

    def test_the_show_shape(self):
        s = self.rows(KEVLAR)[0][0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"], s["lang"],
                          s["method"], s["original"], s["len"], s["genres"], s["soldOut"]),
                         ("kannusali", VENUE, "Kannusali", "", "", "", "", "", "", False))
        self.assertEqual(s["eventId"], "kevlarsjäl")
        common.check_shows({VENUE: [s]}, "kannusali", {VENUE})

    def test_a_hit_it_cannot_read_fails_the_site(self):
        for field, value in (("title", ""), ("path", None), ("path", "fi/tapahtumat/x"),
                             ("eventStartTime", None), ("eventStartTime", "soon"),
                             ("eventStartTime", "2026-11-04T12:00:00"),
                             ("eventEndTime", "later")):
            with self.subTest(field=field, value=value):
                bad = dict(KEVLAR, **{field: value})
                with self.assertRaises(K.EventRowError):
                    self.rows(ISANPAIVA, bad)


class ServiceTest(unittest.TestCase):
    """The service stubbed by URL: it answers slices of `hits` by the body's pagination."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in (("PER_PAGE", 4), ("PAUSE", 0)):
            self.addCleanup(setattr, K, name, getattr(K, name))
            setattr(K, name, value)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = K.get_text
        self.addCleanup(lambda: setattr(K, "get_text", self._get))
        self.calls = []

    def serve(self, hits, total=None, short=False):
        def get_text(url, **kw):
            if url != URL:
                raise AssertionError(f"unexpected request to {url}")
            body = json.loads(kw["data"].decode("utf-8"))
            self.calls.append((body, kw))
            page = body["pagination"]
            got = hits[page["offset"]:page["offset"] + page["perPage"]]
            if short and page["offset"]:
                got = []
            return json.dumps({"total": len(hits) if total is None else total,
                               "hits": [{"_source": h} for h in got], "aggs": {}})
        K.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["kannusali", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def area(self):
        return json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))

    def keep_previous(self):
        kept = {"generated": "2026-10-12T00:00:00+00:00", "dates": ["2026-11-04"],
                "horizon": "2026-11-04",
                "shows": [{"title": "Earlier", "start": "2026-11-04T14:00:00+02:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")

    def test_every_page_is_read_until_the_total_is_covered(self):
        self.serve(HITS)
        with contextlib.redirect_stdout(io.StringIO()):
            shows = K.fetch_site(SITE)[VENUE]
        self.assertEqual([c[0]["pagination"] for c in self.calls],
                         [{"offset": 0, "perPage": 4}, {"offset": 4, "perPage": 4}])
        self.assertEqual([(s["start"][:16], s["title"]) for s in shows], [
            ("2026-10-21T14:00", "Kevlarsjäl"),
            ("2026-11-08T14:00", "Isänpäivä"),
            ("2026-11-22T14:00", "Flow."),
            ("2026-12-16T18:00", "Lumiukko - Elokuvakonsertti"),
            ("2026-12-16T19:30", "Lumiukko - Elokuvakonsertti"),
        ])

    def test_the_request_is_the_listing_s_own_filter(self):
        self.serve(HITS)
        with contextlib.redirect_stdout(io.StringIO()):
            K.fetch_site(SITE)
        body, kw = self.calls[0]
        self.assertEqual(body["filters"]["fixedFilters"]["tprId"], "21430")
        self.assertEqual(body["filters"]["topics"], ["Elokuvat"])
        self.assertEqual((body["langcode"], body["type"], body["showLongLastingEvents"]),
                         ("fi", "event", True))
        self.assertEqual(kw["headers"]["content-type"], "application/json")
        self.assertEqual(kw["headers"]["user-agent"], common.UA)
        self.assertFalse(kw["cache"])

    def test_a_page_with_no_hits_before_the_total_fails(self):
        """It stops at the empty page instead of asking again up to MAX_PAGES times."""
        self.serve(HITS, short=True)
        with self.assertRaisesRegex(RuntimeError, "no hits at offset 4 of a total of 7"):
            K.fetch_site(SITE)
        self.assertEqual(len(self.calls), 2)

    def test_the_run_writes_the_venue_file_and_logs_both_drops(self):
        self.serve(HITS)
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = self.area()["shows"]
        self.assertEqual(len(shows), 5)
        self.assertEqual({s["venue"] for s in shows}, {VENUE})
        self.assertEqual([s["rating"] for s in shows], ["K-12", "K-7", "K-7", "", ""])
        self.assertIn("1 hit(s) spanning over 24 h left out: event:espooevents:agqfestiva", log)
        self.assertIn("collapsed event:espooevents:agqaw7ipcm (Lasten viikonloppu, "
                      "Elokuva: Flow. (K7)), same start as event:espooevents:agqaw5sf2u", log)

    def test_zero_hits_fails_the_run_and_keeps_the_previous_file(self):
        self.keep_previous()
        self.serve([])
        with self.assertRaises(RuntimeError) as ctx:
            K.fetch_site(SITE)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        code, log = self.main()
        self.assertNotEqual(code, 0, log)
        self.assertIn("no hit for place 21430", log)
        self.assertEqual(self.area()["shows"][0]["title"], "Earlier")

    def test_an_unreadable_hit_fails_the_run_and_keeps_the_previous_file(self):
        self.keep_previous()
        self.serve([KEVLAR, dict(ISANPAIVA, eventStartTime="")])
        code, log = self.main()
        self.assertNotEqual(code, 0, log)
        self.assertEqual(self.area()["shows"][0]["title"], "Earlier")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kannusali")
        self.assertIsNotNone(p, "no registry entry for kannusali")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kannusali", "espoo.fi", "list", "kannusali", "cloud"))
        self.assertEqual((p["accent"], p["accentDark"]), ("#00A192", "#81D7B6"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"].upper() == p["accent"].upper()), 1)

    def test_the_venue_is_in_espoo_inside_the_capital_region(self):
        """Its accent is measured against the Espoo view and the Pääkaupunkiseutu row."""
        self.assertEqual({v["city"] for v in SITE["venues"]}, {"Espoo"})
        self.assertIn("Espoo", next(r["cities"] for r in registry.REGIONS
                                    if r["name"] == "Pääkaupunkiseutu"))


class SiteTest(unittest.TestCase):
    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.espoo.fi")
        self.assertNotIn("reads", SITE)
        self.assertEqual(SITE["venues"], [{"id": "kannusali-espoo", "name": "Kannusali",
                                           "short": "Kannusali", "city": "Espoo"}])


if __name__ == "__main__":
    unittest.main()
