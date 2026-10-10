"""The way back from /status/ (2026-09-22).

Reporting a screening opened `/status/?report=...&lang=en#contact` and nothing else, so
"← To showtimes" was `/?lang=en`: the reader lost the cinema, the open film and the day
they had been looking at, and the page had nothing to offer them but the chooser
(docs/research/flow-review.md, 2026-09-22).

The app now sends `area` and `back`, and the page prefers `back`, falls back to `area`,
and writes the current language into whichever it uses so switching language here does not
return the reader to the one they left.

`back` is a URL off a query string, so the other half of this is that it is followed only
when it resolves to this origin. These pin both.

Driven through tests/return_href_harness.js, which extracts the block verbatim from
status/index.html between its markers. Which element carries the href, and the label beside
it, are DOM plumbing and stay verified live.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "return_href_harness.js"
STATUS = (_ctx.ROOT / "status" / "index.html").read_text(encoding="utf-8")
APP = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


class MarkerTest(unittest.TestCase):
    """The markers are the seam. A rename makes the harness exit 2, which shows up as a
    failure below only if those tests run; this asserts the seam itself."""

    def test_the_block_is_there_and_named_after_its_harness(self):
        self.assertIn("// --- return link: pure, extracted verbatim by "
                      "tests/return_href_harness.js ---", STATUS)
        self.assertIn("// --- end return link ---", STATUS)

    def test_the_decision_lives_inside_the_block(self):
        a = STATUS.index("// --- return link:")
        b = STATUS.index("// --- end return link ---")
        block = STATUS[a:b]
        self.assertIn("function internalPath(back, origin){", block)
        self.assertIn("function returnHref(area, lang, langs, back, origin){", block)

    def test_both_links_are_built_through_it_and_nowhere_else(self):
        """One decision. A second copy of the query assembly is how the two would drift."""
        self.assertEqual(STATUS.count("function returnHref("), 1)
        self.assertEqual(STATUS.count("return '/?' + q.toString();"), 1)

    def test_home_is_the_area_and_never_the_one_screening(self):
        """The wordmark says Home. Pointing it at the screening would leave the reader no
        way out of the film they came in on."""
        self.assertIn("returnHref(areaParam, lang, LANGS, '', location.origin)", STATUS)
        self.assertIn("$('homeLink').href = homeHref();", STATUS)


class TheAppsHalfTest(unittest.TestCase):
    """What the app puts on the query. Read out of index.html, because the page can only
    offer the way back that it is given."""

    def test_the_report_link_carries_the_area_and_the_screening(self):
        m = re.search(r"function reportScreening\(s\)\{(.*?)\n  \}", APP, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("q.set('area', state.area)", body)
        self.assertIn("q.set('back', url.slice(location.origin.length))", body)

    def test_the_screening_url_is_the_one_the_draft_quotes(self):
        """One URL, built once: the reader's way back and the line in the email name the
        same screening, and cannot drift into naming two."""
        m = re.search(r"function reportScreening\(s\)\{(.*?)\n  \}", APP, re.S)
        body = m.group(1)
        self.assertEqual(body.count("screeningUrl("), 1)

    def test_the_service_worker_version_is_past_the_one_this_shipped(self):
        sw = (_ctx.ROOT / "sw.js").read_text(encoding="utf-8")
        m = re.search(r"const CACHE = 'leffavuoro-v(\d+)';", sw)
        self.assertTrue(m, "sw.js states no CACHE version")
        self.assertGreaterEqual(int(m.group(1)), 217)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ReturnHrefTest(unittest.TestCase):
    SCREENING = ("/?area=engel-helsinki&lang=sv#m=abc&d=2026-09-28"
                 "&t=2026-09-28T16%3A30%3A00%2B03%3A00&v=engel")

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True)
        if out.returncode != 0:
            raise AssertionError(f"harness failed ({out.returncode}): {out.stderr}")
        cls.got = json.loads(out.stdout)

    def href(self, name):
        return self.got["href"][name]

    def test_the_block_runs_without_anything_outside_itself(self):
        self.assertTrue(self.got["__ran"])

    def test_without_a_return_url_it_is_the_area_and_the_language(self):
        self.assertEqual(self.href("area_fi"), "/?area=engel-helsinki&lang=fi")
        self.assertEqual(self.href("area_en"), "/?area=engel-helsinki&lang=en")
        self.assertEqual(self.href("city_area"), "/?area=city%3AHelsinki&lang=en")

    def test_finnish_is_written_out_like_every_other_language(self):
        """A bare "/" let a stored choice decide instead of the page the reader came from."""
        self.assertIn("lang=fi", self.href("area_fi"))
        self.assertIn("lang=en", self.href("no_area"))

    def test_a_language_the_page_does_not_have_falls_back_to_the_first(self):
        self.assertEqual(self.href("unknown_lang"), "/?area=engel-helsinki&lang=fi")

    def test_a_screening_comes_back_whole(self):
        for name in ("back_fi", "back_en"):
            with self.subTest(case=name):
                self.assertIn("#m=abc&d=2026-09-28", self.href(name))
                self.assertIn("v=engel", self.href(name))
                self.assertIn("area=engel-helsinki", self.href(name))

    def test_the_language_on_the_page_wins_over_the_one_in_the_return_url(self):
        """The link was made in Swedish. Switching to Finnish here and going back must not
        put the reader in Swedish again."""
        self.assertIn("lang=fi", self.href("back_fi"))
        self.assertNotIn("lang=sv", self.href("back_fi"))
        self.assertIn("lang=en", self.href("back_en"))

    def test_a_return_url_with_no_language_gains_one(self):
        self.assertEqual(self.href("back_no_lang"), "/?area=engel-helsinki&lang=en#m=abc")

    def test_the_return_url_wins_over_the_area(self):
        self.assertIn("#m=", self.href("same_host"))
        self.assertIn("area=x", self.href("same_host"))

    def test_a_return_url_that_is_not_this_origin_is_dropped(self):
        for name in ("other_host", "protocol_rel", "javascript", "data_url", "nonsense"):
            with self.subTest(case=name):
                self.assertEqual(self.href(name), "/?area=engel-helsinki&lang=en")
                self.assertEqual(self.got["path"][name], "")

    def test_nothing_it_returns_can_leave_this_origin(self):
        for name, href in self.got["href"].items():
            with self.subTest(case=name):
                self.assertTrue(href.startswith("/"), href)
                self.assertFalse(href.startswith("//"), href)


if __name__ == "__main__":
    unittest.main()
