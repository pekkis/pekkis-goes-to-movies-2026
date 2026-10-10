"""The cloud run commits every directory the page build writes (2026-09-23).

`biorex.yml` stages its output with one `git add` list, written before the Swedish pages
existed. They shipped on 2026-09-22 under `sv/` and the list still named `teatteri
kaupunki en`: each run rebuilt the Swedish pages and left them uncommitted, so the live
ones changed only when a code push regenerated them, and the next code push after a data
run failed the drift check on them. The sitemap names every generated page, so its first
path segments are the directories the list has to carry.
"""
import re
import unittest

import _ctx

ROOT = _ctx.ROOT


def staged():
    wf = (ROOT / ".github" / "workflows" / "biorex.yml").read_text(encoding="utf-8")
    line = re.search(r"^\s*git add ([^\n&|;]+)$", wf, re.M).group(1)
    return set(line.split())


def page_dirs():
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    paths = re.findall(r"<loc>https://leffavuoro\.fi/([^<]*)</loc>", sitemap)
    return {p.split("/", 1)[0] for p in paths if "/" in p}


class PagesCommittedTest(unittest.TestCase):
    def test_every_page_directory_is_staged(self):
        dirs = page_dirs()
        self.assertIn("sv", dirs)                       # the case that was missing
        self.assertEqual(dirs - staged(), set())

    def test_the_rest_of_the_list_is_unchanged(self):
        self.assertTrue({"data", "logs", "sitemap.xml"} <= staged())


if __name__ == "__main__":
    unittest.main()
