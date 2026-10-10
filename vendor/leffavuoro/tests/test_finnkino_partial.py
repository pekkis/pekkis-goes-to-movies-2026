"""One failed date must not publish a six-day week as a fresh seven-day schedule.

`main()` asks OCAPI for seven business dates. A failed request was logged and skipped, and
the remaining days were written as a new snapshot with a fresh timestamp and exit 0. The
client reads a date's absence from `dates` as "not published yet", so a whole day across
seventeen venues read as unpublished with nothing to surface it. The rule is now all seven
or none, and `areas.json` moved down with the schedule files because its age is what an
external monitor watches.

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


# Two sites, because the venue loop indexes per site and a one-site fixture would not
# show a day going missing from *every* venue -- which is the whole shape of the bug.
SITES = [{"id": 1, "name": {"text": "Tennispalatsi"}},
         {"id": 2, "name": {"text": "Itis"}}]

PREVIOUS = "the file that was already committed"


def showtimes_for(date):
    """One OCAPI response: two venues, two films, one screening each per venue."""
    return {
        "relatedData": {
            "films": [{"id": 10, "title": {"text": "Filmi A"},
                       "originalTitle": {"text": "Film A"},
                       "releaseDate": "2026-01-01", "runtimeInMinutes": 100,
                       "genreIds": [], "censorRatingId": 1, "externalIds": {}},
                      {"id": 11, "title": {"text": "Filmi B"},
                       "originalTitle": {"text": "Film B"},
                       "releaseDate": "2026-02-02", "runtimeInMinutes": 90,
                       "genreIds": [], "censorRatingId": 1, "externalIds": {}}],
            "genres": [], "attributes": [],
            "screens": [{"id": 5, "name": {"text": "Sali 1"}}],
            "censorRatings": [{"id": 1, "classification": {"text": "S"}}],
        },
        "showtimes": [
            {"id": f"{date}-{sid}-{fid}", "filmId": fid, "siteId": sid, "screenId": 5,
             "attributeIds": [], "schedule": {"startsAt": f"{date}T18:00:00"}}
            for sid in (1, 2) for fid in (10, 11)
        ],
    }


class SevenDayPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

        # The token is normally handed in by the local wrapper; get_token() returns it
        # without touching the network when it is set. TMDB_TOKEN is cleared so the
        # enrichment block is skipped -- it has its own test file and is not the subject.
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
        self.dates = [(self.today + datetime.timedelta(days=d)).isoformat()
                      for d in range(7)]

    def restore_env(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def stub(self, fail=()):
        """Answer OCAPI by URL. Dates in `fail` raise the way a transient 5xx does."""
        self.asked = []

        def http_get(url, headers, timeout=25):
            self.asked.append(url)
            if url.endswith("/sites"):
                return json.dumps({"sites": SITES})
            if "/showtimes/by-business-date/" in url:
                date = url.split("/by-business-date/")[1].split("?")[0]
                if date in fail:
                    raise RuntimeError(f"HTTP 503 for {date}")
                return json.dumps(showtimes_for(date))
            raise AssertionError(f"unexpected request: {url}")

        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))

    def seed_previous(self):
        """What a healthy earlier run left behind, and what must survive a failure."""
        data = self.root / "data"
        data.mkdir()
        for name in ("areas.json", "films.json", "area-1.json", "area-2.json"):
            (data / name).write_text(json.dumps({"marker": PREVIOUS}))
        return {p.name: p.read_bytes() for p in sorted(data.glob("*.json"))}

    def published(self):
        return {p.name: json.loads(p.read_text())
                for p in sorted((self.root / "data").glob("*.json"))}

    def dates_in(self, name):
        return self.published()[name].get("dates")

    # -- the reported defect -------------------------------------------------------------

    def test_a_failed_middle_date_publishes_nothing(self):
        """Day three of seven raises. Every venue file must be byte-identical to what
        was already committed, and the exit code non-zero so check_runs.py sees it."""
        before = self.seed_previous()
        self.stub(fail=[self.dates[3]])
        rc = fetch_data.main()
        self.assertEqual(rc, 1)
        after = {p.name: p.read_bytes()
                 for p in sorted((self.root / "data").glob("*.json"))}
        self.assertEqual(before, after)

    def test_the_previous_schedule_is_still_the_previous_schedule(self):
        """Stated on the content rather than the bytes, so a rewrite that produced the
        same file by luck would not pass here."""
        self.seed_previous()
        self.stub(fail=[self.dates[3]])
        fetch_data.main()
        for name in ("area-1.json", "area-2.json"):
            self.assertEqual(self.published()[name], {"marker": PREVIOUS}, name)

    def test_areas_json_is_not_stamped_fresh_by_a_failed_run(self):
        """It was written before the seven requests, so a run that published nothing
        still refreshed the one file whose age answers "when did Finnkino last update".
        An external staleness monitor on that age is on the backlog; this is what would
        have made it lie."""
        self.seed_previous()
        self.stub(fail=[self.dates[0]])
        fetch_data.main()
        self.assertEqual(self.published()["areas.json"], {"marker": PREVIOUS})

    def test_the_failure_names_the_date_it_lost(self):
        self.seed_previous()
        self.stub(fail=[self.dates[3]])
        fetch_data.main()
        err = self.err.getvalue()
        self.assertIn(self.dates[3], err)
        self.assertIn("publishing nothing", err)

    # -- which day fails must not matter -------------------------------------------------

    def test_the_first_date_failing_publishes_nothing(self):
        self.seed_previous()
        self.stub(fail=[self.dates[0]])
        self.assertEqual(fetch_data.main(), 1)
        self.assertEqual(self.published()["area-1.json"], {"marker": PREVIOUS})

    def test_the_last_date_failing_publishes_nothing(self):
        """The tempting exception: only the far end of the horizon is missing, and six
        of seven days look like plenty. It is refused for the same reason as the rest --
        the client cannot tell that day from an unpublished one, and the next run is a
        few hours away."""
        self.seed_previous()
        self.stub(fail=[self.dates[6]])
        self.assertEqual(fetch_data.main(), 1)
        self.assertEqual(self.published()["area-1.json"], {"marker": PREVIOUS})

    def test_several_dates_failing_publishes_nothing(self):
        self.seed_previous()
        self.stub(fail=[self.dates[1], self.dates[4]])
        self.assertEqual(fetch_data.main(), 1)
        self.assertEqual(self.published()["area-2.json"], {"marker": PREVIOUS})

    def test_every_date_failing_publishes_nothing(self):
        self.seed_previous()
        self.stub(fail=self.dates)
        self.assertEqual(fetch_data.main(), 1)
        self.assertEqual(self.published()["area-1.json"], {"marker": PREVIOUS})

    def test_a_first_ever_run_that_fails_creates_no_schedule_at_all(self):
        """No previous files to fall back on. The failure must not leave a half-written
        first snapshot behind either."""
        (self.root / "data").mkdir()
        self.stub(fail=[self.dates[2]])
        self.assertEqual(fetch_data.main(), 1)
        self.assertEqual(sorted(p.name for p in (self.root / "data").glob("*.json")), [])

    # -- and the healthy run still publishes ---------------------------------------------

    def test_seven_good_dates_publish_all_seven(self):
        self.seed_previous()
        self.stub()
        self.assertEqual(fetch_data.main(), 0)
        for name in ("area-1.json", "area-2.json"):
            self.assertEqual(self.dates_in(name), self.dates, name)

    def test_a_healthy_run_still_writes_areas_json(self):
        """areas.json moved to the bottom of main(); this is the test that it is still
        written at all, which a move like that is exactly how you lose."""
        self.seed_previous()
        self.stub()
        fetch_data.main()
        areas = self.published()["areas.json"]
        self.assertEqual([a["name"] for a in areas["areas"]], ["Itis", "Tennispalatsi"])
        self.assertTrue(areas["generated"])

    def test_a_healthy_run_writes_both_venues_and_the_film_list(self):
        self.seed_previous()
        self.stub()
        fetch_data.main()
        out = self.published()
        self.assertEqual(len(out["area-1.json"]["shows"]), 14)   # 7 days x 2 films
        self.assertEqual(len(out["area-2.json"]["shows"]), 14)
        self.assertEqual(sorted(out["films.json"]["films"]), ["10", "11"])

    def test_all_seven_dates_are_actually_requested(self):
        """Guards the loop itself. A fixture that never entered day two would let the
        all-or-nothing rule pass while testing one request."""
        self.seed_previous()
        self.stub()
        fetch_data.main()
        asked = [u.split("/by-business-date/")[1].split("?")[0]
                 for u in self.asked if "/by-business-date/" in u]
        self.assertEqual(asked, self.dates)


if __name__ == "__main__":
    unittest.main()
