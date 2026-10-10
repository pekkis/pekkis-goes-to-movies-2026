"""A tag the room name already says is not said twice on one line (2026-09-03).

The Ajat meta line read "LUXE 6 · K-16 · 172 min · 2D · Anniskelu · LUXE": the room
carries the format and the method tag repeats it. 774 rows in five classes on 2026-09-03
(LUXE, "N Plus" and Plus, iSense, Prime, IMAX). The card's stub already had `stubTags`:
drop a tag the room name contains, case-folded, and drop plain 2D. The Ajat line runs the
same function. A glyph tag stays on the stub even when every screening shares it, so the
Anniskelu filter cannot make its own marker disappear.

`stubTags` is sliced verbatim out of index.html by tests/stub_tags_harness.js.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "stub_tags_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def render_times_source():
    return re.search(r"function renderTimes\(\)\{.*?\n  \}\n", HTML, re.S).group(0)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StubTagsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_the_room_keeps_the_format_word(self):
        """The five classes in the data. The room is verbatim, what the ticket prints,
        so it stays; the tag that repeats it goes."""
        self.assertEqual(self.r["luxe_room"], ["Anniskelu"])
        self.assertEqual(self.r["plus_room"], ["Anniskelu"])
        self.assertEqual(self.r["isense_room"], [])
        self.assertEqual(self.r["prime_room"], [])
        self.assertEqual(self.r["imax_room"], ["Anniskelu"])
        self.assertEqual(self.r["luxe_isense_room"], [])

    def test_a_format_the_room_does_not_name_survives(self):
        self.assertEqual(self.r["imax_in_sali"], ["IMAX"])
        self.assertEqual(self.r["three_d_kept"], ["3D"])
        self.assertEqual(self.r["bare_room_only"], ["Anniskelu", "Perheleffa"])

    def test_plain_2d_goes_and_nothing_else_does_without_a_room(self):
        self.assertEqual(self.r["no_room"], ["Anniskelu"])
        self.assertEqual(self.r["null_room"], ["LUXE"])

    def test_the_match_folds_case_and_skips_empty_tags(self):
        self.assertEqual(self.r["case_folds"], [])
        self.assertEqual(self.r["empty_tag"], ["Anniskelu"])


class TagPlacementSourceTest(unittest.TestCase):
    """Where the two renderers apply the rule; pinned on the source."""

    def test_the_ajat_line_runs_the_stub_rule(self):
        src = render_times_source()
        self.assertIn("const tags = stubTags((s.method || '').split(' · ').filter(Boolean), s.aud);", src)
        self.assertNotIn("esc(s.method)", src)
        self.assertIn("...tags.map(x => ['', esc(x)])].filter(x => x[1]);", src)
        self.assertIn("...langParts(s.lang, !pre.length)", src)

    def test_a_glyph_tag_never_folds_onto_the_card(self):
        common = re.search(r"const common = (.*?);\n", HTML).group(1)
        self.assertIn("!glyphOf(f)", common)
        self.assertIn("tagSets.every(set => set.has(f))", common)


if __name__ == "__main__":
    unittest.main()
