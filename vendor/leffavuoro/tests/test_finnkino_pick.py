"""The Finnkino pass judges TMDB hits with enrich_tmdb.pick(), as the cloud pass does.

`fetch_data._pick` took the first exact title or else the first hit: no same-year tie and
no runtime rule (prior review #33). OCAPI's year is the Finnish release date, a reissue's
included, so it filters the search and never refuses a hit: the unfiltered retry is judged
as a title with no year. Stubbed fixtures prove the rule. This file cannot run on a
runner, so a local run is the operational check.
"""
import contextlib
import io
import json
import re
import types
import unittest
import urllib.parse

import _ctx                                                # noqa: F401
import enrich_tmdb
import fetch_data


def hit(i, title, year, original=None):
    return {"id": i, "title": title, "original_title": original or title,
            "release_date": f"{year}-06-01", "vote_average": 7.0, "vote_count": 400}


class FinnkinoPickTest(unittest.TestCase):

    def setUp(self):
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)
        for mod in (fetch_data, enrich_tmdb):
            real = mod.time
            mod.time = types.SimpleNamespace(sleep=lambda *_: None)
            self.addCleanup(setattr, mod, "time", real)

    def judge(self, q, filtered, unfiltered=(), english=(), runtimes=None, m=()):
        """One pass for one film -> its cache entry. The stub answers by the request's
        shape: a year-filtered search, an unfiltered one, an English one, /movie/{id}."""
        self.calls = []

        def http_get(url, headers, timeout=25):
            self.calls.append(url)
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if "/search/movie" in url:
                hits = (english if qs["language"] == ["en-US"] else
                        filtered if "primary_release_year" in qs else unfiltered)
                return json.dumps({"results": list(hits)})
            if url.endswith("/videos"):
                return json.dumps({"results": []})
            mid = int(re.search(r"/movie/(\d+)", url).group(1))
            return json.dumps({"vote_average": 7.0, "vote_count": 400, "genres": [],
                               "runtime": (runtimes or {}).get(mid, 0)})
        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(setattr, fetch_data, "http_get", real)
        cache = {}
        meta = {"10": {"q": q, "fi": q, "y": "2026", "m": list(m)}}
        fetch_data.enrich_cached_ratings(meta, cache, {}, {}, "2026-09-27")
        return cache["10"]

    def unfiltered_searches(self):
        return [u for u in self.calls
                if "/search/movie" in u and "primary_release_year" not in u]

    def test_one_exact_film_of_that_year_is_the_match(self):
        e = self.judge("Film A", [hit(1, "Film A", 2026), hit(2, "Film B", 2026)])
        self.assertEqual((e["i"], e["x"]), (1, True))
        self.assertEqual(self.unfiltered_searches(), [])

    def test_a_second_film_of_that_title_and_year_is_a_tie(self):
        """Weak, and the unfiltered retry does not undo it: the year found the title."""
        e = self.judge("Film A", [hit(1, "Film A", 2026, "Eka"), hit(2, "Film A", 2026, "Toka")],
                       unfiltered=[hit(1, "Film A", 2026, "Eka")])
        self.assertFalse(e["x"])
        self.assertEqual(self.unfiltered_searches(), [])

    def test_the_original_title_breaks_a_same_year_tie(self):
        e = self.judge("Film A", [hit(1, "Film A", 2026, "Muu"), hit(2, "Film A", 2026)])
        self.assertEqual((e["i"], e["x"]), (2, True))

    def test_a_reissue_is_found_without_its_year(self):
        """OCAPI dates "Autot (uudelleenjulkaisu)" 2026; the film is from 2006."""
        e = self.judge("Autot (uudelleenjulkaisu)", [hit(7, "Autot ja kaverit", 2026)],
                       unfiltered=[hit(8, "Autot", 2006)])
        self.assertEqual((e["i"], e["x"]), (8, True))

    def test_without_the_year_the_runtime_decides_between_two_films(self):
        e = self.judge("Autot (uudelleenjulkaisu)", [],
                       unfiltered=[hit(9, "Autot", 1997), hit(8, "Autot", 2006)],
                       runtimes={8: 117, 9: 80}, m=[117])
        self.assertEqual((e["i"], e["x"]), (8, True))
        self.assertTrue([u for u in self.calls if "language=en-US" in u], "no rival search")


if __name__ == "__main__":
    unittest.main()
