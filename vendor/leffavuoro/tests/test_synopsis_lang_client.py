"""Which synopsis a reader is shown, per interface language.

`index.html` is frozen; the maintainer authorised this one exception on 2026-09-16, for the
Swedish selection and nothing else. So what the change may and may not do is worth pinning:
Swedish gains a slot of its own and falls back the way it always did, and Finnish and
English are unchanged.

From 2026-09-22 the same block also answers *which* slot the text came from, so the sheet
can label a synopsis that is not in the reader's language; `tests/test_synopsis_note.py`
covers the label and this file still covers the choice.

Driven through tests/synopsis_lang_harness.js, which extracts `synPick` verbatim from
index.html between its markers. The clamp, the expand button and `esc()` are DOM plumbing
and stay verified live.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "synopsis_lang_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
FI, SV, EN = "Suomeksi.", "På svenska.", "In English."


class MarkerTest(unittest.TestCase):
    """The markers are the seam, and nothing else in the repo guards one.

    A renamed marker makes the harness exit 2, which the tests below would report as a
    failure -- but only if they run. This asserts the seam directly so a rename is a failing
    test rather than a quiet hole.
    """

    def test_the_block_is_there_and_named_after_its_harness(self):
        self.assertIn("// --- synopsis language: pure, extracted verbatim by "
                      "tests/synopsis_lang_harness.js ---", HTML)
        self.assertIn("// --- end synopsis language ---", HTML)

    def test_the_selection_lives_inside_the_block(self):
        a = HTML.index("// --- synopsis language:")
        b = HTML.index("// --- end synopsis language ---")
        block = HTML[a:b]
        self.assertIn("function synPick(s, lang){", block)
        self.assertIn("['sv','fi','en']", block)

    def test_the_sheet_reads_the_synopsis_through_it_and_nowhere_else(self):
        """One call site and one fallback order. A second copy of the ternary is how the
        text and the label that names its language would come to disagree."""
        self.assertEqual(HTML.count("synPick(f.s, lang)"), 1)
        self.assertEqual(HTML.count("['sv','fi','en']"), 1)
        self.assertNotIn("f.s.fi || f.s.en", HTML)

    def test_the_service_worker_version_is_past_the_one_this_change_shipped(self):
        """A floor, not an equality. The bump that had to happen with the Swedish
        selection was to v170 and the history records it; pinning that exact string made
        the next client change fail a test about synopses, which is a test asserting the
        date rather than the rule. Every later commit that touches `index.html` bumps it
        again, and CLAUDE.md is where that rule lives."""
        sw = (_ctx.ROOT / "sw.js").read_text(encoding="utf-8")
        m = re.search(r"const CACHE = 'leffavuoro-v(\d+)';", sw)
        self.assertTrue(m, "sw.js states no CACHE version")
        self.assertGreaterEqual(int(m.group(1)), 170)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SelectionTest(unittest.TestCase):
    """The real function, on every shape a films-extra entry's `s` map can take."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True)
        if out.returncode != 0:
            raise AssertionError(f"harness failed ({out.returncode}): {out.stderr}")
        cls.got = json.loads(out.stdout)

    def case(self, name):
        return self.got[name]

    def test_the_block_runs_without_anything_outside_itself(self):
        self.assertTrue(self.got["__ran"])

    def test_a_swedish_reader_takes_the_swedish_text_first(self):
        self.assertEqual(self.case("all")["sv"], SV)
        self.assertEqual(self.case("sv_only")["sv"], SV)
        self.assertEqual(self.case("sv_and_en")["sv"], SV)

    def test_a_swedish_reader_falls_back_to_finnish_then_english(self):
        """Which is exactly what they saw while no Swedish text existed, so a film without
        one reads the same as it did yesterday."""
        self.assertEqual(self.case("fi_en")["sv"], FI)
        self.assertEqual(self.case("fi_only")["sv"], FI)
        self.assertEqual(self.case("en_only")["sv"], EN)

    def test_finnish_is_unchanged_by_the_swedish_slot(self):
        self.assertEqual(self.case("all")["fi"], FI)
        self.assertEqual(self.case("fi_en")["fi"], FI)
        self.assertEqual(self.case("en_only")["fi"], EN)
        self.assertEqual(self.case("sv_only")["fi"], "",
                         "a Finnish reader is never shown the Swedish text")
        self.assertEqual(self.case("sv_and_en")["fi"], EN)

    def test_english_is_unchanged_by_the_swedish_slot(self):
        self.assertEqual(self.case("all")["en"], EN)
        self.assertEqual(self.case("fi_only")["en"], FI)
        self.assertEqual(self.case("sv_only")["en"], "",
                         "an English reader is never shown the Swedish text")

    def test_nothing_to_show_is_an_empty_string_in_every_language(self):
        for name in ("empty", "none", "undef"):
            with self.subTest(case=name):
                self.assertEqual(set(self.case(name).values()), {""})


if __name__ == "__main__":
    unittest.main()
