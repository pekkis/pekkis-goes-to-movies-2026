"""The film sheet leads with the synopsis, and long content is collapsed.

The sheet is a details view: the reader has already seen the selected day's tickets on
the main page. It renders header, chain key, synopsis, then the whole schedule. The
synopsis is clamped to four lines, so it introduces the film without pushing the first
day off the screen, and past times sit behind the control the cards already use.

Moving the synopsis under the entire schedule instead was a regression: a film with many
future screenings put it several scrolls down, where nothing led to it.

Source-level guards, in the shape tests/test_ticket_anatomy.py uses. The behaviour --
focus, the drag, the scroll position -- stays a live check against the served page.
"""
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HTML = (pathlib.Path(_ctx.ROOT) / "index.html").read_text(encoding="utf-8")


def rule(selector):
    """-> the body of the last rule for exactly this selector."""
    hits = re.findall(re.escape(selector) + r"\{([^}]*)\}", HTML)
    return hits[-1] if hits else ""


class SheetOrderTest(unittest.TestCase):

    def body_template(self):
        """-> the .sheet-body template literal. It is one assignment, so the order of the
        interpolations is the order of the nodes on screen."""
        body = HTML[HTML.index('<div class="sheet-body">'):]
        return body[:body.index("</div>`")]

    def test_the_synopsis_is_rendered_before_the_day_list(self):
        body = self.body_template()
        self.assertLess(body.index("synHtml"), body.index("sheet-days"), body[:200])

    def test_the_legend_leads_and_the_day_list_closes_the_body(self):
        """The whole order in one assertion. Sorted by position, not filtered by
        presence: filtering reads the same whatever order the template is in."""
        body = self.body_template()
        marks = ("${legend}", "synHtml", "sheet-days")
        self.assertEqual(sorted(marks, key=body.index), list(marks))

    def test_only_one_synopsis_is_rendered(self):
        """A second copy under the schedule would satisfy the order check above."""
        self.assertEqual(self.body_template().count("synHtml"), 1)
        self.assertEqual(HTML.count('class="syn${synLong'), 1)

    def test_the_day_list_is_not_split_around_the_synopsis(self):
        """One .sheet-days container holds every day, so the first day cannot be lifted
        above the synopsis while the rest stays below."""
        self.assertEqual(self.body_template().count("sheet-days"), 1)
        self.assertIn('<div class="sheet-days">${body}</div>', HTML)

    def test_a_long_synopsis_is_clamped_and_a_short_one_is_not(self):
        self.assertIn("const synLong = syn.length > 260;", HTML)
        self.assertIn("-webkit-line-clamp:4;", rule(".syn.clamp"))
        self.assertRegex(HTML, r"class=\"syn\$\{synLong \? ' clamp' : ''\}\"")

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_disclosure_boundary_sits_between_260_and_261_characters(self):
        """The decision line, run as written, on both sides of its boundary. A synopsis of
        exactly 260 characters is short: no clamp, no button. 261 is long. The regex the
        earlier test used accepted any number, so `> 0` (a toggle over two lines) and
        `> 600` (no toggle at all) both passed."""
        line = re.search(r"const synLong = syn\.length > \d+;", HTML).group(0)
        script = ("for (const n of [259, 260, 261, 700]) { const syn = 'x'.repeat(n); "
                  + line + " console.log(n, synLong); }")
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                             check=True).stdout.split()
        self.assertEqual(out, ["259", "false", "260", "false", "261", "true", "700", "true"])

    def test_the_disclosure_is_only_rendered_for_a_long_synopsis(self):
        """A short synopsis gets no control: the clamp is what the button reveals, and a
        toggle over two lines reveals nothing."""
        self.assertRegex(HTML, r"synLong \? `<button class=\"synmore\"")

    def test_the_synopsis_leads_the_body_and_the_sticky_key(self):
        """With the synopsis first it is the element meeting the body's border and the
        sticky chain key, so the spacing rules have to name it."""
        top = (".sheet-body > .syn:first-child, "
               ".sheet-body > .sheet-days:first-child")
        after_legend = (".sheet-body > .legend + .syn, "
                        ".sheet-body > .legend + .sheet-days")
        self.assertIn("margin-top:10px", rule(top))
        self.assertIn("margin-top:10px", rule(after_legend))
        self.assertIn("position:sticky", rule(".sheet-body > .legend"))

    def test_the_synopsis_toggle_exists_in_three_languages(self):
        self.assertEqual(len(re.findall(r"synMore:'", HTML)), 3)
        self.assertEqual(len(re.findall(r"synLess:'", HTML)), 3)

    def test_the_sheet_past_times_reuse_the_tested_label(self):
        """pastLabel is the pure function the cards' toggle already uses, so the sheet
        cannot drift into its own wording or its own singular rule."""
        self.assertIn("pastLabel(false, gone.length, L[lang])", HTML)
        self.assertIn('data-pastday=', HTML)

    def test_the_collapsed_past_times_outrank_the_grid_display(self):
        """`hidden` is display:none in the UA sheet and `.stubs.grid{display:grid}` beats
        it. At equal specificity the grid rule also sits later in the file, so the hidden
        rule has to name both classes: without it the collapsed block rendered in full."""
        self.assertIn("display:none", rule(".stubs[hidden], .stubs.grid[hidden]"))
        grid_at = HTML.index(".stubs.grid{")
        hidden_at = HTML.index(".stubs[hidden], .stubs.grid[hidden]{")
        self.assertLess(hidden_at, grid_at, "order alone must not be what makes it win")


if __name__ == "__main__":
    unittest.main()
