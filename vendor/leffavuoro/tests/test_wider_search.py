"""A film search with nothing here can be repeated in the city or the region (2026-09-13, v137).

Searching a film at one cinema on a day it does not play offered the next day it does and
the clear action. Now, under the next-screening action, an empty search offers to run the
same search wider: a venue offers its city and its curated region, a city its region, a
region nothing. The buttons invite a search and promise nothing: no neighbouring schedule
is fetched to decide them. Activation changes the area only, through selectVenue(), and
keeps the search, the day, the chips, the chain restriction, the view and the favourite.

The decision is `widerTargets()`, sliced verbatim out of index.html by
tests/wider_targets_harness.js. The wiring and the copy are pinned at source level here and
verified live against the served page.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "wider_targets_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class WiderTargetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_a_venue_offers_its_city_then_its_region(self):
        self.assertEqual(self.r["venue_in_capital"], ["city:Helsinki", "region:Pääkaupunkiseutu"])

    def test_a_city_offers_its_region_only(self):
        self.assertEqual(self.r["city_helsinki"], ["region:Pääkaupunkiseutu"])

    def test_a_region_offers_nothing(self):
        self.assertEqual(self.r["region"], [])

    def test_a_venue_alone_in_its_city_skips_the_city_and_offers_the_region(self):
        self.assertEqual(self.r["alone_in_city_region_adds"], ["region:Kymenlaakso"])

    def test_a_target_that_adds_no_theatre_is_not_offered(self):
        """Kotka's combined view is one venue: no city, and the region adds Kouvola."""
        self.assertEqual(self.r["city_alone_in_region_twin"], ["region:Kymenlaakso"])

    def test_a_city_in_no_region_offers_no_region(self):
        self.assertEqual(self.r["venue_no_region"], ["city:Tampere"])
        self.assertEqual(self.r["city_no_region"], [])

    def test_the_chain_restriction_decides_what_counts_as_added(self):
        self.assertEqual(self.r["chain_blocks_both"], [])
        self.assertEqual(self.r["chain_admits_both"], ["city:Helsinki", "region:Pääkaupunkiseutu"])
        self.assertEqual(self.r["chain_region_only"], ["region:Pääkaupunkiseutu"])

    def test_a_region_admitting_exactly_the_citys_theatres_yields_to_the_city(self):
        self.assertEqual(self.r["twin_sets_city_only"], ["city:Helsinki"])

    def test_ambiguous_region_membership_offers_no_region(self):
        """Lahti's one venue is the current scope, so no city either: nothing at all."""
        self.assertEqual(self.r["ambiguous_region"], [])

    def test_an_unknown_or_blank_area_offers_nothing(self):
        self.assertEqual(self.r["unknown_venue"], [])
        self.assertEqual(self.r["blank_area"], [])

    def test_targets_carry_kind_name_and_picker_id(self):
        self.assertEqual(self.r["shape"], [
            {"kind": "city", "name": "Helsinki", "id": "city:Helsinki"},
            {"kind": "region", "name": "Pääkaupunkiseutu", "id": "region:Pääkaupunkiseutu"}])

    def test_registry_order_does_not_change_the_answer(self):
        self.assertEqual(self.r["order_independent"], self.r["venue_in_capital"])


class WiringTest(unittest.TestCase):
    """The DOM half, pinned at source level."""

    def test_the_action_order_is_next_screening_wider_then_clear(self):
        self.assertIn("function emptyActions(){ return (nextMatchLink() || nextDayLink()) + widerLinks() + clearTimeLink() + clearFiltersLink(); }", HTML)
        self.assertIn("${L[state.lang].nomore}${emptyContext()}${nextMatchLink() || nextDayLink()}${widerLinks()}", HTML)

    def test_only_a_nonblank_search_gets_the_invitations(self):
        body = HTML[HTML.index("function widerLinks()"):HTML.index("function widenTo(")]
        self.assertIn("if(!(state.filter || '').trim()) return '';", body)
        self.assertNotIn("fetch", body)

    def test_the_decision_reads_the_registries_and_the_chain_restriction(self):
        body = HTML[HTML.index("function widerLinks()"):HTML.index("function widenTo(")]
        self.assertIn("area: state.area, chains: state.chains,", body)
        self.assertIn("cityGroups, regionCities, regionGroups,", body)
        self.assertIn("provider: a.provider", body)

    def test_activation_changes_the_area_only_and_keeps_the_chains(self):
        body = HTML[HTML.index("function widenTo("):HTML.index("function emptyActions()")]
        self.assertIn("selectVenue(id, { keepChains: true, keepDay: true })", body)
        self.assertIn("areaSel.focus()", body)
        self.assertNotIn("state.filter", body)
        self.assertNotIn("prefs.set", body)
        sel = HTML[HTML.index("function selectVenue(id, opts)"):HTML.index("function syncVenueBtn()")]
        self.assertIn("if(!o.keepChains) state.chains = null;", sel)
        self.assertIn("const p = loadSchedule({ keepDay: !!o.keepDay });", sel)
        self.assertIn("return p;", sel)
        self.assertNotIn("prefs.set(", sel)          # no last-browsed slot since 2026-09-13
        self.assertNotIn("fav", sel.replace("syncFav", ""))

    def test_the_click_goes_through_the_list_handler(self):
        handler = HTML[HTML.index("const widen = e.target.closest('[data-widen]');"):]
        handler = handler[:handler.index("return;")]
        self.assertIn("widenTo(widen.dataset.widen)", handler)

    def test_the_button_is_the_lighter_pill(self):
        self.assertRegex(HTML, r'<button class="nextday wider" data-widen="\$\{esc\(t\.id\)\}">\$\{esc\(widenLabel\(t\)\)\}</button>')
        m = re.search(r"(?m)^\s*\.nextday\.wider\{([^}]*)\}", HTML)
        self.assertIsNotNone(m)
        self.assertIn("background:transparent", m.group(1))
        self.assertIn("font-weight:500", m.group(1))

    def test_the_approved_copy_and_the_template_in_three_languages(self):
        self.assertIn("widenTo:'Laajenna hakua: {area}', widenHelsinki:'Etsi Helsingistä'", HTML)
        self.assertIn("widenCapital:'Etsi koko pääkaupunkiseudulta'", HTML)
        self.assertIn("widenTo:'Utöka sökningen: {area}', widenHelsinki:'Sök i Helsingfors'", HTML)
        self.assertIn("widenCapital:'Sök i hela huvudstadsregionen'", HTML)
        self.assertIn("widenTo:'Broaden search: {area}', widenHelsinki:'Search in Helsinki'", HTML)
        self.assertIn("widenCapital:'Search across the capital region'", HTML)
        self.assertEqual(len(re.findall(r"widenTo:'", HTML)), 3)

    def test_other_places_take_the_translated_name_after_a_colon_never_a_suffix(self):
        body = HTML[HTML.index("function widenLabel("):HTML.index("function widerLinks()")]
        self.assertIn("t.kind === 'city' ? cityLabel(t.name) : regionLabel(t.name)", body)
        self.assertIn("T.widenTo.replace('{area}', () => name)", body)
        self.assertNotRegex(body, r"name \+ '(sta|stä|lta|ltä|ssa|ssä)'")


if __name__ == "__main__":
    unittest.main()
