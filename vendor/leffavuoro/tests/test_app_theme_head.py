"""The app sets its theme in <head>, with the generated pages' own script.

`index.html` applied the stored theme from the script at the end of the body, which runs
only once the whole document has parsed, so a dark reader saw the light page and then a
fade (audit K9, 2026-09-25). The pages already set it in <head>; the app now carries the
same script, and this holds the two byte-equal so the rule lives in one place. The body's
`applyTheme` call ignores a stored value other than the two themes, as the head does.
"""
import re
import unittest

import _ctx

import build_pages as bp

INDEX = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


class AppThemeHeadTest(unittest.TestCase):

    def head(self):
        return INDEX.split("</head>", 1)[0]

    def test_the_head_carries_the_pages_theme_script(self):
        self.assertIn(f"<script>{bp.THEME_HEAD_JS}</script>", self.head())

    def test_it_runs_before_any_stylesheet_could_paint(self):
        """Before the body, and before the first <style> block the tokens live in."""
        head = self.head()
        self.assertLess(head.index(bp.THEME_HEAD_JS), head.index("<style"))

    def test_the_body_applies_only_the_two_themes(self):
        m = re.search(r"const storedTheme = store\.k;\s*applyTheme\((.*?)\);", INDEX, re.S)
        self.assertIsNotNone(m, "the body's applyTheme call moved")
        self.assertIn("storedTheme === 'dark' || storedTheme === 'light'", m.group(1))


if __name__ == "__main__":
    unittest.main()
