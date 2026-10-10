"""A Finnkino show carries its film's premiere date while that date is ahead.

The badge read the date from films.json, which the client loads only in English or for a
sheet, so Finnish and Swedish lists never showed it (prior review #26). Driven through
`main()` with OCAPI stubbed, as in test_finnkino_partial.py; a run from an ordinary
connection is the operational check.
"""
import unittest

import _ctx                                                # noqa: F401
import fetch_data
import test_finnkino_partial as tfp


class PremiereOnTheShowTest(unittest.TestCase):
    setUp = tfp.SevenDayPublishTest.setUp
    restore_env = tfp.SevenDayPublishTest.restore_env
    stub = tfp.SevenDayPublishTest.stub
    published = tfp.SevenDayPublishTest.published

    def test_a_premiere_today_is_on_the_show_and_a_past_one_is_not(self):
        ahead = self.today.isoformat()
        self.stub()
        orig = tfp.showtimes_for

        def with_premiere(date):
            doc = orig(date)
            doc["relatedData"]["films"][1]["releaseDate"] = ahead + "T00:00:00"
            return doc
        tfp.showtimes_for = with_premiere
        self.addCleanup(lambda: setattr(tfp, "showtimes_for", orig))
        self.assertEqual(fetch_data.main(), 0, self.err.getvalue())
        shows = [s for n in ("area-1.json", "area-2.json") for s in self.published()[n]["shows"]]
        self.assertEqual({s["title"]: s.get("rd") for s in shows},
                         {"Filmi A": None, "Filmi B": ahead})
        self.assertEqual(len(shows), 28)


if __name__ == "__main__":
    unittest.main()
