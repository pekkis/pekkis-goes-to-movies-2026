"""What the Lapsille filter admits, and what an empty rating actually means.

Heureka's whole planetarium programme was invisible to the filter: 192 showtimes, most of
them children's films. Two independent gates rejected them. `rating` is empty, because
Heureka publishes no KAVI classification, and the filter required S or K-7. `age` is
`K-5` on every show, the planetarium's five-year admission floor rather than a
classification, and the screening-limit gate accepted only S and K-7.

Both are the field-presence trap CLAUDE.md names: a rule written against the fields
Finnkino populates, applied to a provider that populates different ones. The gates are
sliced verbatim out of index.html, so these run the shipped decision.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "kids_filter_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class KidsFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- the line the filter has always drawn ------------------------------------------------

    def test_classifications_are_unchanged(self):
        """The fix must not loosen what a published classification means."""
        self.assertEqual(self.r["ratings"],
                         {"S": True, "K-7": True, "K-12": False, "K-16": False, "K-18": False})

    def test_a_licensed_room_still_refuses_an_s_rated_film(self):
        """The screening's own limit outranks the film's rating."""
        self.assertFalse(self.r["licensed_room"]["s_film_in_k18_room"])

    # -- the reported defect --------------------------------------------------------------------

    def test_heurekas_children_recommendations_are_admitted(self):
        """The whole report. Heureka publishes a recommendation instead of a
        classification, and every one of its 192 showtimes was filtered out."""
        h = self.r["heureka"]
        self.assertTrue(h["Suositus 5–10 v"])
        self.assertTrue(h["Suositus yli 7 v"])
        self.assertTrue(h["Suositus yli 10 v"])

    def test_heurekas_adult_recommendation_is_refused(self):
        """The one exception the reader asked for. Heureka marks these itself."""
        self.assertFalse(self.r["heureka"]["Suositus aikuisille"])

    def test_the_planetariums_five_year_floor_admits_children(self):
        """`K-5` is an admission floor, not a classification, and is more permissive than
        the K-7 the gate already accepted. Rejecting it was the second reason the whole
        programme disappeared."""
        self.assertTrue(self.r["admitted"]["K-5"])

    def test_both_gates_together_on_the_real_heureka_shape(self):
        rows = {r["method"]: r["passes"] for r in self.r["heureka_rows"]}
        self.assertEqual(rows, {"Suositus 5–10 v": True, "Suositus yli 7 v": True,
                                "Suositus yli 10 v": True, "Suositus aikuisille": False})

    # -- what the fallback must not let in --------------------------------------------------------

    def test_an_unrated_show_with_no_recommendation_stays_out(self):
        """378 of 2916 showtimes carry no rating. Riviera's 81 and Cinema Orion's 14 are
        arthouse programmes with no audience recommendation at all, and reading "no
        rating" as "unrestricted" would pull every one of them into Lapsille."""
        u = self.r["unrated_no_recommendation"]
        self.assertFalse(u["bare"])
        self.assertFalse(u["strand"])
        self.assertFalse(u["anniskelu"])

    def test_a_recommendation_never_overrides_a_published_classification(self):
        """The recommendation is read only where a classification is missing."""
        self.assertFalse(
            self.r["recommendation_does_not_override"]["k18_with_kid_recommendation"])

    # -- the screening limit ------------------------------------------------------------------------

    def test_limits_at_or_below_seven_admit_and_higher_ones_do_not(self):
        a = self.r["admitted"]
        for ok in ("(empty)", "S", "K-3", "K-5", "K-7"):
            self.assertTrue(a[ok], ok)
        for no in ("K-12", "K-16", "K-18"):
            self.assertFalse(a[no], no)

    def test_an_unrecognised_limit_is_treated_as_a_restriction(self):
        """A limit the parser does not recognise is not evidence that children are
        admitted, and guessing in that direction is the error this filter avoids."""
        self.assertFalse(self.r["admitted"]["Sallittu"])
        self.assertFalse(self.r["admitted"]["18"])


if __name__ == "__main__":
    unittest.main()
