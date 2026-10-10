"""A stale homepage city list fails the pages build (2026-09-14).

A city crossing into its second venue gains a landing page, and `index.html`'s static
chooser has to gain the link. The build already noticed and printed a line; nothing read
it. On 2026-09-14 the kino-bot data commit 92005f27 gave Nurmijärvi its second venue, the
page and the sitemap entry were committed, `run-pages.log` carried "[pages] index.html
city links stale" above `exit=0`, and `test_home_static` sat red on main for hours.
`check_runs.py` reads `exit=`, and a data commit starts no Checks run, so the exit code is
the only channel out of that log. The pages must still publish: the stale list costs the
homepage one link, and withholding a whole build over it would cost every page.

Two cities of two venues each, so the ordering and the per-city loop both run.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from datetime import date, timedelta

import _ctx                                                # noqa: F401
import build_pages as bp
from test_build_date import Clock, show

D = date(2026, 9, 5)
VENUES = [("2001", "Kino Testi Espoo"), ("2002", "Studio Testi Espoo"),
          ("2003", "Kino Testi Oulu"), ("2004", "Studio Testi Oulu")]
SHELL = ("<!doctype html><html><body><ul class=\"cities\">"
         + bp.HOME_START + "{block}" + bp.HOME_END + "</ul><ul>"
         + bp.PAGES_START + "{block}" + bp.PAGES_END + "</ul></body></html>")


def write_fixture(root):
    data = root / "data"
    data.mkdir()
    (data / "providers.json").write_text(json.dumps({"providers": [
        {"id": "finnkino", "label": "Finnkino", "host": "finnkino.fi",
         "accent": "#E4551F", "book": "buy"}]}), encoding="utf-8")
    (data / "tmdb-genres.json").write_text(json.dumps({"fi": {}, "sv": {}, "en": {}}), encoding="utf-8")
    (data / "films-extra.json").write_text(json.dumps({"generated": "2026-09-01", "films": {}}),
                                           encoding="utf-8")
    (data / "areas.json").write_text(json.dumps({
        "generated": "2026-09-05T05:00:00+00:00",
        "areas": [{"id": i, "name": n} for i, n in VENUES]}), encoding="utf-8")
    for vid, name in VENUES:
        shows = [show(vid, name, D + timedelta(days=k)) for k in range(-1, 6)]
        (data / f"area-{vid}.json").write_text(json.dumps({
            "generated": "2026-09-05T05:00:00+00:00",
            "dates": sorted({s["start"][:10] for s in shows}),
            "shows": shows}), encoding="utf-8")


class HomeSyncExitTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        write_fixture(self.root)
        for name in ("ROOT", "DATA", "INDEX", "datetime"):
            self.addCleanup(setattr, bp, name, getattr(bp, name))
        bp.ROOT, bp.DATA = self.root, self.root / "data"
        bp.INDEX = self.root / "index.html"
        bp._unmirrored_hosts.clear()
        self.write_block("")                 # neither city is listed yet

    # -- helpers ---------------------------------------------------------------------------

    def write_block(self, block):
        bp.INDEX.write_text(SHELL.format(block=block), encoding="utf-8")

    def current_block(self):
        return bp.home_block(bp.INDEX.read_text(encoding="utf-8"))[1]

    def build(self, argv=None):
        bp.datetime = Clock(D)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = bp.cli(argv) if argv is not None else bp.main(today=D)
        return code, buf.getvalue()

    def assertPagesWritten(self):
        """Both city pages, both languages, every venue page and the sitemap."""
        for rel in ("kaupunki/espoo/index.html", "kaupunki/oulu/index.html",
                    "en/city/espoo/index.html", "en/city/oulu/index.html", "sitemap.xml"):
            self.assertTrue((self.root / rel).is_file(), rel)
        self.assertEqual(len(list((self.root / "teatteri").iterdir())), len(VENUES))

    # -- the exit code ----------------------------------------------------------------------

    def test_a_stale_city_list_exits_3_and_still_writes_every_page(self):
        code, out = self.build()
        self.assertEqual(code, 3, "the run has to go red at biorex.yml's final step")
        self.assertIn("[pages] index.html city links stale: run build_pages.py --home", out)
        self.assertIn("urls in sitemap", out, "the summary still reaches the log")
        self.assertPagesWritten()

    def test_a_list_in_sync_exits_0(self):
        self.write_block(bp.home_links_html(bp.home_cities()))
        code, out = self.build()
        self.assertEqual(code, 0)
        self.assertNotIn("stale", out)
        self.assertPagesWritten()

    def test_one_missing_city_is_enough_to_fail_it(self):
        """The case that happened: the list is right except for the city that just gained
        its second venue."""
        both = bp.home_cities()
        self.write_block(bp.home_links_html([c for c in both if c["city"] != "Oulu"]))
        self.assertEqual(len(both), 2)
        code, out = self.build()
        self.assertEqual(code, 3)
        self.assertIn("city links stale", out)

    def test_a_stale_page_list_alone_fails_it_and_home_repairs_both(self):
        """The disclosure's copy of the list is the homepage's rendered way into the pages
        (2026-09-29), so it is held to the same rule as the list above it."""
        links = bp.home_links_html(bp.home_cities())
        bp.INDEX.write_text(SHELL.replace("{block}", links, 1).replace("{block}", ""),
                            encoding="utf-8")
        code, out = self.build()
        self.assertEqual(code, 3)
        self.assertIn("city links stale", out)
        self.build(argv=["--home"])
        html = bp.INDEX.read_text(encoding="utf-8")
        self.assertEqual(bp.home_block(html, None, bp.PAGES_START, bp.PAGES_END)[1], links)

    # -- --home is the fix, and it stays green ------------------------------------------------

    def test_home_rewrites_and_exits_0_and_the_next_build_is_clean(self):
        code, out = self.build(argv=["--home"])
        self.assertEqual(code, 0, "--home is the repair; it never reports a failure")
        self.assertIn("rewritten", out)
        block = self.current_block()
        self.assertEqual(block.count("<li>"), 2)
        self.assertLess(block.index("Espoo"), block.index("Oulu"), "Finnish order")
        self.assertIn('href="/kaupunki/oulu/"', block)
        code, out = self.build()
        self.assertEqual(code, 0)
        self.assertNotIn("stale", out)

    def test_home_on_an_already_synced_file_changes_nothing_and_exits_0(self):
        self.build(argv=["--home"])
        before = bp.INDEX.read_text(encoding="utf-8")
        code, out = self.build(argv=["--home"])
        self.assertEqual(code, 0)
        self.assertIn("unchanged", out)
        self.assertEqual(bp.INDEX.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
