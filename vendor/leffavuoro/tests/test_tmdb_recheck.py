"""Which cached titles the TMDB pass re-reads, and how many at once.

The rule was `c.get("v") or c.get("c") == today`, so a film with a trailer was never read
again: on 2026-09-01, 96 of 156 entries had a trailer and 71 of those were last read on
2026-08-27. The pass needs a token, so the decision, `due()`, is tested against a
fabricated cache: a rating must not be permanent, and one pass must not re-fetch every
title.
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
import enrich_tmdb
import refresh


TODAY = "2026-09-01"


def entry(day, trailer=True, title=None, **over):
    """A complete cache entry as the current shape writes one.

    `a` is left out unless a test sets it: absent means never attempted, which is the
    state every entry written before this field existed is in.

    `q` is the search string the entry was judged on, and it is written whenever the
    caller names the title: without one, `reconsider()` treats the entry as judged by an
    unknown cleaner and re-judges it, which is a different pass from the refresh these
    tests drive. `tests/test_tmdb_matching.py` is where the missing case is covered.
    """
    e = {"r": 7.1, "n": 400, "v": "abc123" if trailer else "", "x": True,
         "g": [18], "i": 42, "c": day, "fi": "Suomeksi", "en": "In English", "p": "/a.jpg"}
    if title is not None:
        e["q"] = enrich_tmdb.norm(enrich_tmdb.clean(title))
    e.update(over)
    return e


def due(cache, **kw):
    """-> (sorted keys this pass would fetch, how many are refreshes, deferred)."""
    keys, refreshes, deferred = enrich_tmdb.due(list(cache), cache, TODAY, **kw)
    return sorted(keys), len(refreshes), deferred


class WhatIsDueTest(unittest.TestCase):

    # -- the defect --------------------------------------------------------------------

    def test_a_trailer_no_longer_freezes_the_rating(self):
        """The whole item. Eight days after it was last read, this entry is re-read."""
        keys, refreshed, deferred = due({"old": entry("2026-08-24")}, max_age=7)
        self.assertEqual(keys, ["old"])
        self.assertEqual((refreshed, deferred), (1, 0))

    def test_a_recently_read_entry_with_a_trailer_is_left_alone(self):
        """Otherwise this becomes a re-fetch of everything on every run."""
        keys, refreshed, _ = due({"fresh": entry("2026-08-30")}, max_age=7)
        self.assertEqual(keys, [])
        self.assertEqual(refreshed, 0)

    def test_the_boundary_is_the_age_itself(self):
        cache = {"at": entry("2026-08-25"), "under": entry("2026-08-26")}
        self.assertEqual(due(cache, max_age=7)[0], ["at"])

    # -- what must not change ----------------------------------------------------------

    def test_a_title_with_no_trailer_is_still_re_checked_daily(self):
        """Unchanged behaviour, and the reason it exists: a trailer may not have been
        published when the film opened, so the entry is asked again the next day."""
        cache = {"yesterday": entry("2026-08-31", trailer=False),
                 "already-today": entry(TODAY, trailer=False)}
        self.assertEqual(due(cache)[0], ["yesterday"])

    def test_a_daily_re_check_is_not_charged_to_the_refresh_budget(self):
        """They are different work: one is looking for a trailer that may not exist yet,
        the other is re-reading a rating. Budgeting the first would stop new films being
        picked up because old ones were being refreshed."""
        cache = {f"n{i}": entry("2026-08-31", trailer=False) for i in range(30)}
        cache.update({f"o{i}": entry("2026-08-20") for i in range(30)})
        keys, refreshed, deferred = due(cache, max_age=7, budget=2)
        self.assertEqual(len(keys), 32)
        self.assertEqual((refreshed, deferred), (2, 28))

    def test_an_entry_missing_a_field_is_incomplete_and_costs_one_pass(self):
        """`n` arrived with the MIN_VOTES gate. An entry without it carries an ungated
        rating, and treating that as incomplete is what made adding the gate cost a
        re-check rather than a cache wipe. A trailer does not exempt it."""
        cache = {"nogate": entry(TODAY, n=None)}
        del cache["nogate"]["n"]
        self.assertEqual(due(cache)[0], ["nogate"])

    def test_a_title_that_is_not_cached_at_all_is_fetched(self):
        self.assertEqual(enrich_tmdb.due(["brand new"], {}, TODAY)[0], {"brand new"})

    def test_a_refresh_is_handed_back_as_keys_so_its_outcome_can_be_reported(self):
        """A scheduled refresh whose detail request fails is not a refreshed rating, and
        main can only say so if it knows which keys were scheduled."""
        cache = {"old": entry("2026-08-01"), "fresh": entry("2026-08-31")}
        _, refreshes, _ = enrich_tmdb.due(list(cache), cache, TODAY, max_age=7)
        self.assertEqual(refreshes, {"old"})

    def test_the_score_and_its_sample_size_are_one_entry(self):
        """`n` travels with `r`, so the MIN_VOTES threshold can be retuned without
        re-fetching. Both are written by the same path, so a refresh carries both."""
        self.assertTrue(enrich_tmdb.is_complete(entry(TODAY)))
        thin = entry(TODAY)
        del thin["n"]
        self.assertFalse(enrich_tmdb.is_complete(thin))


class BudgetTest(unittest.TestCase):
    """A ceiling on how much of the backlog one pass takes, and a report of the rest."""

    def stale(self, n, oldest=30):
        return {f"t{i:02d}": entry(f"2026-08-{oldest - i:02d}") for i in range(n)}

    def test_one_pass_never_re_reads_more_than_the_budget(self):
        """The property the whole ceiling exists for: with everything past the age, this
        is a bounded number of extra requests and not a full re-fetch."""
        for n in (13, 40, 200):
            with self.subTest(stale=n):
                keys, refreshed, deferred = due(self.stale(n, oldest=25),
                                                max_age=7, budget=12)
                self.assertEqual(len(keys), 12)
                self.assertEqual((refreshed, deferred), (12, n - 12))

    def test_among_entries_never_attempted_the_oldest_go_first(self):
        cache = {"a": entry("2026-08-01"), "b": entry("2026-08-20"),
                 "c": entry("2026-08-10"), "d": entry("2026-08-25")}
        self.assertEqual(due(cache, max_age=7, budget=2)[0], ["a", "c"])

    def test_an_entry_never_attempted_outranks_an_older_one_that_was(self):
        """The starvation rule. An id that can never be read keeps `c` where it is and
        ages further every day, so ordering on `c` alone would let a dozen of them hold
        the budget for ever while the rest of the backlog never moved."""
        cache = {"tried": entry("2026-06-01", a=TODAY),
                 "untried": entry("2026-08-20")}
        self.assertEqual(due(cache, max_age=7, budget=1)[0], ["untried"])

    def test_among_entries_all_attempted_the_least_recent_attempt_goes_first(self):
        cache = {"yesterday": entry("2026-06-01", a="2026-08-31"),
                 "last-week": entry("2026-06-01", a="2026-08-25"),
                 "today": entry("2026-06-01", a=TODAY)}
        self.assertEqual(due(cache, max_age=7, budget=2)[0],
                         ["last-week", "yesterday"])

    def test_a_backlog_larger_than_the_budget_rotates_instead_of_repeating(self):
        """Two rounds with the first round's picks marked attempted-and-failed: `c` does
        not move, because nothing was read, so only `a` can stop them being picked again.
        """
        cache = {f"t{i:02d}": entry(f"2026-08-{20 - i:02d}") for i in range(9)}
        first = set(enrich_tmdb.due(list(cache), cache, TODAY, max_age=7, budget=3)[1])
        for k in first:
            cache[k]["a"] = TODAY                   # attempted, and it failed
        second = set(enrich_tmdb.due(list(cache), cache, TODAY, max_age=7, budget=3)[1])
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(first & second, set(),
                         "the same entries were scheduled twice while others waited")

    def test_an_entry_with_no_date_counts_as_the_oldest_thing_there_is(self):
        """An entry from a shape this code no longer writes has an unknown age, and
        unknown is not fresh -- reading it as 0 days old would park it for ever."""
        cache = {"dated": entry("2026-08-01"), "undated": entry("2026-08-01", c="")}
        self.assertEqual(due(cache, max_age=7, budget=1)[0], ["undated"])

    def test_nothing_is_selected_when_nothing_is_stale(self):
        cache = {f"t{i}": entry("2026-08-30") for i in range(50)}
        self.assertEqual(due(cache, max_age=7, budget=12), ([], 0, 0))

    def test_the_choice_is_the_same_on_every_machine(self):
        """Ties break on the key, so the log names the same entries twice in a row and a
        second run does not re-read a different arbitrary dozen."""
        cache = {f"t{i:02d}": entry("2026-08-01") for i in range(30)}
        first = due(cache, max_age=7, budget=5)
        self.assertEqual(first, due(cache, max_age=7, budget=5))
        self.assertEqual(first[0], ["t00", "t01", "t02", "t03", "t04"])


class AgainstTheCommittedCacheTest(unittest.TestCase):
    """The catch-up, against the real cache rather than a fixture.

    A fixture can be built to fit the budget. This asks the question of the cache that
    exists, on a date by which every entry in it is past the age.
    """

    def setUp(self):
        import json
        import pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / "data" / "tmdb-titles.json"
        self.cache = json.loads(path.read_text(encoding="utf-8"))

    def test_a_run_a_fortnight_from_the_oldest_entry_still_fits_the_budget(self):
        """The catch-up is bounded. Every entry in the committed cache is past the age on
        this date, and one pass still re-reads only the budget."""
        keys, refreshes, deferred = enrich_tmdb.due(
            list(self.cache), self.cache, "2026-09-30")
        self.assertEqual(len(refreshes), refresh.REFRESH_BUDGET)
        self.assertGreater(deferred, 0, "nothing was deferred, so nothing was capped")


class MainPathTest(unittest.TestCase):
    """What a refresh writes back, driven through main() rather than through `due()`.

    `due()` decides which entries to re-read; everything the review found wrong was in
    what happened afterwards, so this drives the whole pass. TMDB itself is the one thing
    stubbed -- the pass needs a token and a third party, and neither belongs in a suite --
    and the stub is a dispatch on the URL, so the sequence of calls the code makes is
    still its own.
    """

    ID = 42

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        for attr, value in (("DATA", self.dir), ("CACHE", self.dir / "tmdb-titles.json"),
                            ("GENRES", self.dir / "tmdb-genres.json"),
                            ("EXTRA", self.dir / "films-extra.json")):
            saved = getattr(enrich_tmdb, attr)
            setattr(enrich_tmdb, attr, value)
            self.addCleanup(lambda a=attr, v=saved: setattr(enrich_tmdb, a, v))

        # The paced sleeps are the courtesy to TMDB, not behaviour under test.
        real_time = enrich_tmdb.time
        enrich_tmdb.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(enrich_tmdb, "time", real_time))

        saved_token = os.environ.get("TMDB_TOKEN")
        os.environ["TMDB_TOKEN"] = "test-token"
        self.addCleanup(lambda: (os.environ.__setitem__("TMDB_TOKEN", saved_token)
                                 if saved_token is not None
                                 else os.environ.pop("TMDB_TOKEN", None)))

        self.today = datetime.date.today().isoformat()
        self.stale_day = (datetime.date.today()
                          - datetime.timedelta(days=10)).isoformat()
        (self.dir / "area-zz.json").write_text(json.dumps({
            "generated": self.today, "dates": [], "horizon": "",
            "shows": [{"title": "Old Film", "start": "2026-09-02T18:00:00+03:00"},
                      {"title": "Other Film", "start": "2026-09-02T20:00:00+03:00"}],
        }), encoding="utf-8")
        self.write_cache({
            "old film": entry(self.stale_day, i=self.ID, title="Old Film"),
            # A second entry, so the loop and the counters are exercised rather than a
            # single-item shortcut through them.
            "other film": entry(self.today, i=99, title="Other Film"),
        })
        self.calls = []

    def write_cache(self, cache):
        (self.dir / "tmdb-titles.json").write_text(json.dumps(cache), encoding="utf-8")

    def cache(self):
        return json.loads((self.dir / "tmdb-titles.json").read_text(encoding="utf-8"))

    def run_main(self, detail, videos=None):
        """main() with TMDB stubbed. -> (exit code, everything it printed).

        `detail` answers /movie/{id}?language=... and `videos` answers
        /movie/{id}/videos. The default lets videos succeed, which is why a hole outside
        the detail handler stayed green: every failure a test could write landed inside
        the one place the code already guards.
        """
        def fake_get(url, headers, timeout=25):
            self.calls.append(url)
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}]}
            if url.endswith("/videos"):
                return videos(url) if videos else {
                    "results": [{"site": "YouTube", "type": "Trailer",
                                 "official": True, "key": "zzz"}]}
            return detail(url)

        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = enrich_tmdb.main()
        return code, buf.getvalue()

    # -- the defect --------------------------------------------------------------------

    def test_a_failed_detail_request_keeps_the_entry_and_leaves_it_due(self):
        """Both localized detail requests fail and /videos answers. The pass used to
        write the old rating stamped with today, empty the cached synopses, count the
        rating as re-read and park the entry for another seven days."""
        def boom(url):
            raise RuntimeError("500 from TMDB")

        code, out = self.run_main(boom)
        self.assertEqual(code, 0)
        e = self.cache()["old film"]
        self.assertEqual(e["fi"], "Suomeksi", "a cached synopsis was emptied")
        self.assertEqual(e["en"], "In English", "a cached synopsis was emptied")
        self.assertEqual((e["r"], e["n"]), (7.1, 400), "figures changed without a read")
        self.assertEqual(e["c"], self.stale_day,
                         "the entry was parked for a week on figures nothing re-read")
        self.assertIn("1 scheduled, 0 re-read, 1 failed and still due", out)

    def test_an_entry_a_failed_refresh_left_alone_is_due_again_next_run(self):
        """The property the date is for. Nothing here asserts a log line; what matters is
        whether the next pass picks it up, which is what `due()` will be asked."""
        def boom(url):
            raise RuntimeError("500 from TMDB")

        self.run_main(boom)
        cache = self.cache()
        _, refreshes, _ = enrich_tmdb.due(list(cache), cache, self.today)
        self.assertIn("old film", refreshes)

    # -- and the path that works --------------------------------------------------------

    def test_a_detail_response_with_vote_data_settles_the_entry(self):
        def ok(url):
            return {"overview": "Uusi teksti", "vote_count": 900,
                    "vote_average": 8.2, "genres": [{"id": 18}],
                    "poster_path": "/b.jpg"}

        code, out = self.run_main(ok)
        self.assertEqual(code, 0)
        e = self.cache()["old film"]
        self.assertEqual((e["r"], e["n"]), (8.2, 900))
        self.assertEqual(e["fi"], "Uusi teksti")
        self.assertEqual(e["c"], self.today)
        self.assertIn("1 scheduled, 1 re-read, 0 failed and still due", out)

    def test_a_settled_entry_is_not_due_again_tomorrow(self):
        def ok(url):
            return {"overview": "Uusi teksti", "vote_count": 900,
                    "vote_average": 8.2, "genres": [{"id": 18}]}

        self.run_main(ok)
        cache = self.cache()
        _, refreshes, _ = enrich_tmdb.due(list(cache), cache, self.today)
        self.assertEqual(refreshes, set())

    def test_a_response_that_really_has_no_overview_still_clears_the_text(self):
        """Seeding from the cache must not turn into "never clear". A detail response
        that arrived and carries no overview is TMDB saying there is none."""
        def empty(url):
            return {"overview": "", "vote_count": 900, "vote_average": 8.2}

        self.run_main(empty)
        e = self.cache()["old film"]
        self.assertEqual(e["fi"], "")
        self.assertEqual(e["en"], "")
        self.assertEqual(e["c"], self.today)

    def test_a_detail_response_carrying_no_vote_data_does_not_settle_the_entry(self):
        """"A detail response arrived" and "the rating was re-read" are different things.
        TMDB sends vote_count on every /movie/{id} today, so this is the defensive half
        of the rule -- what the entry is parked on is the figures, and text alone is not
        them. The overview still lands, because that part of the response did arrive."""
        def no_votes(url):
            return {"overview": "Teksti ilman ääniä", "genres": [{"id": 18}]}

        _, out = self.run_main(no_votes)
        e = self.cache()["old film"]
        self.assertEqual(e["fi"], "Teksti ilman ääniä")
        self.assertEqual((e["r"], e["n"]), (7.1, 400))
        self.assertEqual(e["c"], self.stale_day)
        self.assertIn("1 scheduled, 0 re-read, 1 failed and still due", out)

    def test_a_response_with_only_a_vote_count_settles_nothing(self):
        """It used to set the rating to 0 over the top of a real one, stamp the entry
        with today and log it as re-read. The pair is what an entry is parked on."""
        _, out = self.run_main(lambda url: {"overview": "Teksti", "vote_count": 900})
        e = self.cache()["old film"]
        self.assertEqual((e["r"], e["n"]), (7.1, 400), "a real rating was erased")
        self.assertEqual(e["c"], self.stale_day)
        self.assertIn("1 scheduled, 0 re-read, 1 failed and still due", out)
        # Handled, not survived: half a pair must be ignored rather than carried into
        # the arithmetic and caught by the per-title guard three lines later.
        self.assertNotIn("[enrich] Old Film:", out)

    def test_a_response_with_only_a_vote_average_settles_nothing(self):
        """The other half, which used not to be noticed at all: no `vote_count` meant the
        branch never ran, so the entry was written with today's date anyway."""
        _, out = self.run_main(lambda url: {"overview": "Teksti", "vote_average": 8.2})
        e = self.cache()["old film"]
        self.assertEqual((e["r"], e["n"]), (7.1, 400))
        self.assertEqual(e["c"], self.stale_day)
        self.assertIn("1 scheduled, 0 re-read, 1 failed and still due", out)
        self.assertNotIn("[enrich] Old Film:", out)

    def test_a_film_nobody_has_voted_on_is_still_a_successful_read(self):
        """Zero is a value. Rejecting it would park every unrated film for ever, and the
        MIN_VOTES gate already decides whether a score is worth showing."""
        _, out = self.run_main(lambda url: {"overview": "Teksti", "vote_count": 0,
                                            "vote_average": 0})
        e = self.cache()["old film"]
        self.assertEqual((e["r"], e["n"]), (0, 0))
        self.assertEqual(e["c"], self.today)
        self.assertIn("1 scheduled, 1 re-read, 0 failed and still due", out)

    # -- the backlog rotates -------------------------------------------------------------

    def backlog(self, n=8, budget=3):
        """`n` stale entries against a forced budget of `budget`. -> {key: entry}.

        More stale than one run can take, so which of them a second run picks is the
        question. Oldest first by `c`, ids 100 upward, none of them ever attempted.
        """
        stale = {enrich_tmdb.norm(f"T{i:02d}"):
                 entry((datetime.date.today()
                        - datetime.timedelta(days=20 - i)).isoformat(), i=100 + i,
                       title=f"T{i:02d}")
                 for i in range(n)}
        self.write_cache(stale)
        (self.dir / "area-zz.json").write_text(json.dumps({
            "generated": self.today, "dates": [], "horizon": "",
            "shows": [{"title": f"T{i:02d}", "start": "2026-09-02T18:00:00+03:00"}
                      for i in range(n)],
        }), encoding="utf-8")
        # Patched where it lives. enrich_tmdb used to carry a copy of this name, and a
        # copy is a thing that stops being the one the code reads.
        saved = refresh.REFRESH_BUDGET
        refresh.REFRESH_BUDGET = budget
        self.addCleanup(lambda: setattr(refresh, "REFRESH_BUDGET", saved))
        return stale

    def ids_asked(self):
        """The movie ids this run went to TMDB for, and reset. -> set of str."""
        asked = {u.split("/movie/")[1].split("/")[0].split("?")[0]
                 for u in self.calls if "/movie/" in u and "/genre/" not in u}
        self.calls.clear()
        return asked

    def test_a_failed_id_does_not_hold_the_budget_on_the_next_run(self):
        """Driven twice through main(). Every detail read fails, so `c` never moves and
        only the recorded attempt can stop the same ids being asked again."""
        self.backlog()

        def boom(url):
            raise RuntimeError("500 from TMDB")

        self.run_main(boom)
        first = self.ids_asked()
        self.run_main(boom)
        second = self.ids_asked()
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(first & second, set(),
                         "the same failed ids held the budget a second time")

    def test_a_refresh_that_dies_after_the_detail_read_still_records_the_attempt(self):
        """The same starvation through the path the guard above does not cover.

        `a` was written just before the cache entry, after the video request, so a title
        that read its detail and then failed on `/videos` skipped the write entirely and
        kept an entry saying it had never been attempted. Never-attempted sorts ahead of
        everything, so the same three ids came back every run for ever. The detail
        request succeeds here on purpose: the failure has to land outside the one handler
        the earlier tests exercise.
        """
        stale = self.backlog()

        def ok(url):
            return {"overview": "Teksti", "vote_count": 900, "vote_average": 8.2,
                    "genres": [{"id": 18}]}

        def no_videos(url):
            raise RuntimeError("500 from TMDB")

        self.run_main(ok, videos=no_videos)
        first = self.ids_asked()
        self.run_main(ok, videos=no_videos)
        second = self.ids_asked()
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(first & second, set(),
                         "a title that died after its detail read stayed at the head "
                         "of the queue")

    def test_such_a_title_keeps_everything_it_had(self):
        """Only the attempt marker moves. `c` in particular: the entry aborted before a
        complete replacement could be written, so it is still due."""
        stale = self.backlog()

        def ok(url):
            return {"overview": "Uusi teksti", "vote_count": 900, "vote_average": 8.2}

        def no_videos(url):
            raise RuntimeError("500 from TMDB")

        self.run_main(ok, videos=no_videos)
        after = self.cache()
        touched = [k for k, v in after.items() if v.get("a") == self.today]
        self.assertEqual(len(touched), 3, "the attempt was not recorded")
        for k in touched:
            was = stale[k]
            self.assertEqual(after[k]["c"], was["c"], "the entry was parked")
            for field in ("r", "n", "fi", "en", "v", "i", "x", "g", "p"):
                self.assertEqual(after[k][field], was[field], f"{k}.{field}")

    def test_an_exception_after_the_write_does_not_put_the_old_entry_back(self):
        """The other side of the same guard. Everything up to and including the cache
        write succeeded, so the refresh is real and must survive whatever raises after
        it -- restoring the cached entry there would undo a rating that was read."""
        self.backlog(n=1)

        def exploding_sleep(seconds=0):
            if seconds == 0.25:                # the per-title pause, after the write
                raise RuntimeError("after the write")

        enrich_tmdb.time = types.SimpleNamespace(sleep=exploding_sleep)

        def ok(url):
            return {"overview": "Uusi teksti", "vote_count": 900, "vote_average": 8.2}

        self.run_main(ok)
        e = self.cache()[enrich_tmdb.norm("T00")]
        self.assertEqual((e["r"], e["n"]), (8.2, 900), "a real refresh was rolled back")
        self.assertEqual(e["c"], self.today)
        self.assertEqual(e["a"], self.today)

    def test_the_fresh_entry_is_not_touched_at_all(self):
        """Two entries, one due and one not. The one that is not must cost no requests,
        or the budget means nothing."""
        self.run_main(lambda url: {"overview": "x", "vote_count": 1, "vote_average": 1})
        self.assertEqual([u for u in self.calls if "/99" in u], [])
        self.assertEqual(self.cache()["other film"]["c"], self.today)

    def test_a_failed_refresh_does_not_turn_the_pass_into_a_re_search(self):
        """The id is kept even when the detail read fails, so the next pass spends two
        requests on it rather than starting from a title search again."""
        def boom(url):
            raise RuntimeError("500 from TMDB")

        self.run_main(boom)
        self.assertEqual(self.cache()["old film"]["i"], self.ID)
        self.assertEqual([u for u in self.calls if "/search/movie" in u], [])


if __name__ == "__main__":
    unittest.main()
