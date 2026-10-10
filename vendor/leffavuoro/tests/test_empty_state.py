"""An empty result can clear the filter that caused it.

12 September with Anniskelu on rendered "Yksikään elokuva ei vastaa suodattimia." and
nothing else: the reader had to work out which of five chips, a chain filter or the search
box had emptied the list and undo it themselves. The message now carries a button that
clears all of them.

Source-level guards. The click itself is verified live against the served page.
"""
import pathlib
import re
import unittest

import _ctx

HTML = (pathlib.Path(_ctx.ROOT) / "index.html").read_text(encoding="utf-8")


def rule(css, selector):
    """The body of the rule whose selector list is exactly `selector`, anchored at the
    start of a line."""
    m = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


class EmptyStateActionTest(unittest.TestCase):

    def test_the_clear_action_only_appears_when_a_filter_is_on(self):
        """An empty day with no filter set is not a filter problem, and the button would
        claim otherwise."""
        self.assertRegex(HTML, r"function clearFiltersLink\(\)\{\s*\n\s*return anyFilter\(\)")

    def test_a_chain_filter_counts_as_a_filter(self):
        """The chain legend empties the list the same way the chips do, and emptyMsg
        blames the filters for it too."""
        self.assertRegex(HTML, r"function anyFilter\(\)\{[^}]*state\.chains")

    def test_clearing_resets_every_filter_and_the_search_box(self):
        body = HTML[HTML.index("function clearFilters()"):]
        body = body[:body.index("\n  }")]
        for bit in ("state.filter = ''", "searchEl.value = ''", "state.fLang = false",
                    "state.fKids = false", "state.fAnnis = false", "state.chains = null"):
            self.assertIn(bit, body)

    def test_the_label_exists_in_three_languages(self):
        self.assertEqual(len(re.findall(r"clearFilters:'", HTML)), 3)


class ClearFiltersTapTargetTest(unittest.TestCase):
    """The control is a tap target and was under the floor.

    `.nextday` carries both the clear-filters button and the next-day link, and one line
    of .85rem type inside 8px padding renders 33px: 112.5 x 33 for "Rensa filtren" at
    320px, against the 44px floor the date chip already meets.

    Declared rather than computed, because the rendered height is font metrics plus
    line-height plus padding and modelling that in Python would be guesswork. Measured on
    the served page at 320 and 390 in fi, sv and en: both buttons 44.0px, no horizontal
    overflow, focus ring 2px solid at 2px offset.
    """

    def test_the_control_declares_the_44px_floor(self):
        body = rule(HTML, ".nextday")
        self.assertIsNotNone(body, ".nextday rule not found")
        m = re.search(r"min-height:\s*([\d.]+)px", body)
        self.assertIsNotNone(m, ".nextday declares no min-height")
        self.assertGreaterEqual(float(m.group(1)), 44.0)

    def test_the_label_stays_centred_in_the_taller_box(self):
        """min-height on a block button pins the label to the top and leaves the pill
        looking wrong, which is how a fix for the target size becomes a visual defect."""
        body = rule(HTML, ".nextday")
        self.assertIn("display:flex", body)
        self.assertIn("align-items:center", body)


if __name__ == "__main__":
    unittest.main()
