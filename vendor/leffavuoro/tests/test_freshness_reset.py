"""The freshness a selection claims is that selection's, or nothing.

`state.generated` is the timestamp the stale banner ages on and the footer's credit line
prints. It was written only when the newly loaded payload had one -- `if(cache.generated)`
-- so a selection carrying none kept the previous cinema's, and the paint below returned
before hiding either. A combined city whose every part failed is exactly that selection:
`loadGroup` builds `generated` from the parts it got and there were none, which the
partial-city notice above the banner is already written for.

Structural, and the limit is worth stating: the live path needs two selectable areas where
the second carries no timestamp, and `tests/browser`'s fixture is one venue in one city.
The behaviour either side of these lines -- the banner's wording, the age arithmetic -- is
covered by the status tests; what is pinned here is that a selection cannot inherit a
freshness claim from the one before it.
"""
import pathlib
import re
import unittest

import _ctx                                                # noqa: F401


ROOT = pathlib.Path(_ctx.ROOT)
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


class GeneratedResetTest(unittest.TestCase):
    def test_every_load_writes_the_timestamp_it_found(self):
        """The error this prevents: a payload with no `generated` leaving the previous
        area's in place, so the footer dates this cinema by another one's run."""
        self.assertIn("state.generated = cache.generated || '';", HTML)
        self.assertNotIn("if(cache.generated) state.generated = cache.generated;", HTML)

    def test_a_selection_with_no_timestamp_claims_nothing(self):
        """Returning early left whatever the last area painted: its stale banner, and its
        "updated 16.9. klo 08.10" under a cinema that has no data at all."""
        m = re.search(r"const staleEl = document\.querySelector\('#stale'\);(.*?)\n    \}",
                      HTML, re.S)
        self.assertTrue(m, "the stale paint changed shape")
        block = m.group(1)
        self.assertIn("if(!state.generated){", block)
        self.assertIn("staleEl.style.display = 'none';", block)
        self.assertIn("if(noStamp) noStamp.textContent = '';", block)

    def test_the_missing_element_guard_is_kept_separate(self):
        """`#stale` absent is a different question from a selection with no timestamp, and
        conflating them is how the second case went unhandled for as long as it did."""
        self.assertIn("if(!staleEl) return;", HTML)
        self.assertNotIn("if(!staleEl || !state.generated) return;", HTML)


if __name__ == "__main__":
    unittest.main()
