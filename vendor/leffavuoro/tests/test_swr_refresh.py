"""A background refresh lands in the slot it was asked for, sees every cinema, and refreshes metadata.

The worker serves data JSON from cache and posts `{fresh: path}` when a refresh lands.
Rules pinned here: every held slot the refreshed file feeds is compared and written, its
own and the combined city holding it, whether or not it is the one on screen; each is
compared against the entry taken before its await; a render happens only if that area is
still on screen; a slot emptied or
refilled meanwhile is left alone, since the entry is compared by identity; a city is
compared on a per-member `stamp` while its `generated` keeps reporting the oldest member;
the re-read comes from Cache Storage, never a fetch, so no message loop is possible and
there is no cooldown; a burst of member messages folds into one follow-up read.

`films-extra.json` has its own store, `makeExtraStore`: a failed fetch is not memoised,
concurrent loads share one fetch, the worker's message is a cache read compared on the
serialised content, an open sheet is redrawn once on a real change, and a load in flight
when the message arrives cannot overwrite the newer copy.

All sliced verbatim out of index.html by tests/swr_refresh_harness.js.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "swr_refresh_harness.js"

A_GEN = "2026-09-05T06:00:00+00:00"     # the oldest member, and the one that stays put
B_GEN = "2026-09-05T07:00:00+00:00"
B_NEW = "2026-09-05T08:00:00+00:00"
A_NEW = "2026-09-05T09:00:00+00:00"
A_RELOAD = "2026-09-05T10:00:00+00:00"  # what loadSchedule refilled the slot with
A_LATEST = "2026-09-05T11:00:00+00:00"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class BackgroundRefreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- the slot a late answer lands in ------------------------------------------------------

    def test_a_late_answer_for_a_never_touches_b(self):
        """The reader switched to B during A's read. B's slot is byte-for-byte what it was."""
        r = self.r["late_answer_after_switch"]
        self.assertEqual(r["B"]["generated"], B_GEN)
        self.assertEqual([s["theatre"] for s in r["B"]["shows"]], ["B"])

    def test_a_late_answer_for_a_is_kept_for_a(self):
        """The payload is not thrown away: A's slot takes it, so returning to A serves the
        refreshed programme without another fetch."""
        r = self.r["late_answer_after_switch"]
        self.assertEqual(r["A"]["generated"], A_NEW)
        self.assertEqual([s["theatre"] for s in r["A"]["shows"]], ["A"])

    def test_a_late_answer_for_a_does_not_redraw_b(self):
        """B is on screen and B did not change. A render here would flash B's own data
        back at the reader for no reason -- or, in the old code, draw A's under B."""
        self.assertEqual(self.r["late_answer_after_switch"]["applied"], 0)

    def test_a_refresh_for_the_cinema_on_screen_is_applied_and_drawn(self):
        r = self.r["answer_still_selected"]
        self.assertEqual(r["A"]["generated"], A_NEW)
        self.assertEqual(r["applied"], 1)
        self.assertEqual(r["B"]["generated"], B_GEN)

    def test_the_same_generated_changes_nothing(self):
        r = self.r["unchanged"]
        self.assertEqual(r["applied"], 0)
        self.assertEqual(r["A"]["generated"], A_GEN)

    def test_the_harness_ran_every_scenario(self):
        """A scenario that throws, or one whose handler never settles, used to print
        nothing and error every test in setUpClass, which a mutation run scores as no test
        going red. The harness prints what it has and names the failure here instead."""
        self.assertNotIn("__error", self.r, self.r.get("__error", ""))

    def test_a_file_no_held_slot_is_fed_by_reads_nothing(self):
        r = self.r["not_a_hit"]
        self.assertEqual(r["reads"], [])
        self.assertEqual(r["applied"], 0)

    # -- slots the reader is not looking at ---------------------------------------------

    def test_a_held_slot_off_screen_is_refreshed(self):
        """B is on screen and the message names A. loadSchedule serves a held slot without
        re-reading it, so leaving A alone here served the stale copy on the way back."""
        r = self.r["unselected_venue_slot"]
        self.assertEqual(r["reads"], ["data/area-A.json"])
        self.assertEqual(r["A"]["generated"], A_NEW)

    def test_refreshing_an_off_screen_slot_draws_nothing(self):
        """Writing a slot nobody is looking at must not redraw the cinema that is."""
        r = self.r["unselected_venue_slot"]
        self.assertEqual(r["applied"], 0)
        self.assertEqual(r["B"]["generated"], B_GEN)

    def test_a_member_of_a_held_city_off_screen_is_refreshed(self):
        """The combined city is held behind A. Its member b changed, so the fold is redone
        from both members and the stamp carries b's new time."""
        r = self.r["unselected_city_member"]
        self.assertEqual(r["reads"], ["data/area-a.json", "data/area-b.json"])
        self.assertEqual(r["city"]["key"], f"a@{A_GEN} b@{B_NEW}")
        self.assertEqual(r["applied"], 0)
        self.assertEqual(r["A"]["generated"], A_GEN)

    def test_one_file_refreshes_both_the_venue_and_its_city(self):
        """a is on screen and city:X is held behind it. The two entries go stale
        independently, so one message writes both; only the one on screen is drawn."""
        r = self.r["venue_and_its_city"]
        self.assertEqual(r["reads"],
                         ["data/area-a.json", "data/area-a.json", "data/area-b.json"])
        self.assertEqual(r["a"]["generated"], A_NEW)
        self.assertEqual(r["city"]["titles"], ["Film at a, later", "Film at b"])
        self.assertEqual(r["applied"], 1)

    def test_one_file_refreshes_the_venue_its_city_and_its_area(self):
        """An area is a third slot over the same venue files. The area is on screen, so it
        is the only one drawn, and all three hold the newer programme."""
        r = self.r["venue_city_and_area"]
        self.assertEqual(r["a"]["generated"], A_NEW)
        self.assertEqual(r["city"]["titles"], ["Film at a, later", "Film at b"])
        self.assertEqual(r["area"]["titles"], ["Film at a, later", "Film at b"])
        self.assertEqual(r["applied"], 1)

    def test_a_selection_with_nothing_loaded_is_left_to_load_schedule(self):
        r = self.r["nothing_held"]
        self.assertEqual(r["reads"], [])
        self.assertEqual(r["keys"], ["B"])

    # -- a refresh that lands before its slot exists ----------------------------------------

    def test_an_early_refresh_is_replayed_when_the_slot_is_filled(self):
        """At boot the worker's refresh lands before loadSchedule fills the slot, which it
        then fills with the older copy the prefetch was handed. The message reads nothing;
        filling the slot reads the cached copy once and draws it."""
        r = self.r["early_then_filled"]
        self.assertEqual(r["readsAtMessage"], 0)
        self.assertEqual(r["ids"], ["A"])
        self.assertEqual(r["A"], A_NEW)
        self.assertEqual(r["applied"], 1)
        self.assertEqual((r["again"], r["reads"]), ([], 1), "replayed once, not per fill")

    def test_an_early_refresh_of_a_city_member_rereads_the_city(self):
        r = self.r["early_city_member"]
        self.assertEqual(r["ids"], ["b"])
        self.assertEqual(r["applied"], 1)
        self.assertIn("Film at b, later", r["city"]["titles"])

    def test_a_fill_with_no_early_refresh_reads_nothing(self):
        r = self.r["filled_nothing_early"]
        self.assertEqual((r["ids"], r["reads"], r["applied"]), ([], 0, 0))

    def test_an_early_refresh_waits_for_its_own_slot_across_a_switch(self):
        """The reader left A for B before A's slot existed. B's fill replays nothing of A;
        A's fill later still takes the newer copy, and draws nothing over B."""
        r = self.r["early_across_switch"]
        self.assertEqual(r["onB"], [])
        self.assertTrue(r["earlyA"])
        self.assertEqual(r["onA"], ["A"])
        self.assertEqual(r["A"], A_NEW)
        self.assertEqual(r["B"], "2026-09-05T07:00:00+00:00")
        self.assertEqual(r["applied"], 0, "A is not on screen")

    def test_a_slot_emptied_during_the_read_stays_empty(self):
        """refreshAll clears the whole cache and reloads the selection. A late write here
        would race that reload; the answer is to leave the slot to it."""
        r = self.r["invalidated_during_read"]
        self.assertEqual(r["keys"], [])
        self.assertEqual(r["applied"], 0)

    def test_a_slot_refilled_during_the_read_keeps_the_refill(self):
        """refreshAll emptied A and loadSchedule refilled it with a 10:00 schedule before
        the read answered with a 09:00 snapshot. The refill is the newer one and stays;
        an existence check after the await let the snapshot overwrite it."""
        r = self.r["refilled_during_read"]
        self.assertEqual(r["A"]["generated"], A_RELOAD)
        self.assertEqual([s["title"] for s in r["A"]["shows"]], ["Film at A, reloaded"])
        self.assertEqual(r["applied"], 0)

    def test_a_follow_up_read_compares_against_the_refill(self):
        """A message queued behind the discarded read still gets its follow-up, and that
        follow-up measures against the refilled entry: a newer copy is applied."""
        r = self.r["refilled_then_follow_up"]
        self.assertEqual(r["duringFirst"], 1, "the queued message started no read of its own")
        self.assertEqual(r["afterFirst"]["applied"], 0)
        self.assertEqual(r["afterFirst"]["generated"], A_RELOAD)
        self.assertEqual(r["afterFirst"]["reads"], 2, "exactly one follow-up read")
        self.assertEqual(r["A"]["generated"], A_LATEST)
        self.assertEqual(r["applied"], 1)
        self.assertEqual(r["pending"], 0)

    def test_a_follow_up_for_an_emptied_slot_reads_nothing(self):
        """Emptied and not refilled: there is nothing to compare a read against, so the
        queued message costs no read and the slot is left to whoever emptied it."""
        r = self.r["emptied_then_follow_up"]
        self.assertEqual(r["reads"], 1)
        self.assertEqual(r["applied"], 0)
        self.assertEqual(r["keys"], ["B"])
        self.assertEqual(r["pending"], 0)

    # -- the fold: freshness stays the oldest member's ------------------------------------------

    def test_a_city_reports_its_oldest_member(self):
        """The stale banner's contract, unchanged: the weakest link and its provider."""
        f = self.r["fold"]
        self.assertEqual((f["both"]["generated"], f["both"]["oldest"]), (A_GEN, "p1"))
        self.assertEqual((f["a_newer"]["generated"], f["a_newer"]["oldest"]), (B_GEN, "p2"))
        self.assertEqual((f["a_missing"]["generated"], f["a_missing"]["oldest"]), (B_GEN, "p2"))
        self.assertEqual(f["a_missing"]["missing"], ["A"])
        self.assertEqual((f["none"]["generated"], f["none"]["missing"]), ("", ["A", "B"]))

    def test_the_change_key_is_not_the_freshness_timestamp(self):
        """One member changing must move the key even when `generated` cannot move."""
        f = self.r["fold"]
        self.assertNotEqual(f["both"]["key"], f["a_newer"]["key"])
        self.assertNotEqual(f["both"]["key"], f["a_missing"]["key"])
        self.assertNotEqual(f["both"]["key"], f["none"]["key"])
        self.assertTrue(f["none"]["key"], "an empty city still has a key to compare against")

    # -- the reported defect ----------------------------------------------------------------------

    def test_a_newer_member_updating_is_adopted(self):
        """Cinema A's timestamp is fixed and stays the oldest; cinema B refreshes with a new
        timestamp and a new show. The combined view must take B's update."""
        r = self.r["newer_member_updates"]
        self.assertEqual(r["applied"], 1)
        self.assertIn("Film at b, later", r["city"]["titles"])
        self.assertNotIn("Film at b", r["city"]["titles"])
        self.assertIn("Film at a", r["city"]["titles"])

    def test_the_adopted_view_still_reports_a_for_freshness(self):
        """B moved, A did not, so the banner keeps naming A's age and A's provider."""
        r = self.r["newer_member_updates"]
        self.assertEqual(r["city"]["generated"], A_GEN)
        self.assertEqual(r["city"]["oldest"], "p1")
        self.assertEqual(r["A"]["generated"], A_GEN, "a city refresh must not write into a venue's slot")

    def test_the_oldest_member_updating_moves_the_freshness_source(self):
        r = self.r["oldest_member_updates"]
        self.assertEqual(r["applied"], 1)
        self.assertEqual((r["city"]["generated"], r["city"]["oldest"]), (B_GEN, "p2"))
        self.assertIn("Film at a, later", r["city"]["titles"])

    def test_a_member_dropping_out_or_coming_back_is_a_change(self):
        gone = self.r["member_goes_missing"]
        self.assertEqual(gone["applied"], 1)
        self.assertEqual(gone["city"]["missing"], ["B"])
        self.assertEqual(gone["city"]["titles"], ["Film at a"])
        back = self.r["member_comes_back"]
        self.assertEqual(back["applied"], 1)
        self.assertEqual(back["city"]["missing"], [])
        self.assertEqual(sorted(back["city"]["titles"]), ["Film at a", "Film at b"])

    def test_a_city_where_nothing_moved_is_left_alone(self):
        r = self.r["city_unchanged"]
        self.assertEqual(r["applied"], 0)

    # -- the cooldown's replacement --------------------------------------------------------------

    def test_messages_during_a_read_fold_into_one_more_read(self):
        """Three messages while the first read runs: one read in flight, none started for
        the second and third, exactly one follow-up read after the first settles, and that
        follow-up sees the member that landed late."""
        r = self.r["burst"]
        self.assertEqual(r["afterFirst"], 2, "the first read fetched both members")
        self.assertEqual(r["duringFirst"], 2, "messages during the read start nothing")
        self.assertEqual(r["afterSecondStarted"], 4, "one follow-up read, not one per message")
        self.assertEqual(r["settled"], 4)
        self.assertIn("Film at b, later", r["city"]["titles"])
        self.assertIn("Film at a, later", r["city"]["titles"])

    def test_a_burst_renders_each_time_something_changed(self):
        """The first read carried a's update, the follow-up b's; the read after the drain
        found nothing new and drew nothing."""
        self.assertEqual(self.r["burst"]["applied"], 2)

    def test_after_the_drain_a_new_message_reads_again(self):
        """Nothing is dropped and nothing is swallowed once the drain is over."""
        r = self.r["burst"]
        self.assertEqual(r["afterFourth"], 6)
        self.assertEqual(r["pending"], 0)

    # -- film metadata behind an open sheet ---------------------------------------------------

    def test_an_open_sheet_gains_a_synopsis_when_the_file_refreshes(self):
        """The film had no entry when the sheet opened. The worker cached a newer file and
        posted a message. The store read the cache, swapped the map in and redrew the sheet
        once. No second fetch."""
        r = self.r["meta_open_sheet_gains_synopsis"]
        self.assertIsNone(r["before"])
        self.assertEqual(r["after"], "Marjane Satrapin lapsuus")
        self.assertEqual((r["changed"], r["redraws"]), (1, 1))
        self.assertEqual(r["fetches"], 0, "the refresh must not fetch")
        self.assertEqual(r["pendingReads"], 0)

    def test_a_failed_fetch_is_not_memoised_and_a_later_one_succeeds(self):
        """The old memo wrote `{}` on failure, so no later sheet in the tab had a synopsis.
        Two callers during one load share the fetch. The failed load returns an empty map.
        The next caller fetches again and succeeds. After that the map is memoised."""
        r = self.r["meta_failed_then_succeeds"]
        self.assertTrue(r["shared"])
        self.assertEqual(r["firstResult"], [])
        self.assertTrue(r["fetchedAgain"])
        self.assertEqual(r["second"], "Marjane Satrapin lapsuus")
        self.assertEqual(r["thirdFetches"], 0)
        self.assertTrue(r["memoised"])
        self.assertEqual(r["changed"], 0, "a load is not a change; the caller renders it")

    def test_an_unchanged_rewrite_redraws_nothing_and_fetches_nothing(self):
        """The file is rewritten several times a day with the same content and the same
        bare date. Three messages during one read fold into one follow-up read. Neither
        read finds a change. Nothing is redrawn and nothing touches the network."""
        r = self.r["meta_unchanged_no_redraw"]
        self.assertEqual(r["readsDuring"], 1)
        self.assertEqual(r["followUp"], 1, "one follow-up read for the two queued messages")
        self.assertEqual((r["changed"], r["redraws"]), (0, 0))
        self.assertEqual(r["fetches"], 0)
        self.assertEqual(r["pendingReads"], 0)

    def test_a_delayed_first_load_cannot_overwrite_the_newer_copy(self):
        """The worker answers a load from its cache and refreshes behind, so a load still
        in flight when the message arrives carries the older copy. The fresh read waits for
        it, then applies the newer copy on top. The final map is the newer one."""
        r = self.r["meta_delayed_load_cannot_overwrite"]
        self.assertEqual(r["readBeforeLoad"], 0, "the read waits for the load to land")
        self.assertEqual(r["final"], "Marjane Satrapin lapsuus")
        self.assertEqual((r["changed"], r["redraws"]), (1, 1))

    def test_a_message_before_anyone_asked_for_the_file_costs_nothing(self):
        r = self.r["meta_fresh_before_any_load"]
        self.assertEqual((r["reads"], r["fetches"], r["changed"]), (0, 0, 0))
        self.assertIsNone(r["films"])

    def test_a_change_with_no_sheet_open_updates_the_map_without_a_redraw(self):
        r = self.r["meta_change_sheet_closed"]
        self.assertEqual(r["after"], "Marjane Satrapin lapsuus")
        self.assertEqual((r["changed"], r["redraws"]), (1, 0))

    def test_the_handler_routes_the_file_to_the_store_only(self):
        r = self.r["meta_routed"]
        self.assertEqual(r["metaFresh"], 2)
        self.assertEqual((r["reads"], r["applied"]), (0, 0), "no area read for a metadata message")
        self.assertEqual(r["areaMessageMetaFresh"], 0)

    def test_the_re_read_comes_from_cache_storage_not_the_network(self):
        """A fetch through the worker would start another background refresh and another
        message -- the loop the cooldown used to hold back. The harness has no fetch at
        all, so a reader that reached for one would have failed above."""
        r = self.r["read_cached"]
        self.assertEqual(r["hit"]["generated"], A_GEN)
        self.assertIn("not cached", r["miss"])
        self.assertFalse(r["fetchDefined"])


if __name__ == "__main__":
    unittest.main()
