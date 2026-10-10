"""How /status/ stays current: one path may reach the network and the other may not.

The loop this pins down shipped on 2026-09-07 and rate-limited the origin. sw.js posts
`{fresh: path}` to every window client after a successful revalidation, including one that
changed nothing; the page answered by loading again, which refetched all 38 metadata files
and produced 38 more messages, in every open tab at once. Five messages took the request
count from 38 to 228.

The source-text checks that were already here did not catch it, because the code read
correctly and the comment above it asserted the opposite of what it did. These drive the
real store through a stubbed `io` and count requests, which is the only thing that would
have failed.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "status_store_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StatusStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_the_harness_ran_every_scenario(self):
        """A scenario that throws prints nothing, and a mutation run reads an empty stdout
        as no test going red. Removing the requeue did exactly that and came back VOID."""
        self.assertNotIn("__error", self.r, self.r.get("__error", ""))

    # -- the deliberate path -------------------------------------------------------------

    def test_the_first_load_reads_the_list_and_every_file_it_names(self):
        r = self.r["first_load"]
        self.assertEqual(r["paths"], ["/data/providers.json", "/data/venuelists-local.json",
                                      "/data/venuelists-cloud.json", "/data/areas.json",
                                      "/data/venues-orion.json", "/data/venues-kinometso.json"])
        self.assertEqual(r["providers"], 3)
        self.assertEqual(r["metaKeys"], ["finnkino", "kinometso", "orion"])
        self.assertEqual(r["renders"], 1)

    # -- the two combined venue files --------------------------------------------------------

    def test_a_load_reads_the_combined_files_and_no_single_provider_file(self):
        r = self.r["combined_load"]
        self.assertEqual(r["paths"], ["/data/providers.json", "/data/venuelists-local.json",
                                      "/data/venuelists-cloud.json", "/data/areas.json"])

    def test_each_providers_health_is_what_its_own_file_gives(self):
        """Freshness, stale, pending and the rest, identical to reading the files one by
        one: the combined file carries them verbatim."""
        r = self.r["combined_load"]
        self.assertTrue(r["sameAsSingleFiles"])
        self.assertEqual((r["meta"]["orion"]["stale"], r["meta"]["kinometso"]["pending"]), (1, 1))
        self.assertEqual(r["meta"]["kinometso"]["oldest"], "2026-09-07T07:00:00+00:00")
        self.assertEqual(r["meta"]["finnkino"]["venues"], 1, "areas.json, Finnkino's own shape")

    def test_a_missing_combined_file_costs_only_its_own_half(self):
        r = self.r["local_half_missing"]
        self.assertIn("/data/venues-orion.json", r["paths"])
        self.assertNotIn("/data/venues-kinometso.json", r["paths"])
        self.assertEqual(r["metaKeys"], ["finnkino", "kinometso", "orion"])

    def test_an_entry_that_is_not_a_provider_file_is_read_on_its_own(self):
        r = self.r["malformed_entry"]
        self.assertIn("/data/venues-kinometso.json", r["paths"])
        self.assertNotIn("/data/venues-orion.json", r["paths"])
        self.assertEqual(r["metsoPending"], 1, "taken from the provider's own file")

    def test_finnkino_ages_on_the_weakest_venue_areas_json_names(self):
        """fetch_data.py stamped areas.json on every run, a venue kept from an earlier
        run included, so Finnkino read as fresh as its newest venue (prior review #17)."""
        r = self.r["finnkino_oldest"]
        self.assertEqual(r["kept"], "2026-09-06T20:00:00+00:00")
        self.assertEqual(r["generated"], "2026-09-07T06:00:00+00:00")
        self.assertEqual(r["legacy"], "2026-09-07T06:00:00+00:00", "no `oldest`: `generated`")

    def test_a_refreshed_combined_file_updates_its_providers_from_the_cache(self):
        """The live path: a worker message for a combined file updates every provider in
        it, never asks the network, and an older entry does not replace a newer one."""
        r = self.r["fresh_combined"]
        self.assertEqual(r["afterNewer"], {"oldest": "2026-09-07T09:00:00+00:00",
                                           "status": "partial", "stale": 1})
        self.assertEqual(r["afterOlder"], "2026-09-07T09:00:00+00:00")
        self.assertEqual(r["orion"], "2026-09-07T06:00:00+00:00", "the other half is untouched")
        self.assertEqual(r["netAdded"], 0)

    def test_the_choice_of_files_is_the_apps_own_function(self):
        """One rule in two pages: the store's copy of venueFilesFrom is the app's, token
        for token."""
        app = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
        page = (_ctx.ROOT / "status" / "index.html").read_text(encoding="utf-8")
        grab = lambda t: " ".join(t[t.index("function venueFilesFrom("):].split("return { files, missing")[0].split())
        self.assertEqual(grab(page), grab(app))

    def test_the_first_load_reads_no_cache(self):
        """It goes through the worker, which serves the cache itself. Reading Cache Storage
        here as well would double every request the page makes."""
        self.assertEqual(self.r["first_load"]["cache"], 0)

    # -- the loop ---------------------------------------------------------------------------

    def test_worker_messages_add_no_network_requests(self):
        """The whole defect in one number. sw.js messages after every revalidation,
        unchanged responses included, so this has to hold for messages that carry nothing
        new: five of them took 38 requests to 228."""
        r = self.r["unchanged_messages"]
        self.assertEqual(r["added"], 0)
        self.assertEqual(r["netAfterMessages"], r["netAfterLoad"])

    def test_worker_messages_are_answered_from_cache_storage(self):
        """Not answered at all would also add no requests, so the cache reads are what
        show the message was actually handled."""
        self.assertGreater(self.r["unchanged_messages"]["cacheReads"], 0)

    def test_a_burst_settles_into_one_pass(self):
        """One message lands per file and a run touches many. Twenty must not schedule
        twenty timers, and must not leave one scheduling the next."""
        r = self.r["burst"]
        self.assertEqual(r["timersScheduled"], 1)
        # One load in a world with no combined files: the list, the two combined files it
        # asks for first, areas.json and the two provider files. Six, and no more after.
        self.assertEqual(r["netAfter"], 6)
        self.assertEqual(r["rendersTotal"], 1)

    # -- what a message may and may not change -------------------------------------------------

    def test_changed_cached_bytes_update_the_state_and_redraw_once(self):
        r = self.r["changed_message"]
        self.assertEqual(r["before"], "2026-09-07T06:00:00+00:00")
        self.assertEqual(r["after"], "2026-09-07T08:30:00+00:00")
        self.assertEqual(r["rendersAdded"], 1)

    def test_an_unchanged_message_redraws_nothing(self):
        """A render that changes nothing is what folding the burst is trying to avoid."""
        self.assertEqual(self.r["unchanged_no_redraw"]["rendersAdded"], 0)

    def test_a_message_for_a_file_the_cache_does_not_hold_changes_nothing(self):
        """And in particular does not fall back to the network, which would be the loop
        again by another route."""
        r = self.r["cache_miss"]
        self.assertEqual(r["netAdded"], 0)
        self.assertEqual(r["rendersAdded"], 0)
        self.assertTrue(r["orionStillHeld"])

    # -- asking the network on purpose -----------------------------------------------------------

    def test_a_resumed_tab_is_throttled(self):
        """Opened, backgrounded and reopened repeatedly is otherwise 38 requests each time."""
        r = self.r["resume_throttle"]
        self.assertFalse(r["secondRan"])
        self.assertEqual(r["afterSecond"], r["afterFirst"])

    def test_a_later_retry_is_still_allowed(self):
        """The throttle delays a resume; it must not disable one."""
        r = self.r["resume_throttle"]
        self.assertTrue(r["thirdRan"])
        self.assertGreater(r["afterThird"], r["afterFirst"])

    def test_a_forced_load_bypasses_the_throttle(self):
        """Boot, and anything else deliberate."""
        r = self.r["force_bypasses_throttle"]
        self.assertTrue(r["ran"])
        self.assertTrue(r["netGrew"])

    def test_a_slower_earlier_load_does_not_overwrite_a_newer_one(self):
        r = self.r["stale_load_dropped"]
        self.assertFalse(r["slowWrote"])
        self.assertTrue(r["fastWrote"])

    # -- state moving underneath a pass ------------------------------------------------------

    def test_a_cache_read_that_started_before_a_newer_load_does_not_win(self):
        """The regression: a pass captures 10:00 bytes, a load completes with 11:00 while
        the read is in flight, and the read then answers. Writing it back walks the page
        backwards to a timestamp the load already superseded."""
        r = self.r["stale_cache_read"]
        self.assertEqual(r["pendingReads"], 1)
        self.assertEqual(r["afterLoad"], "2026-09-07T11:00:00+00:00")
        self.assertEqual(r["afterStaleRead"], "2026-09-07T11:00:00+00:00")

    def test_a_refresh_still_applies_when_no_load_intervened(self):
        """The guard drops a pass that was overtaken. It must not drop every pass."""
        r = self.r["fresh_applies_without_a_load"]
        self.assertEqual(r["after"], "2026-09-07T11:00:00+00:00")

    def test_passes_do_not_overlap(self):
        """`timer` alone did not stop this: it is cleared before the awaits, so a second
        burst could schedule and run beside the first, two passes writing the same keys."""
        r = self.r["no_overlapping_passes"]
        self.assertEqual(r["timersWhileRunning"], 0)
        self.assertEqual(r["readsWhileRunning"], 1)

    def test_a_burst_arriving_during_a_pass_is_drained_after_it(self):
        """Serialising passes must not drop the messages that arrived during one."""
        r = self.r["no_overlapping_passes"]
        self.assertEqual(r["secondPassStarted"], 1)
        self.assertEqual(r["orion"], "2026-09-07T11:00:00+00:00")
        self.assertEqual(r["kinometso"], "2026-09-07T11:30:00+00:00")
        self.assertEqual(r["net"], 6, "one load's six requests and none from the messages")

    def test_a_pass_overtaken_by_a_load_keeps_the_loads_data_and_still_serves_its_queue(self):
        """A load lands while a pass holds a read. The stale bytes that read captured are
        refused, the load's newer payload stands, and the message that arrived meanwhile is
        still applied. Asserted on the state rather than on how the pass got there: whether
        it abandons or runs on and refuses the write, the answer has to be the same."""
        r = self.r["abandoned_pass_requeues"]
        self.assertEqual(r["orion"], "2026-09-07T11:00:00+00:00")
        self.assertEqual(r["kinometso"], "2026-09-07T12:00:00+00:00")
        self.assertEqual(r["net"], 12, "messages added network requests: two loads are 12")

    def test_a_refresh_that_began_under_a_running_load_cannot_regress_the_state(self):
        """The ordering `gen` missed. It moves when a load starts, so a refresh beginning
        while one is already in flight shares that load's generation and passed the guard.
        A load in flight is left to finish, and what it wrote is what stands."""
        r = self.r["refresh_under_a_running_load"]
        self.assertEqual(r["readsWhileLoading"], 0, "a pass started under a running load")
        self.assertEqual(r["afterLoad"], "2026-09-07T11:00:00+00:00")
        self.assertEqual(r["final"], "2026-09-07T11:00:00+00:00")
        self.assertEqual(r["netAddedAfterLoad"], 0)

    def test_a_cache_read_answering_before_the_load_does_not_win_either(self):
        """The reverse completion order. The pass was already running when the load
        started, its read answers first with older bytes, and the load answers after."""
        r = self.r["cache_answers_before_the_load"]
        self.assertEqual(r["readsBefore"], 1)
        self.assertEqual(r["afterCache"], "2026-09-07T06:00:00+00:00")
        self.assertEqual(r["final"], "2026-09-07T11:00:00+00:00")

    def test_a_message_queued_during_a_load_is_drained_after_it_without_requests(self):
        r = self.r["queued_during_load"]
        self.assertEqual(r["readsDuringLoad"], 0)
        self.assertEqual(r["timersAfterLoad"], 1, "the load did not reschedule the pass")
        self.assertEqual(r["netAddedByMessage"], 0)
        self.assertEqual(r["kinometso"], "2026-09-07T12:00:00+00:00")

    def test_a_failed_provider_list_clears_the_rows_and_records_the_check(self):
        """statusModel reads no rows as "could not check". Keeping the old rows would show
        a list nothing had just verified."""
        r = self.r["provider_list_failed"]
        self.assertEqual(r["heldBefore"], 3)
        self.assertEqual(r["providersAfter"], 0)
        self.assertTrue(r["checkedAtMoved"])


if __name__ == "__main__":
    unittest.main()
