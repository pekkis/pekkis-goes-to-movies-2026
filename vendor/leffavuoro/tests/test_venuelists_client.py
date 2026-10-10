"""The client's reading of the two combined venue files.

`venueFilesFrom` in index.html decides which provider files the combined files supply and
which providers still need their own `data/venues-{id}.json`. Sliced out verbatim by
tests/venuelists_harness.js. A combined file that is missing, is not JSON (the fetch
rejects, so it arrives as null) or has the wrong shape costs only its own providers a
request each; a provider in both files is taken from the one that wrote it last.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "venuelists_harness.js"
ALL = ["biorex", "engel", "kinola", "regina"]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class VenueFilesFromTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_two_good_files_need_no_single_request(self):
        self.assertEqual(self.r["both"], {"files": ALL, "missing": []})

    def test_a_missing_file_costs_only_its_own_providers(self):
        self.assertEqual(self.r["local_missing"],
                         {"files": ["biorex", "kinola"], "missing": ["regina", "engel"]})
        self.assertEqual(self.r["cloud_missing"],
                         {"files": ["engel", "regina"], "missing": ["biorex", "kinola"]})
        self.assertEqual(self.r["both_missing"]["missing"], ["regina", "engel", "biorex", "kinola"])

    def test_a_file_of_the_wrong_shape_counts_as_missing(self):
        self.assertEqual(self.r["not_an_object"]["files"], [])
        self.assertEqual(self.r["providers_an_array"]["missing"], ["regina", "engel"])

    def test_an_entry_that_is_not_a_provider_file_is_fetched_on_its_own(self):
        self.assertEqual(self.r["entry_without_venues"]["missing"], ["regina"])
        self.assertEqual(self.r["entry_venues_not_array"]["missing"], ["regina", "engel"])

    def test_a_provider_neither_file_carries_yet_is_fetched_on_its_own(self):
        self.assertEqual(self.r["new_provider_in_neither"]["missing"], ["engel", "kinola"])

    def test_the_missing_list_keeps_the_callers_order(self):
        self.assertEqual(self.r["order"], ["engel", "regina"])

    def test_a_provider_in_both_files_is_taken_from_the_newer(self):
        self.assertEqual(self.r["moved_half_newest_wins"], 2)
        self.assertEqual(self.r["moved_half_newest_wins_either_order"], 2)

    def test_the_provider_file_is_passed_through_as_it_is(self):
        self.assertTrue(self.r["verbatim"])


if __name__ == "__main__":
    unittest.main()
