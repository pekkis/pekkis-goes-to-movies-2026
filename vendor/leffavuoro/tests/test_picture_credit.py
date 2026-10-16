"""The credit a non-film event's picture carries in the app's sheet.

Kannusali's pictures come from Espoo's Linked Events, CC BY 4.0 by default and "event only"
for a picture that must not leave its event (HRI's page for the dataset, read 2026-10-16).
The credit names the photographer where one is given, the source and the picture's own
licence, and an "event only" picture is never called CC BY. A picture under any other
licence gets no credit, and the app draws the tile for it. `pictureCredit` is sliced
verbatim out of index.html by tests/picture_credit_harness.js and run with the shipped strings.
"""
import json
import shutil
import subprocess
import unittest

import _ctx

HARNESS = _ctx.ROOT / "tests" / "picture_credit_harness.js"
CC = '<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="license noopener">CC BY 4.0</a>'


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PictureCreditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_an_event_only_picture_names_its_photographer_source_and_licence(self):
        self.assertEqual(self.r["event_only_credited"],
                         "Kuva: Mikko Mäntyniemi · Espoon tapahtumarajapinta · "
                         "käyttö vain tapahtuman yhteydessä (event only)")

    def test_a_picture_with_no_photographer_names_the_source(self):
        self.assertEqual(self.r["event_only_uncredited"],
                         "Kuva: Espoon tapahtumarajapinta · "
                         "käyttö vain tapahtuman yhteydessä (event only)")

    def test_a_cc_by_picture_links_its_licence(self):
        self.assertEqual(self.r["cc_by_uncredited"],
                         f"Kuva: Espoon tapahtumarajapinta · {CC}")

    def test_an_event_only_picture_is_never_called_cc_by(self):
        for k in ("event_only_credited", "event_only_uncredited", "event_only_sv",
                  "event_only_en"):
            with self.subTest(k=k):
                self.assertNotIn("CC BY", self.r[k])
                self.assertIn("(event only)", self.r[k])

    def test_the_credit_follows_the_language(self):
        self.assertEqual(self.r["event_only_sv"],
                         "Bild: Katri Kuusela · Espoon tapahtumarajapinta · "
                         "endast i samband med evenemanget (event only)")
        self.assertEqual(self.r["event_only_en"],
                         "Photo: Espoon tapahtumarajapinta · "
                         "for use with this event only (event only)")

    def test_a_picture_under_no_known_licence_gets_no_credit(self):
        self.assertEqual((self.r["unknown_licence"], self.r["no_licence"]), ("", ""))

    def test_the_photographer_is_escaped(self):
        self.assertIn("&lt;b&gt;Kuvaaja&lt;/b&gt;", self.r["escaped"])


if __name__ == "__main__":
    unittest.main()
