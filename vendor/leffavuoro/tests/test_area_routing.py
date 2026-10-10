"""`?area=` and `?lang=` deep links: applied on load and kept in the URL while they are the answer.

The app used to apply `?area=` and delete it, so a reload fell through to the stored
restore and the favourite beat the deep-linked venue. The parameter now stays while it is
the answer and is rewritten when the reader picks something else. `?lang=` follows the
same rules (2026-09-02): an English landing page must open the English app for a reader
with nothing stored, and a stored choice is never overwritten by a link.

`startupArea`, `areaParamAfterSelect`, `startupLang` and `langParamAfterSelect` are sliced
verbatim out of index.html by tests/area_routing_harness.js and run on their own.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "area_routing_harness.js"

FAV = "fi-cine-atlas"
DEEP = "sk-tapio"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class AreaRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        payload = json.loads(out.stdout)
        cls.r = payload["routing"]
        cls.u = payload["urls"]
        cls.l = payload["lang"]
        cls.lu = payload["langUrls"]
        cls.h = payload["homeHrefs"]
        cls.hp = payload["homePages"]

    # -- the seven behaviours the fix has to hold ----------------------------------------

    def test_favourite_and_no_deep_link_opens_the_favourite(self):
        self.assertEqual(self.r["fav_only_no_deep"]["area"], FAV)

    def test_a_deep_link_beats_the_favourite(self):
        self.assertEqual(self.r["fav_and_deep"]["area"], DEEP)

    def test_reloading_the_deep_linked_tab_still_opens_the_deep_link(self):
        """The defect. The second load sees the same parameter because the first one no
        longer deletes it, so it decides again instead of falling through to the
        favourite."""
        self.assertEqual(self.r["reload_with_deep"]["area"], DEEP)

    def test_the_deep_link_is_kept_in_the_url_while_it_is_the_answer(self):
        """`keepParam` is what stops the first load from erasing its own reason."""
        self.assertTrue(self.r["fav_and_deep"]["keepParam"])
        self.assertTrue(self.r["reload_with_deep"]["keepParam"])

    def test_arriving_by_deep_link_never_touches_the_favourite(self):
        """Nothing in this path writes `fav`, so following a link cannot restar
        somebody's cinema -- which is why the favourite still wins on a later ordinary
        visit. Since 2026-09-13 nothing writes the last-browsed slot either: the route
        carries no `remember` and the caller stores nothing."""
        self.assertNotIn("remember", self.r["fav_and_deep"])
        self.assertEqual(self.r["fav_only_no_deep"]["area"], FAV)

    def test_picking_another_cinema_rewrites_the_parameter(self):
        """Otherwise the next reload bounces back to the venue the reader navigated away
        from, which is the failure the old delete-on-apply was avoiding."""
        self.assertEqual(self.u["deep_then_pick"], "area=sk-maxim")

    def test_a_city_deep_link_behaves_the_same(self):
        self.assertEqual(self.r["city_deep"]["area"], "city:Helsinki")
        self.assertTrue(self.r["city_deep"]["keepParam"])

    def test_an_unknown_deep_link_falls_through(self):
        """To the favourite when there is one, otherwise to the chooser (null); the
        stored last-browsed slot no longer catches it."""
        self.assertEqual(self.r["unknown_deep"]["area"], FAV)
        self.assertIsNone(self.r["unknown_deep_no_fav"]["area"])
        self.assertIsNone(self.r["unknown_deep_nothing"]["area"])

    # -- and the URL never contradicts the picker -----------------------------------------

    def test_a_link_that_decided_nothing_is_taken_out_of_the_url(self):
        """`keepParam` false with a parameter present is the caller's signal to strip
        it. A URL saying `?area=sk-gone` beside a picker showing Cine Atlas is the
        disagreement this rule exists to prevent."""
        self.assertFalse(self.r["unknown_deep"]["keepParam"])
        self.assertFalse(self.r["unknown_deep_nothing"]["keepParam"])

    def test_a_pick_on_the_bare_page_writes_the_parameter(self):
        """Since 2026-09-13 `/` is the chooser and the URL is the location's identity, so
        a pick from `/` writes `?area=`; until then only an existing parameter was
        rewritten. Other parameters survive."""
        self.assertEqual(self.u["no_param"], "area=sk-maxim")
        self.assertEqual(self.u["other_params_only"], "lang=en&area=sk-maxim")

    def test_other_query_parameters_survive_the_rewrite(self):
        self.assertEqual(self.u["deep_with_other_params"], "area=sk-maxim&lang=en")

    def test_picking_the_venue_you_arrived_on_changes_nothing(self):
        """Null: the URL already says it, so the caller adds no history entry."""
        self.assertIsNone(self.u["deep_then_pick_same"])

    def test_a_city_selection_is_encoded_into_the_parameter(self):
        """The colon is percent-encoded on the way out and URLSearchParams decodes it on
        the way back in, so the round trip is what matters rather than the spelling."""
        self.assertEqual(self.u["deep_then_pick_city"], "area=city%3AHelsinki")

    def test_an_empty_area_parameter_is_filled_rather_than_ignored(self):
        """`?area=` is present but names nothing; the reader is in a tab that carries the
        parameter, so a selection belongs in it."""
        self.assertEqual(self.u["empty_area_param"], "area=sk-maxim")

    # -- the rest of the restore, unchanged ------------------------------------------------

    def test_the_favourite_still_beats_the_stored_area(self):
        self.assertEqual(self.r["fav_beats_stored"]["area"], "br-redi")

    def test_the_stored_last_browsed_slot_is_ignored(self):
        """An older build wrote `area` on every pick. It is not an explicit choice and
        must not bypass the chooser."""
        self.assertIsNone(self.r["stored_only"]["area"])

    def test_a_first_visit_decides_nothing_and_leaves_it_to_the_caller(self):
        """null is the chooser: no guess, no first venue of the list."""
        self.assertIsNone(self.r["nothing_at_all"]["area"])
        self.assertIsNone(self.r["stale_stored"]["area"])

    def test_city_links_point_at_the_pages_until_the_lists_arrive(self):
        """Without the venue lists, which a reader without script never gets, each language
        links its own city page."""
        self.assertEqual(self.h["fi"], "/kaupunki/jyvaskyla/")
        self.assertEqual(self.h["sv"], "/sv/kaupunki/jyvaskyla/")
        self.assertEqual(self.h["en"], "/en/city/jyvaskyla/")

    def test_city_links_open_the_programme_once_the_lists_are_in(self):
        """The maintainer's instruction, 2026-09-29: a tap, a copied link and a new tab all
        reach the programme, the combined view for two or more cinemas and the cinema for
        one, in every language."""
        self.assertEqual(self.h["multi"], "/?area=city%3AJyv%C3%A4skyl%C3%A4")
        self.assertEqual(self.h["single"], "/?area=kl-fantasia")

    def test_a_city_link_carries_the_query_a_pick_would_leave(self):
        self.assertEqual(self.h["keepsQuery"], "/?lang=sv&area=city%3AJyv%C3%A4skyl%C3%A4")
        self.assertEqual(self.h["replacesArea"], "/?area=city%3AJyv%C3%A4skyl%C3%A4&lang=en")

    def test_the_page_list_links_the_pages_that_exist(self):
        """The chooser's "Kaupunkisivut" list is the homepage's rendered link into the city
        pages: with the programme as the city links' href, a rendered crawl from `/`
        otherwise reached none of the 454 sitemap pages (2026-09-28)."""
        self.assertEqual(self.hp, {"fi": "/kaupunki/jyvaskyla/", "sv": "/sv/kaupunki/jyvaskyla/",
                                   "en": "/en/city/jyvaskyla/"})

    def test_a_city_with_one_venue_is_not_a_valid_area(self):
        """`known()` only accepts a `city:` id where the city has more than one venue,
        and a deep link naming a single-venue city falls through like any stale id."""
        self.assertEqual(self.r["city_deep_single_venue"]["area"], FAV)

    # -- the language half of the link ----------------------------------------------------

    def test_the_link_language_beats_the_stored_one(self):
        """An English landing page opens the English app whatever the reader had before."""
        self.assertEqual(self.l["en_link_fi_stored"]["lang"], "en")
        self.assertEqual(self.l["fi_link_en_stored"]["lang"], "fi")

    def test_the_link_language_opens_the_app_for_a_reader_with_nothing_stored(self):
        """The case the pages were shipped without: no preference, English page, and the
        app used to default to Finnish."""
        self.assertEqual(self.l["en_link_nothing_stored"]["lang"], "en")

    def test_the_link_language_is_kept_in_the_url_while_it_is_the_answer(self):
        """Same reason as the venue: a reload has to be able to decide again."""
        for case in ("en_link_fi_stored", "en_link_nothing_stored", "sv_link_fi_stored"):
            with self.subTest(case=case):
                self.assertTrue(self.l[case]["keepParam"])

    def test_a_stored_choice_is_never_overwritten_by_a_link(self):
        """`remember` is false when something valid is stored. Following one English link
        must not switch a Finnish reader's app for good."""
        self.assertFalse(self.l["en_link_fi_stored"]["remember"])
        self.assertFalse(self.l["fi_link_en_stored"]["remember"])

    def test_a_first_visit_keeps_the_language_it_arrived_in(self):
        """Nothing valid stored: the link seeds the preference, so a later plain visit
        stays in the language of the page the reader came through."""
        self.assertTrue(self.l["en_link_nothing_stored"]["remember"])
        self.assertTrue(self.l["en_link_bad_stored"]["remember"])

    def test_only_a_supported_value_decides_anything(self):
        """Exact match against LANGS: `EN` and `xx` fall through to the stored language,
        and `keepParam` false tells the caller to strip them."""
        for case, expect in (("upper_case_param", "fi"), ("bad_param_en_stored", "en")):
            with self.subTest(case=case):
                self.assertEqual(self.l[case]["lang"], expect)
                self.assertFalse(self.l[case]["keepParam"])
                self.assertFalse(self.l[case]["remember"])

    def test_with_nothing_valid_anywhere_the_default_is_finnish(self):
        for case in ("bad_param_nothing_stored", "no_param_nothing_stored",
                     "no_param_bad_stored"):
            with self.subTest(case=case):
                self.assertEqual(self.l[case]["lang"], "fi")
                self.assertFalse(self.l[case]["keepParam"])

    def test_without_a_parameter_the_stored_language_applies_as_before(self):
        self.assertEqual(self.l["no_param_en_stored"]["lang"], "en")
        self.assertFalse(self.l["no_param_en_stored"]["keepParam"])
        self.assertFalse(self.l["no_param_en_stored"]["remember"])

    def test_swedish_is_a_supported_value(self):
        """The pages never write it, but the app has it, so a hand-written link may."""
        self.assertEqual(self.l["sv_link_fi_stored"]["lang"], "sv")

    def test_the_language_decision_never_touches_the_venue_or_the_favourite(self):
        """The result carries only its own three fields; nothing here can reach `fav`
        or `area`."""
        for case, r in self.l.items():
            with self.subTest(case=case):
                self.assertEqual(set(r), {"lang", "remember", "keepParam"})

    def test_toggling_the_language_rewrites_the_parameter(self):
        """Otherwise the value the reader arrived with would put them back on reload."""
        self.assertEqual(self.lu["deep_lang_then_toggle"], "area=sk-tapio&lang=fi")
        self.assertEqual(self.lu["lang_only_then_toggle"], "lang=sv")

    def test_toggling_never_grows_a_language_parameter(self):
        self.assertIsNone(self.lu["area_only_then_toggle"])
        self.assertIsNone(self.lu["plain_visit_then_toggle"])

    def test_an_empty_language_parameter_is_filled_rather_than_ignored(self):
        self.assertEqual(self.lu["empty_lang_param"], "lang=en")


if __name__ == "__main__":
    unittest.main()
