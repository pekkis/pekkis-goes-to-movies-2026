"""The Finnkino rating cache gets the same refresh schedule as the title cache.

`data/tmdb.json` skipped an entry on `v or c == today`, so a cached trailer froze its
rating: 46 of 59 entries on 2026-09-01, 45 of them last read on 2026-08-28. Its detail
request was also conditional on `not votes or not gids`, so an age rule alone would have
fetched nothing. Finnkino answers a datacenter address with a 403, so the decision and
the pass around it are tested with TMDB stubbed by URL.
"""
import contextlib
import datetime
import io
import json
import types
import unittest

import _ctx                                                # noqa: F401
import fetch_data
import refresh


TODAY = "2026-09-01"


def entry(day, trailer=True, **over):
    """A complete entry in the shape data/tmdb.json carries.

    Seven fields, and no synopsis or poster: Finnkino publishes both itself, which is why
    this cache needs its own completeness predicate rather than the title cache's.
    """
    e = {"r": 7.1, "n": 400, "v": "abc123" if trailer else "", "x": True,
         "g": [18], "i": 42, "c": day}
    e.update(over)
    return e


class BothCacheShapesTest(unittest.TestCase):
    """One scheduler, two schemas. The predicate is the only thing that differs."""

    def test_the_finnkino_shape_is_complete_without_a_synopsis_or_poster(self):
        self.assertTrue(fetch_data._tmdb_complete(entry(TODAY)))

    def test_the_title_caches_predicate_would_reject_every_finnkino_entry(self):
        """Which is why they are not shared. Requiring `fi`/`en`/`p` here would mark the
        whole cache incomplete and re-fetch all of it on every run, for ever."""
        import enrich_tmdb
        self.assertFalse(enrich_tmdb.is_complete(entry(TODAY)))

    def test_a_finnkino_entry_missing_a_field_is_incomplete(self):
        for field in ("n", "x", "g"):
            with self.subTest(missing=field):
                e = entry(TODAY)
                del e[field]
                self.assertFalse(fetch_data._tmdb_complete(e))

    def test_the_same_scheduler_answers_for_the_finnkino_cache(self):
        cache = {"1": entry("2026-08-20"), "2": entry(TODAY)}
        todo, refreshes, _ = refresh.due(list(cache), cache, TODAY,
                                         fetch_data._tmdb_complete, max_age=7)
        self.assertEqual(refreshes, {"1"})
        self.assertEqual(todo, {"1"})

    def test_a_trailer_no_longer_freezes_a_finnkino_entry(self):
        cache = {"1": entry("2026-08-20")}
        self.assertEqual(refresh.due(["1"], cache, TODAY,
                                     fetch_data._tmdb_complete, max_age=7)[1], {"1"})

    def test_the_backlog_rotates_on_the_attempt_and_not_the_last_success(self):
        cache = {"tried": entry("2026-06-01", a=TODAY), "untried": entry("2026-08-20")}
        picked = refresh.due(list(cache), cache, TODAY, fetch_data._tmdb_complete,
                             max_age=7, budget=1)[1]
        self.assertEqual(picked, {"untried"})


class PassTest(unittest.TestCase):
    """enrich_cached_ratings driven directly, with TMDB stubbed by URL."""

    def setUp(self):
        self.calls = []
        # The pass reports every failed request by design -- the committed run.log is
        # what you read after a run. Swallowed here so a passing suite stays quiet.
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)
        real_time = fetch_data.time
        fetch_data.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(fetch_data, "time", real_time))

    def stub(self, detail=None, videos=None, search=None):
        """Answer TMDB by URL. Each callable may return a dict or raise."""
        def http_get(url, headers, timeout=25):
            self.calls.append(url)
            if "/search/movie" in url:
                return json.dumps(search(url) if search else {"results": []})
            if url.endswith("/videos"):
                return json.dumps(videos(url) if videos else {"results": [
                    {"site": "YouTube", "type": "Trailer", "official": True,
                     "key": "zzz"}]})
            return json.dumps(detail(url) if detail else
                              {"vote_average": 8.2, "vote_count": 900,
                               "genres": [{"id": 18}]})
        real = fetch_data.http_get
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))

    def films(self, n=1):
        """The shape main() builds: search string, Finnish title, release year.

        `y` is not decoration -- the search loop reads it to decide whether a year-less
        candidate may be accepted, and leaving it out made the pass raise KeyError on
        every uncached film. Which is the argument for driving the real pass rather than
        a reimplementation of it.
        """
        return {str(100 + i): {"q": f"Film {i}", "fi": f"Filmi {i}", "y": "2026"}
                for i in range(n)}

    def stale_cache(self, n=1, oldest=20):
        """`n` entries, all past the age, none ever attempted, distinct ids."""
        return {str(100 + i): entry((datetime.date.today()
                                     - datetime.timedelta(days=oldest - i)).isoformat(),
                                    i=200 + i)
                for i in range(n)}

    def ids_asked(self):
        got = {u.split("/movie/")[1].split("/")[0].split("?")[0]
               for u in self.calls if "/movie/" in u}
        self.calls.clear()
        return got

    def run_pass(self, films, cache, **stub):
        self.stub(**stub)
        today = datetime.date.today().isoformat()
        return fetch_data.enrich_cached_ratings(films, cache, {}, {}, today), today

    # -- the defect --------------------------------------------------------------------

    def test_a_stale_rating_is_actually_re_read(self):
        """The detail request is conditional on missing votes or genres, so before this
        an age rule would have scheduled the entry, fetched no detail and stamped it
        current -- worse than not refreshing at all."""
        cache = self.stale_cache()
        stats, today = self.run_pass(self.films(), cache)
        self.assertEqual(stats["scheduled"], 1)
        self.assertEqual(stats["settled"], 1)
        self.assertEqual((cache["100"]["r"], cache["100"]["n"]), (8.2, 900))
        self.assertEqual(cache["100"]["c"], today)
        self.assertEqual(cache["100"]["a"], today)

    def test_a_film_with_no_cache_entry_is_searched_and_written(self):
        """The other half of the completeness rule: an entry that is not there at all is
        fetched, not skipped. Without it a new film would never get a rating."""
        stats, today = self.run_pass(
            self.films(), {},
            search=lambda url: {"results": [{"id": 555, "title": "Film 0"}]})
        self.assertEqual(stats["looked"], 1)
        self.assertEqual(stats["rechecked"], 0)

    # -- failure outside and inside the detail handler ----------------------------------

    def test_a_failed_detail_read_keeps_the_entry_and_leaves_it_due(self):
        def boom(url):
            raise RuntimeError("500 from TMDB")

        cache = self.stale_cache()
        was = dict(cache["100"])
        stats, today = self.run_pass(self.films(), cache, detail=boom)
        self.assertEqual((stats["scheduled"], stats["settled"]), (1, 0))
        self.assertEqual((cache["100"]["r"], cache["100"]["n"]), (was["r"], was["n"]))
        self.assertEqual(cache["100"]["c"], was["c"], "the entry was parked")
        self.assertEqual(cache["100"]["a"], today, "the attempt was not recorded")

    def test_a_failed_video_read_keeps_the_trailer_it_already_had(self):
        """The video request has always had its own handler here, which is why this half
        was quiet: `yt` started at "" and a failed read wrote that over a real trailer."""
        def boom(url):
            raise RuntimeError("500 from TMDB")

        cache = self.stale_cache()
        self.run_pass(self.films(), cache, videos=boom)
        self.assertEqual(cache["100"]["v"], "abc123", "a cached trailer was emptied")

    def test_a_video_read_that_answers_and_finds_none_does_clear_it(self):
        """Seeding from the cache must not turn into "never clear"."""
        cache = self.stale_cache()
        self.run_pass(self.films(), cache, videos=lambda url: {"results": []})
        self.assertEqual(cache["100"]["v"], "")

    def test_half_a_vote_pair_settles_nothing(self):
        for partial in ({"vote_count": 900}, {"vote_average": 8.2}):
            with self.subTest(partial=partial):
                cache = self.stale_cache()
                was = dict(cache["100"])
                stats, _ = self.run_pass(self.films(), cache,
                                         detail=lambda url: dict(partial))
                self.assertEqual(stats["settled"], 0)
                self.assertEqual((cache["100"]["r"], cache["100"]["n"]),
                                 (was["r"], was["n"]), "a real rating was erased")
                self.assertEqual(cache["100"]["c"], was["c"])

    def test_a_film_nobody_has_voted_on_is_a_successful_read(self):
        cache = self.stale_cache()
        stats, today = self.run_pass(self.films(), cache,
                                     detail=lambda url: {"vote_average": 0,
                                                         "vote_count": 0})
        self.assertEqual(stats["settled"], 1)
        self.assertEqual(cache["100"]["c"], today)

    def test_a_title_that_aborts_outside_both_handlers_still_records_the_attempt(self):
        """Both requests here have their own handler, so the outer one is reached by the
        code between them -- a cached rating that is not a number, from a torn or
        hand-edited file, makes `round()` raise. The entry must keep everything and still
        lose its place in the rotation, or a corrupt row holds the head of the queue for
        ever."""
        cache = self.stale_cache()
        cache["100"]["r"] = "7.1"                  # a string where a float belongs

        def boom(url):
            raise RuntimeError("500 from TMDB")

        stats, today = self.run_pass(self.films(), cache, detail=boom)
        self.assertEqual((stats["scheduled"], stats["settled"]), (1, 0))
        self.assertEqual(cache["100"]["r"], "7.1", "the entry was rewritten")
        self.assertEqual(cache["100"]["a"], today, "the attempt was not recorded")

    def test_an_exception_after_the_write_does_not_put_the_old_entry_back(self):
        """The other side of that guard. Everything up to the write succeeded, so the
        refresh is real and has to survive whatever raises after it."""
        cache = self.stale_cache()

        def exploding_sleep(seconds=0):
            if seconds == 0.25:                    # the per-film pause, after the write
                raise RuntimeError("after the write")

        fetch_data.time = types.SimpleNamespace(sleep=exploding_sleep)
        stats, today = self.run_pass(self.films(), cache)
        self.assertEqual((cache["100"]["r"], cache["100"]["n"]), (8.2, 900),
                         "a real refresh was rolled back")
        self.assertEqual(cache["100"]["c"], today)

    # -- the backlog rotates -------------------------------------------------------------

    def test_a_failed_id_does_not_hold_the_budget_on_the_next_run(self):
        """Two runs over a backlog larger than the budget, every detail read failing, so
        `c` never moves and only the recorded attempt can stop the same ids coming back.
        """
        def boom(url):
            raise RuntimeError("500 from TMDB")

        saved = refresh.REFRESH_BUDGET
        refresh.REFRESH_BUDGET = 3
        self.addCleanup(lambda: setattr(refresh, "REFRESH_BUDGET", saved))

        films, cache = self.films(8), self.stale_cache(8)
        self.run_pass(films, cache, detail=boom)
        first = self.ids_asked()
        self.run_pass(films, cache, detail=boom)
        second = self.ids_asked()
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(first & second, set(),
                         "the same failed ids held the budget a second time")

    def test_the_pass_reports_what_became_of_each_scheduled_refresh(self):
        def boom(url):
            raise RuntimeError("500 from TMDB")

        saved = refresh.REFRESH_BUDGET
        refresh.REFRESH_BUDGET = 2
        self.addCleanup(lambda: setattr(refresh, "REFRESH_BUDGET", saved))
        stats, _ = self.run_pass(self.films(5), self.stale_cache(5), detail=boom)
        self.assertEqual((stats["scheduled"], stats["settled"], stats["deferred"]),
                         (2, 0, 3))
        self.assertEqual(refresh.report(2, 0, 3, budget=2),
                         "rating refresh: 2 scheduled, 0 re-read, 2 failed and still "
                         "due, 3 deferred (budget 2)")

    def test_an_entry_read_today_is_not_touched_again(self):
        """The daily half is unchanged: a trailer hunt that costs nothing once it has
        run, and the reason `c` still advances there without a detail read."""
        cache = {"100": entry(datetime.date.today().isoformat(), trailer=False)}
        self.run_pass(self.films(), cache)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
