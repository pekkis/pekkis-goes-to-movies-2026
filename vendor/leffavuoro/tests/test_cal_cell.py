"""The month picker marks the selected day with aria-current="date".

The `sel` class alone left the chosen date out of the accessibility tree, while the day
chips above the picker already said `aria-current="date"`. `calCell` is sliced verbatim
out of index.html by tests/cal_cell_harness.js: it takes a day number, an ISO date,
whether the date has showtimes and the selected date, and returns markup. Focus movement,
Escape and the month-nav focus restore stay verified live.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "cal_cell_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class CalCellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- the reported gap ----------------------------------------------------------

    def test_the_selected_day_announces_itself_as_current(self):
        """The whole point: the selected cell carries the same state the day chips do."""
        self.assertIn('aria-current="date"', self.r["selected_available"])

    def test_an_unselected_day_does_not(self):
        """A grid where every cell is current says nothing at all."""
        self.assertNotIn("aria-current", self.r["unselected_available"])

    # -- what must never carry it --------------------------------------------------

    def test_a_day_with_no_showtimes_is_not_a_control(self):
        """It renders as a span, so there is nothing to press and nothing to be current."""
        self.assertTrue(self.r["unselected_unavailable"].startswith("<span"))
        self.assertNotIn("aria-current", self.r["unselected_unavailable"])
        self.assertNotIn("data-day", self.r["unselected_unavailable"])

    def test_an_unavailable_day_matching_the_selection_still_gets_nothing(self):
        """drawCal cannot produce this today. The rule is about what a span may claim,
        not about which inputs happen to reach it, so it is asserted rather than assumed."""
        self.assertTrue(self.r["selected_unavailable"].startswith("<span"))
        self.assertNotIn("aria-current", self.r["selected_unavailable"])

    # -- nothing else moved --------------------------------------------------------

    def test_the_classes_are_unchanged(self):
        """The visual state is still the class, and the styling hangs off it."""
        self.assertIn('class="cal-day has sel"', self.r["selected_available"])
        self.assertIn('class="cal-day has"', self.r["unselected_available"])
        self.assertIn('class="cal-day off"', self.r["unselected_unavailable"])

    def test_the_click_target_still_carries_its_date(self):
        """`data-day` is what the click handler reads."""
        self.assertIn('data-day="2026-09-02"', self.r["unselected_available"])

    def test_the_day_number_is_the_label(self):
        self.assertIn(">30</button>", self.r["two_digit_day"])


if __name__ == "__main__":
    unittest.main()
