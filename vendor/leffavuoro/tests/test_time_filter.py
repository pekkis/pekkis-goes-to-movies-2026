"""Ajat answers "what can I still see after 18:00" (2026-09-20).

Sorting by time already existed; narrowing did not, so a reader scrolled past the
afternoon to find the evening. A minimum start time, inclusive, in the Ajat view only.

It is a time-of-day question, not a past/future one: "starts at or after 18:00" means the
same thing next Saturday as today, so the control is not gated on the date and the
existing past-screening behaviour is untouched. The comparison runs on `fiTime(s.start)`,
which formats through Europe/Helsinki, so a reader abroad gets Finland wall time. Both
sides are zero-padded 24-hour HH:MM, which is why a string compare is a time compare.

Held in `state.minTime`, memory only: it is a browsing aid for one visit, not a saved
preference, and `kino-prefs` is untouched. `startsAtOrAfter` is sliced verbatim out of
index.html by tests/time_filter_harness.js.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "time_filter_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def render_times_source():
    return re.search(r"function renderTimes\(\)\{.*?\n  \}\n", HTML, re.S).group(0)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StartsAtOrAfterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        payload = json.loads(out.stdout)
        cls.r = payload["after"]
        cls.slots = payload["slots"]

    def test_no_case_threw(self):
        threw = {k: v for k, v in self.r.items() if isinstance(v, dict)}
        self.assertEqual(threw, {})

    def test_the_default_is_all_times(self):
        for key in ("no_min_empty", "no_min_null", "no_min_undefined", "blank_clock_no_min"):
            with self.subTest(key):
                self.assertIs(self.r[key], True)

    def test_the_boundary_is_inclusive(self):
        """"Alkaen 18:00" shows the 18:00 screening. This is the whole point."""
        self.assertIs(self.r["exactly_at"], True)
        self.assertIs(self.r["midnight_exact"], True)
        self.assertIs(self.r["one_minute_before"], False)
        self.assertIs(self.r["one_minute_after"], True)

    def test_zero_padding_makes_the_compare_a_time_compare(self):
        self.assertIs(self.r["morning_vs_evening"], False)
        self.assertIs(self.r["evening_vs_morning"], True)
        self.assertIs(self.r["padded_nine_vs_ten"], True)
        self.assertIs(self.r["midnight_vs_evening"], False)
        self.assertIs(self.r["late_vs_midnight"], True)

    def test_a_screening_with_no_clock_is_not_admitted_under_a_restriction(self):
        for key in ("blank_clock", "null_clock"):
            with self.subTest(key):
                self.assertIs(self.r[key], False)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class TimeSlotsTest(StartsAtOrAfterTest):
    """Which marks the select offers."""

    def test_today_starts_half_an_hour_behind_the_clock(self):
        """A screening that has just begun is still reachable."""
        self.assertEqual(self.slots["today_starts_30_back"][0], "17:30")
        self.assertEqual(self.slots["today_rounds_down"][0], "17:30", "18:29 rounds down")
        self.assertEqual(self.slots["today_on_the_half"][0], "18:00", "18:30 less 30 is exact")

    def test_every_mark_is_half_an_hour_apart(self):
        got = self.slots["today_starts_30_back"]
        self.assertEqual(got, ["17:30", "18:00", "18:30", "19:00", "19:30",
                               "20:00", "20:30", "21:00", "21:30"])

    def test_it_never_starts_before_the_days_first_screening(self):
        """At 06:10 with nothing before 20:00, marks from 05:30 all mean "all times"."""
        self.assertEqual(self.slots["today_before_first"], ["20:00", "20:30", "21:00"])
        self.assertEqual(self.slots["early_morning_clamped"][0], "10:00")

    def test_another_day_has_no_now_to_sit_behind(self):
        self.assertEqual(self.slots["other_day_from_first"][0], "13:00")
        self.assertEqual(self.slots["other_day_single"], ["19:00"])

    def test_it_ends_at_the_last_screening(self):
        self.assertEqual(self.slots["today_starts_30_back"][-1], "21:30")
        self.assertEqual(self.slots["other_day_from_first"][-1], "18:30")

    def test_no_marks_when_there_is_nothing_to_narrow(self):
        for key in ("no_screenings", "all_junk", "now_past_last"):
            with self.subTest(key):
                self.assertEqual(self.slots[key], [])

    def test_an_unreadable_clock_is_ignored_rather_than_guessed(self):
        self.assertEqual(self.slots["junk_ignored"], ["18:00"])

    def test_without_marks_the_bar_is_drawn_only_for_the_reveal(self):
        """A day wholly in the past has no mark worth offering but does have a reveal."""
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("if(!slots.length) return reveal ?", bar)
        self.assertIn(": '';", bar)


class AjatFloorTest(unittest.TestCase):
    """Ajat's floor is now unless the reader lowers it or names one.

    Reverses a 2026-09-01 entry that dropped a past-showtimes option because "past rows
    are already handled" at 45% opacity with pointer-events:none. Dimming does not remove
    the scroll: 257 of 449 of a day's screenings, 57%, had already started at 18:34 on
    2026-09-20. The argument and the measurement are in docs/archive/2026-09-app.md.
    """

    def test_the_default_floor_is_now(self):
        src = render_times_source()
        self.assertIn("(state.showPast ? matched : matched.filter(s => s.start >= now))", src)
        self.assertIn("showPast:false", HTML.replace(" ", ""))

    def test_a_chosen_mark_is_the_floor_and_admits_what_started_after_it(self):
        """"Alkaen 17:30" means from 17:30, including the screening that began at 17:45."""
        src = render_times_source()
        self.assertIn("const rows = state.minTime", src)
        self.assertIn("? matched.filter(s => startsAtOrAfter(fiTime(s.start), state.minTime))", src)

    def test_the_reveal_is_the_label_the_cards_and_the_sheet_use(self):
        """No new string: pastLabel already has all three languages and both directions."""
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("pastLabel(state.showPast, goneCount, T)", bar)
        self.assertIn('class="pastlink tpast"', bar)
        self.assertIn('aria-expanded="${state.showPast}"', bar)

    def test_the_reveal_stands_down_while_a_mark_is_chosen(self):
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("const reveal = (!state.minTime && goneCount)", bar)

    def test_a_day_that_has_wholly_passed_still_offers_the_reveal(self):
        """No marks left to choose, but something to reveal."""
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("if(!slots.length) return reveal ? `<div class=\"tbar\">${reveal}</div>` : '';", bar)

    def test_toggling_it_keeps_focus_on_it(self):
        self.assertIn("if(e.target.closest('[data-showpast]')){", HTML)
        self.assertIn("state.showPast = !state.showPast;", HTML)
        self.assertIn("const again = document.querySelector('[data-showpast]');", HTML)

    def test_the_reveal_is_memory_only_like_the_mark(self):
        self.assertNotRegex(HTML, r"prefs\.set\(\{[^}]*showPast")


class TimeFilterWiringTest(unittest.TestCase):
    """Where it applies, where it does not, and what it is held in."""

    def test_it_runs_on_finland_wall_time(self):
        self.assertIn("startsAtOrAfter(fiTime(s.start), state.minTime)", HTML)
        self.assertIn("const fiTime = d => fiTimeFmt.format(d);", HTML)
        self.assertIn("timeZone: FI_TZ", HTML)

    def test_it_applies_only_in_ajat(self):
        """passFilters is shared with Leffat, so the restriction must not live there."""
        pf = re.search(r"function passFilters\(s\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertNotIn("minTime", pf)
        self.assertNotIn("startsAtOrAfter", pf)
        self.assertIn("startsAtOrAfter", render_times_source())

    def test_it_narrows_what_the_other_filters_already_matched(self):
        """Combined, not instead of: the search and the chips run first, and the floor
        -- whether the mark or `now` -- narrows what they matched."""
        src = render_times_source()
        self.assertIn("const matched = state.shows.filter(passFilters)", src)
        self.assertIn("const gone = matched.filter(s => s.start < now);", src)
        self.assertIn("matched.filter(s => startsAtOrAfter(fiTime(s.start), state.minTime))", src)

    def test_it_is_memory_only(self):
        """A browsing aid for one visit. kino-prefs keeps venue, theme and favourite."""
        self.assertIn("minTime:''", HTML.replace(" ", ""))
        self.assertNotRegex(HTML, r"prefs\.set\(\{[^}]*minTime")
        self.assertNotIn("'kino-minTime'", HTML)

    def test_switching_views_leaves_the_selection_alone(self):
        """Leffat ignores it; coming back to Ajat re-applies it."""
        for fn in (r"function setView\(", r"function clearFilters\("):
            m = re.search(fn + r".*?\n  \}", HTML, re.S)
            if m:
                self.assertNotIn("minTime", m.group(0),
                                 f"{fn} must not reset the time restriction")

    def test_the_control_is_one_native_select_above_the_list(self):
        """Half-hour marks, not a free clock and not preset chips or a slider."""
        src = render_times_source()
        self.assertIn("main.innerHTML = timesLegend + bar + rows.map(s => {", src)
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn('<select class="tinput" id="minTime"', bar)
        self.assertNotIn('type="time"', bar)
        self.assertNotIn("range", bar)
        self.assertEqual(len(re.findall(r'id="minTime"', HTML)), 1)

    def test_all_times_is_the_first_option_not_a_second_button(self):
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("<option value=\"\"", bar)
        self.assertIn("esc(T.tAll)", bar)
        self.assertNotIn("tclear", bar)

    def test_a_value_off_the_list_stays_selectable(self):
        """The clock moves; a mark chosen before it passed must not silently vanish."""
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn("slots.includes(state.minTime)", bar)

    def test_the_box_is_36_and_the_select_itself_owns_the_44_floor(self):
        """The select carries the hit area, not a wrapper overlay. An ::after on the
        wrapper covered it and ate every click in both engines (2026-09-20), and could
        never have extended it: a wrapper's pseudo-element is not part of the select."""
        rule = re.search(r"\.tinput\{(.*?)\}", HTML, re.S).group(1).replace(" ", "")
        box = re.search(r"\.tfield\{(.*?)\}", HTML, re.S).group(1).replace(" ", "")
        # `height`, not `min-height`: WebKit ignores min-height on a menulist and drew the
        # select 19 px, half the floor, while Chromium honoured it (both measured).
        self.assertIn("height:44px", rule, "the control is the hit area")
        self.assertIn("margin:-4px0", rule, "4 px past the box above and below")
        self.assertNotIn("min-height", rule)
        self.assertIn("appearance:none", rule)
        self.assertIn("-webkit-appearance:none", rule)
        self.assertIn("background:transparent", rule)
        self.assertIn("height:36px", box, "the wrapper draws what is seen")
        self.assertNotIn(".tfield::after", HTML, "no overlay over the control")

    def test_the_focus_ring_follows_the_control_into_the_wrapper(self):
        """The select's own outline is suppressed, so the box has to show focus."""
        self.assertIn(".tfield:focus-within{outline:2px solid var(--accent)", HTML)
        self.assertIn(".tinput:focus{outline:none}", HTML)

    def test_appearance_none_brings_its_own_chevron(self):
        """Stripping the native control strips its arrow; #areaSelect's is reused."""
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn('class="tchev"', bar)
        self.assertIn('aria-hidden="true"', bar)
        self.assertIn("M3 5.2 7 9.2 11 5.2", bar, "the same path the venue button draws")
        self.assertIn("pointer-events:none", re.search(r"\.tfield \.tchev\{(.*?)\}", HTML, re.S).group(1),
                      "the chevron must not intercept the click either")

    def test_an_emptied_list_says_so_and_clears_only_the_time(self):
        """One empty path, so the list-status pairing rule keeps holding."""
        src = render_times_source()
        self.assertIn("state.timeEmptied = !rows.length && matched.length > 0;", src)
        self.assertEqual(src.count("main.innerHTML"), 2, "one empty render and one list render")
        self.assertIn("if(state.view === 'times' && state.minTime && state.timeEmptied) return t.tNone;",
                      HTML)
        self.assertIn("function clearTimeLink()", HTML)
        self.assertIn("widerLinks() + clearTimeLink() + clearFiltersLink();", HTML)
        self.assertIn("if(e.target.closest('[data-cleartime]')){ state.minTime = ''; render(); return; }",
                      HTML)
        self.assertNotIn("clearFilters", re.search(r"function clearTimeLink\(\)\{.*?\n  \}",
                                                   HTML, re.S).group(0))

    def test_the_field_is_labelled_and_reachable(self):
        bar = re.search(r"function timeBar\(goneCount\)\{.*?\n  \}", HTML, re.S).group(0)
        self.assertIn('<label class="tlbl" for="minTime">', bar)
        self.assertIn('aria-label="${esc(T.tFromA)}"', bar)
        self.assertIn(".tfield:focus-within{outline:2px solid var(--accent)", HTML)

    def test_all_three_languages_carry_every_string(self):
        for key in ("tFrom", "tAll", "tFromA", "tNone"):
            with self.subTest(key):
                # \b so `sheetNone:'` is not counted as a `tNone:'`.
                self.assertEqual(len(re.findall(r"\b" + key + r":'", HTML)), 3)
        for want in ("tFrom:'Alkaen'", "tFrom:'Från'", "tFrom:'From'",
                     "tAll:'Kaikki ajat'", "tAll:'Alla tider'", "tAll:'All times'"):
            self.assertIn(want, HTML)


if __name__ == "__main__":
    unittest.main()
