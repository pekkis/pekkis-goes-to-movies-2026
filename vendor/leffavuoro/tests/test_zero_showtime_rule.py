"""A provider that parses zero showtimes fails the run, for every half of the pipeline.

CLAUDE.md states the rule and `run.Tally.site` holds the run-level backstop: a site with no
live venue that its adapter did not confirm empty counts as a failure. A mutation turning
that line off survived the whole suite on 2026-09-25 (audit Q), because every test that
reached it had a second reason to fail. Two sites here, one live, so the run's own "no
venue at all" check cannot stand in for it. The Finnkino pass in `fetch_data.py` had no
whole-run check at all (audit A2): a renamed `showtimes` key published seventeen venues
empty under a fresh `areas.json`.
"""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import types
import unittest

import _ctx                                                # noqa: F401
import common
import fetch_data
import run
import test_finnkino_partial as tfp
from test_run_partial import show

NOW = "2026-09-26T12:00:00+03:00"


def module(name, answers, confirms=False):
    """An adapter whose sites answer from `answers` by provider id."""
    mod = types.ModuleType(name)
    mod.SITES = [{"provider": pid, "label": pid.title(), "base": f"https://{pid}.test",
                  "venues": [{"id": f"{pid}-v", "name": pid.title(), "short": pid.title(),
                              "city": "Espoo"}]} for pid in answers]
    if confirms:
        mod.EMPTY_VENUES_CONFIRMED = True

    def fetch_site(site):
        got = answers[site["provider"]]
        if isinstance(got, Exception):
            raise got
        if not isinstance(got, int):
            return got                      # a mapping as the adapter would return it
        return {f"{site['provider']}-v": [dict(show("Film", "2027-01-09T18:00:00+02:00"),
                                               venue=f"{site['provider']}-v",
                                               provider=site["provider"])] * got}
    mod.fetch_site = fetch_site
    return mod


class RunTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        saved = run.OUT
        run.OUT = pathlib.Path(tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", saved))

    def main(self, mod):
        sys.modules[mod.__name__] = mod
        self.addCleanup(sys.modules.pop, mod.__name__, None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = run.main([mod.__name__, "--half", "all"])
        return code, out.getvalue()

    def test_a_site_with_no_live_venue_fails_the_run_beside_a_live_one(self):
        code, log = self.main(module("zz_zero_a", {"zzlive": 1, "zzdead": {}}))
        self.assertEqual(code, 1, log)

    def test_the_same_site_confirmed_empty_by_its_adapter_does_not(self):
        code, log = self.main(module("zz_zero_b", {"zzlive": 1, "zzdead": {"zzdead-v": []}},
                                     confirms=True))
        self.assertEqual(code, 0, log)

    def test_an_empty_programme_does_not_either(self):
        code, log = self.main(module("zz_zero_c", {"zzlive": 1,
                                                   "zzdead": common.EmptyProgramme("none")}))
        self.assertEqual(code, 0, log)


class FinnkinoTest(unittest.TestCase):
    """The Finnkino pass, driven the way `test_finnkino_partial` drives it."""
    setUp = tfp.SevenDayPublishTest.setUp
    restore_env = tfp.SevenDayPublishTest.restore_env
    stub = tfp.SevenDayPublishTest.stub
    seed_previous = tfp.SevenDayPublishTest.seed_previous

    def test_seven_answered_days_with_no_showtime_publish_nothing_and_fail(self):
        """OCAPI renames `showtimes`: every date answers, none lists a screening."""
        before = self.seed_previous()
        orig = tfp.showtimes_for

        def renamed(date):
            doc = orig(date)
            doc["shows"] = doc.pop("showtimes")
            return doc
        tfp.showtimes_for = renamed
        self.addCleanup(lambda: setattr(tfp, "showtimes_for", orig))
        self.stub()
        self.assertEqual(fetch_data.main(), 1)
        after = {p.name: p.read_bytes() for p in sorted((self.root / "data").glob("*.json"))}
        self.assertEqual(before, after)
        self.assertIn("no showtime", self.err.getvalue())

    def test_a_normal_week_still_publishes(self):
        self.seed_previous()
        self.stub()
        self.assertEqual(fetch_data.main(), 0, self.err.getvalue())


if __name__ == "__main__":
    unittest.main()
