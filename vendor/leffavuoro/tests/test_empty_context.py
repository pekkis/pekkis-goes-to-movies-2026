"""An empty result names what emptied it (2026-09-13, v136).

"Valitulle päivälle ei löytynyt näytöksiä näillä hakuehdoilla." blamed the filters without
saying which: the search box, three chips and the chain legend all empty the list the same
way. The message now carries two compact lines under it, the search as typed and the labels
of the filters that are on, chain names included; either line is dropped when it has
nothing, and nothing is shown when neither has anything.

The decision is `emptyContextParts()`, sliced verbatim out of index.html by
tests/empty_context_harness.js. The rendering, the escaping and the copy are pinned at
source level here and verified live against the served page.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "empty_context_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class EmptyContextPartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_the_search_and_the_chips_that_are_on(self):
        self.assertEqual(self.r["search_and_two_chips"],
                         {"query": "Autofiktio", "filters": ["Suom. puhe", "Lapsille"]})

    def test_a_search_alone_leaves_the_filter_half_empty(self):
        self.assertEqual(self.r["search_only"], {"query": "Dune", "filters": []})

    def test_chips_alone_leave_the_search_half_empty(self):
        self.assertEqual(self.r["chips_only"], {"query": "", "filters": ["Anniskelu"]})

    def test_nothing_on_is_two_empty_halves(self):
        self.assertEqual(self.r["nothing"], {"query": "", "filters": []})
        self.assertEqual(self.r["blank_search"]["query"], "")

    def test_a_chain_restriction_is_a_filter_by_its_display_name(self):
        """Sorted by id, so the line reads the same whichever chain was clicked first."""
        self.assertEqual(self.r["chains"]["filters"], ["BioRex", "Gilda"])
        self.assertEqual(self.r["chains_and_chip"]["filters"], ["Lapsille", "Finnkino"])
        self.assertEqual(self.r["unknown_chain"]["filters"], ["zzz"])

    def test_user_text_is_returned_as_typed_for_the_renderer_to_escape(self):
        self.assertEqual(self.r["markup_in_query"]["query"], "<img src=x onerror=alert(1)> $&")

    def test_every_filter_at_once_in_chip_order_then_chains(self):
        self.assertEqual(self.r["many"]["filters"],
                         ["Suom. puhe", "Lapsille", "Anniskelu", "BioRex", "Finnkino", "Gilda"])


class WiringTest(unittest.TestCase):
    """The DOM half, pinned at source level."""

    def test_both_empty_states_and_the_nothing_left_message_carry_it(self):
        self.assertEqual(HTML.count("${emptyMsg()}${emptyContext()}${emptyActions()}"), 2)
        self.assertIn("${L[state.lang].nomore}${emptyContext()}${nextMatchLink() || nextDayLink()}", HTML)

    def test_it_reads_the_state_the_filter_reads(self):
        body = HTML[HTML.index("function emptyContext()"):HTML.index("function emptyActions()")]
        self.assertIn("emptyContextParts(state.filter, state, state.chains, T,", body)

    def test_user_text_is_escaped_and_inserted_literally(self):
        body = HTML[HTML.index("function emptyContext()"):HTML.index("function emptyActions()")]
        self.assertIn("esc(T.searchCtx.replace('{query}', () => p.query))", body)
        self.assertIn("esc(T.filtersCtx.replace('{list}', () => p.filters.join(', ')))", body)

    def test_lines_are_separated_by_a_break_and_dropped_when_empty(self):
        body = HTML[HTML.index("function emptyContext()"):HTML.index("function emptyActions()")]
        self.assertIn("if(p.query) lines.push(", body)
        self.assertIn("if(p.filters.length) lines.push(", body)
        self.assertIn("lines.join('<br>')", body)
        self.assertIn("lines.length ? `<p class=\"ctx\">", body)
        self.assertNotIn("\\u00b7", body)

    def test_it_is_text_and_not_in_the_live_region(self):
        """#listStatus keeps announcing emptyStatus(); the context is readable in the
        list itself and is not announced a second time."""
        body = HTML[HTML.index("function emptyStatus()"):HTML.index("function nextDayLink()")]
        self.assertNotIn("emptyContext", body)
        self.assertNotIn("<button", HTML[HTML.index("function emptyContext()"):HTML.index("// --- widerTargets: pure")])

    def test_the_copy_exists_in_three_languages(self):
        self.assertIn("searchCtx:'Hakusi: \\u201d{query}\\u201d'", HTML)
        self.assertIn("searchCtx:'Din sökning: \\u201d{query}\\u201d'", HTML)
        self.assertIn("searchCtx:'Your search: \\u201c{query}\\u201d'", HTML)
        self.assertEqual(len(re.findall(r"searchCtx:'", HTML)), 3)
        self.assertIn("filtersCtx:'Suodattimet: {list}'", HTML)
        self.assertIn("filtersCtx:'Filter: {list}'", HTML)
        self.assertIn("filtersCtx:'Filters: {list}'", HTML)
        self.assertEqual(len(re.findall(r"filtersCtx:'", HTML)), 3)

    def test_a_long_query_wraps_inside_the_column(self):
        m = re.search(r"(?m)^\s*\.status \.ctx\{([^}]*)\}", HTML)
        self.assertIsNotNone(m)
        self.assertIn("overflow-wrap:anywhere", m.group(1))
        self.assertIn("max-width:36em", m.group(1))


if __name__ == "__main__":
    unittest.main()
