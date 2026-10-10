"""A link can name one screening (2026-09-13, v144).

`?area=` and `#m=<film id>` stay as they were; the fragment may add `d=YYYY-MM-DD` and
`t=<start>`. `screeningHash`, `screeningUrl`, `parseSheetHash` and `screeningTarget` are
sliced verbatim out of index.html by tests/screening_link_harness.js and run on their own,
with nextMatch beside them, since the fallback is its rule. The sheet plumbing (the mark
on the ticket, the scroll) is pinned on the source here and checked live.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "screening_link_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
START = "2026-09-13T15:10:00+03:00"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ScreeningLinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        o = json.loads(out.stdout)
        cls.h, cls.u, cls.p, cls.t = o["hash"], o["url"], o["parse"], o["target"]

    # -- building --------------------------------------------------------------------------
    def test_a_plain_film_link_is_what_it_was(self):
        self.assertEqual(self.h["plain"], "m=HO00000413")
        self.assertEqual(self.u["bare"], "https://leffavuoro.fi/?area=city%3AHelsinki#m=1499")

    def test_day_and_start_ride_in_the_fragment_encoded(self):
        self.assertEqual(self.h["full"], "m=HO00000413&d=2026-09-13&t=2026-09-13T15%3A10%3A00%2B03%3A00")
        self.assertEqual(self.h["odd_id"], "m=a%26b%3Dc%20%23x")

    def test_the_share_url_keeps_the_tabs_other_params_and_replaces_area_and_fragment(self):
        self.assertEqual(self.u["full"],
                         "https://leffavuoro.fi/?area=1004&lang=sv#m=HO00000413&d=2026-09-13&t=2026-09-13T15%3A10%3A00%2B03%3A00&v=1004")
        self.assertEqual(self.u["from_page"], "https://leffavuoro.fi/kaupunki/tampere/?area=city%3ATampere#m=61")

    # -- parsing ---------------------------------------------------------------------------
    def test_a_built_fragment_reads_back(self):
        self.assertEqual(self.p["round_trip"], {"fid": "HO00000413", "day": "2026-09-13", "start": START, "venue": ""})
        self.assertEqual(self.h["with_venue"], "m=spider%20man&d=2026-09-13&t=2026-09-13T17%3A00%3A00%2B03%3A00&v=1151")
        self.assertEqual(self.p["with_venue"]["venue"], "1151")
        self.assertEqual(self.p["odd_id"]["fid"], "a&b=c #x")

    def test_an_older_film_link_reads_as_before(self):
        self.assertEqual(self.p["old_link"], {"fid": "HO00000413", "day": "", "start": "", "venue": ""})
        self.assertEqual(self.p["old_link_encoded"]["fid"], "Ryhmä Hau: Dinoelokuva")

    def test_a_malformed_day_or_start_is_dropped_not_guessed(self):
        self.assertEqual(self.p["bad_day"]["day"], "")
        self.assertEqual(self.p["bad_day"]["start"], START, "a raw + in the offset is given back")
        self.assertEqual(self.p["bad_start"], {"fid": "x", "day": "2026-09-13", "start": "", "venue": ""})

    def test_no_film_means_no_sheet(self):
        for case in ("no_film", "empty_film", "nothing", "other_hash"):
            self.assertIsNone(self.p[case], case)

    # -- the screening the sheet opens on ----------------------------------------------------
    def test_a_named_screening_still_ahead_is_the_one(self):
        self.assertEqual(self.t["exact_ahead"], "2026-09-13T15:10")
        self.assertEqual(self.t["exact_other_offset"], "2026-09-13T15:10", "the instant, not the spelling")

    def test_a_named_screening_that_has_gone_falls_back_to_the_next_one(self):
        self.assertEqual(self.t["exact_gone_same_day"], "2026-09-13T15:10")
        self.assertEqual(self.t["day_past"], "2026-09-13T15:10")

    def test_a_named_day_lands_on_its_first_screening_ahead(self):
        self.assertEqual(self.t["start_unknown_day_known"], "2026-09-14T18:00", "the time moved, the day stands")
        self.assertEqual(self.t["day_only"], "2026-09-16T20:45")

    def test_a_day_with_nothing_or_nothing_named_is_the_films_next_screening(self):
        self.assertEqual(self.t["day_without_screenings"], "2026-09-13T15:10")
        self.assertEqual(self.t["nothing_named"], "2026-09-13T15:10")
        self.assertEqual(self.t["no_want"], "2026-09-13T15:10")

    def test_two_cinemas_at_the_same_minute_are_told_apart_by_the_venue(self):
        """57 same-city, same-title, same-start pairs in the committed files (48 in
        Helsinki): a share of Sello 17:00 must not open on Omena 17:00."""
        self.assertEqual(self.t["pair_sello"], "2026-09-13T17:00@1151")
        self.assertEqual(self.t["pair_omena"], "2026-09-13T17:00@1157")
        self.assertEqual(self.t["pair_no_venue"], "2026-09-13T17:00@1151", "an older link without v= takes the first")

    def test_a_named_venue_whose_time_moved_stays_at_that_venue_that_day(self):
        self.assertEqual(self.t["pair_venue_time_gone"], "2026-09-13T17:00@1157", "not Sello's 17:00, Omena's")
        self.assertEqual(self.t["pair_venue_time_moved"], "2026-09-13T17:00@1151")
        self.assertEqual(self.t["pair_unknown_venue"], "2026-09-13T17:00@1151", "a venue the list lacks decides nothing")

    def test_nothing_ahead_is_null_never_a_past_screening(self):
        self.assertIsNone(self.t["all_gone"])
        self.assertIsNone(self.t["empty"])


class SheetPlumbingTest(unittest.TestCase):
    """The sheet reads the fragment through parseSheetHash and marks the target ticket."""

    def test_both_hash_readers_use_the_parser_and_the_old_regex_is_gone(self):
        self.assertNotIn("location.hash.match(/m=(.+)$/)", HTML)
        # syncSheet, refreshOpenSheet, and twice in showSheet's own guard: the film it
        # was opened for, and the film the fragment names once an await has resolved.
        self.assertEqual(HTML.count("parseSheetHash(location.hash)"), 4)
        self.assertIn("if(want) showSheet(want.fid, want);", HTML)

    def test_a_card_click_builds_the_fragment_with_the_same_function(self):
        self.assertIn("location.hash = screeningHash(el.dataset.id);", HTML)
        self.assertNotIn("location.hash = 'm=' +", HTML)

    def test_the_target_ticket_is_marked_and_its_day_scrolled_to(self):
        body = re.search(r"async function showSheet\(fid, want, keepFocus\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertIn("if(want && (want.day || want.start)){", body, "a plain film link changes nothing")
        self.assertIn("screeningTarget(all, want, now, fiDate)", body)
        self.assertIn('.stubs:not([hidden]) .stub[data-i="${hit._i}"]', body, "by index: two cinemas can share a start")
        self.assertNotIn("data-start", body)
        self.assertIn("el.classList.add('pick');", body)
        self.assertIn('data-i="${s._i}"', body)
        self.assertIn("s._vid = s._vid || s.venue || state.area;", body, "every screening in the sheet knows its venue")
        self.assertIn("let h = el.closest('.stubs');", body,
                      "from the day's box: the stub's own siblings are the other tickets")
        self.assertIn("body.scrollTop = h.getBoundingClientRect().top - body.getBoundingClientRect().top", body)
        self.assertIn(".stub.pick{border-color:var(--accent)", HTML)

    def test_a_metadata_refresh_redraws_without_moving_the_mark_the_scroll_or_the_focus(self):
        """Structure, not behaviour, and deliberately: this path is entered from the
        service worker's `{fresh}` message, and `tests/browser` blocks service workers, so
        the browser suite covers the counterweight (a sheet the reader opens takes the
        keyboard) and this covers the wiring. A live test would need a hook in
        `index.html`, which is the maintainer's to grant."""
        fn = re.search(r"async function refreshOpenSheet\(\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertIn("await showSheet(want.fid, want, true);", fn,
                      "the mark is redrawn and the focus flag is passed")
        self.assertLess(fn.index("await showSheet("), fn.index("nb.scrollTop = y"),
                        "then the scroll is put back")
        self.assertLess(fn.index("const key = sheetFocusKey"), fn.index("await showSheet("),
                        "focus is noted before the redraw destroys the control")
        self.assertLess(fn.index("nb.scrollTop = y"), fn.index("back.focus()"),
                        "and restored after")

    def test_only_the_refresh_path_keeps_the_reader_s_focus(self):
        """`keepFocus` is a parameter rather than a test of whether the sheet is already
        open, because a reader following a link to another film from an open sheet is
        opening a sheet and must get the keyboard. One caller passes it."""
        self.assertIn("async function showSheet(fid, want, keepFocus){", HTML)
        self.assertIn("if(closeBtn && !keepFocus) closeBtn.focus();", HTML)
        self.assertEqual(len(re.findall(r"showSheet\([^)]*,\s*true\)", HTML)), 1)

    def test_the_focus_key_survives_the_redraw_by_naming_the_control(self):
        """The markup is rebuilt, so the element is gone: what is kept is what finds it
        again. A control the redraw dropped simply is not found, and focus stays put."""
        fn = re.search(r"function sheetFocusKey\(el\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertIn("if(!el || !sheetEl.contains(el)) return '';", fn,
                      "focus outside the sheet is not the sheet's to move")
        self.assertIn("'.sheet-close'", fn)
        self.assertIn('data-i="${el.dataset.i}"', fn)
        self.assertIn('[data-pastday="${el.dataset.pastday}"]', fn)


if __name__ == "__main__":
    unittest.main()
