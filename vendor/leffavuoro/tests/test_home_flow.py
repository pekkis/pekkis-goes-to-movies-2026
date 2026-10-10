"""The homepage is a chooser until a location is named (2026-09-13).

tests/home_flow_harness.js runs the real selectVenue(), loadSchedule(), showHome() and
onPopState() from index.html, plus the <head> script that decides the first paint,
against stubbed DOM, history and data. Routing precedence itself (URL, favourite, chooser)
is test_area_routing.py's; this file pins what happens around a pick and Back/Forward.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "home_flow_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class HomeFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.o = json.loads(out.stdout)

    # 5. a pick loads the screenings and names the location in the URL, saving nothing
    def test_a_pick_from_the_chooser_loads_and_writes_the_url(self):
        s = self.o["pick_from_home"]
        self.assertEqual(s["area"], "v1")
        self.assertEqual(s["search"], "?area=v1")
        self.assertIn("push /?area=v1", s["calls"])
        self.assertIn("fetch data/area-v1.json", s["calls"])
        self.assertIn("render", s["calls"])
        self.assertEqual(s["classes"], ["scoped"])

    def test_a_pick_saves_no_favourite_and_no_last_browsed_slot(self):
        s = self.o["pick_from_home"]
        self.assertEqual(s["prefs"], {"fav": ""})
        self.assertFalse([c for c in s["calls"] if c.startswith("prefs.set")])

    def test_picking_what_the_url_already_names_adds_no_history_entry(self):
        s = self.o["pick_same"]
        self.assertFalse([c for c in s["calls"] if c.startswith("push") or c.startswith("replace")])
        self.assertEqual(s["area"], "v1")

    # 8. asynchronous loading never lands on the chooser
    def test_a_schedule_that_resolves_after_back_to_the_chooser_is_not_drawn(self):
        s = self.o["stale_load"]
        self.assertEqual(s["area"], "")
        self.assertEqual(s["main"], '<section id="home">HOME</section>')
        self.assertNotIn("render", s["calls"])
        self.assertEqual(s["classes"], [])

    def test_a_failure_that_arrives_after_back_to_the_chooser_is_not_drawn_either(self):
        s = self.o["stale_failure"]
        self.assertEqual(s["main"], '<section id="home">HOME</section>')
        self.assertNotIn("ERR", s["main"])
        self.assertEqual(s["area"], "")

    def test_a_refresh_on_the_chooser_fetches_and_draws_nothing(self):
        """refreshAll() runs on tab focus and rollover and ends in loadSchedule(); with no
        location that used to fetch `data/area-.json` and draw its 404 over the chooser."""
        s = self.o["refresh_on_chooser"]
        self.assertEqual(s["calls"], [])
        self.assertEqual(s["main"], '<section id="home">HOME</section>')

    def test_back_to_the_bare_page_restores_the_chooser(self):
        s = self.o["back_to_home"]
        self.assertEqual((s["area"], s["classes"], s["homeNote"]), ("", [], ""))
        self.assertEqual(s["main"], '<section id="home">HOME</section>')
        self.assertIn("renderStatus", s["calls"], "the credit line and banners are cleared")

    def test_back_to_the_bare_page_with_a_favourite_shows_the_favourite(self):
        """`/` means the same thing on Back as on a visit: the favourite when one is
        stored. The URL stays bare and no history entry is added."""
        s = self.o["back_to_home_with_fav"]
        self.assertEqual((s["area"], s["search"]), ("v1", ""))
        self.assertFalse([c for c in s["calls"] if c.startswith("push") or c.startswith("replace")])
        self.assertIn("fetch data/area-v1.json", s["calls"])
        self.assertNotIn("renderHome ", s["calls"])

    def test_forward_to_a_location_shows_it_without_a_new_entry(self):
        s = self.o["forward_to_area"]
        self.assertEqual((s["area"], s["search"]), ("v2", "?area=v2"))
        self.assertIn("fetch data/area-v2.json", s["calls"])
        self.assertFalse([c for c in s["calls"] if c.startswith("push")])

    # 7. an unknown location recovers to the chooser with the note
    def test_a_history_entry_naming_an_unknown_location_shows_the_chooser_with_a_note(self):
        s = self.o["popstate_unknown"]
        self.assertEqual(s["area"], "")
        # The key, not the text: renderHome() translates it, so a language switch redraws
        # the note in the new language (audit K7).
        self.assertEqual(s["homeNote"], "homeUnknown")
        self.assertIn("renderHome homeUnknown", s["calls"])

    def test_a_hash_only_step_changes_nothing(self):
        """`hashchange` fires for this one and owns the fragment. Reconciling the sheet
        here as well would redraw it twice for one step."""
        s = self.o["popstate_hash_only"]
        self.assertEqual(s["calls"], [])
        self.assertEqual(s["area"], "v1")

    def test_a_step_to_another_venue_closes_the_sheet_before_loading(self):
        """The sheet is modal and belongs to the venue being left. A traversal that
        changes the area and the fragment together fires no hashchange, so this is the
        only thing that closes it -- and it happens before the new schedule is asked for,
        so the wrong cinema's film is never on screen beside the right one's page."""
        s = self.o["forward_to_area"]
        self.assertIn("hideSheet", s["calls"])
        self.assertLess(s["calls"].index("hideSheet"), s["calls"].index("class+scoped"),
                        "closed before the new venue is selected")
        self.assertEqual(s["calls"][-1], "syncSheet",
                         "and the entry's own fragment is honoured once its shows are in")

    def test_a_slow_venue_load_does_not_reopen_a_sheet_the_reader_left(self):
        """`.then(() => { if(state.area === id) syncSheet(); })`. The fetch for the entry
        being travelled to lands after the reader has gone back to the chooser, and the
        entry's own `#m=` would otherwise open that venue's film over the chooser -- with
        the sheet modal, over a page it has no business covering."""
        s = self.o["stale_sheet_after_move"]
        self.assertIn("hideSheet", s["calls"], "the traversal closed the old sheet")
        self.assertNotIn("syncSheet", s["calls"],
                         "a load that landed after the reader moved on reopened a sheet")
        self.assertEqual(s["area"], "")

    def test_the_same_load_arriving_in_time_is_honoured(self):
        """The counterweight: the guard must not cost the ordinary case, or Forward into
        a sheet entry would stop opening anything."""
        s = self.o["sheet_after_arrival"]
        self.assertEqual(s["calls"][-1], "syncSheet")
        self.assertEqual(s["area"], "v2")

    def test_a_step_back_to_the_chooser_closes_the_sheet(self):
        """Home clears the selection, after which `syncSheet` returns early and no later
        hashchange could close it either."""
        for key in ("back_to_home", "back_to_home_with_fav"):
            with self.subTest(step=key):
                self.assertIn("hideSheet", self.o[key]["calls"])

    # 9. a film link without a location waits, then opens in the chosen scope
    def test_a_film_link_without_a_location_opens_after_the_pick(self):
        s = self.o["film_link_after_pick"]
        self.assertEqual(s["calls"][-1], "syncSheet")
        self.assertEqual(s["search"], "?area=v1")

    # 7. a boot that fails before anything is on screen recovers to the chooser
    def test_a_failed_boot_shows_the_chooser_with_the_load_failure_line(self):
        b = self.o["boot_fallback"]
        self.assertEqual(b["fav_or_link_lists_failed"], "loadFail")
        self.assertEqual(b["nothing_asked_lists_failed"], "")
        self.assertIsNone(b["location_already_shown"], "the schedule's own error stands")

    # 1, 4, 7. the first paint decision
    def test_the_head_script_scopes_only_a_link_or_a_favourite(self):
        e = self.o["early"]
        self.assertFalse(e["nothing"]["scoped"])
        self.assertTrue(e["fav"]["scoped"])
        self.assertTrue(e["url"]["scoped"])
        self.assertFalse(e["old_area_slot_only"]["scoped"], "an older build's last-browsed slot")

    def test_the_head_script_survives_corrupt_or_unavailable_storage(self):
        e = self.o["early"]
        for case in ("corrupt", "storage_throws", "storage_throws_with_url"):
            self.assertFalse(e[case]["threw"], case)
        self.assertFalse(e["corrupt"]["scoped"])
        self.assertFalse(e["storage_throws"]["scoped"])
        self.assertTrue(e["storage_throws_with_url"]["scoped"], "a link scopes before storage is touched")


if __name__ == "__main__":
    unittest.main()
