"""What /status/ says about the published metadata, for every state a run can produce.

The model is sliced verbatim out of status/index.html by tests/status_harness.js, so
these assertions run the shipped decision rather than a copy of it. Rules pinned here:
healthState stays the authority on severity; a file that never arrived and a timestamp
that will not parse both read as "could not check" rather than as a measured delay; a
chain past the threshold is described by its oldest venue and never as a whole chain
that failed; a confirmed-empty venue is named and never folded into "everything
updated"; and nothing that failed, was skipped or could not be read renders green.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "status_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StatusModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def row(self, case, rid):
        for r in self.r[case]["rows"]:
            if r["id"] == rid:
                return r
        raise AssertionError(f"no row {rid} in {case}")

    # -- the healthy baseline ------------------------------------------------------------

    def test_every_provider_fresh_reads_as_up_to_date(self):
        m = self.r["healthy"]
        self.assertEqual(m["level"], "good")
        self.assertEqual(m["title"], "Näytösajat ovat ajan tasalla")
        self.assertEqual(m["icon"], "✓")
        self.assertTrue(all(r["state"] == "ok" for r in m["rows"]))

    def test_a_single_venue_provider_names_its_city_and_a_chain_counts_its_venues(self):
        self.assertTrue(self.row("healthy", "orion")["meta"].startswith("Helsinki, "))
        self.assertTrue(self.row("healthy", "biorex")["meta"].startswith("12 teatteria, "))

    # -- delay ---------------------------------------------------------------------------

    def test_one_delayed_single_venue_provider_is_named_in_the_summary(self):
        """The approved wording for exactly one delayed venue, with its last success."""
        m = self.r["one_late"]
        self.assertEqual(m["level"], "warn")
        self.assertEqual(m["title"], "Yhden teatterin tietojen päivitys viivästyy")
        self.assertIn("Cinema Orion", m["detail"])
        self.assertIn("11 tuntia sitten", m["detail"])
        # A sentence, not a dotted list (2026-09-23).
        self.assertEqual(m["detail"], "Cinema Orion päivitettiin viimeksi 11 tuntia sitten.")

    def test_a_delayed_chain_is_not_described_as_a_whole_chain_that_failed(self):
        """`oldest` is a minimum. It says one venue is behind and nothing about the rest,
        so the detail may not claim every cinema in the chain failed."""
        d = self.row("chain_late", "biorex")["detail"]
        self.assertIn("Vanhimmat tiedot", d)
        self.assertIn("Osa teattereista on voitu päivittää myöhemmin", d)

    def test_a_delayed_chain_does_not_use_the_single_venue_summary(self):
        """Twelve cinemas behind one timestamp is not "one cinema is delayed"."""
        self.assertEqual(self.r["chain_late"]["title"],
                         "Kaikkien tietojen ajantasaisuutta ei voitu varmistaa")

    # -- partial and confirmed empty -------------------------------------------------------

    def test_a_kept_venue_is_named_and_counted_against_the_chain(self):
        r = self.row("partial", "biorex")
        self.assertEqual(r["state"], "partial")
        self.assertEqual(r["meta"], "12 teatteria, 1/12 teatterin tiedot päivittämättä")
        self.assertIn("Vaasa", r["detail"])

    def test_an_unverified_venue_is_partial_rather_than_confirmed_empty(self):
        """run.py cannot tell "added before its programme" from "a parse that never
        worked", so the case stays visible instead of reading as a quiet pending."""
        r = self.row("unverified", "etiketti")
        self.assertEqual(r["state"], "partial")
        self.assertIn("Uusi Kino", r["detail"])

    def test_a_confirmed_empty_venue_is_its_own_state_and_is_named(self):
        r = self.row("pending", "kinometso")
        self.assertEqual(r["state"], "pending")
        self.assertEqual(r["label"], "Ei julkaistua ohjelmistoa")
        self.assertIn("Muurame", r["detail"])
        self.assertIn("Tikkakoski", r["detail"])

    def test_a_confirmed_empty_venue_is_named_in_the_summary_not_hidden_by_green(self):
        """Nothing failed, so the headline stays green, but the venue without a programme
        may not disappear into "every data source updated successfully"."""
        m = self.r["pending"]
        self.assertEqual(m["level"], "good")
        self.assertIn("Kino Metso", m["detail"])
        self.assertNotEqual(m["detail"], "Kaikki tietolähteet päivitettiin onnistuneesti.")

    # -- what cannot be read ----------------------------------------------------------------

    def test_an_unparseable_timestamp_is_unknown_rather_than_a_measured_delay(self):
        """healthState calls this `behind`, which would claim a delay nobody measured."""
        r = self.row("bad_stamp", "orion")
        self.assertEqual(r["state"], "unknown")
        self.assertEqual(r["label"], "Tilaa ei voitu tarkistaa")

    def test_a_provider_whose_file_never_arrived_is_unknown_and_the_rest_still_render(self):
        self.assertEqual(self.row("missing", "orion")["state"], "unknown")
        self.assertEqual(self.row("missing", "biorex")["state"], "ok")

    def test_an_unknown_provider_says_nothing_about_the_cinemas_own_site(self):
        self.assertIn("ei kerro teatterin oman sivuston toiminnasta",
                      self.row("missing", "orion")["detail"])

    def test_every_request_failing_reads_as_could_not_check(self):
        m = self.r["all_failed"]
        self.assertEqual(m["level"], "unknown")
        self.assertEqual(m["title"], "Tilaa ei voitu tarkistaa")
        self.assertEqual(m["icon"], "?")

    def test_no_provider_list_at_all_is_a_failed_check_not_a_healthy_one(self):
        """providers.json not arriving leaves nothing checked. Falling through to the
        green headline would report health that was never measured."""
        m = self.r["no_providers"]
        self.assertEqual(m["level"], "unknown")
        self.assertEqual(m["title"], "Tilaa ei voitu tarkistaa")
        self.assertEqual(m["rows"], [])

    # -- aggregate and order ------------------------------------------------------------------

    def test_late_and_partial_together_do_not_claim_a_single_delayed_venue(self):
        m = self.r["mixed"]
        self.assertEqual(m["level"], "warn")
        self.assertEqual(m["title"], "Kaikkien tietojen ajantasaisuutta ei voitu varmistaa")

    def test_affected_providers_come_first_and_each_group_sorts_by_name(self):
        self.assertEqual(self.r["order"],
                         ["bravo:late", "delta:partial", "alfa:ok", "zulu:ok"])

    def test_the_threshold_is_the_apps_and_decides_both_sides(self):
        t = self.r["threshold"]
        self.assertEqual(t["stale_h"], 8)
        self.assertEqual(t["just_inside"], "ok")
        self.assertEqual(t["just_outside"], "late")

    # -- translations ---------------------------------------------------------------------------

    def test_every_language_renders_its_own_words(self):
        """A missing key would fall through to Finnish or to undefined; both are visible
        here because the same fixture is run three times."""
        langs = self.r["langs"]
        self.assertEqual(set(langs), {"fi", "sv", "en"})
        titles = {l: v["title"] for l, v in langs.items()}
        self.assertEqual(len(set(titles.values())), 3, titles)
        for l, v in langs.items():
            for field in ("title", "label", "meta", "detail", "count"):
                self.assertTrue(v[field], f"{l}.{field} is empty")
                self.assertNotIn("undefined", v[field], f"{l}.{field}")

    def test_the_finnish_row_label_is_not_reused_in_swedish_or_english(self):
        labels = {l: v["label"] for l, v in self.r["langs"].items()}
        self.assertEqual(labels["fi"], "Päivitys viivästynyt")
        self.assertNotEqual(labels["sv"], labels["fi"])
        self.assertNotEqual(labels["en"], labels["fi"])


if __name__ == "__main__":
    unittest.main()
