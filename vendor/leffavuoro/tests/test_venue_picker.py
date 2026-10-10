"""The venue picker's row model: what a query shows, and in which order.

Order is behaviour: Enter picks the first row, so a combined "Kaikki {city}" row sorting
above a searched venue changes what Enter selects. Searching "itis" once put Kaikki
Helsinki first. Driven through tests/venue_picker_harness.js, which extracts the pure model
verbatim from index.html. Focus, inert, Escape and keyboard behaviour stay verified live.
"""
import json
import pathlib
import shutil
import subprocess
import re
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "venue_picker_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class CombinedRowLabelTest(unittest.TestCase):
    """The combined row reads "{city} – kaikki teatterit (n)": the city first, so the
    trigger's ellipsis eats the generic tail and never the city. Every language carries
    the placeholder, and both renderers compose through it."""
    HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")

    def test_every_language_has_a_city_placeholder(self):
        labels = re.findall(r"allIn:'([^']*)'", self.HTML)
        self.assertEqual(len(labels), 3)
        for label in labels:
            self.assertTrue(label.startswith("{city} – "), label)
        self.assertIn("{city} – kaikki teatterit", labels)

    def test_both_renderers_compose_through_the_placeholder(self):
        """Two call sites, the trigger and the row, both for a city. An area composes
        neither: its row and its trigger read the name and the count, because an area has
        no single-venue twin to tell itself apart from."""
        self.assertEqual(self.HTML.count(".allIn.replace('{city}',"), 2)
        self.assertNotRegex(self.HTML, r"\$\{T\.allIn\} ")
        self.assertNotRegex(self.HTML, r"\.allIn\} \$\{")


class VenuePickerModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- what Enter selects --------------------------------------------------------

    def test_a_venue_query_puts_the_venue_first_not_the_combined_row(self):
        """Searching "itis" must select Finnkino Itis on Enter, never Kaikki
        Helsinki. The combined row may not ride along on a venue match."""
        rows = self.r["venue_query_first_row"]
        self.assertEqual(rows, ["#Helsinki", "venue:itis"])

    def test_a_city_query_offers_the_combined_row_first(self):
        """The other side of the same rule: for "helsinki" the combined view is the
        natural pick, so there it does come first."""
        rows = self.r["city_query"]
        self.assertEqual(rows[0], "#Helsinki")
        self.assertEqual(rows[1], "all:city:Helsinki")
        self.assertIn("venue:itis", rows)

    def test_kaikki_finds_every_combined_row_and_no_venues(self):
        self.assertEqual(self.r["kaikki_query"], ["#Helsinki", "all:city:Helsinki"])

    # -- matching ------------------------------------------------------------------

    def test_diacritics_fold_both_ways(self):
        self.assertEqual(self.r["diacritics"], ["#Järvelä", "venue:ja"])

    def test_swedish_mode_matches_both_city_names(self):
        """Labels carry no city, so the haystack has to hold the raw name and the
        display name: Turku and Åbo both find the Turku venue in Swedish."""
        self.assertIn("venue:tku", self.r["sv_alias_fi_name"])
        self.assertIn("venue:tku", self.r["sv_alias_sv_name"])

    def test_no_match_yields_no_rows(self):
        self.assertEqual(self.r["none"], [])

    def test_the_highlight_lands_on_the_match(self):
        """vfold strips combining marks without changing the string length, so the
        <mark> offsets index the NFC original."""
        self.assertEqual(self.r["hl"], "<mark>Järvelä</mark>n Kino")

    # -- the pinned favourite ------------------------------------------------------

    def test_a_saved_venue_is_pinned_on_top(self):
        rows = self.r["fav_venue"]
        self.assertEqual(rows[:2], ["#Oma teatteri", "venue:ja"])

    def test_a_saved_combined_city_is_pinned_too(self):
        """city:* ids are valid favourites everywhere else (fillAreaSelect restores
        them), so the pinned section has to show them as well."""
        rows = self.r["fav_city"]
        self.assertEqual(rows[:2], ["#Oma teatteri", "all:city:Helsinki"])

    def test_the_pinned_row_obeys_the_filter(self):
        self.assertNotIn("all:city:Helsinki", self.r["fav_city_filtered_out"])
        self.assertIn("venue:tku", self.r["fav_city_filtered_out"])

    # -- areas ---------------------------------------------------------------------

    def test_the_city_view_is_the_list_areas_never_joined(self):
        """The point of the second view: with areas in the data, an empty query in the
        city view returns exactly the rows it returned before areas existed."""
        self.assertEqual(self.r["cities_view"], self.r["no_query"])

    def test_the_areas_view_lists_the_areas_alone(self):
        self.assertEqual(self.r["areas_view"],
                         ["#Alueet", "area:region:Uusimaa", "area:region:Varsinais-Suomi"])

    def test_an_area_row_carries_its_cinema_count(self):
        """The count is the row's own column, so the model has to produce it: three
        cinemas across two cities, one in the other area."""
        self.assertEqual(self.r["areas_view_counts"], ["Uusimaa:3", "Varsinais-Suomi:1"])

    def test_the_selected_area_is_the_current_row(self):
        self.assertEqual(self.r["area_current"], ["Uusimaa:true", "Varsinais-Suomi:false"])

    def test_an_area_name_query_reads_the_same_from_either_view(self):
        """Search spans both lists, so the switch cannot hide an area from a query."""
        self.assertEqual(self.r["area_name_query"], ["#Alueet", "area:region:Uusimaa"])
        self.assertEqual(self.r["area_name_query_from_areas_view"],
                         self.r["area_name_query"])

    def test_a_query_matching_only_a_member_city_puts_the_area_below(self):
        """Enter takes the first row, so "turku" has to select the cinema in Turku. The
        area is offered below the cinemas."""
        self.assertEqual(self.r["city_query_puts_area_below"],
                         ["#Turku", "venue:tku", "#Alueet", "area:region:Varsinais-Suomi"])
        self.assertEqual(self.r["city_query_from_areas_view"],
                         self.r["city_query_puts_area_below"])

    def test_kaikki_finds_the_combined_rows_and_no_areas(self):
        """An area row shows its name and its count, so "kaikki teatterit" is not text an
        area carries, and the highlight has to be computed against the text it shows."""
        self.assertEqual(self.r["kaikki_query_with_areas"],
                         ["#Helsinki", "all:city:Helsinki"])

    def test_an_area_row_names_the_cities_it_stands_for(self):
        """A row reading only "Kymenlaakso 4" leaves the reader guessing whether their
        town is in it, and selecting the row to find out closes the picker."""
        self.assertEqual(self.r["area_cities"],
                         ["Uusimaa: Helsinki, Järvelä", "Varsinais-Suomi: Turku"])

    def test_the_cities_on_the_row_follow_the_language(self):
        """Same rule as the group headings: the key stays Finnish, the reader sees Åbo."""
        self.assertEqual(self.r["area_cities_sv"], ["Helsingfors, Järvelä", "Åbo"])

    def test_an_area_row_reads_the_reader_s_language(self):
        """The Finnish name is the key everywhere it is stored; the row shows the
        translation, so an English reader never meets a Finnish area name."""
        self.assertEqual(self.r["area_labels_en"], ["Uusimaa region", "Southwest Finland"])
        self.assertEqual(self.r["area_labels_sv"], ["Nyland", "Egentliga Finland"])

    def test_an_area_is_found_by_any_of_its_three_names(self):
        """"Capital region" returned nothing while the area was labelled in Finnish only.
        The haystack is all three names in every language, the way a Turku venue is
        already found under Åbo."""
        self.assertEqual(self.r["en_query_in_finnish"],
                         ["#Alueet", "area:region:Varsinais-Suomi"])
        self.assertEqual(self.r["sv_query_in_finnish"],
                         ["#Alueet", "area:region:Varsinais-Suomi"])
        self.assertEqual(self.r["fi_query_in_english"],
                         ["#Alueet", "area:region:Varsinais-Suomi"])

    def test_the_highlight_lands_on_the_name_the_row_shows(self):
        """Matching reads three names and the row shows one, so the mark has to be
        computed against the visible string or it lands on the wrong characters."""
        self.assertEqual(self.r["en_query_highlight"], ["<mark>Southwest</mark> Finland"])

    def test_a_saved_area_is_pinned_in_both_views(self):
        self.assertEqual(self.r["fav_area_in_cities_view"][:2],
                         ["#Oma teatteri", "area:region:Uusimaa"])
        self.assertEqual(self.r["fav_area_in_areas_view"][:2],
                         ["#Oma teatteri", "area:region:Uusimaa"])

    def test_a_saved_venue_is_not_pinned_into_the_areas_view(self):
        """A venue row above a list of areas would be the clutter the second view
        avoids, and the venue is one switch away."""
        self.assertEqual(self.r["fav_venue_in_areas_view"],
                         ["#Alueet", "area:region:Uusimaa", "area:region:Varsinais-Suomi"])

    # -- the unfiltered list -------------------------------------------------------

    def test_no_query_shows_every_group_with_combined_rows_where_multi(self):
        rows = self.r["no_query"]
        self.assertEqual(rows[:4], ["#Helsinki", "all:city:Helsinki",
                                    "venue:itis", "venue:tripla"])
        self.assertIn("#Järvelä", rows)
        self.assertNotIn("all:city:Järvelä", rows, "a one-venue city has no combined row")


if __name__ == "__main__":
    unittest.main()
