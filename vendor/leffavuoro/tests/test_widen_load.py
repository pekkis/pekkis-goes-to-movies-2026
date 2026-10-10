"""A wider search keeps the selected day through the load (2026-09-13, v138).

widenTo() went through selectVenue() and loadSchedule() like a pick from the venue list,
and loadSchedule() carries the late-evening rule: today with no shows at all moves to the
next day that has some. A wider search is the same search on the same day in a bigger
place, so the day has to survive the load, decided before anything is drawn. A plain pick
keeps the old behaviour.

tests/widen_load_harness.js runs the real selectVenue(), loadSchedule(), selectDay() and
widenTo() with stubbed DOM and payloads, on a fetch and on a cache hit. The advance itself
is not the reader's choice: it tracks nothing and saves no day (2026-09-26).
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "widen_load_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class WidenLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_the_day_stays_today_when_the_wider_scope_has_nothing_on_it(self):
        s = self.r["widen_nothing_today"]
        self.assertEqual(s["dateStr"], self.r["today"])
        self.assertEqual(s["area"], "city:C")
        self.assertEqual(s["shows"], 0, "the empty state is what renders")
        self.assertEqual(s["renders"], 1)
        self.assertFalse(s["advanced"], "the advance flag is not touched either")

    def test_search_chips_chains_view_and_the_favourite_survive(self):
        s = self.r["widen_nothing_today"]
        self.assertEqual((s["filter"], s["chains"], s["fKids"], s["view"]),
                         ("Zzzz", ["finnkino"], True, "times"))
        self.assertEqual(s["fav"], "v1")
        self.assertEqual(s["prefArea"], "v1", "the last-browsed slot is not written by any pick since 2026-09-13")
        self.assertIsNone(s.get("prefDay"), "the day is not rewritten")
        self.assertTrue(s["focused"])

    def test_a_plain_pick_still_advances_and_resets_the_chains(self):
        s = self.r["pick_nothing_today"]
        self.assertEqual(s["dateStr"], self.r["tomorrow"])
        self.assertTrue(s["advanced"])
        self.assertIsNone(s["chains"])
        self.assertEqual(s["filter"], "Zzzz", "a pick never touched the search")

    def test_the_advance_is_not_the_readers_choice(self):
        """It went through selectDay(), which tracks `date_changed` and saves the day,
        although the reader chose nothing (prior review #28)."""
        s = self.r["pick_nothing_today"]
        self.assertEqual(s["dateStr"], self.r["tomorrow"])
        self.assertIsNone(s.get("prefDay"))
        self.assertNotIn("date_changed", s["tracked"])
        self.assertIn("area_opened", s["tracked"], "the recorder sees the pick's own event")

    def test_a_readers_own_day_is_tracked_and_saved(self):
        s = self.r["reader_picks_day"]
        self.assertEqual(s["dateStr"], self.r["tomorrow"])
        self.assertEqual(s["prefDay"], self.r["tomorrow"])
        self.assertEqual(s["tracked"].count("date_changed"), 1)

    def test_a_wider_scope_with_shows_today_keeps_the_day_and_shows_them(self):
        s = self.r["widen_shows_today"]
        self.assertEqual(s["dateStr"], self.r["today"])
        self.assertEqual(s["shows"], 1)

    def test_the_cache_hit_path_keeps_the_day_too(self):
        s = self.r["widen_cached"]
        self.assertEqual(s["dateStr"], self.r["today"])
        self.assertNotIn("group city:C", s["calls"], "served from jsonCache, nothing fetched")

    def test_a_day_chosen_by_hand_is_kept_on_a_plain_pick_as_before(self):
        s = self.r["pick_after_manual_day"]
        self.assertEqual(s["dateStr"], self.r["today"])

    def test_an_unknown_target_does_nothing(self):
        s = self.r["widen_unknown"]
        self.assertEqual((s["area"], s["renders"], s["focused"]), ("v1", 0, False))


class WiringTest(unittest.TestCase):
    def test_the_day_is_decided_before_the_render(self):
        body = HTML[HTML.index("async function loadSchedule(opts)"):HTML.index("// Stale banner and footer credit")]
        self.assertIn("const keepDay = !!(opts && opts.keepDay);", body)
        self.assertIn("if(!keepDay && !state.advanced && state.dateStr === fiToday() && !state.shows.length){", body)
        self.assertLess(body.index("if(!keepDay"), body.index("render();"))


if __name__ == "__main__":
    unittest.main()
