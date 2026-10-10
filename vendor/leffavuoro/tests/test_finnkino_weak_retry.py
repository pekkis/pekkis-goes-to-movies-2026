"""The Finnkino pass keeps a weak TMDB candidate and searches it again on a schedule.

Same rule as test_tmdb_weak_retry, for data/tmdb.json. main() deleted every weak entry as
the cache loaded, so each one was searched from scratch on every local run. Keeping it
needs more than removing the sweep: a weak entry is complete to refresh.due(), which
would park it for a day or a week and then re-read the wrong id without searching.

The pass is driven directly on a controlled date, TMDB stubbed on the URL; publishing is
checked through main() with OCAPI stubbed as in test_finnkino_trust.
"""
import contextlib
import datetime
import io
import json
import types
import unittest
import urllib.parse

import _ctx                                                # noqa: F401
import fetch_data
import test_finnkino_trust as trust

WEAK = {"id": 99, "title": "Another Film", "original_title": "Another Film",
        "release_date": "2020-01-01", "vote_average": 8.1, "vote_count": 5000}
EXACT = {"id": 10, "title": "Film A", "original_title": "Film A",
         "release_date": "2026-01-01", "vote_average": 6.4, "vote_count": 400}
D1, D2, D3 = "2026-09-13", "2026-09-14", "2026-09-15"


def meta(q="Film A", y="2026"):
    return {"10": {"q": q, "fi": "Filmi A", "y": y}}


class PassHarness(unittest.TestCase):

    def setUp(self):
        self.calls = []
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)
        real_time = fetch_data.time
        fetch_data.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(fetch_data, "time", real_time))
        self.cache = {}

    def run_pass(self, today, films=None, table=None, aliases=None, fail=None, trailer="k99"):
        """One pass on `today`. `table` maps a query to its hits (default: the weak one
        for "Film A"); `fail` is a URL substring whose requests raise."""
        table = {"Film A": [WEAK]} if table is None else table

        def http_get(url, headers, timeout=25):
            self.calls.append(url)
            if fail and fail in url:
                raise RuntimeError("HTTP Error 429: Too Many Requests")
            if "/search/movie" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                return json.dumps({"results": table.get(q, [])})
            if url.endswith("/videos"):
                return json.dumps({"results": [{"site": "YouTube", "type": "Trailer",
                                                "official": True, "key": trailer}]
                                   if trailer else []})
            return json.dumps({"vote_average": 8.1, "vote_count": 5000,
                               "genres": [{"id": 28}]})
        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))
        self.calls = []
        return fetch_data.enrich_cached_ratings(films or meta(), self.cache, aliases or {},
                                                {}, today)

    def searched(self):
        return any("/search/movie" in u for u in self.calls)

    def weak_on(self, day, **kw):
        self.run_pass(day, **kw)
        e = self.cache["10"]
        self.assertEqual((e["i"], e["x"], e["a"]), (99, False, day))
        self.assertTrue(self.searched())
        return e


class ScheduleTest(PassHarness):

    def test_a_weak_entry_is_kept_and_not_searched_again_the_same_day(self):
        before = self.weak_on(D1)
        self.assertEqual((before["q"], before["y"], before["t"]),
                         ("film a", "2026", "Another Film"))
        stats = self.run_pass(D1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.cache["10"], before)
        self.assertEqual((stats["kept"], stats["kept_until"]),
                         (["Film A -> Another Film"], D2))

    def test_the_next_day_it_is_searched_although_it_carries_a_trailer(self):
        """Complete with a trailer, refresh.due() would park it for a week."""
        self.weak_on(D1)
        self.run_pass(D2)
        self.assertTrue(self.searched())
        self.assertEqual(self.cache["10"]["a"], D2)

    def test_the_next_day_it_is_searched_and_not_only_re_read(self):
        """Without a trailer refresh.due() takes it daily, but the loop sees a cached id
        and only reads the wrong film's details again."""
        self.weak_on(D1, trailer="")
        self.run_pass(D2, trailer="")
        self.assertTrue(self.searched())

    def test_a_retry_that_finds_the_film_trusts_it(self):
        self.weak_on(D1)
        self.run_pass(D2, table={"Film A": [EXACT]})
        e = self.cache["10"]
        self.assertEqual((e["i"], e["x"]), (10, True))
        self.assertFalse({"q", "y", "t"} & set(e), "only a weak entry records these")

    def test_unmatched_and_trusted_entries_keep_their_schedule(self):
        self.cache = {"20": {"r": 0, "n": 0, "v": "", "x": False, "g": [], "i": "",
                             "c": D1, "a": ""},
                      "30": {"r": 6.4, "n": 400, "v": "k", "x": True, "g": [18], "i": 30,
                             "c": D1, "a": D1}}
        films = {"20": {"q": "Nothing", "fi": "Ei mitään", "y": "2026"},
                 "30": {"q": "Settled", "fi": "Selvä", "y": "2026"}}
        self.run_pass(D1, films=films)
        self.assertEqual(self.calls, [], "both judged today")
        self.run_pass(D2, films=films)
        self.assertTrue(any("query=Nothing" in u for u in self.calls), "daily retry")
        self.assertFalse(any("Settled" in u or "/movie/30" in u for u in self.calls))


class NewEvidenceTest(PassHarness):

    def test_an_original_title_arriving_re_judges_it_the_same_day(self):
        self.weak_on(D1)
        new = "Film A (The Original)"
        self.run_pass(D1, films=meta(q=new), table={new: [dict(EXACT, title=new)]})
        self.assertTrue(self.searched())
        self.assertEqual(self.cache["10"]["x"], True)

    def test_a_changed_release_year_re_judges_it_the_same_day(self):
        self.weak_on(D1)
        self.run_pass(D1, films=meta(y="2025"))
        self.assertTrue(self.searched())
        self.assertEqual(self.cache["10"]["y"], "2025")

    def test_an_alias_id_takes_over_the_same_day(self):
        self.weak_on(D1)
        self.run_pass(D1, aliases={"filmi a": "10"})
        e = self.cache["10"]
        self.assertEqual((e["i"], e["x"]), (10, True))

    def test_an_alias_string_that_still_finds_nothing_exact_waits_for_the_schedule(self):
        self.weak_on(D1)
        aliases = {"filmi a": "Film A Alias"}
        table = {"Film A": [WEAK], "Film A Alias": [WEAK]}
        self.run_pass(D1, aliases=aliases, table=table)
        self.assertTrue(any("Film%20A%20Alias" in u for u in self.calls), "searched at once")
        self.assertEqual(self.cache["10"]["al"], "Film A Alias")
        self.run_pass(D1, aliases=aliases, table=table)
        self.assertEqual(self.calls, [], "and not again that day")
        self.run_pass(D2, aliases=aliases, table=table)
        self.assertTrue(self.searched(), "then on its schedule")


class FailedRequestTest(PassHarness):

    def test_a_failed_retry_keeps_the_entry_and_its_schedule(self):
        """No trailer: the restored entry keeps yesterday's `c`, which refresh.due() would
        take as a daily re-read if a kept entry reached it."""
        before = self.weak_on(D1, trailer="")
        self.run_pass(D2, fail="/search/movie", trailer="")
        self.assertTrue(self.calls)
        self.assertEqual(self.cache["10"], {**before, "a": D2})
        self.run_pass(D2, fail="/search/movie", trailer="")
        self.assertEqual(self.calls, [], "an outage is not a retry every run")
        self.run_pass(D3)
        self.assertTrue(self.searched())

    def test_a_failed_alias_search_keeps_the_weak_entry(self):
        before = self.weak_on(D1)
        self.run_pass(D1, aliases={"filmi a": "Film A Alias"}, fail="/search/movie")
        self.assertEqual(self.cache["10"], {**before, "a": D1})


class PublishTest(unittest.TestCase):
    """A kept weak entry, end to end through main(): nothing of it is published and no
    request is made for it. The harness is test_finnkino_trust's, borrowed rather than
    inherited so its own tests do not run twice."""

    setUp = trust.TrustedOnlyTest.setUp
    published = trust.TrustedOnlyTest.published
    stub_both = trust.TrustedOnlyTest.stub_both

    def test_a_kept_weak_entry_publishes_nothing_and_is_not_searched(self):
        today = datetime.date.today().isoformat()
        (self.root / "data").mkdir()
        kept = {"r": 8.1, "n": 5000, "v": "key99", "x": False, "g": [28], "i": 99,
                "c": today, "a": today, "q": "film a", "y": "2026", "t": "Another Film"}
        (self.root / "data" / "tmdb.json").write_text(json.dumps({"10": kept}))
        asked = []
        self.stub_both()
        stubbed = fetch_data.http_get

        def recording(url, headers, timeout=25):
            asked.append(url)
            return stubbed(url, headers, timeout)
        fetch_data.http_get = recording
        self.assertEqual(fetch_data.main(), 0)
        out = self.published()
        self.assertEqual(out["tmdb.json"]["10"], kept)
        self.assertFalse([u for u in asked if "query=Film%20A" in u or "/movie/99" in u])
        for s in out["area-1.json"]["shows"]:
            if s["eventId"] == "10":
                self.assertFalse({"tmdb", "votes", "gids", "tmdbId"} & set(s))
        self.assertEqual(out["films.json"]["films"]["10"]["tr"], trust.FINNKINO_TRAILER)


if __name__ == "__main__":
    unittest.main()
