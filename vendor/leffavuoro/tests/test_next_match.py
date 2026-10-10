"""An empty film search offers the next day that search finds a screening (2026-09-13).

Searching for a film on a day it does not play rendered "Yksikään elokuva ei vastaa
suodattimia" and a clear-filters button, even when the film plays later that week. The
next-day link was suppressed by design whenever a filter was on. Now a nonblank search
with nothing on the selected day offers the earliest later screening the same search and
filters find, as one button in the existing empty-state style, beside the clear action;
clicking it selects that day through the ordinary date path and keeps the search, the
area, the filters and the view. Without a search the plain next-day link is unchanged.

The decision is `nextMatch()`, sliced verbatim out of index.html by
tests/next_match_harness.js and driven with controlled schedules. The DOM half is pinned
at source level here and verified live against the served page.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "next_match_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class NextMatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_the_film_plays_tomorrow(self):
        self.assertEqual(self.r["tomorrow"], {"title": "Dune", "iso": "2026-09-16",
                                              "at": "2026-09-16T16:30:00.000Z"})

    def test_days_without_the_film_are_skipped(self):
        self.assertEqual(self.r["days_later"]["iso"], "2026-09-19")

    def test_an_earlier_candidate_that_fails_a_filter_is_passed_over(self):
        self.assertEqual(self.r["filtered"]["iso"], "2026-09-18")

    def test_no_future_match_means_no_suggestion(self):
        self.assertIsNone(self.r["none"])

    def test_todays_matches_all_past_offers_the_later_one(self):
        self.assertEqual(self.r["today_passed"]["iso"], "2026-09-17")

    def test_the_earliest_of_several_wins_whatever_the_input_order(self):
        self.assertEqual(self.r["earliest"]["at"], "2026-09-16T09:15:00.000Z")

    def test_a_blank_search_is_no_search(self):
        self.assertIsNone(self.r["blank"])
        self.assertIsNone(self.r["empty"])

    def test_the_helsinki_date_decides_the_day(self):
        self.assertEqual(self.r["boundary_after_midnight"]["iso"], "2026-09-16")
        self.assertIsNone(self.r["boundary_same_day"])

    def test_a_later_day_never_leads_to_a_past_screening(self):
        self.assertIsNone(self.r["later_day_but_past"])

    def test_bad_starts_are_ignored(self):
        self.assertIsNone(self.r["bad_start"])


class WiringTest(unittest.TestCase):
    """The DOM half, pinned at source level."""

    def test_both_empty_states_and_the_nothing_left_message_offer_it(self):
        self.assertRegex(HTML, r"function emptyActions\(\)\{ return \(nextMatchLink\(\) \|\| nextDayLink\(\)\) \+ widerLinks\(\) \+ clearTimeLink\(\) \+ clearFiltersLink\(\); \}")
        self.assertRegex(HTML, r"nomore\}\$\{emptyContext\(\)\}\$\{nextMatchLink\(\) \|\| nextDayLink\(\)\}\$\{widerLinks\(\)\}")
        # Both views announce the suggestion with the empty message.
        self.assertEqual(HTML.count("setListStatus(emptyStatus());"), 2)

    def test_the_suggestion_is_computed_from_current_state_at_render(self):
        body = HTML[HTML.index("function nextMatchInfo()"):HTML.index("function nextMatchLink()")]
        self.assertIn("jsonCache[state.area]", body)
        # The list's own predicate and the Helsinki date, not a UTC slice.
        self.assertIn("nextMatch(all, state.filter, state.dateStr, new Date(), passFilters, fiDate)", body)
        self.assertNotIn("state.shows", body)          # the day-narrowed list is not the source

    def test_the_action_reuses_the_date_path_and_the_button_style(self):
        self.assertRegex(HTML, r'<button class="nextday" data-goto="\$\{esc\(hit\.iso\)\}">\$\{esc\(hit\.label\)\}</button>')
        handler = HTML[HTML.index("const goto = e.target.closest('[data-goto]');"):]
        handler = handler[:handler.index("return;")]
        self.assertIn("selectDay(iso)", handler)
        self.assertIn("chip.focus()", handler)

    def test_the_label_exists_in_three_languages(self):
        self.assertEqual(len(re.findall(r"nextMatch:'", HTML)), 3)
        self.assertEqual(len(re.findall(r"atTime:'", HTML)), 3)
        self.assertIn("nextMatch:'Seuraava näytös', atTime:'klo'", HTML)
        self.assertIn("nextMatch:'Nästa visning', atTime:'kl.'", HTML)
        self.assertIn("nextMatch:'Next screening', atTime:'at'", HTML)


if __name__ == "__main__":
    unittest.main()
