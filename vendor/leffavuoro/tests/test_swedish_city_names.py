"""The Swedish pages name a city as the app's Swedish mode does.

Until 2026-09-25 `sv/kaupunki/turku/` read "Filmer och visningstider – Turku" while the
app's Swedish city list shows "Åbo" and links to that page. `build_pages.city_sv()` reads
the app's own `CITY_SV` out of index.html rather than keeping a second copy. It is display
text only: the slug, `?area=` and the JSON-LD locality keep the Finnish name, as the app's
keys do.
"""
import json
import re
import shutil
import subprocess
import unittest

import _ctx

import build_pages as bp

ROOT = _ctx.ROOT


class CitySvTableTest(unittest.TestCase):

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_table_read_is_the_one_the_app_evaluates(self):
        src = (ROOT / "index.html").read_text(encoding="utf-8")
        literal = re.search(r"const CITY_SV = (\{.*?\});", src, re.S).group(1)
        out = subprocess.run(["node", "-e", f"console.log(JSON.stringify({literal}))"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(bp.city_sv(), json.loads(out.stdout))

    def test_the_committed_app_carries_the_table(self):
        """With no table the build falls back to Finnish names, so the loss is caught
        here rather than by a reader."""
        names = bp.city_sv()
        self.assertGreaterEqual(len(names), 40)
        self.assertEqual(names.get("Turku"), "Åbo")

    def test_only_swedish_takes_the_swedish_name(self):
        names = {"Turku": "Åbo"}
        self.assertEqual([bp.city_name("Turku", lang, names) for lang in ("fi", "sv", "en")],
                         ["Turku", "Åbo", "Turku"])
        self.assertEqual(bp.city_name("Forssa", "sv", names), "Forssa",
                         "a city with no Swedish name keeps its own")


class CommittedPagesTest(unittest.TestCase):
    """Read off the committed pages, which the drift check keeps equal to a rebuild."""

    def test_every_swedish_city_page_heads_with_its_swedish_name(self):
        names = bp.city_sv()
        cities = {bp.slug(c): c for c in names}
        pages = sorted((ROOT / "sv" / "kaupunki").glob("*/index.html"))
        self.assertTrue(pages)
        for p in pages:
            fi = cities.get(p.parent.name)
            if not fi:
                continue
            with self.subTest(page=p.parent.name):
                text = p.read_text(encoding="utf-8")
                h1 = re.search(r"<h1[^>]*>([^<]*)</h1>", text).group(1)
                self.assertTrue(h1.endswith(f"– {names[fi]}"), h1)
                title = re.search(r"<title>([^<]*)</title>", text).group(1)
                self.assertIn(names[fi], title)
                self.assertIn(f'"addressLocality":"{fi}"', text,
                              "the structured data keeps the official Finnish key")

    def test_the_finnish_and_english_pages_keep_the_finnish_name(self):
        for path in ("kaupunki/turku/index.html", "en/city/turku/index.html"):
            with self.subTest(page=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertNotIn("Åbo", text)
                self.assertRegex(re.search(r"<h1[^>]*>([^<]*)</h1>", text).group(1),
                                 r"Turku$")


if __name__ == "__main__":
    unittest.main()
