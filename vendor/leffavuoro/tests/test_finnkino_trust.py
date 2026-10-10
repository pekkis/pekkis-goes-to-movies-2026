"""The Finnkino pass publishes TMDB metadata from trusted matches only.

Same rule as enrich_tmdb (see test_tmdb_trust): `tmdbId` was already withheld from a weak
match, while the rating, the votes, the genre ids and the trailer were written from the
wrong film, and TMDB's trailer replaced Finnkino's own. The pass is driven end to end with
OCAPI and TMDB both stubbed on the URL, the way test_finnkino_partial drives it.
"""
import contextlib
import io
import json
import os
import pathlib
import tempfile
import types
import unittest
import urllib.parse

import _ctx                                                # noqa: F401
import fetch_data
from test_finnkino_partial import SITES, showtimes_for

WEAK = {"id": 99, "title": "Another Film", "original_title": "Another Film",
        "release_date": "2020-01-01", "vote_average": 8.1, "vote_count": 5000}
EXACT = {"id": 11, "title": "Film B", "original_title": "Film B",
         "release_date": "2026-02-02", "vote_average": 6.4, "vote_count": 400}
FINNKINO_TRAILER = "https://www.finnkino.fi/trailers/film-a"


def with_trailer(date):
    doc = showtimes_for(date)
    doc["relatedData"]["films"][0]["trailers"] = [{"uri": FINNKINO_TRAILER}]
    return doc


class TrustedOnlyTest(unittest.TestCase):
    """Not a subclass of SevenDayPublishTest: that would run its tests a second time."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        saved = {k: os.environ.get(k) for k in ("FINNKINO_TOKEN", "TMDB_TOKEN")}
        os.environ["FINNKINO_TOKEN"] = "stub-token"
        os.environ["TMDB_TOKEN"] = "stub-tmdb"

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        real_time = fetch_data.time
        fetch_data.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(fetch_data, "time", real_time))
        fetch_data._poster_cache.clear()
        for redirect in (contextlib.redirect_stdout(io.StringIO()),
                         contextlib.redirect_stderr(io.StringIO())):
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)

    def published(self):
        return {p.name: json.loads(p.read_text())
                for p in sorted((self.root / "data").glob("*.json"))}

    def stub_both(self):
        def http_get(url, headers, timeout=25):
            if url.endswith("/sites"):
                return json.dumps({"sites": SITES})
            if "/showtimes/by-business-date/" in url:
                date = url.split("/by-business-date/")[1].split("?")[0]
                return json.dumps(with_trailer(date))
            if "/search/movie" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                return json.dumps({"results": [WEAK] if q == "Film A" else
                                   [EXACT] if q == "Film B" else []})
            if url.endswith("/videos"):
                mid = url.split("/movie/")[1].split("/")[0]
                return json.dumps({"results": [{"site": "YouTube", "type": "Trailer",
                                                "official": True,
                                                "key": f"key{mid}"}]})
            if "/movie/" in url:
                mid = int(url.split("/movie/")[1].split("?")[0])
                return json.dumps({"vote_average": 8.1 if mid == 99 else 6.4,
                                   "vote_count": 5000 if mid == 99 else 400,
                                   "genres": [{"id": 28 if mid == 99 else 18}]})
            raise AssertionError(f"unexpected request: {url}")
        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))

    def run_pass(self):
        self.stub_both()
        self.assertEqual(fetch_data.main(), 0)
        out = self.published()
        cache = out["tmdb.json"]
        self.assertEqual((cache["10"]["i"], cache["10"]["x"]), (99, False), "Film A stays weak")
        self.assertEqual((cache["11"]["i"], cache["11"]["x"]), (11, True))
        shows = out["area-1.json"]["shows"]
        return out, [s for s in shows if s["eventId"] == "10"], [s for s in shows if s["eventId"] == "11"]

    def test_a_weak_candidate_publishes_nothing_onto_the_shows(self):
        out, weak, exact = self.run_pass()
        self.assertTrue(weak and exact)
        for s in weak:
            for field in ("tmdb", "votes", "gids", "tmdbId"):
                self.assertNotIn(field, s, f"{field} came from the weak candidate")

    def test_finnkinos_own_trailer_stands_where_tmdbs_is_not_trusted(self):
        out, weak, exact = self.run_pass()
        self.assertEqual(out["films.json"]["films"]["10"]["tr"], FINNKINO_TRAILER)

    def test_a_trusted_match_still_enriches(self):
        out, weak, exact = self.run_pass()
        for s in exact:
            self.assertEqual((s["tmdb"], s["votes"], s["gids"], s["tmdbId"]), (6.4, 400, [18], 11))
        self.assertEqual(out["films.json"]["films"]["11"]["tr"],
                         "https://www.youtube.com/watch?v=key11")

    def test_films_json_carries_only_a_trusted_id(self):
        out, weak, exact = self.run_pass()
        films = out["films.json"]["films"]
        self.assertEqual((films["11"].get("i"), films["10"].get("i")), (11, None))

    def test_a_weak_entry_left_by_an_earlier_run_publishes_nothing_either(self):
        """The cache the previous run wrote holds the weak candidate with its figures;
        this run's search finds the same fallback. Nothing of it reaches the files."""
        (self.root / "data").mkdir()
        (self.root / "data" / "tmdb.json").write_text(json.dumps({
            "10": {"r": 8.1, "n": 5000, "v": "key99", "x": False, "g": [28], "i": 99,
                   "c": "2026-09-12", "a": "2026-09-12"}}))
        out, weak, exact = self.run_pass()
        for s in weak:
            self.assertFalse(any(f in s for f in ("tmdb", "votes", "gids", "tmdbId")))
        self.assertEqual(out["films.json"]["films"]["10"]["tr"], FINNKINO_TRAILER)


if __name__ == "__main__":
    unittest.main()


class AliasOverrideTest(unittest.TestCase):
    """`alias_overrides`: which cached Finnkino films an alias replaces."""

    META = {"HO1": {"q": "Avengers: Endgame Encore", "fi": "Avengers: Endgame Encore", "y": "2026"},
            "HO2": {"q": "Film B", "fi": "Film B", "y": "2026"},
            "HO3": {"q": "Avengers: Endgame Encore (2D)", "fi": "Avengers: Endgame Encore (2D)",
                    "y": "2026"}}

    def test_an_alias_id_that_disagrees_replaces_an_exact_entry(self):
        """The Finnkino half of 2026-09-25: HO00000564 held a one-vote record on 96 rows
        with an alias for 299534 in the file."""
        cache = {"HO1": {"i": 1774125, "x": True}, "HO2": {"i": 11, "x": True}}
        got = fetch_data.alias_overrides(cache, self.META,
                                         {"avengers endgame encore": "299534"})
        self.assertEqual(got, ["HO1"])

    def test_an_alias_that_agrees_or_a_string_alias_leaves_an_exact_entry(self):
        cache = {"HO1": {"i": 299534, "x": True}, "HO2": {"i": 11, "x": True}}
        self.assertEqual(fetch_data.alias_overrides(
            cache, self.META, {"avengers endgame encore": "299534", "film b": "Film B"}), [])

    def test_a_weak_entry_with_any_alias_is_replaced_as_before(self):
        cache = {"HO2": {"i": 12, "x": False}}
        self.assertEqual(fetch_data.alias_overrides(cache, self.META, {"film b": "Film B"}),
                         ["HO2"])

    def test_the_cleaned_finnish_title_reaches_the_alias(self):
        cache = {"HO3": {"i": 1777404, "x": True}}
        self.assertEqual(fetch_data.alias_overrides(
            cache, self.META, {"avengers endgame encore": "299534"}), ["HO3"])

