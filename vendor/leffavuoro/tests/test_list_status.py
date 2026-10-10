"""An empty result is announced to a screen reader, not only painted.

Filtering to nothing replaces the list with "Ei elokuvia suodattimilla" and leaves focus
in the search field, so a screen reader heard nothing. A `role="status"` node created
together with its text is not reliably announced, so `#listStatus` is markup and the
renderers write into it, the pattern the venue picker already used. What the region
sounds like stays a live check.
"""
import pathlib
import re
import unittest

import _ctx


ROOT = pathlib.Path(_ctx.ROOT)
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
LINES = HTML.splitlines()

REGION = re.search(r'<div id="listStatus"[^>]*>', HTML)


class RegionMarkupTest(unittest.TestCase):

    def test_the_region_exists_in_the_markup(self):
        """Not created by a renderer: it has to pre-exist the text it announces."""
        self.assertIsNotNone(REGION, "#listStatus is not in the static markup")

    def test_it_is_a_polite_atomic_status(self):
        tag = REGION.group(0)
        self.assertIn('role="status"', tag)
        self.assertIn('aria-live="polite"', tag)
        self.assertIn('aria-atomic="true"', tag)

    def test_it_starts_empty(self):
        """A region with text in it announces on load, which is noise, and would also be
        read again on the first real change."""
        self.assertRegex(HTML, r'<div id="listStatus"[^>]*></div>')

    def test_it_lives_outside_main(self):
        """Every render assigns main.innerHTML. Inside <main> the region would be
        destroyed and recreated on each render, which is the failure it exists to avoid."""
        start = HTML.index('<div id="listStatus"')
        self.assertLess(start, HTML.index("<main id=\"main\">"))

    def test_it_is_hidden_without_leaving_the_accessibility_tree(self):
        """display:none and visibility:hidden both remove a node from the tree, and a
        removed node announces nothing at all."""
        m = re.search(r"\.sr-only\{(.*?)\}", HTML, re.S)
        self.assertIsNotNone(m, ".sr-only rule missing")
        rule = m.group(1)
        self.assertNotIn("display:none", rule)
        self.assertNotIn("visibility:hidden", rule)
        self.assertIn("clip-path:inset(50%)", rule)

    def test_the_class_is_actually_applied(self):
        self.assertIn('class="sr-only"', REGION.group(0))


class RenderPairingTest(unittest.TestCase):
    """Every write to the list says what the list now contains, including "nothing"."""

    @staticmethod
    def render_sites():
        return [i for i, ln in enumerate(LINES) if "main.innerHTML" in ln and "=" in ln]

    def test_every_render_path_sets_the_region(self):
        """Eight sites today: two empty states, two lists, two loading states and two
        error states. A ninth added without a status write would leave the last
        announcement standing over content it no longer describes."""
        sites = self.render_sites()
        self.assertGreaterEqual(len(sites), 8)
        for i in sites:
            window = "\n".join(LINES[max(0, i - 3):i + 1])
            with self.subTest(line=i + 1, code=LINES[i].strip()[:60]):
                self.assertIn("setListStatus(", window)

    def test_the_empty_paths_announce_the_visible_message(self):
        """The same call that paints the sentence supplies the words, so the two cannot
        drift into saying different things in different languages. Since v134 the
        announcement is emptyStatus(): the message, then the next-screening suggestion
        when there is one, which is the button's own label."""
        empty = [i for i in self.render_sites() if "emptyMsg()" in LINES[i]]
        self.assertEqual(len(empty), 2, "expected the times list and the movie list")
        for i in empty:
            window = "\n".join(LINES[max(0, i - 3):i + 1])
            with self.subTest(line=i + 1):
                self.assertIn("setListStatus(emptyStatus())", window)
        body = HTML[HTML.index("function emptyStatus()"):]
        body = body[:body.index("\n  }")]
        self.assertIn("return emptyMsg() + (hit ? ' ' + hit.label : '')", body)

    def test_the_other_paths_clear_it(self):
        """Otherwise "no movies" is still in the region when the next render succeeds,
        and the next unrelated change re-announces it."""
        for i in self.render_sites():
            if "emptyMsg()" in LINES[i]:
                continue
            window = "\n".join(LINES[max(0, i - 3):i + 1])
            with self.subTest(line=i + 1, code=LINES[i].strip()[:60]):
                self.assertIn("setListStatus('')", window)

    def test_no_status_write_sits_under_a_braceless_branch(self):
        """Proximity is not control flow. Inserting setListStatus('') above

            if(state.lang !== 'fi')
              main.innerHTML = ...

        makes the assignment unconditional while every line stays exactly where the
        pairing test wants it -- which is how it happened, and why this looks at the line
        above rather than at the distance between two lines.

        Stated as an allowlist. The first version enumerated the headers it rejected --
        if, else if, for, while -- and a braceless `else`, or a condition wrapped across
        two lines so the line above ends in `)`, walked straight through it. A rule that
        lists what may precede a status write fails closed on the shape nobody thought of.

        Three things this does not cover, written down so the next reader does not have
        to work them out again:

          * it only sees `setListStatus(`. A direct `listStatusEl.textContent = ...`
            bypasses the helper and no guard in this file notices.
          * stripping the trailing comment would also cut a string literal that contains
            ` //`, which makes the preceding line look shorter than it is. That can only
            reject a line that was fine, never accept one that was not, so it is a false
            positive and index.html has none today.
          * it reads the immediately-preceding real line and nothing else. The mirror
            ordering -- `main.innerHTML` first and `setListStatus` second under a
            braceless branch -- escapes it, and is caught instead by
            test_every_render_path_sets_the_region and test_the_other_paths_clear_it.
            Weakening either of those reopens that half.
        """
        allowed = ("{", ";", "}")
        # A trailing comment hides the brace on `if(...){   // why`. `//` has to follow
        # whitespace, so a `https://` inside a string is not mistaken for one.
        code = lambda ln: re.sub(r"\s+//.*$", "", ln).rstrip()
        for i, line in enumerate(LINES):
            if "setListStatus(" not in line:
                continue
            j = i - 1
            while j >= 0 and (not LINES[j].strip() or LINES[j].strip().startswith("//")):
                j -= 1
            above = code(LINES[j])
            with self.subTest(line=i + 1, above=above.strip()[:60]):
                self.assertTrue(
                    above.endswith(allowed),
                    f"line {j + 1} ends {above.strip()[-24:]!r}; a status write may only "
                    f"follow a line ending in {' '.join(allowed)}")

    def test_the_region_goes_inert_with_the_rest_of_the_background(self):
        """It lives outside <main> so a render cannot destroy it, which also means the
        modal lifecycle has to name it explicitly. Without this a background render
        finishing while a sheet is open announces the list behind the modal."""
        m = re.search(r"const BEHIND = \(\) => \[(.*?)\];", HTML, re.S)
        self.assertIsNotNone(m, "BEHIND() not found")
        self.assertIn("listStatusEl", m.group(1))

    def test_the_region_carries_words_and_not_controls(self):
        """nextDayLink() renders a button. Inside a live region it would be announced as
        text on every change and its focus behaviour would be unpredictable, so the
        visible empty state keeps it and the region gets only the sentence."""
        self.assertNotRegex(HTML, r"setListStatus\([^\n]*nextDayLink")


if __name__ == "__main__":
    unittest.main()
