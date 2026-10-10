"""The past-times control inflects its count in Finnish.

One hidden screening reads "Näytä aiempi", two or more "Näytä {n} aiempaa"; the reverse
action is "Piilota aiemmat" whatever the count. The label used to be one template, which
produced "Näytä 1 aiempaa". `pastLabel(open, n, T)` is sliced verbatim out of index.html by
tests/past_label_harness.js and run with the shipped strings, so the decision and the
words are both under test.
"""
import json
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = _ctx.ROOT / "tests" / "past_label_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PastLabelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_one_hidden_screening_is_singular(self):
        self.assertEqual(self.r["fi_one"], "Näytä aiempi")
        self.assertNotIn("1", self.r["fi_one"])

    def test_two_or_more_take_the_count(self):
        self.assertEqual(self.r["fi_two"], "Näytä 2 aiempaa")
        self.assertEqual(self.r["fi_eleven"], "Näytä 11 aiempaa")

    def test_the_reverse_action_ignores_the_count(self):
        self.assertEqual(self.r["fi_open_one"], "Piilota aiemmat")
        self.assertEqual(self.r["fi_open_two"], "Piilota aiemmat")

    def test_swedish_and_english_have_their_own_singular(self):
        self.assertEqual(self.r["sv_one"], "Visa en tidigare")
        self.assertEqual(self.r["sv_three"], "Visa 3 tidigare")
        self.assertEqual(self.r["en_one"], "Show 1 earlier")
        self.assertEqual(self.r["en_three"], "Show 3 earlier")

    def test_every_language_carries_all_three_strings(self):
        for lang in ("fi", "sv", "en"):
            t = self.r["__L"][lang]
            self.assertIn("{n}", t["showPast"], lang)
            self.assertNotIn("{n}", t["showPastOne"], lang)
            self.assertTrue(t["hidePast"], lang)

    def test_the_renderer_calls_the_shared_function(self):
        self.assertIn("pastLabel(open, gone.length, L[state.lang])", HTML)
        self.assertNotIn(".showPast.replace('{n}', gone.length)", HTML)


if __name__ == "__main__":
    unittest.main()
