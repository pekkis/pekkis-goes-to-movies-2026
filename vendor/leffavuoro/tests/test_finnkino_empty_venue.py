"""A venue that drops out of the feed must not freeze its file for ever.

OCAPI is asked for seven business dates across every site at once, so a site missing from
the answer cannot be told apart from a site with nothing on. `main()` therefore keeps the
previous file rather than blanking seventeen venues on a partial response, and that rule
stands.

What it did not ask was whether the kept file was worth keeping. Maxim Helsinki, site
1103, ran six screenings on 2026-09-17 and was absent from every business date the next
run asked for. Its file stayed at `07:08:33Z` with six screenings that had all finished,
while the other sixteen moved to `21:12:04Z`. The client ages a combined city view on its
oldest part, so every reader of Helsinki and Paakaupunkiseutu got
"Finnkino: naytostiedot eivat ole paivittyneet (14 h)", and the number climbs for as long
as the venue stays out of the feed.

So a file is kept only while it still describes a day that has not passed. One whose last
day is behind us is published empty instead, with a current timestamp and no dates, which
is the shape three venues already carry from the confirmed-empty path in `run.py`.

www.finnkino.fi answers a datacenter address with a Cloudflare 403, so `main()` is driven
with OCAPI stubbed by URL in a temporary directory. The next run from an ordinary
connection is the operational check.
"""
import contextlib
import datetime
import io
import json
import os
import pathlib
import tempfile
import types
import unittest

import _ctx                                                # noqa: F401
import fetch_data


SITES = [{"id": 1, "name": {"text": "Tennispalatsi"}},
         {"id": 2, "name": {"text": "Maxim"}}]


def showtimes_for(date, present):
    """One OCAPI response. `present` names the sites the answer carries a screening for."""
    return {
        "relatedData": {
            "films": [{"id": 10, "title": {"text": "Filmi A"},
                       "originalTitle": {"text": "Film A"},
                       "releaseDate": "2026-01-01", "runtimeInMinutes": 100,
                       "genreIds": [], "censorRatingId": 1, "externalIds": {}}],
            "genres": [], "attributes": [],
            "screens": [{"id": 5, "name": {"text": "Sali 1"}}],
            "censorRatings": [{"id": 1, "classification": {"text": "S"}}],
        },
        "showtimes": [
            {"id": f"{date}-{sid}-10", "filmId": 10, "siteId": sid, "screenId": 5,
             "attributeIds": [], "schedule": {"startsAt": f"{date}T18:00:00"}}
            for sid in present
        ],
    }


class SpentFileTest(unittest.TestCase):
    """Site 2 answers nothing on every date. What happens to its committed file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

        self.env = {}
        for k, v in (("FINNKINO_TOKEN", "stub-token"), ("TMDB_TOKEN", "")):
            self.env[k] = os.environ.get(k)
            if v:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        self.addCleanup(self.restore_env)

        real_time = fetch_data.time
        fetch_data.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(fetch_data, "time", real_time))
        fetch_data._poster_cache.clear()

        self.err = io.StringIO()
        for redirect in (contextlib.redirect_stdout(io.StringIO()),
                         contextlib.redirect_stderr(self.err)):
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)

        self.today = datetime.date.today()
        self.stub()

    def restore_env(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def stub(self):
        def http_get(url, headers, timeout=25):
            if url.endswith("/sites"):
                return json.dumps({"sites": SITES})
            if "/showtimes/by-business-date/" in url:
                date = url.split("/by-business-date/")[1].split("?")[0]
                return json.dumps(showtimes_for(date, present=(1,)))
            raise AssertionError(f"unexpected request: {url}")

        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))

    def day(self, offset):
        return (self.today + datetime.timedelta(days=offset)).isoformat()

    def seed(self, body):
        """Write site 2's committed file. -> its bytes, for a byte-identical comparison."""
        data = self.root / "data"
        data.mkdir(exist_ok=True)
        p = data / "area-2.json"
        p.write_text(body if isinstance(body, str) else json.dumps(body))
        return p, p.read_bytes()

    def seeded_file(self, last_day):
        return {"generated": "2020-01-01T00:00:00+00:00",
                "dates": [last_day], "horizon": last_day,
                "shows": [{"eventId": "old", "title": "Vanha",
                           "start": f"{last_day}T18:00:00+03:00"}]}

    def published(self, name="area-2.json"):
        return json.loads((self.root / "data" / name).read_text())

    # -- the file still has something ahead, so it is kept ---------------------------------

    def test_a_file_with_a_future_day_is_kept(self):
        p, before = self.seed(self.seeded_file(self.day(3)))
        self.assertEqual(fetch_data.main(), 0)
        self.assertEqual(p.read_bytes(), before, "a live schedule was overwritten")
        self.assertIn("2: no shows, keeping previous file", self.err.getvalue())

    def test_a_file_whose_last_day_is_today_is_kept(self):
        """A day is not over while it is running, so today counts as ahead."""
        p, before = self.seed(self.seeded_file(self.day(0)))
        self.assertEqual(fetch_data.main(), 0)
        self.assertEqual(p.read_bytes(), before)

    def test_an_unreadable_file_is_kept(self):
        """It cannot be shown to be spent, and a disk fault must not delete a schedule."""
        p, before = self.seed("{ not json at all")
        self.assertEqual(fetch_data.main(), 0)
        self.assertEqual(p.read_bytes(), before)

    # -- the file is spent, so it is published empty ---------------------------------------

    def test_a_file_whose_last_day_has_passed_is_published_empty(self):
        self.seed(self.seeded_file(self.day(-1)))
        self.assertEqual(fetch_data.main(), 0)
        doc = self.published()
        self.assertEqual(doc["dates"], [])
        self.assertEqual(doc["shows"], [])
        self.assertEqual(doc["horizon"], "")

    def test_the_republished_file_carries_a_current_timestamp(self):
        """The whole point. A frozen stamp is what put the banner on every Helsinki view."""
        self.seed(self.seeded_file(self.day(-1)))
        self.assertEqual(fetch_data.main(), 0)
        stamp = self.published()["generated"]
        self.assertNotEqual(stamp, "2020-01-01T00:00:00+00:00")
        self.assertTrue(stamp.startswith(datetime.datetime.now(datetime.timezone.utc)
                                         .date().isoformat()), stamp)

    def test_the_log_says_it_published_rather_than_kept(self):
        self.seed(self.seeded_file(self.day(-1)))
        self.assertEqual(fetch_data.main(), 0)
        self.assertIn("nothing left ahead in the kept file", self.err.getvalue())

    # -- the venue that answered is untouched by any of it ---------------------------------

    def test_the_venue_that_answered_still_publishes_its_seven_days(self):
        self.seed(self.seeded_file(self.day(-1)))
        self.assertEqual(fetch_data.main(), 0)
        self.assertEqual(self.published("area-1.json")["dates"],
                         [self.day(d) for d in range(7)])

    def test_a_venue_with_no_file_at_all_still_gets_one(self):
        """areas.json lists every site, so the picker would otherwise link to a 404."""
        (self.root / "data").mkdir(exist_ok=True)
        self.assertEqual(fetch_data.main(), 0)
        self.assertEqual(self.published()["dates"], [])

    # -- areas.json ages on the venue it kept (prior review #17) ----------------------------

    def test_areas_json_ages_on_the_venue_it_kept(self):
        """Site 1 refreshes, site 2 keeps its 2020 file. `generated` is this run, which
        check_staleness.py reads as a run having happened; `oldest` is site 2's stamp."""
        self.seed(self.seeded_file(self.day(3)))
        self.assertEqual(fetch_data.main(), 0)
        areas = self.published("areas.json")
        self.assertEqual(areas["oldest"], "2020-01-01T00:00:00+00:00")
        self.assertEqual(areas["generated"], self.published("area-1.json")["generated"])
        self.assertNotEqual(areas["generated"], areas["oldest"])
        self.assertEqual([a["id"] for a in areas["areas"]], ["2", "1"])

    def test_areas_json_is_as_old_as_the_run_when_nothing_is_kept(self):
        """A spent file is published empty and stamped now, so nothing older remains."""
        self.seed(self.seeded_file(self.day(-1)))
        self.assertEqual(fetch_data.main(), 0)
        areas = self.published("areas.json")
        self.assertEqual(areas["oldest"], areas["generated"])


class HasFutureShowsTest(unittest.TestCase):
    """The decision on its own, including the shapes `main()` does not produce today."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = pathlib.Path(self.tmp.name) / "area-x.json"

    def write(self, doc):
        self.p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
        return self.p

    def test_dates_decide_when_they_are_there(self):
        self.assertTrue(fetch_data.has_future_shows(
            self.write({"dates": ["2026-09-17", "2026-09-19"]}), "2026-09-18"))
        self.assertFalse(fetch_data.has_future_shows(
            self.write({"dates": ["2026-09-16", "2026-09-17"]}), "2026-09-18"))

    def test_todays_date_counts_as_ahead(self):
        self.assertTrue(fetch_data.has_future_shows(
            self.write({"dates": ["2026-09-18"]}), "2026-09-18"))

    def test_horizon_answers_for_a_file_written_before_dates_existed(self):
        self.assertTrue(fetch_data.has_future_shows(
            self.write({"horizon": "2026-09-19"}), "2026-09-18"))
        self.assertFalse(fetch_data.has_future_shows(
            self.write({"horizon": "2026-09-17"}), "2026-09-18"))

    def test_an_already_empty_file_is_not_worth_keeping(self):
        """Otherwise the first empty publish would freeze the stamp all over again."""
        self.assertFalse(fetch_data.has_future_shows(
            self.write({"dates": [], "horizon": "", "shows": []}), "2026-09-18"))

    def test_what_cannot_be_read_is_kept(self):
        self.assertTrue(fetch_data.has_future_shows(self.write("{ broken"), "2026-09-18"))
        self.assertTrue(fetch_data.has_future_shows(self.write([1, 2, 3]), "2026-09-18"))
        missing = pathlib.Path(self.tmp.name) / "nope.json"
        self.assertTrue(fetch_data.has_future_shows(missing, "2026-09-18"))


if __name__ == "__main__":
    unittest.main()
