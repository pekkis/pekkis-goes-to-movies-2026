"""The chooser is in the initial HTML: intro, prompt and city links without JavaScript.

The city list between the `cities:start` / `cities:end` markers is written by
`build_pages.py --home` from the same multi-venue rule as the city pages, so this file
recomputes it from data/ and fails when index.html lags the data (CI runs on every push
touching index.html or tests/, so a stale list is caught at the next human push).
"""
import re
import unittest

import _ctx
import build_pages

ROOT = _ctx.ROOT
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
MAIN = re.search(r"<main id=\"main\">(.*?)</main>", HTML, re.S).group(1)
SW = (ROOT / "sw.js").read_text(encoding="utf-8")


def strings(lang):
    """The L[lang] block's home strings."""
    block = re.search(r"\n    " + lang + r":\{(.*?)\n    \w+:\{|\n    " + lang + r":\{(.*?)\n  \};", HTML, re.S)
    text = (block.group(1) or block.group(2)) if block else ""
    return dict(re.findall(r"(home\w+):'([^']*)'", text))


class StaticChooserTest(unittest.TestCase):

    def test_the_intro_and_heading_are_in_the_markup_and_quotable(self):
        home = re.search(r'<section id="home" class="home">(.*?)</section>', MAIN, re.S).group(1)
        self.assertIn('<p class="intro">Suomen elokuvateatterien näytösajat yhdessä paikassa.</p>', home)
        self.assertIn("<h2>Näytösajat kaupungeittain</h2>", home)
        self.assertNotIn("data-nosnippet", re.sub(r'<div class="note"[^>]*>', "", home),
                         "only the note line is a transient control")
        self.assertIn('<div class="note" id="homeNote" data-nosnippet hidden></div>', home)

    def test_the_list_ends_with_an_item_that_opens_the_picker(self):
        """The cities with pages are not all the cities: the last item says so and opens
        the picker, where every city and theatre is."""
        self.assertIn('<li class="more"><button type="button" id="homeMore">Ja paljon muita…</button></li>', MAIN)
        self.assertGreater(MAIN.index('id="homeMore"'), MAIN.index("<!-- cities:end -->"),
                           "outside the generated block and last in the markup, so the Tab order holds without JS")
        self.assertIn("if(e.target.closest('#homeMore')){ openVenueSheet(); return; }", HTML)
        for lang, text in (("fi", "Ja paljon muita…"), ("sv", "Och många fler…"), ("en", "And many more…")):
            self.assertEqual(strings(lang).get("homeMore"), text, lang)

    def test_the_picker_prompt_is_the_static_trigger_label(self):
        self.assertIn('<span class="vlbl">Valitse kaupunki tai teatteri</span>', HTML)

    def test_the_city_links_are_the_generated_ones(self):
        cities = build_pages.home_cities()
        self.assertGreaterEqual(len(cities), 5)
        _, current = build_pages.home_block(HTML)
        self.assertEqual(current, build_pages.home_links_html(cities),
                         "index.html lags the data: run scripts/build_pages.py --home")
        self.assertFalse(build_pages.sync_home(write=False))

    def test_every_city_link_is_an_existing_page_in_both_page_languages(self):
        for c in build_pages.home_cities():
            for path in (f"kaupunki/{c['slug']}/index.html", f"en/city/{c['slug']}/index.html"):
                self.assertTrue((ROOT / path).exists(), path)
        hrefs = re.findall(r'<li><a href="([^"]+)" data-city="[^"]+" data-slug="[^"]+">', MAIN)
        want = [f"/kaupunki/{c['slug']}/" for c in build_pages.home_cities()]
        self.assertEqual(hrefs, want + want, "the city list, then the same pages under the disclosure")

    def test_the_city_pages_have_a_list_of_their_own(self):
        """A disclosure under the chooser, native so it opens without script, holding the
        same generated links: the first list's hrefs become the programme in the app."""
        self.assertIn('<details class="cpages"><summary>Kaupunkisivut</summary><ul>'
                      + build_pages.PAGES_START, MAIN)
        _, pages = build_pages.home_block(HTML, None, build_pages.PAGES_START, build_pages.PAGES_END)
        self.assertEqual(pages, build_pages.home_links_html(build_pages.home_cities()))
        for lang, text in (("fi", "Kaupunkisivut"), ("sv", "Stadssidor"), ("en", "City pages")):
            self.assertEqual(strings(lang).get("homePages"), text, lang)

    def test_the_list_is_in_finnish_alphabetical_order(self):
        names = [c["city"] for c in build_pages.home_cities()]
        self.assertEqual(names, sorted(names, key=str.casefold))

    def test_the_exact_strings_in_all_three_languages(self):
        want = {
            "fi": ("Suomen elokuvateatterien näytösajat yhdessä paikassa.", "Valitse kaupunki tai teatteri",
                   "Näytösajat kaupungeittain"),
            "sv": ("Visningstider för biografer i Finland på ett ställe.", "Välj stad eller biograf",
                   "Visningstider per stad"),
            "en": ("Cinema showtimes across Finland in one place.", "Choose a city or cinema",
                   "Showtimes by city"),
        }
        for lang, (intro, pick, by_city) in want.items():
            s = strings(lang)
            self.assertEqual((s.get("homeIntro"), s.get("homePick"), s.get("homeByCity")),
                             (intro, pick, by_city), lang)
            self.assertTrue(s.get("homeUnknown"), lang)

    def test_the_schedule_controls_are_out_of_the_tree_until_a_location_is_chosen(self):
        rule = re.search(r"html:not\(\.scoped\) #favBtn,.*?\{display:none\}", HTML, re.S).group(0)
        for sel in ("#favBtn", ".search", ".days", ".tools", "#tagkey", "#stale", "#partial", ".boot",
                    "#priceNote", "#credit"):
            self.assertIn(f"html:not(.scoped) {sel}", rule, sel)
        self.assertIn("html.scoped #home{display:none}", HTML)
        self.assertNotIn("html:not(.scoped) #areaSelect", HTML, "the trigger is the picker and stays")

    def test_the_head_script_sets_a_class_and_nothing_else(self):
        early = re.search(r"<script>(\(function\(\)\{var d=document\.documentElement;.*?)</script>", HTML, re.S).group(1)
        self.assertIn("classList.add('scoped')", early)
        for forbidden in ("setItem", "fetch(", "navigator", "cookie", "geolocation", "XMLHttpRequest", "sendBeacon"):
            self.assertNotIn(forbidden, early, forbidden)
        self.assertLess(HTML.index(early), HTML.index("<style>"), "before first paint")

    def test_nothing_writes_or_reads_the_last_browsed_slot(self):
        self.assertNotIn("prefs.set({ area", HTML)
        self.assertNotIn("pr.area", HTML.replace("(`pr.area`)", ""))

    def test_no_arbitrary_default_location(self):
        self.assertNotIn("areas[0].id", HTML)
        self.assertNotIn("route.area || areas", HTML)

    def test_head_metadata_is_unchanged(self):
        self.assertIn('<link rel="canonical" href="https://leffavuoro.fi/">', HTML)
        self.assertIn('"@type":"WebSite","name":"Leffavuoro","url":"https://leffavuoro.fi/"', HTML)
        self.assertIn('<meta name="description" content="Suomen elokuvateatterien näytösajat yhdessä paikassa:', HTML)

    def test_the_service_worker_moved_with_the_page(self):
        self.assertGreaterEqual(int(re.search(r"leffavuoro-v(\d+)", SW).group(1)), 141)


if __name__ == "__main__":
    unittest.main()
