"""sw.js never caches a failed response, and its cache writes outlive the response.

Posters are cache-first, so a cached 404 stays broken for the life of the cache version;
the generic branch holds index.html, whose cached copy is the offline fallback. Once the
response promise settles the browser may stop the worker, so every write goes through
e.waitUntil. The harness models that: put() settles on a macrotask and `stored` is read
only after the response and every waitUntil promise have settled.

Driven through tests/sw_fetch_harness.js, which runs the real sw.js with stubbed Cache and
fetch and records which URLs the code chose to cache.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "sw_fetch_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ServiceWorkerCacheTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.results = {r["name"]: r for r in json.loads(out.stdout)}

    def stored(self, name):
        return self.results[name]["stored"]

    # -- failures are never written ------------------------------------------------

    def test_a_404_poster_is_not_cached(self):
        self.assertEqual(self.stored("poster_404"), [],
                         "a cache-first 404 stays broken for the life of the cache")

    def test_a_500_poster_is_not_cached(self):
        self.assertEqual(self.stored("poster_500"), [])

    def test_a_500_page_is_not_cached(self):
        self.assertEqual(self.stored("page_500"),
                         [], "a cached 500 becomes the offline fallback")

    def test_a_404_data_file_is_not_cached(self):
        self.assertEqual(self.stored("data_404"), [])

    # -- success still is ----------------------------------------------------------

    def test_a_200_poster_is_cached(self):
        self.assertEqual(len(self.stored("poster_200")), 1)

    def test_a_200_page_is_cached(self):
        self.assertEqual(len(self.stored("page_200")), 1)

    def test_a_200_data_file_is_cached(self):
        self.assertEqual(len(self.stored("data_200")), 1)

    # -- scope ---------------------------------------------------------------------

    def test_cross_origin_is_left_alone(self):
        """Ticket links and trailers are someone else's origin; the SW must not touch
        them at all, not merely decline to cache them."""
        self.assertFalse(self.results["cross_origin"]["intercepted"])

    def test_a_non_get_is_left_alone(self):
        self.assertFalse(self.results["not_get"]["intercepted"])

    # -- the background check is reported, whatever it answered ---------------------

    def posted(self, name):
        return self.results[name]["posted"]

    def test_a_cached_file_is_answered_at_once_and_its_check_reported(self):
        """The page gets the cached copy, and one message: newer bytes landed and the
        check is done. `fresh` is what re-reads the slot; `checked` releases the banner."""
        r = self.results["check_cached_200"]
        self.assertEqual(r["body"], "old")
        self.assertEqual(self.posted("check_cached_200"),
                         [{"fresh": "/data/area-x.json", "checked": "/data/area-x.json", "ok": True}])

    def test_a_failed_check_is_reported_and_says_nothing_is_fresh(self):
        """A 500 or a dropped connection behind a cached copy: the page keeps what it has
        and learns the check is over, so a late copy gets its warning without the wait."""
        for name in ("check_cached_500", "check_cached_offline"):
            with self.subTest(name):
                self.assertEqual(self.results[name]["body"], "old")
                self.assertEqual(self.posted(name), [{"checked": "/data/area-x.json", "ok": False}])

    def test_a_first_fetch_reports_its_check_without_fresh(self):
        """No cached copy: the response is the network's, so nothing is to re-read."""
        self.assertEqual(self.posted("check_first_200"),
                         [{"checked": "/data/area-x.json", "ok": True}])
        r = self.results["check_first_offline"]
        self.assertTrue(r["rejected"], "the page still sees the failure")
        self.assertEqual(r["posted"], [{"checked": "/data/area-x.json", "ok": False}])

    def test_a_refused_cache_write_still_answers_the_page(self):
        """Storage full: put() rejects. The first fetch's 200 used to reach the page as a
        network error, and a cached file lost its check. The answer stands, nothing is
        stored, and `fresh` is withheld because nothing newer is in the cache."""
        r = self.results["put_fails_first"]
        self.assertFalse(r["rejected"], "a 200 turned into a network error")
        self.assertEqual(r["stored"], [])
        self.assertEqual(r["posted"], [{"checked": "/data/area-x.json", "ok": True}])
        r = self.results["put_fails_cached"]
        self.assertEqual(r["body"], "old")
        self.assertEqual(r["posted"], [{"checked": "/data/area-x.json", "ok": True}])

    def test_only_data_files_are_reported(self):
        for name in ("poster_200", "page_200"):
            with self.subTest(name):
                self.assertEqual(self.posted(name), [])


ACTIVATE = pathlib.Path(__file__).resolve().parent / "sw_activate_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ServiceWorkerActivationTest(unittest.TestCase):
    """What a new worker does with the previous version's cache before deleting it.

    A worker activates with an empty cache of its own: the navigation that discovered the
    update was served by the old worker, network-first, so nothing had written the new
    one. Deleting the old cache there left an app that had just updated with no shell, no
    schedule and no posters, and a reader who closed the tab got nothing on the next
    offline launch. The sweep also deleted every key it did not recognise, which on a
    shared origin is another tool's storage.
    """

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(ACTIVATE)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=120)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)
        # The harness prints this instead of hanging or dying, so a mutation that breaks
        # activate is a red test rather than a harness that "failed to run".
        if "error" in cls.r:
            raise AssertionError(f"harness error: {cls.r['error']}")

    def test_the_schedule_and_the_posters_survive_the_upgrade(self):
        c = self.r["migrates_the_previous_version"]
        self.assertEqual(c["current"], [
            "https://leffavuoro.fi/data/area-1111.json",
            "https://leffavuoro.fi/data/posters/a.jpg"])
        self.assertEqual(c["deleted"], ["leffavuoro-v188"])

    def test_the_shell_is_not_migrated(self):
        """The rule the delete was written for stands: an old index.html must not come
        back as the offline fallback. Only /data/ crosses a version bump."""
        self.assertNotIn("https://leffavuoro.fi/",
                         self.r["migrates_the_previous_version"]["current"])

    def test_nothing_outside_data_crosses_a_version_bump(self):
        c = self.r["two_version_jump_prefers_the_newer"]
        self.assertNotIn("https://leffavuoro.fi/old.json", c["current"])

    def test_an_entry_this_version_already_holds_is_not_overwritten(self):
        c = self.r["keeps_what_this_version_already_has"]
        self.assertEqual(c["from"]["https://leffavuoro.fi/"], "leffavuoro-v189")
        self.assertEqual(c["from"]["https://leffavuoro.fi/data/area-1111.json"],
                         "leffavuoro-v188")

    def test_only_this_apps_caches_are_deleted(self):
        c = self.r["leaves_a_foreign_cache_alone"]
        self.assertIn("some-other-app", c["surviving"])
        self.assertEqual(c["deleted"], ["leffavuoro-v188"])

    def test_a_two_version_jump_carries_both_and_drops_both(self):
        c = self.r["two_version_jump_prefers_the_newer"]
        self.assertEqual(c["surviving"], ["leffavuoro-v189"])
        self.assertEqual(c["deleted"], ["leffavuoro-v187", "leffavuoro-v188"])
        self.assertIn("https://leffavuoro.fi/data/area-1111.json", c["current"])
        self.assertEqual(c["from"]["https://leffavuoro.fi/data/area-1111.json"],
                         "leffavuoro-v188", "the newer of the two is preferred")

    def test_a_first_install_with_nothing_to_migrate_does_not_fail(self):
        self.assertEqual(self.r["nothing_to_migrate"]["current"], [])
        self.assertEqual(self.r["nothing_to_migrate"]["deleted"], [])


if __name__ == "__main__":
    unittest.main()
