"""A cinema with no programme says so, instead of "Ei enää näytöksiä tänään".

`run.py` already distinguishes three empty venues: `pending`, where the adapter confirmed
the upstream answered and listed nothing; `stale`, which keeps its previous programme; and
`unverified`, which has never had data and must stay visibly degraded. Only the status page
read that. The app said the same "nothing more today" about a cinema that is closed for the
season as about one whose last film started an hour ago, on every date the reader tried.

`pendingNotice` is the decision, and it is deliberately narrow:

* it never fires while the payload carries a screening anywhere, so a filter that matched
  nothing, a date past the horizon and an ordinary empty day all keep their own messages;
* a combined city or region needs **every** member pending, because one quiet cinema beside
  one that is playing is not a city with nothing on;
* `unverified` is empty too and is not in `pending`, which is the distinction run.py exists
  to make, so it keeps its own state.

The strings live in `L` and were unused before this: `noProgYet` in all three languages,
left behind when `healthState` moved to the status page in 2026-09-07.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "pending_state_harness.js"
INDEX = _ctx.ROOT / "index.html"

# name, ids in view, the pending ones, payload has any show, expected notice
CASES = [
    # -- one venue --------------------------------------------------------------------
    ("single_pending_empty", ["tahtikino-muhos"], ["tahtikino-muhos"], False, True),
    ("single_pending_but_has_shows", ["ritz-vaasa"], ["ritz-vaasa"], True, False),
    ("single_not_pending_empty", ["kino-x"], [], False, False),
    ("single_unverified_empty", ["kino-new"], [], False, False),
    # -- a combined city or region ----------------------------------------------------
    ("combined_all_pending", ["a", "b", "c"], ["a", "b", "c"], False, True),
    ("combined_some_pending", ["a", "b", "c"], ["a", "b"], False, False),
    ("combined_one_pending", ["a", "b"], ["b"], False, False),
    ("combined_none_pending", ["a", "b"], [], False, False),
    ("combined_all_pending_but_has_shows", ["a", "b"], ["a", "b"], True, False),
    ("combined_pending_lists_a_stranger", ["a", "b"], ["a", "b", "z"], False, True),
    # -- shapes that must not fire ----------------------------------------------------
    ("no_ids_at_all", [], [], False, False),
    ("no_ids_but_pending_listed", [], ["a"], False, False),
    ("ids_null", None, ["a"], False, False),
    ("pending_null", ["a"], None, False, False),
]


def js_cases():
    return [{"name": n, "ids": i, "pendingIds": p, "hasShows": h}
            for n, i, p, h, _ in CASES]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PendingNoticeTest(unittest.TestCase):
    """index.html's pendingNotice(), extracted verbatim."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], input=json.dumps(js_cases()),
                             capture_output=True, text=True, cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stdout}{out.stderr}")
        cls.r = json.loads(out.stdout)
        if "error" in cls.r:
            raise AssertionError(f"harness error: {cls.r['error']}")

    def test_every_case(self):
        for name, ids, pending, has, want in CASES:
            with self.subTest(case=name):
                self.assertEqual(self.r[name], want)

    def test_a_payload_with_any_screening_never_shows_the_notice(self):
        """The guard that keeps filter-empty, past-horizon and ordinary empty days on
        their own messages: all three have a payload with screenings in it."""
        for name, ids, pending, has, want in CASES:
            if has:
                with self.subTest(case=name):
                    self.assertFalse(self.r[name])

    def test_one_playing_cinema_keeps_a_combined_view_out_of_the_notice(self):
        self.assertFalse(self.r["combined_some_pending"])
        self.assertFalse(self.r["combined_one_pending"])
        self.assertTrue(self.r["combined_all_pending"])


class WiringTest(unittest.TestCase):
    """The parts around the pure function, read out of index.html."""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_the_notice_is_decided_before_the_filter_and_date_messages(self):
        """Precedence: a confirmed-empty cinema is not "no match for your filters" and
        not "nothing more today"."""
        body = self.html[self.html.index("function emptyMsg()"):]
        body = body[:body.index("\n  }")]
        self.assertLess(body.index("pendingNotice("), body.index("t.nomatch"),
                        "the pending notice has to be decided first")
        self.assertIn("t.noProgYet", body)

    def test_an_empty_answer_past_the_stale_window_is_not_repeated_as_current(self):
        """Navettakino, 2026-10-10: "no programme right now" under a banner saying the
        schedule had not refreshed for 88 hours, while the cinema listed three screenings.
        The age is judged by the same `staleNotice` and `STALE_H` as that banner."""
        body = self.html[self.html.index("function emptyMsg()"):]
        body = body[:body.index("\n  }")]
        self.assertIn("return staleNotice(state.sources, Date.now(), STALE_H) "
                      "? t.noProgUnchecked : t.noProgYet;", body)

    def test_the_venue_list_marks_pending_without_another_request(self):
        """Read off the provider file already being parsed for its venues. A second
        request per provider on boot is what this must not become."""
        block = self.html[self.html.index("async function fetchVenueLists"):]
        block = block[:block.index("async function loadAreas")]
        self.assertIn("Array.isArray(j.pending)", block)
        self.assertIn("pending: pend.has(v.id)", block)
        # areas.json for the Finnkino list, the two combined files, and one
        # venues-{prov}.json per provider neither carries, are what this function fetches;
        # pending must add no URL and no second read of the provider file.
        self.assertEqual(block.count("data/venues-"), 1)
        self.assertEqual(block.count("fetchJSON("), 3)
        self.assertNotIn("pending.json", block)

    def test_noProgYet_is_defined_in_all_three_languages_and_now_used(self):
        keys = re.findall(r"noProgYet:'([^']*)'", self.html)
        self.assertEqual(len(keys), 3, "fi, sv and en")
        for k in keys:
            with self.subTest(text=k):
                self.assertTrue(k.strip())
        self.assertIn("t.noProgYet", self.html, "defined and unused was the defect")

    def test_the_three_translations_are_the_expected_ones(self):
        """Pinned so a language cannot quietly lose the string that this feature turns
        on. These are the ones already in the file, unchanged by this change."""
        self.assertIn("noProgYet:'Ei ohjelmistoa juuri nyt'", self.html)
        self.assertIn("noProgYet:'Inget program just nu'", self.html)
        self.assertIn("noProgYet:'No programme right now'", self.html)

    def test_noProgUnchecked_is_defined_in_all_three_languages(self):
        self.assertIn("noProgUnchecked:'Ohjelmistoa ei voitu tarkistaa'", self.html)
        self.assertIn("noProgUnchecked:'Programmet kunde inte kontrolleras'", self.html)
        self.assertIn("noProgUnchecked:'The programme could not be checked'", self.html)
        self.assertEqual(len(re.findall(r"\bnoProgUnchecked:'", self.html)), 3)

    def test_every_language_block_still_carries_the_other_empty_messages(self):
        """Preserved behaviour: the notice is an addition, and nomatch, notpublished,
        nomore and noshows all still exist for the cases that keep them."""
        for key in ("nomatch", "notpublished", "nomore", "noshows"):
            with self.subTest(key=key):
                self.assertEqual(len(re.findall(rf"\b{key}:'", self.html)), 3, key)

    def test_a_combined_view_resolves_its_members_and_a_single_venue_itself(self):
        block = self.html[self.html.index("function viewVenueIds()"):]
        block = block[:block.index("\n  }")]
        self.assertIn("groupIdsOf(state.area)", block)
        self.assertIn("venueIndex[state.area] ? [state.area] : []", block)

    def test_the_cache_moved_with_index_html(self):
        sw = (_ctx.ROOT / "sw.js").read_text(encoding="utf-8")
        m = re.search(r"const CACHE = 'leffavuoro-v(\d+)'", sw)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 195)


if __name__ == "__main__":
    unittest.main()
