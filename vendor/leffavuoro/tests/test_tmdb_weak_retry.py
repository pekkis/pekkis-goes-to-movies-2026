"""A weak TMDB candidate stays cached and is searched again on a schedule.

Until 2026-09-25 main() deleted every weak entry as the cache loaded, so the same ten
titles were searched from scratch on every run: 53 of the 56 TMDB requests a run made
when nothing else was due. The entry now stays, still untrusted, and is searched again
once a day. New evidence and an alias still reach it at once, a failed request keeps it,
and keeping it publishes nothing.

Successive runs on a controlled date, TMDB stubbed on the URL as in test_tmdb_trust.
"""
import contextlib
import datetime
import io
import json
import types
import unittest
import urllib.parse
from unittest import mock

import _ctx                                                # noqa: F401
import enrich_tmdb
from test_tmdb_matching import hit
from test_tmdb_trust import OBSESSION, RIGHT, WRONG, TrustHarness, regina

WEAK = {("Naisen kasvot", ""): [OBSESSION]}


class Clock(datetime.date):
    day = datetime.date(2026, 9, 13)

    @classmethod
    def today(cls):
        return cls(cls.day.year, cls.day.month, cls.day.day)


class WeakRetryHarness(TrustHarness):

    def setUp(self):
        super().setUp()
        real = enrich_tmdb.datetime
        enrich_tmdb.datetime = types.SimpleNamespace(date=Clock)
        self.addCleanup(lambda: setattr(enrich_tmdb, "datetime", real))
        self.set_day(13)
        self.urls = []

    def set_day(self, d):
        Clock.day = datetime.date(2026, 9, d)

    def run_pass(self, table=WEAK, detail=None, videos=None, fail=None):
        """One pass. Every request but the genre lists is recorded in `urls`; `fail` is a
        URL substring whose requests raise, as a TMDB 429 does."""
        detail = {4780: WRONG} if detail is None else detail
        videos = {4780: WRONG["v"]} if videos is None else videos

        def fake_get(url, headers, timeout=25):
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}]}
            self.urls.append(url)
            if fail and fail in url:
                raise RuntimeError("HTTP Error 429: Too Many Requests")
            if "/search/movie" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                key = (q["query"][0], (q.get("primary_release_year") or [""])[0])
                return {"results": table.get(key, [])}
            mid = int(url.split("/movie/")[1].split("/")[0].split("?")[0])
            if url.endswith("/videos"):
                key = videos.get(mid)
                return {"results": [{"site": "YouTube", "type": "Trailer", "official": True,
                                     "key": key}] if key else []}
            d = detail.get(mid) or {}
            lang = "fi" if "language=fi-FI" in url else "en"
            return {"overview": d.get(lang, ""), "vote_count": d.get("n"),
                    "vote_average": d.get("r"), "genres": [{"id": g} for g in d.get("g", [])],
                    "poster_path": f"/{mid}.jpg"}
        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        self.urls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(enrich_tmdb.main(), 0)
        return buf.getvalue()

    def weak_today(self, **kw):
        self.shows(regina(year="", original=""))
        self.run_pass(**kw)
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"], e["a"]), (4780, False, Clock.today().isoformat()))
        self.assertTrue(self.urls, "the first run searched")
        return e


class BeforeDueTest(WeakRetryHarness):

    def test_a_weak_entry_is_kept_and_not_searched_again_the_same_day(self):
        before = self.weak_today()
        self.assertEqual(before["t"], "Obsession", "the candidate's title, for the log")
        out = self.run_pass()
        self.assertEqual(self.urls, [], "no request for a title judged today")
        self.assertEqual(self.cache()["naisen kasvot"], before, "kept as it was")
        self.assertIn("weak candidate kept, not searched until 2026-09-14 (1): "
                      "Naisen kasvot -> Obsession", out)
        self.assertNotIn("dropped", out)

    def test_a_kept_weak_entry_gets_no_rating_refresh_either(self):
        """No trailer and no vote pair leave the entry in the state refresh.due() reads
        daily; a kept weak entry is outside that schedule, since it publishes nothing."""
        self.weak_today(detail={4780: {"fi": "Teksti."}}, videos={})
        self.run_pass(detail={4780: {"fi": "Teksti."}}, videos={})
        self.assertEqual(self.urls, [])

    def test_keeping_it_publishes_nothing(self):
        """Not from the cache, and not what run.py carried from the previous file."""
        self.weak_today()
        self.shows(regina(year="", original="", tmdb=7.3, votes=1200, gids=[53],
                          tmdbId=4780, tr="https://www.youtube.com/watch?v=wrongkey"))
        self.run_pass()
        self.assertEqual(self.urls, [])
        self.assert_no_tmdb_fields(self.area()["shows"][0])
        self.assertFalse((self.assert_no_tmdb_extra("naisen kasvot").get("s") or {}).get("fi"))


class WhenDueTest(WeakRetryHarness):

    def test_the_next_day_it_is_searched_again(self):
        self.weak_today()
        self.set_day(14)
        self.run_pass()
        self.assertTrue(any("/search/movie" in u for u in self.urls))
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"], e["a"]), (4780, False, "2026-09-14"))

    def test_a_retry_that_finds_the_film_publishes_it(self):
        self.weak_today()
        self.set_day(14)
        self.run_pass({("Naisen kasvot", ""): [hit(76848, "Naisen kasvot", 1938)]},
                      detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"]), (76848, True))
        self.assertNotIn("t", e, "only a weak entry names its candidate")
        self.assertEqual(self.area()["shows"][0]["tmdbId"], 76848)


class NewEvidenceTest(WeakRetryHarness):

    def test_a_published_year_and_original_title_re_judge_it_the_same_day(self):
        self.weak_today()
        self.shows(regina())                  # the cinema now publishes 1938 and the original
        out = self.run_pass({("Naisen kasvot", "1938"): [hit(76848, "Naisen kasvot", 1938)]},
                            detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        self.assertIn("re-judging 1 title(s)", out)
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"], e["y"]), (76848, True, "1938"))
        self.assertEqual(self.area()["shows"][0]["tmdbId"], 76848)

    def test_a_changed_search_string_re_judges_it_the_same_day(self):
        self.weak_today()
        with mock.patch.object(enrich_tmdb, "clean", lambda s: "Naisen kasvot 2"):
            self.run_pass({("Naisen kasvot 2", ""): [hit(76848, "Naisen kasvot 2", 1938)]},
                          detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        self.assertEqual(self.cache()["naisen kasvot"]["i"], 76848)

    def test_an_alias_id_takes_over_the_same_day(self):
        self.weak_today()
        (self.dir / "tmdb-aliases.json").write_text(json.dumps({"naisen kasvot": "76848"}))
        self.run_pass(detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"]), (76848, True))
        self.assertEqual(self.area()["shows"][0]["tmdbId"], 76848)

    def test_an_alias_string_that_still_finds_nothing_exact_waits_for_the_schedule(self):
        """Without the record of the alias it was searched with, the alias would supersede
        the weak entry it produced on every run."""
        self.weak_today()
        (self.dir / "tmdb-aliases.json").write_text(
            json.dumps({"naisen kasvot": "En kvinnas ansikte"}))
        table = {**WEAK, ("En kvinnas ansikte", ""): [OBSESSION]}
        self.run_pass(table)
        self.assertIn("En kvinnas ansikte", " ".join(map(urllib.parse.unquote, self.urls)),
                      "the new alias is searched at once")
        self.assertEqual(self.cache()["naisen kasvot"]["al"], "En kvinnas ansikte")
        self.run_pass(table)
        self.assertEqual(self.urls, [], "and not again that day")
        self.set_day(14)
        self.run_pass(table)
        self.assertTrue(self.urls, "then on its schedule")


class FailedRequestTest(WeakRetryHarness):

    def test_a_failed_retry_keeps_the_entry_and_its_schedule(self):
        before = self.weak_today()
        self.set_day(14)
        self.run_pass(fail="/search/movie")
        self.assertTrue(self.urls, "the retry was attempted")
        self.assertEqual(self.cache()["naisen kasvot"], {**before, "a": "2026-09-14"},
                         "the entry survives with only its attempt date moved")
        self.assert_no_tmdb_fields(self.area()["shows"][0])
        self.run_pass(fail="/search/movie")
        self.assertEqual(self.urls, [], "an outage does not turn into a retry every run")
        self.set_day(15)
        self.run_pass()
        self.assertTrue(any("/search/movie" in u for u in self.urls))
        self.assertEqual(self.cache()["naisen kasvot"]["a"], "2026-09-15")

    def test_a_failed_alias_search_keeps_the_weak_entry(self):
        before = self.weak_today()
        (self.dir / "tmdb-aliases.json").write_text(
            json.dumps({"naisen kasvot": "En kvinnas ansikte"}))
        self.run_pass(fail="/search/movie")
        self.assertEqual(self.cache()["naisen kasvot"]["i"], before["i"])
        self.assertFalse(self.cache()["naisen kasvot"]["x"])
        self.assert_no_tmdb_fields(self.area()["shows"][0])


class LeftTheProgrammeTest(WeakRetryHarness):

    def test_the_candidates_text_in_an_entry_written_before_ts_is_taken_back(self):
        """unpublish_extra recognises TMDB text in an entry without `ts` by comparing it
        with the candidate's own overview. With weak entries deleted on load, a film that
        had left the programme had no entry to compare with, and the text stood."""
        self.weak_today()
        self.extra_write({"naisen kasvot": {"s": {"fi": WRONG["fi"], "en": ""},
                                            "r": 0, "tr": ""}})
        self.shows({"title": "Jokin muu", "provider": "regina", "venue": "regina"})
        self.run_pass({})
        fx = self.extra().get("naisen kasvot") or {}
        self.assertEqual((fx.get("s") or {}).get("fi", ""), "")
        self.assertEqual(fx, {}, "left with no text and no film showing, the entry goes (E10)")


if __name__ == "__main__":
    unittest.main()
