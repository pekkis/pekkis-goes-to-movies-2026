"""Finnkino's site ids end up as filenames, so their shape is checked before use.

`data/area-{sid}.json` is the one write path in this pipeline whose filename component is
third-party text: `sid` comes straight from the upstream `/sites` response. Every other
provider's venue ids come from `registry.py`, and `common.check_shows` refuses a show filed
under a venue its own site does not list. This path has neither guard.

The same value is interpolated into the `siteIds` query, which is why `site_query` encodes
it. That encoding cannot fire while the id filter holds; it is tested on its own contract
rather than through the filter, so the two do not have to be read together.
"""
import unittest

import _ctx                                                # noqa: F401
import fetch_data


# One good id, one with a path separator, and the neighbouring shapes that decide where
# the line sits. Two of each kind, so a loop is exercised rather than a first element.
RAW_SITES = [
    {"id": "1004", "name": {"text": "Finnkino Promenadi"}},
    {"id": "kr-regina_2", "name": {"text": "Dash and underscore"}},
    {"id": "../../../etc/cron.d/x", "name": {"text": "Parent path"}},
    {"id": "1100/../1101", "name": {"text": "Relative path"}},
    {"id": "1100 1101", "name": {"text": "Space"}},
    {"id": "x" * 33, "name": {"text": "Past the length cap"}},
    {"id": "", "name": {"text": "No id"}},
    {"id": "1102", "name": {"text": ""}},
    {"id": "1103"},
    "not a dict",
]


class SiteIdFilterTest(unittest.TestCase):

    def setUp(self):
        self.sites, self.dropped = fetch_data.usable_sites(RAW_SITES)

    def test_only_an_id_that_can_be_a_filename_is_kept(self):
        self.assertEqual([s["id"] for s in self.sites], ["1004", "kr-regina_2"])

    def test_a_path_separator_is_dropped_and_named(self):
        """Named rather than dropped quietly: a cinema vanishing from the site list is
        worth a line in the run log, whatever the reason."""
        self.assertEqual([d["id"] for d in self.dropped],
                         ["../../../etc/cron.d/x", "1100/../1101", "1100 1101", "x" * 33])
        self.assertEqual(self.dropped[0]["name"], "Parent path")

    def test_a_row_with_no_id_or_no_name_is_skipped_in_silence(self):
        """Unchanged from before the filter. An incomplete row is not a hostile one, and
        it never reached a filename either way."""
        seen = self.sites + self.dropped
        self.assertNotIn("No id", [x["name"] for x in seen])
        self.assertNotIn("1102", [x["id"] for x in seen])    # an id, an empty name
        self.assertNotIn("1103", [x["id"] for x in seen])    # an id, no name key
        self.assertNotIn("not a dict", [x["id"] for x in seen])

    def test_the_length_cap_holds_at_its_edge(self):
        at, over = fetch_data.usable_sites(
            [{"id": "y" * 32, "name": {"text": "At"}}, {"id": "y" * 33, "name": {"text": "Over"}}])
        self.assertEqual([s["name"] for s in at], ["At"])
        self.assertEqual([d["name"] for d in over], ["Over"])


class SiteQueryTest(unittest.TestCase):

    def test_ordinary_ids_read_the_way_they_always_did(self):
        self.assertEqual(fetch_data.site_query([{"id": "1004"}, {"id": "1100"}]),
                         "siteIds=1004&siteIds=1100")

    def test_a_value_that_would_change_the_query_is_encoded(self):
        """Unreachable while SITE_ID holds. Tested on the function's own contract so the
        query is safe to read on its own."""
        self.assertEqual(fetch_data.site_query([{"id": "a b&c=1"}]),
                         "siteIds=a%20b%26c%3D1")
        self.assertEqual(fetch_data.site_query([{"id": "1004&admin=1"}, {"id": "1100"}]),
                         "siteIds=1004%26admin%3D1&siteIds=1100")


if __name__ == "__main__":
    unittest.main()
