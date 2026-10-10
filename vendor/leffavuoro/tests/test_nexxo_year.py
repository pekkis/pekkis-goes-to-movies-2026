"""Nexxo: the cinema's production year goes on the show as the TMDB pass's search hint.

On 2026-09-28 "Liisa ihmemaassa" searched with no year took Burton's 2010 film as an
exact match; with Kino Aurora's own 1951 it takes Disney's. A shorts programme's
"1937-1949" is no one film's year.
"""
import unittest

import _ctx                                                # noqa: F401
import nexxo
from test_nexxo_rooms import PLAIN_VENUE, row

SITE = {"provider": "kinox", "label": "Kino X", "base": "https://api.example",
        "programme": "/ohjelmisto/", "venues": [PLAIN_VENUE]}


class YearTest(unittest.TestCase):
    def years(self, *values):
        rows = [{**row(1, "Kino X", f"Film {i}", f"2026-09-02 1{i}:00:00"), "release_year": v}
                for i, v in enumerate(values)]
        shows = nexxo.parse({"shows": {"2026-09-02": rows}}, SITE, PLAIN_VENUE)
        return [s["year"] for s in sorted(shows, key=lambda s: s["start"])]

    def test_a_year_is_published(self):
        self.assertEqual(self.years("1951", " 2026 "), ["1951", "2026"])

    def test_a_range_or_nothing_is_not(self):
        self.assertEqual(self.years("1937-1949", "", None, "0000"), ["", "", "", ""])


if __name__ == "__main__":
    unittest.main()
