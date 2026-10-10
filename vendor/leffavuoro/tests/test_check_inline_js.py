"""check_inline_js.py: node --check on the inline script, with line numbers against the HTML.

There is no build step, so a syntax error in index.html's script block ships and the
service worker keeps serving the last good copy to whoever pushed it. node reports line
numbers against the fragment it was handed; the script maps them back to the HTML file.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import _ctx
import check_inline_js as chk


SCRIPT = _ctx.ROOT / "scripts" / "check_inline_js.py"


def html(*bodies, blank_lines=0):
    """A page with `bodies` as inline scripts, pushed down the file by blank lines."""
    parts = ["<!doctype html>", "<html><head></head><body>"] + [""] * blank_lines
    for b in bodies:
        parts.append("<script>")
        parts.append(b)
        parts.append("</script>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class CheckInlineJsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return p

    def check(self, name, text):
        return chk.check_file(self.write(name, text))

    # -- the file it exists for ----------------------------------------------------------

    def test_the_repos_own_client_passes(self):
        """Run against index.html, status/index.html, tietosuoja/index.html, sw.js and
        pageview.js themselves, not a fixture. If this goes red the client is broken, which is the
        whole point."""
        out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                             text=True, cwd=str(_ctx.ROOT), timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        # index.html's inline script and its WebSite JSON-LD, status/index.html,
        # tietosuoja/index.html, sw.js. index.html carries two inline scripts since
        # 2026-09-13: the app and the <head> script that decides the first paint;
        # tietosuoja/index.html gained one on 2026-09-22, for the way back in the reader's
        # language; index.html gained the <head> theme script on 2026-09-25;
        # tietosuoja/index.html gained the same <head> theme script and its toggle on
        # 2026-09-28. pageview.js, the generated pages' analytics, joined on 2026-10-07.
        # Ten.
        self.assertIn("10 script(s) checked, 0 problem(s)", out.stdout)

    # -- what it has to catch ------------------------------------------------------------

    def test_a_broken_inline_script_fails(self):
        n, bad = self.check("broken.html", html("const x = {;"))
        self.assertEqual(n, 1)
        self.assertTrue(bad)

    def test_the_line_number_is_the_html_line_not_the_fragment_line(self):
        """The reason the offset exists. The error is on the first line of the script,
        which is line 24 of this file; a checker that reported line 1 would send you to
        the doctype."""
        page = html("const x = {;", blank_lines=20)
        n, bad = self.check("offset.html", page)
        self.assertEqual(n, 1)
        expected = page.splitlines().index("const x = {;") + 1
        self.assertEqual(expected, 24)
        self.assertTrue(any(f":{expected}" in line for line in bad),
                        f"no complaint mentions line {expected}: {bad}")

    def test_both_of_two_blocks_are_checked(self):
        """A one-block fixture would pass while the loop checked only the first. The
        break is in the second."""
        n, bad = self.check("two.html", html("const a = 1;", "const b = {;"))
        self.assertEqual(n, 2)
        self.assertTrue(bad)

    def test_a_file_with_no_inline_script_is_a_failure(self):
        """Not "nothing to do". Zero blocks in a page that has one means the tag shape
        moved and the check has been passing on air."""
        n, bad = self.check("empty.html", "<html><body>no scripts</body></html>")
        self.assertEqual(n, 0)
        self.assertTrue(any("no inline <script>" in b for b in bad))

    def test_a_broken_service_worker_fails(self):
        n, bad = self.check("sw.js", "self.addEventListener('fetch', e => {")
        self.assertEqual(n, 1)
        self.assertTrue(bad)

    def test_broken_json_ld_fails(self):
        """A `<script type="application/ld+json">` is not JavaScript, and node --check
        would reject a perfectly good one. It is parsed as JSON instead, because a broken
        one drops the page out of every rich result and nothing else here would notice."""
        page = ('<html><body><script type="application/ld+json">'
                '{"@context": "https://schema.org",}</script></body></html>')
        n, bad = self.check("ld.html", page)
        self.assertEqual(n, 1)
        self.assertTrue(any("JSON-LD" in b for b in bad))

    # -- and what it must not trip over ---------------------------------------------------

    def test_valid_json_ld_passes(self):
        page = ('<html><body><script type="application/ld+json">'
                '{"@context": "https://schema.org", "@type": "Movie"}'
                '</script></body></html>')
        n, bad = self.check("ld-ok.html", page)
        self.assertEqual((n, bad), (1, []))

    def test_an_external_script_is_somebody_elses_file(self):
        """`<script src=...>` has no body to check, and counting it would make the
        no-inline-script rule fire on a page that legitimately has none of its own."""
        page = ('<html><body><script src="/x.js"></script>'
                '<script>const a = 1;</script></body></html>')
        n, bad = self.check("ext.html", page)
        self.assertEqual((n, bad), (1, []))

    def test_a_good_page_passes(self):
        n, bad = self.check("ok.html", html("const a = 1;", "const b = 2;"))
        self.assertEqual((n, bad), (2, []))

    def test_a_missing_file_is_reported_rather_than_crashing(self):
        n, bad = chk.check_file(self.dir / "nope.html")
        self.assertEqual(n, 0)
        self.assertTrue(any("no such file" in b for b in bad))


if __name__ == "__main__":
    unittest.main()
